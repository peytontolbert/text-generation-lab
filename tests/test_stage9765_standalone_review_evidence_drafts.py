from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9765_standalone_review_evidence_drafts.py"
    spec = importlib.util.spec_from_file_location("stage9765", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9765_materializes_evidence_backed_review_drafts():
    mod = _load()
    built = mod.build_drafts(
        mod.load_jsonl(mod.SOURCE_PACKETS),
        mod.load_json(mod.STUB_MANIFEST),
        mod.load_json(mod.TRUTHFUL_QUEUE),
        mod.load_json(mod.HARNESS_PREP_AUDIT),
    )

    assert built["failures"] == []
    assert built["metrics"]["supported_cells"] == 13
    assert built["metrics"]["remaining_standalone_review_tasks"] == 26
    assert built["metrics"]["harness_ready_now_after_prep_completion"] == 0
    assert built["metrics"]["top_queue_entry"] == (
        "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    )


def test_stage9765_draft_payload_shapes():
    mod = _load()
    packets = mod.load_jsonl(mod.SOURCE_PACKETS)
    rubric = mod._rubric_draft(packets[0])
    anti = mod._anti_cheat_draft(packets[0])

    assert rubric["status"] == "draft_evidence_ready_for_human_rubric_review"
    assert rubric["reviewer_must_confirm"] is True
    assert len(rubric["subskills"]) == 16
    assert anti["status"] == "draft_evidence_ready_for_human_cell_specific_review"
    assert anti["global_stage9717_gate_passed"] is True
    assert len(anti["challenge_families"]) == 6
