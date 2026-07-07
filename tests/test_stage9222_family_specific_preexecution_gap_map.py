from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9222_family_specific_preexecution_gap_map.py"
spec = importlib.util.spec_from_file_location("stage9222", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9222_records_common_and_family_specific_gaps():
    card = mod.build_card()
    assert set(card["family_specific_gaps"]) == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }
    assert "fresh_family_specific_final_preexecution_audit" in card["common_preexecution_gaps"]
    assert "row_token_loss_real_per_position_required" in card["family_specific_gaps"]["bounded_decoder_ce_probe"]
    assert "target_resolver_readonly_recheck" in card["family_specific_gaps"]["denoise_repair_probe"]


def test_stage9222_keeps_all_execution_cleanup_runtime_arxiv_closed():
    card = mod.build_card()
    for key in [
        "trainer_executed_now",
        "model_forward_attempted",
        "backward_attempted",
        "checkpoint_written_now",
        "cleanup_authorized_now",
        "runtime_verifier_execution_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        assert card["metrics"][key] is False
    assert not any(card["authority"].values())


def test_stage9222_validation_rejects_family_selection_or_missing_gap():
    card = mod.build_card()
    card["metrics"]["family_selected_now"] = True
    assert "family_selected_now" in mod.validate_card(card)

    card = mod.build_card()
    card["common_preexecution_gaps"].remove("explicit_one_family_request")
    assert "missing_common_gap:explicit_one_family_request" in mod.validate_card(card)

    card = mod.build_card()
    del card["family_specific_gaps"]["denoise_repair_probe"]
    assert "missing_family_gap_map:denoise_repair_probe" in mod.validate_card(card)
