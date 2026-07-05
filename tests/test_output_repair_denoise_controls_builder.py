from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.output_repair_denoise_controls_builder import REQUIRED_GATE_KEYS, build_row


def base_row(action: str = "REPAIR_SHORT_OUTPUT") -> dict:
    return {
        "row_id": "old_row",
        "split": "train",
        "source_stage": "stage8647",
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "repair_signal": "short_output_visible",
            "candidate_surface": "candidate exists",
            "bad_output_features": {"too_short": True},
            "budget": {"max_repair_steps": 2, "decoder_budget_ok": False},
        },
        "clean_state": {"output_repair_action": action, "action_sequence": ["EXPAND_FROM_STRUCTURED_STATE"]},
    }


def test_repair_candidate_keeps_denoise_ce_closed() -> None:
    out = build_row(base_row("REPAIR_SHORT_OUTPUT"))
    assert out["clean_state"]["denoise_gate_decision"] == "DENOISE_CANDIDATE_EXPAND_MISSING_SPANS"
    assert out["clean_state"]["denoise_candidate_eligible_later"] is True
    assert out["clean_state"]["denoise_ce_eligible_now"] is False
    assert out["loss_mask"]["denoise_ce"] is False
    assert out["authority"]["denoise_ce_training_authorized_next"] is False
    assert all(out["gate_status"][key] is True for key in REQUIRED_GATE_KEYS)


def test_abstain_blocks_denoise_candidate() -> None:
    out = build_row(base_row("ABSTAIN_UNRECOVERABLE"))
    assert out["clean_state"]["denoise_gate_decision"] == "DENOISE_BLOCK_ABSTAIN_UNRECOVERABLE"
    assert out["clean_state"]["denoise_candidate_eligible_later"] is False
    assert "denoise_block_abstain_unrecoverable" in out["hard_blockers"]


def test_no_raw_text_flags_visible() -> None:
    out = build_row(base_row())
    assert out["anti_cheat"]["raw_decoder_text_included"] is False
    assert out["anti_cheat"]["bad_output_text_in_encoder"] is False
    assert out["anti_cheat"]["target_text_in_encoder"] is False
