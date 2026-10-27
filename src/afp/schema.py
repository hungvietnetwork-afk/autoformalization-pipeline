"""Data contracts of the pipeline (Section 1-2 of the week-2 design).

DataUnit      = <problem_id, source, natural_statement, domain, metadata>
InferenceTask = <problem_id, natural_statement, prompt_version, seed>      -> k candidates
VerifyTask    = <candidate_id, lean_code, timeout>                          -> VerifyResult
VerifyResult  = <status, compiler_message, latency_ms, peak_ram>

TaskHash = SHA256(problem_id || prompt_version || candidate_index)
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

SEP = "\x1f"  # unit separator used for the "||" concatenation in hashes

# ---- Verification statuses (PDF section 2 + taxonomy in section 6) ----
COMPILE_OK = "COMPILE_OK"
PARSE_ERROR = "PARSE_ERROR"
UNKNOWN_IDENTIFIER = "UNKNOWN_IDENTIFIER"
TYPE_MISMATCH = "TYPE_MISMATCH"
TIMEOUT = "TIMEOUT"
OTHER_ERROR = "OTHER_ERROR"
EMPTY_OUTPUT = "EMPTY_OUTPUT"  # model produced no theorem at all
ALL_STATUSES = [COMPILE_OK, PARSE_ERROR, UNKNOWN_IDENTIFIER, TYPE_MISMATCH,
                TIMEOUT, OTHER_ERROR, EMPTY_OUTPUT]


def sha256_hex(*parts: Any) -> str:
    h = hashlib.sha256()
    h.update(SEP.join(str(p) for p in parts).encode("utf-8"))
    return h.hexdigest()


def task_hash(problem_id: str, prompt_version: str, candidate_index: int) -> str:
    """TaskHash = SHA256(problem_id || prompt_version || candidate_index)."""
    return sha256_hex(problem_id, prompt_version, candidate_index)


def partition_index(problem_id: str, num_partitions: int) -> int:
    """PartitionIndex = hash(problem_id) mod R  (stable across processes/machines).

    Python's built-in hash() is salted per process, so we use SHA-256 instead.
    """
    return int(hashlib.sha256(problem_id.encode("utf-8")).hexdigest()[:16], 16) % num_partitions


@dataclass
class DataUnit:
    problem_id: str
    source: str
    natural_statement: str
    domain: str
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict) -> "DataUnit":
        return DataUnit(d["problem_id"], d["source"], d["natural_statement"],
                        d["domain"], d.get("metadata") or {})


@dataclass
class Candidate:
    task_hash: str            # SHA256(problem_id || prompt_version || candidate_index)
    problem_id: str
    prompt_version: str
    candidate_index: int
    lean_code: str            # theorem statement ending with ":= by sorry"
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class VerifyResult:
    task_hash: str
    problem_id: str
    prompt_version: str
    candidate_index: int
    status: str
    compiler_message: str
    latency_ms: float
    peak_ram_mb: float
    worker_id: str = ""
    run_id: str = ""
    attempt: int = 1
    finished_at: float = 0.0
    error_kinds: str = ""     # all error kinds found (";"-joined) for the taxonomy
    stmt_chars: int = 0

    def as_row(self) -> dict:
        return dataclasses.asdict(self)
