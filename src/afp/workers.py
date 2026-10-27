"""Worker processes.

inference_main : leases problems from q_problems in batches of `batch`, asks the inference
                 backend for k candidates each (cache hit -> no model call), enqueues VerifyTasks.
verifier_main  : owns one warm Lean REPL; leases VerifyTasks in batches of `batch`, checks each with a
                 hard wall-clock timeout, UPSERTs the result by TaskHash and acks.
"""
from __future__ import annotations

import os
import time
import traceback

from .lean.classify import classify
from .lean.repl import LeanREPL, ReplCrash, ReplTimeout
from .factory import make_queue, make_store
from .schema import EMPTY_OUTPUT, TIMEOUT, VerifyResult, partition_index


# ----------------------------------------------------------------------------- inference stage
def inference_main(cfg: dict) -> None:
    from .inference.backends import make_backend
    db, R, run_id = cfg["db"], cfg["partitions"], cfg["run_id"]
    qp = make_queue(cfg, "problems")
    qv = make_queue(cfg, "verify")
    rs = make_store(cfg)
    backend = make_backend(cfg["backend"])
    wid = "inf-0"
    rs.event(run_id, wid, "inference_start", {"pid": os.getpid(), "backend": cfg["backend"]["kind"]})
    n_batches = n_cands = 0
    while True:
        tasks = qp.lease(wid, list(range(R)), cfg["batch"], lease_s=cfg.get("lease_s", 120))
        if not tasks:
            if qp.pending() == 0:
                break
            time.sleep(0.05)
            continue
        t0 = time.perf_counter()
        cands = backend.generate_batch([p for _, p, _ in tasks])
        dt = (time.perf_counter() - t0) * 1000
        qv.enqueue([(c["task_hash"], partition_index(c["problem_id"], R), c) for c in cands])
        qp.ack([th for th, _, _ in tasks])
        n_batches += 1
        n_cands += len(cands)
        rs.event(run_id, wid, "inference_batch", {"n_problems": len(tasks), "n_candidates": len(cands), "ms": round(dt, 2)})
    rs.event(run_id, wid, "inference_done", {"batches": n_batches, "candidates": n_cands,
                                             "backend_stats": backend.stats()})


# ----------------------------------------------------------------------------- verify stage
def verifier_main(cfg: dict, worker_idx: int) -> None:
    db, R, run_id = cfg["db"], cfg["partitions"], cfg["run_id"]
    n_workers = cfg["workers"]
    wid = f"lean-{worker_idx}"
    home = [p for p in range(R) if p % n_workers == worker_idx]     # home partitions, steal the rest
    qv = make_queue(cfg, "verify")
    qp = make_queue(cfg, "problems")
    rs = make_store(cfg)
    timeout_s, batch, lease_s = cfg["timeout_s"], cfg["batch"], cfg.get("lease_s", 60)
    # True (default, used by every run since 16/10): before a REPL restart (~40 s) the rest of the leased batch is
    # handed back to the queue. False = the behaviour before that fix, kept for the ablation `ab_release_*`: the
    # worker keeps its batch through the restart and checks the rest itself afterwards.
    release_on_restart = bool(cfg.get("release_on_restart", True))
    repl = LeanREPL(cfg["header"])
    try:
        startup = repl.start()
    except Exception as e:
        rs.event(run_id, wid, "worker_failed", {"error": repr(e)})
        raise
    rs.event(run_id, wid, "worker_ready", {"pid": os.getpid(), "repl_pid": repl.proc.pid,
                                          "startup_s": round(startup, 2), "mem": repl.mem(pss=True)})
    inference_done = False
    processed = 0
    while True:
        tasks = qv.lease(wid, home, batch, lease_s)
        if not tasks:
            if not inference_done:
                inference_done = qp.pending() == 0 and rs.has_event("inference_done")
            if inference_done and qv.pending() == 0:
                break
            time.sleep(0.02)
            continue
        to_ack, last_extend = [], time.time()

        def restart_repl(remaining: list[str]) -> None:
            # flush acks first (finished tasks must not wait ~40 s for the restart and expire), then hand the
            # rest of the batch back so other workers process it during the restart instead of waiting for us
            qv.ack(to_ack)
            to_ack.clear()
            if release_on_restart:
                qv.release(remaining)
            else:                               # keep the batch: its leases must outlive the restart
                qv.extend(remaining, lease_s + 120)
            repl.restart()
            if not release_on_restart:
                qv.extend(remaining, lease_s)
            rs.event(run_id, wid, "repl_restarted", {"startup_s": round(repl.startup_s[-1], 2),
                                                     "repl_pid": repl.proc.pid,
                                                     "released": len(remaining) if release_on_restart else 0,
                                                     "kept": 0 if release_on_restart else len(remaining)})

        for i, (th, payload, attempt) in enumerate(tasks):
            remaining = [t for t, _, _ in tasks[i + 1:]]
            code = payload.get("lean_code") or ""
            res = VerifyResult(task_hash=th, problem_id=payload["problem_id"],
                               prompt_version=payload["prompt_version"], candidate_index=payload["candidate_index"],
                               status="", compiler_message="", latency_ms=0.0, peak_ram_mb=0.0,
                               worker_id=wid, run_id=run_id, attempt=attempt, stmt_chars=len(code))
            need_restart = False
            if not code:
                res.status, res.error_kinds, res.compiler_message = EMPTY_OUTPUT, "empty_output", "no theorem produced"
            else:
                try:
                    resp, ms = repl.check(code, timeout_s)
                    res.status, res.error_kinds, res.compiler_message, _ = classify(resp)
                    res.latency_ms = ms
                except ReplTimeout:
                    res.status, res.error_kinds = TIMEOUT, "wall_timeout"
                    res.compiler_message = f"hard timeout after {timeout_s}s (REPL killed and restarted)"
                    res.latency_ms = timeout_s * 1000.0
                    rs.event(run_id, wid, "repl_timeout", {"task_hash": th})
                    need_restart = True
                except ReplCrash as e:
                    # infrastructure failure (e.g. OOM-killed Lean): give the task back -> retry (<= 3 attempts)
                    rs.event(run_id, wid, "repl_crash", {"task_hash": th, "error": str(e)[:300]})
                    qv.nack(th, f"repl crash: {e}")
                    restart_repl(remaining)
                    if release_on_restart:
                        break                   # the rest of the batch was released to other workers
                    last_extend = time.time()
                    continue
            mem = repl.mem()
            res.peak_ram_mb = round(mem.get("VmHWM", 0.0), 1)
            res.finished_at = time.time()
            rs.upsert(res)                      # idempotent: ON CONFLICT(run_id, task_hash) DO UPDATE
            to_ack.append(th)
            processed += 1
            if need_restart:
                restart_repl(remaining)
                if release_on_restart:
                    break                       # the rest of the batch was released to other workers
                last_extend = time.time()
                continue
            if time.time() - last_extend > lease_s / 3:
                qv.extend(to_ack + remaining, lease_s)   # done-but-unacked tasks need the lease too
                last_extend = time.time()
        qv.ack(to_ack)
        if repl.n_cmds >= cfg.get("recycle_every", 5000):
            repl.restart()
            rs.event(run_id, wid, "repl_recycled", {"startup_s": round(repl.startup_s[-1], 2)})
    rs.event(run_id, wid, "worker_exit", {"processed": processed, "restarts": repl.restarts, "mem": repl.mem(pss=True)})
    repl.close()


def run_safely(fn, *args):
    try:
        fn(*args)
    except Exception:
        traceback.print_exc()
        raise
