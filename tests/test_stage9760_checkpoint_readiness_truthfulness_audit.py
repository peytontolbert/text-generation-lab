from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9760_checkpoint_readiness_truthfulness_audit.py"
    spec = importlib.util.spec_from_file_location("stage9760", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9760_reclassifies_false_ready_checkpoint_tasks():
    mod = _load()
    built = mod.build_audit(
        mod.load_json(mod.READY_QUEUE),
        mod.load_json(mod.STANDALONE_QUEUE),
        mod.load_json(mod.UNIFIED),
    )
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["checkpoint_tasks_inspected"] == 13
    assert metrics["checkpoint_tasks_marked_ready_in_stage9759"] == 13
    assert metrics["checkpoint_tasks_truthfully_ready_now"] == 0
    assert metrics["checkpoint_tasks_reclassified_blocked"] == 13
    assert metrics["corrected_standalone_ready_now_tasks"] == 26
    assert metrics["corrected_cross_front_ready_now_tasks"] == 98
    first = built["records"][0]
    assert first["final_checkpoint_exported"] is False
    assert first["reclassified_status"] == "blocked_missing_frozen_export_or_checkpoint_hash"
