from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8893_no_execution_telemetry_gate_matrix import AUTHORITY_CLOSED, MATRIX, build_matrix_audit


def test_matrix_covers_core_no_execution_gates() -> None:
    assert {
        "curriculum_compiler_loss_gate",
        "native_probe_preflight_gate",
        "model_output_packet_telemetry_contract",
        "model_output_capture_preflight_audit",
        "closed_bounded_decoder_ce_gate",
        "source_backed_decoder_target_materialization",
        "output_repair_denoise_controls",
        "verifier_guided_repair_target_materialization",
        "authority_ticket_and_inactive_execution",
    }.issubset(MATRIX)


def test_matrix_audit_keeps_authority_closed() -> None:
    registry = {"metrics": {"latest_stage": 8891, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    summaries = [
        {"passed": True, "stage_name": "a", "authority": dict(AUTHORITY_CLOSED)},
        {"passed": True, "stage_name": "b", "authority": dict(AUTHORITY_CLOSED)},
        {"passed": True, "stage_name": "c", "authority": dict(AUTHORITY_CLOSED)},
    ]
    card = build_matrix_audit(registry, summaries)
    assert card["authority"] == AUTHORITY_CLOSED
    assert card["metrics"]["authority_rows"] == 0
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert card["metrics"]["runtime_authorized_flag"] is False
