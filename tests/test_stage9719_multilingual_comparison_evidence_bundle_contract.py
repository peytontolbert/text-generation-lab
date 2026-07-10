from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9719_multilingual_comparison_evidence_bundle_contract.py"
    spec = importlib.util.spec_from_file_location("stage9719_bundle_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9719_real_templates_cover_all_locked_cells():
    mod = _load()
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    templates = [mod.build_template(record) for record in ledger["records"]]
    assert len(templates) == 72
    assert all(template["claim_ready_candidate"] is False for template in templates)


def test_stage9719_merge_marks_record_claim_ready_when_bundle_is_complete():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    record = next(
        row for row in ledger["records"]
        if row["cell_key"] == "standalone_100m_weights::python::symbol_binding"
    )
    bundle = mod.build_template(record)
    bundle["same_surface_comparison"] = {
        "present": True,
        "prompt_surface_hash_100m": "abc",
        "prompt_surface_hash_gemma12b": "abc",
        "score_100m": 0.82,
        "score_gemma12b": 0.78,
        "scoring_constraints_hash": "same",
        "same_surface_verified": True,
        "hundred_m_beats_gemma12b": True,
    }
    bundle["expert_maintainer_rubric"]["present"] = True
    bundle["expert_maintainer_rubric"]["passed"] = True
    bundle["expert_maintainer_rubric"]["subskills"] = {name: True for name in mod.RUBRIC_SUBSKILLS}
    bundle["anti_cheat_attachment"] = {
        "present": True,
        "stage9717_gate_passed": True,
        "passed": True,
        "anti_cheat_card_paths": ["runs/local/cards/example.json"],
    }
    bundle["evidence_artifacts"] = {
        "frozen_export_or_checkpoint_hash": "ckpt_hash",
        "standalone_generation_or_structured_action_outputs": "runs/local/out/100m.json",
        "same_prompt_surface_gemma12b_outputs": "runs/local/out/gemma.json",
        "language_slice_scores": "runs/local/out/scores.json",
        "expert_maintainer_rubric_scores": "runs/local/out/rubric.json",
        "anti_cheat_cards": "runs/local/out/anticheat.json",
        "telemetry_bundle": "runs/local/out/telemetry.json",
    }
    merged = mod.merge_bundle_into_record(bundle, record, contract)
    assert merged["claim_ready"] is True
    assert merged["claim_status"] == "claim_ready"
    assert merged["blockers"] == []


def test_stage9719_validation_rejects_same_surface_mismatch_and_missing_rubric():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    record = next(
        row for row in ledger["records"]
        if row["cell_key"] == "standalone_100m_weights::python::symbol_binding"
    )
    bundle = mod.build_template(record)
    bundle["same_surface_comparison"]["present"] = True
    bundle["same_surface_comparison"]["prompt_surface_hash_100m"] = "a"
    bundle["same_surface_comparison"]["prompt_surface_hash_gemma12b"] = "b"
    bundle["same_surface_comparison"]["score_100m"] = 0.9
    bundle["same_surface_comparison"]["score_gemma12b"] = 0.8
    bundle["same_surface_comparison"]["same_surface_verified"] = False
    bundle["same_surface_comparison"]["hundred_m_beats_gemma12b"] = True
    failures = mod.validate_bundle(bundle, record, contract)
    assert "prompt_surface_hash_mismatch" in failures
    assert "same_surface_not_verified" in failures
    assert "expert_maintainer_rubric_not_passed" in failures
