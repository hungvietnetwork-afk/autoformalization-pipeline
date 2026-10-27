"""Pick the queue / result-store implementation from the run config.

cfg["broker"] = {"kind": "sqlite"}                          (default: one machine, file in runs/<id>/run.db)
cfg["broker"] = {"kind": "sqlite", "indexed": True}         (covering indexes + periodic sweeps, see afp/bench_queue.py)
cfg["broker"] = {"kind": "sqlite", "max_attempts": 1}       (retry budget: deliveries per task before dead-letter)
cfg["broker"] = {"kind": "redis", "url": "redis://h:6379/0"} (several machines share one Redis)
"""
from __future__ import annotations


def make_queue(cfg: dict, name: str):
    b = cfg.get("broker") or {"kind": "sqlite"}
    if b["kind"] == "redis":
        from .redis_backend import RedisQueue
        return RedisQueue(b["url"], name, cfg["partitions"], run_id=cfg["run_id"])
    from .queue import PartitionedQueue
    return PartitionedQueue(cfg["db"], name, cfg["partitions"], max_attempts=int(b.get("max_attempts", 3)),
                            indexed=bool(b.get("indexed", False)))


def make_store(cfg: dict):
    b = cfg.get("broker") or {"kind": "sqlite"}
    if b["kind"] == "redis":
        from .redis_backend import RedisResultStore
        return RedisResultStore(b["url"], cfg["run_id"])
    from .store import ResultStore
    return ResultStore(cfg["db"])
