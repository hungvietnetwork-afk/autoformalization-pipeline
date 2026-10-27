"""Warm Lean 4 REPL process (leanprover-community/repl) with a hard wall-clock timeout.

Why a warm REPL: `import Mathlib` costs several seconds and ~1 GB of RAM. A cold
`lean file.lean` per candidate pays that every time; a warm REPL pays it once per worker
and then elaborates each candidate in environment 0 (header already loaded).
"""
from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import threading
import time
from typing import Optional

DEFAULT_LEAN_ROOT = os.environ.get("AFP_LEAN_ROOT", "/home/claude/lean")


class ReplTimeout(Exception):
    pass


class ReplCrash(Exception):
    pass


def lake_env(project_dir: str, lake_bin: str) -> dict:
    """Environment of `lake env` (LEAN_PATH etc.), computed once and reused for every REPL."""
    out = subprocess.run([lake_bin, "env", "printenv"], cwd=project_dir, capture_output=True, text=True, check=True)
    env = {}
    for line in out.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def _proc_status(pid: int, pss: bool = False) -> dict:
    """Memory of a process in MB.

    /proc/<pid>/status is cheap (~0.1 ms). smaps_rollup (PSS) costs ~125 ms for a REPL that maps
    ~9,000 .olean files, so it is only read when explicitly requested (start/exit events).
    RssFile = shared, clean .olean pages (page cache, shared by all workers); RssAnon = private heap.
    """
    d = {}
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith(("VmRSS", "VmHWM", "RssAnon", "RssFile")):
                    k, v = line.split(":")
                    d[k] = int(v.split()[0]) / 1024.0
        if pss:
            with open(f"/proc/{pid}/smaps_rollup") as f:
                for line in f:
                    if line.startswith("Pss:"):
                        d["Pss"] = int(line.split()[1]) / 1024.0
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
    return d


class LeanREPL:
    def __init__(self, header: str, lean_root: str = DEFAULT_LEAN_ROOT, toolchain: str = "lean-4.35.0-linux",
                 project: str = "mathlib4", env: Optional[dict] = None):
        self.header = header
        self.project_dir = os.path.join(lean_root, project)
        self.repl_bin = os.path.join(lean_root, "repl", ".lake", "build", "bin", "repl")
        self.lake_bin = os.path.join(lean_root, toolchain, "bin", "lake")
        self.env = env or {**os.environ, **lake_env(self.project_dir, self.lake_bin)}
        self.proc: Optional[subprocess.Popen] = None
        self.base_env: Optional[int] = None
        self.n_cmds = 0
        self.restarts = 0
        self.startup_s: list[float] = []
        self._buf = b""
        self._stderr_tail: list[str] = []

    # ------------------------------------------------------------------ lifecycle
    def start(self, timeout: float = 300.0) -> float:
        t0 = time.time()
        self.proc = subprocess.Popen([self.repl_bin], cwd=self.project_dir, env=self.env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True, bufsize=0)
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._buf = b""
        resp = self._send({"cmd": self.header}, timeout)
        errs = [m for m in resp.get("messages", []) if m.get("severity") == "error"]
        if errs or "env" not in resp:
            raise RuntimeError(f"header failed: {errs or resp}")
        self.base_env = resp["env"]
        self.n_cmds = 0
        dt = time.time() - t0
        self.startup_s.append(dt)
        return dt

    def _drain_stderr(self):
        p = self.proc
        try:
            for line in iter(p.stderr.readline, b""):
                self._stderr_tail = (self._stderr_tail + [line.decode(errors="replace")])[-20:]
        except Exception:
            pass

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(5)
            except Exception:
                pass
        self.proc = None

    def restart(self) -> float:
        self.kill()
        self.restarts += 1
        return self.start()

    close = kill

    # ------------------------------------------------------------------ protocol
    def _send(self, obj: dict, timeout: float) -> dict:
        if self.proc is None or self.proc.poll() is not None:
            raise ReplCrash("repl not running")
        data = (json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8")
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise ReplCrash(f"write failed: {e}")
        deadline = time.time() + timeout
        fd = self.proc.stdout.fileno()
        while b"\n\n" not in self._buf:
            left = deadline - time.time()
            if left <= 0:
                self.kill()
                raise ReplTimeout(f"no answer within {timeout}s")
            r, _, _ = select.select([fd], [], [], min(left, 0.5))
            if r:
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    raise ReplCrash("repl exited: " + "".join(self._stderr_tail)[-500:])
                self._buf += chunk
        raw, self._buf = self._buf.split(b"\n\n", 1)
        return json.loads(raw.decode("utf-8"))

    def check(self, code: str, timeout: float = 10.0) -> tuple[dict, float]:
        """Elaborate `code` in the warm header environment. Returns (response, latency_ms)."""
        t0 = time.perf_counter()
        resp = self._send({"cmd": code, "env": self.base_env}, timeout)
        self.n_cmds += 1
        return resp, (time.perf_counter() - t0) * 1000.0

    # ------------------------------------------------------------------ memory
    def mem(self, pss: bool = False) -> dict:
        """RSS / peak RSS (VmHWM) / RssAnon / RssFile (and PSS if asked) of the REPL process in MB."""
        if not self.proc:
            return {}
        return _proc_status(self.proc.pid, pss)
