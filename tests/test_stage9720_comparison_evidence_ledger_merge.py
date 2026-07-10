from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9720_comparison_evidence_ledger_merge.py"
    spec = importlib.util.spec_from_file_location("stage9720_merge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9720_template_only_merge_keeps_all_cells_blocked():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    bundles = mod.load_jsonl(mod.SOURCE_TEMPLATES)
    merged = mod.merge_records(contract, ledger, bundles)
    assert merged["passed"] is True
    assert merged["merged_bundle_count"] == 72
    assert merged["metrics"]["claim_ready_cells"] == 0
    assert merged["metrics"]["blocked_cells"] == 72


def test_stage9720_real_passing_bundle_makes_one_cell_claim_ready():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    bundles = mod.load_jsonl(mod.SOURCE_TEMPLATES)
    target = next(bundle for bundle in bundles if bundle["cell_key"] == "standalone_100m_weights::python::symbol_binding")
    target["same_surface_comparison"] = {
        "present": True,
        "prompt_surface_hash_100m": "abc",
        "prompt_surface_hash_gemma12b": "abc",
        "score_100m": 0.82,
        "score_gemma12b": 0.78,
        "scoring_constraints_hash": "same",
        "same_surface_verified": True,
        "hundred_m_beats_gemma12b": True,
    }
    target["expert_maintainer_rubric"]["present"] = True
    target["expert_maintainer_rubric"]["passed"] = True
    target["expert_maintainer_rubric"]["subskills"] = {name: True for name in target["expert_maintainer_rubric"]["subskills"]}
    target["anti_cheat_attachment"] = {
        "present": True,
        "stage9717_gate_passed": True,
        "passed": True,
        "anti_cheat_card_paths": ["runs/local/cards/example.json"],
    }
    target["evidence_artifacts"] = {
        "frozen_export_or_checkpoint_hash": "ckpt_hash",
        "standalone_generation_or_structured_action_outputs": "runs/local/out/100m.json",
        "same_prompt_surface_gemma12b_outputs": "runs/local/out/gemma.json",
        "language_slice_scores": "runs/local/out/scores.json",
        "expert_maintainer_rubric_scores": "runs/local/out/rubric.json",
        "anti_cheat_cards": "runs/local/out/anticheat.json",
        "telemetry_bundle": "runs/local/out/telemetry.json",
    }
    merged = mod.merge_records(contract, ledger, bundles)
    assert merged["metrics"]["claim_ready_cells"] == 1
    assert merged["metrics"]["mode_claim_ready_counts"] == {"standalone_100m_weights": 1}
    record = next(row for row in merged["records"] if row["cell_key"] == "standalone_100m_weights::python::symbol_binding")
    assert record["claim_ready"] is True
    assert record["blockers"] == []


def test_stage9720_unknown_bundle_cell_key_fails():
    mod = _load()
    contract = mod.load_json(mod.SOURCE_CONTRACT)
    ledger = mod.load_json(mod.SOURCE_LEDGER)
    bundles = mod.load_jsonl(mod.SOURCE_TEMPLATES)
    bundles.append({"cell_key": "unknown::cell"})
    merged = mod.merge_records(contract, ledger, bundles)
    assert merged["passed"] is False
    assert "unknown_bundle_cell_keys_present" in merged["failures"]
