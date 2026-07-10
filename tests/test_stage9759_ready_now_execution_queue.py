from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9759_ready_now_execution_queue.py"
    spec = importlib.util.spec_from_file_location("stage9759", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9759_builds_prioritized_ready_now_queue():
    mod = _load()
    built = mod.build_ready_now_queue(
        mod.load_json(mod.STANDALONE_CHECKLIST),
        mod.load_json(mod.HARNESS_CHECKLIST),
    )
    metrics = built["metrics"]
    queue_entries = built["queue_entries"]
    assert built["failures"] == []
    assert metrics["ready_now_entries"] == 111
    assert metrics["standalone_entries"] == 39
    assert metrics["harness_entries"] == 72
    assert metrics["top_queue_entry"] == "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    first = queue_entries[0]
    assert first["front"] == "standalone"
    assert first["cell_key"] == "standalone_100m_weights::python::symbol_binding"
    assert first["task"] == "expert_maintainer_rubric_review"
    assert first["impact_band"] == "highest"
    assert first["queue_position"] == 1
    assert any(
        row["front"] == "harness" and row["priority_bucket"] == "aligned_with_supported_standalone_cell"
        for row in queue_entries
    )
