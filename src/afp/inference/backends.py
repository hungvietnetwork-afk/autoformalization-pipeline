"""Inference backends.

All backends implement  generate_batch(problem_payloads) -> list[candidate dict]  and consult the
candidate cache first (TaskHash = SHA256(problem_id || prompt_version || candidate_index)), so a retry
or a re-run never pays for tokens twice.

* cache          : replay candidates that are already in data/candidates.db (used in the experiments;
                   they were produced by the offline batch jobs in afp.inference.batchfile)
* openai_compat  : any OpenAI-compatible /v1/chat/completions endpoint (vLLM, Ollama, LM Studio,
                   DeepSeek, OpenAI, Together, ...) with batching, bounded concurrency, client-side
                   rate limiting (RPM) and exponential back-off on HTTP 429/5xx.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import threading
import time
import urllib.error
import urllib.request

from ..ingest import est_tokens
from ..prompts import sanitize, system_prompt, user_prompt
from ..schema import Candidate, task_hash
from ..store import CandidateStore


def _cand_dict(c: Candidate, payload: dict) -> dict:
    return {"task_hash": c.task_hash, "problem_id": payload["problem_id"], "prompt_version": c.prompt_version,
            "candidate_index": c.candidate_index, "lean_code": c.lean_code, "model": c.model,
            "prompt_tokens": c.prompt_tokens, "completion_tokens": c.completion_tokens}


class CacheBackend:
    """Replay from the candidate cache. A payload may carry `source_task_hash` (trace replay)."""

    def __init__(self, db: str):
        self.store = CandidateStore(db)
        self.hits = self.misses = 0

    def generate_batch(self, payloads: list[dict]) -> list[dict]:
        out = []
        for p in payloads:
            for i in range(p.get("k", 1)):
                th_src = p.get("source_task_hash") or task_hash(p["problem_id"], p["prompt_version"], i)
                c = self.store.get(th_src)
                if c is None:
                    self.misses += 1
                    c = Candidate(task_hash=th_src, problem_id=p["problem_id"], prompt_version=p["prompt_version"],
                                  candidate_index=i, lean_code="")
                else:
                    self.hits += 1
                th = task_hash(p["problem_id"], p["prompt_version"], i)  # task identity of *this* problem id
                c = Candidate(th, p["problem_id"], p["prompt_version"], i, c.lean_code, c.model,
                              c.prompt_tokens, c.completion_tokens)
                out.append(_cand_dict(c, p))
        return out

    def stats(self) -> dict:
        return {"cache_hits": self.hits, "cache_misses": self.misses}


class _RateLimiter:
    def __init__(self, rpm: float):
        self.interval = 60.0 / rpm if rpm else 0.0
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self):
        if not self.interval:
            return
        with self.lock:
            now = time.time()
            t = max(now, self.next_t)
            self.next_t = t + self.interval
        time.sleep(max(0.0, t - now))


class OpenAICompatBackend:
    def __init__(self, base_url: str, model: str, db: str, api_key_env: str = "OPENAI_API_KEY",
                 max_concurrency: int = 8, rpm: float = 0, temperature: float = 0.7, max_tokens: int = 512,
                 timeout_s: float = 120, max_retries: int = 6):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens
        self.key = os.environ.get(api_key_env, "")
        self.pool = cf.ThreadPoolExecutor(max_concurrency)
        self.limiter = _RateLimiter(rpm)
        self.timeout_s, self.max_retries = timeout_s, max_retries
        self.store = CandidateStore(db)
        self.calls = self.hits = self.retries = self.prompt_tokens = self.completion_tokens = 0
        self.lock = threading.Lock()

    def _call(self, version: str, nl: str, seed: int) -> tuple[str, int, int]:
        body = {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens, "seed": seed,
                "messages": [{"role": "system", "content": system_prompt(version)},
                             {"role": "user", "content": user_prompt(nl)}]}
        data = json.dumps(body).encode()
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            req = urllib.request.Request(self.url, data=data, headers={
                "Content-Type": "application/json", **({"Authorization": f"Bearer {self.key}"} if self.key else {})})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    j = json.loads(r.read())
                u = j.get("usage") or {}
                text = j["choices"][0]["message"]["content"]
                return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    with self.lock:
                        self.retries += 1
                    retry_after = float(e.headers.get("Retry-After") or delay)
                    time.sleep(retry_after)
                    delay = min(delay * 2, 60)
                    continue
                raise
        raise RuntimeError("unreachable")

    def _one(self, p: dict, i: int) -> dict:
        th = task_hash(p["problem_id"], p["prompt_version"], i)
        c = self.store.get(th)
        if c is not None:                      # idempotent: never pay twice for the same TaskHash
            with self.lock:
                self.hits += 1
            return _cand_dict(c, p)
        seed = int(p.get("seed", 0)) * 1000 + i
        raw, pt, ct = self._call(p["prompt_version"], p["natural_statement"], seed)
        pt = pt or est_tokens(system_prompt(p["prompt_version"]) + user_prompt(p["natural_statement"]))
        ct = ct or est_tokens(raw)
        c = Candidate(th, p["problem_id"], p["prompt_version"], i, sanitize(raw, "cand_" + th[:12]), self.model, pt, ct)
        self.store.upsert(c, raw, job_id="online")
        with self.lock:
            self.calls += 1
            self.prompt_tokens += pt
            self.completion_tokens += ct
        return _cand_dict(c, p)

    def generate_batch(self, payloads: list[dict]) -> list[dict]:
        futs = [self.pool.submit(self._one, p, i) for p in payloads for i in range(p.get("k", 1))]
        return [f.result() for f in futs]

    def stats(self) -> dict:
        return {"model_calls": self.calls, "cache_hits": self.hits, "retries_429_5xx": self.retries,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens}


def make_backend(spec: dict):
    kind = spec["kind"]
    if kind == "cache":
        return CacheBackend(spec["db"])
    if kind == "openai_compat":
        return OpenAICompatBackend(spec["base_url"], spec["model"], spec["db"],
                                   api_key_env=spec.get("api_key_env", "OPENAI_API_KEY"),
                                   max_concurrency=spec.get("max_concurrency", 8), rpm=spec.get("rpm", 0),
                                   temperature=spec.get("temperature", 0.7), max_tokens=spec.get("max_tokens", 512))
    raise ValueError(kind)
