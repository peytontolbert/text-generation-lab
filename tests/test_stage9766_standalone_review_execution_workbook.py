from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9766_standalone_review_execution_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9766", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9766_workbook_matches_remaining_queue():
    mod = _load()
    built = mod.build_workbook(
        mod.load_json(mod.QUEUE),
        mod.load_jsonl(mod.PACKETS),
        mod.load_json(mod.DRAFTS),
        mod.load_json(mod.HARNESS_PREP_AUDIT),
    )

    assert built["failures"] == []
    assert built["metrics"]["standalone_review_tasks"] == 26
    assert built["metrics"]["unique_cells"] == 13
    assert built["metrics"]["rubric_tasks"] == 13
    assert built["metrics"]["anti_cheat_tasks"] == 13
    assert built["metrics"]["harness_ready_now_after_prep_completion"] == 0
    assert built["metrics"]["top_queue_entry"] == (
        "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    )


def test_stage9766_first_row_points_to_draft_and_stub():
    mod = _load()
    built = mod.build_workbook(
        mod.load_json(mod.QUEUE),
        mod.load_jsonl(mod.PACKETS),
        mod.load_json(mod.DRAFTS),
        mod.load_json(mod.HARNESS_PREP_AUDIT),
    )
    first = built["rows"][0]
    assert first["task"] == "expert_maintainer_rubric_review"
    assert first["draft_artifact_path"].endswith("expert_maintainer_review_evidence_draft.json")
    assert first["target_stub_path"].endswith("expert_maintainer_rubric_review.json")
    assert first["required_human_action"] == "assign rubric subskill judgments and failure traces"
