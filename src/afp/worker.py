"""Join a running pipeline from another machine (Redis broker only).

    # machine A (coordinator):  python -m afp.pipeline --run-id big --tier T1K --workers 2 --batch 8 --redis redis://A:6379/0
    # machine B, C, ... :       python -m afp.worker --redis redis://A:6379/0 --run-id big --idx 2 --of 4

Each extra worker starts its own warm Lean REPL and pulls from the same partitioned streams
(home partitions = p mod --of == --idx, then work stealing).
"""
from __future__ import annotations

import argparse
import json

from .workers import verifier_main


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--redis", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--idx", type=int, required=True)
    ap.add_argument("--of", type=int, required=True, help="total number of workers (for home partitions)")
    a = ap.parse_args(argv)
    import redis
    cfg = json.loads(redis.Redis.from_url(a.redis).get(f"afp:{a.run_id}:cfg"))
    cfg["workers"] = a.of
    verifier_main(cfg, a.idx)


if __name__ == "__main__":
    main()
