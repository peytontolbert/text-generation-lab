from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9767_enriched_standalone_review_targets.py"
    spec = importlib.util.spec_from_file_location("stage9767", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9767_enriches_all_remaining_targets():
    mod = _load()
    built = mod.enrich_targets(mod.load_json(mod.WORKBOOK))
    assert built["failures"] == []
    assert built["metrics"]["enriched_tasks"] == 26
    assert built["metrics"]["rubric_targets_enriched"] == 13
    assert built["metrics"]["anti_cheat_targets_enriched"] == 13
    assert built["metrics"]["unique_cells"] == 13
    assert built["metrics"]["top_queue_entry"] == (
        "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review"
    )


def test_stage9767_first_targets_contain_evidence_anchors():
    mod = _load()
    mod.enrich_targets(mod.load_json(mod.WORKBOOK))
    root = Path(__file__).resolve().parents[1]
    rubric = json.loads((root / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets/standalone_100m_weights__python__symbol_binding/expert_maintainer_rubric_review.json").read_text(encoding="utf-8"))
    anti = json.loads((root / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets/standalone_100m_weights__python__symbol_binding/anti_cheat_review_card.json").read_text(encoding="utf-8"))

    assert rubric["status"] == "pending_human_review"
    assert rubric["evidence_draft_path"].endswith("expert_maintainer_review_evidence_draft.json")
    assert rubric["same_surface_hash_100m"] == "5a6973526613681be3c67dc07178401f03a105d6bf5c2853b6194a278b2234ce"
    assert "subskill_evidence_hints" in rubric

    assert anti["status"] == "pending_cell_specific_review"
    assert anti["evidence_draft_path"].endswith("anti_cheat_review_evidence_draft.json")
    assert anti["same_surface_hash_100m"] == "5a6973526613681be3c67dc07178401f03a105d6bf5c2853b6194a278b2234ce"
    assert anti["challenge_families"][0]["required_requirements"]
