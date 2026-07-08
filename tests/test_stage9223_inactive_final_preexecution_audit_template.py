from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9223_inactive_final_preexecution_audit_template.py"
spec = importlib.util.spec_from_file_location("stage9223", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9223_declares_template_sections_and_supported_families():
    card = mod.build_card()
    assert set(card["supported_families"]) == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }
    assert "manifest_and_loss_mask_hashes" in card["required_sections"]
    assert "safe_cleanup_dry_run_contract" in card["required_sections"]
    assert "authority_and_forbidden_paths" in card["required_sections"]


def test_stage9223_family_telemetry_requirements_cover_key_artifacts():
    card = mod.build_card()
    assert "row_field_logits.jsonl" in card["family_telemetry_requirements"]["structured_policy_probe"]
    assert "row_token_loss.jsonl" in card["family_telemetry_requirements"]["bounded_decoder_ce_probe"]
    assert "target_resolver_readonly_proof.json" in card["family_telemetry_requirements"]["denoise_repair_probe"]


def test_stage9223_template_keeps_all_execution_and_cleanup_closed():
    card = mod.build_card()
    for key in mod.TEMPLATE_METRICS_FALSE:
        assert card["metrics"][key] is False
    assert not any(card["authority"].values())


def test_stage9223_validation_rejects_open_metric_or_missing_contract():
    card = mod.build_card()
    card["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in mod.validate_card(card)

    card = mod.build_card()
    del card["family_telemetry_requirements"]["bounded_decoder_ce_probe"]
    assert "missing_family_telemetry:bounded_decoder_ce_probe" in mod.validate_card(card)

    card = mod.build_card()
    del card["section_requirements"]["runtime_assertion_contract"]
    assert "missing_section:runtime_assertion_contract" in mod.validate_card(card)
