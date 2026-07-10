from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9754_supported_standalone_completion_checklist.py"
    spec = importlib.util.spec_from_file_location("stage9754", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9754_separates_pre_and_post_gemma_work():
    mod = _load()
    built = mod.build_checklist(mod.load_jsonl(mod.PACKETS), mod.load_json(mod.STUBS))
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["checklist_rows"] == 13
    assert metrics["pre_gemma_tasks_total"] == 39
    assert metrics["post_gemma_tasks_total"] == 26
    assert metrics["cells_ready_for_human_review_now"] == 13
    assert metrics["cells_blocked_on_gemma_runner"] == 13
    assert metrics["top_priority_cell"] == "standalone_100m_weights::python::symbol_binding"
    first = built["records"][0]
    assert first["pre_gemma_completion_count"] == 0
    assert first["post_gemma_completion_count"] == 0
    assert [task["task"] for task in first["pre_gemma_tasks"]] == [
        "expert_maintainer_rubric_review",
        "cell_specific_anti_cheat_review",
        "frozen_checkpoint_hash_attach",
    ]
    assert [task["task"] for task in first["post_gemma_tasks"]] == [
        "same_surface_gemma_execution",
        "claim_ready_merge",
    ]
