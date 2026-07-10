from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9762_harness_prep_completion_audit.py"
    spec = importlib.util.spec_from_file_location("stage9762", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9762_marks_harness_prep_complete():
    mod = _load()
    built = mod.build_audit(
        mod.load_json(mod.HARNESS_CHECKLIST),
        mod.load_jsonl(mod.HARNESS_PACKETS),
        mod.load_json(mod.HARNESS_STUBS),
        mod.load_json(mod.TRUTHFUL_QUEUE),
    )
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["harness_cells_audited"] == 36
    assert metrics["harness_prep_tasks_completed"] == 72
    assert metrics["truthful_queue_entries_before"] == 98
    assert metrics["truthful_queue_entries_after_harness_prep_completion"] == 26
    assert metrics["remaining_standalone_entries_after_completion"] == 26
    assert metrics["remaining_harness_entries_after_completion"] == 0
