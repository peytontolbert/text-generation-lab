from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9755_full_product_harness_completion_checklist.py"
    spec = importlib.util.spec_from_file_location("stage9755", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9755_separates_harness_prep_from_runner_blocked_work():
    mod = _load()
    built = mod.build_checklist(mod.load_json(mod.QUEUE), mod.load_json(mod.RUNBOOK))
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["checklist_rows"] == 36
    assert metrics["pre_harness_tasks_total"] == 108
    assert metrics["pre_harness_tasks_ready_now"] == 72
    assert metrics["post_harness_tasks_total"] == 252
    assert metrics["post_harness_tasks_ready_now"] == 0
    assert metrics["cells_ready_for_harness_when_authorized"] == 36
    assert metrics["cells_blocked_on_harness_runner"] == 36
    assert metrics["top_priority_cell"] == "full_product_harness::python::symbol_binding"
    first = built["records"][0]
    assert first["priority_bucket"] == "aligned_with_supported_standalone_cell"
    assert [task["task"] for task in first["pre_harness_tasks"]] == [
        "recover_or_authorize_harness_runner_surface",
        "prepare_cell_specific_anti_cheat_review",
        "prepare_expert_maintainer_rubric_review",
    ]
    assert first["pre_harness_ready_now_count"] == 2
    assert len(first["post_harness_tasks"]) == 7
