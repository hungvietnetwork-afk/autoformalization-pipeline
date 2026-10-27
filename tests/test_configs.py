"""configs/ must describe what the code actually does."""
import inspect
import json
import os

from afp import experiments, ingest, paths, pipeline, prompts, queue, workers


def _defaults() -> dict:
    with open(os.path.join(paths.CONFIGS, "pipeline_defaults.json"), encoding="utf-8") as f:
        return json.load(f)


def test_pipeline_defaults_match_code():
    d = _defaults()
    sig = inspect.signature(pipeline.run_pipeline).parameters
    for k in ("partitions", "timeout_s", "lease_s", "prompt_version", "k"):
        assert sig[k].default == d[k], k
    assert inspect.signature(queue.PartitionedQueue.__init__).parameters["max_attempts"].default == d["max_attempts"]
    assert inspect.signature(ingest.make_tiers).parameters["seed"].default == d["tier_seed"]
    assert f"maxHeartbeats {d['max_heartbeats']}" in prompts.LEAN_HEADER
    src = inspect.getsource(workers)
    assert f'cfg.get("recycle_every", {d["recycle_every"]})' in src
    assert f'cfg.get("release_on_restart", {d["release_on_restart"]})' in src


def test_experiment_grid_is_complete():
    g = experiments.load_grid()
    for section in ("tiers", "matrix", "scaling", "batch_sweep", "baseline", "fault", "retry", "release", "repro",
                    "broker"):
        assert section in g, section
    assert set(g["matrix"]["configs"]) == {"A", "B", "C"}
    assert set(g["batch_sweep"]["tiers"]) <= set(g["tiers"])
    assert g["scaling"]["tier"] in g["tiers"]
    for tier in g["tiers"].values():
        assert os.path.exists(os.path.join(paths.TIERS_DIR, f"{tier['tier']}.txt"))
    assert os.path.exists(os.path.join(paths.TIERS_DIR, f"{g['baseline']['tier']}.txt"))
    assert set(g["baseline"]["runs"].values()) <= set(prompts.PROMPT_VERSIONS)
