from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9761_truthful_ready_now_execution_queue.py"
    spec = importlib.util.spec_from_file_location("stage9761", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9761_builds_truthful_ready_now_queue():
    mod = _load()
    built = mod.build_truthful_queue(
        mod.load_json(mod.READY_QUEUE),
        mod.load_json(mod.CHECKPOINT_AUDIT),
    )
    metrics = built["metrics"]
    queue_entries = built["queue_entries"]
    assert built["failures"] == []
    assert metrics["ready_now_entries"] == 98
    assert metrics["standalone_entries"] == 26
    assert metrics["harness_entries"] == 72
    assert metrics["removed_false_ready_entries"] == 13
    assert metrics["top_queue_entry"] == "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    assert all(row["task"] != "frozen_checkpoint_hash_attach" for row in queue_entries if row["front"] == "standalone")
