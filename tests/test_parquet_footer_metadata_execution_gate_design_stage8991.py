from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8991_parquet_footer_metadata_execution_gate_design import (  # noqa: E402
    ALLOWED_PROBE_TYPE,
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    GATE_STATE,
    REQUIRED_OUTPUTS,
    REQUIRED_RUNTIME_ASSERTIONS,
    build_gate,
    validate_design,
    validate_gate,
)


def ticket() -> dict[str, object]:
    return {"ticket_id": "t", "selected_candidate_ids": ["c1", "c2"]}


def selected() -> list[dict[str, object]]:
    return [{"candidate_id": "c1"}, {"candidate_id": "c2"}]


def card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "gate_failures": 0,
            "gate_granted": False,
            "footer_access_authorized_now": False,
            "execution_authorized": False,
            "parquet_footer_access_performed": False,
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
    }


def test_stage8991_builds_not_granted_gate_with_required_contract() -> None:
    gate = build_gate(ticket(), selected())
    assert gate["gate_state"] == GATE_STATE
    assert gate["allowed_probe_type"] == ALLOWED_PROBE_TYPE
    assert gate["execution_authorized"] is False
    assert gate["footer_access_authorized_now"] is False
    assert set(REQUIRED_OUTPUTS).issubset(set(gate["required_outputs"]))
    assert set(FORBIDDEN_OPERATIONS).issubset(set(gate["forbidden_operations"]))
    assert set(REQUIRED_RUNTIME_ASSERTIONS).issubset(set(gate["required_runtime_assertions"]))
    assert validate_gate(gate, ticket(), selected()) == []


def test_stage8991_gate_validation_rejects_any_execution_grant() -> None:
    gate = build_gate(ticket(), selected())
    bad = dict(gate)
    bad["execution_authorized"] = True
    assert "execution_authorized" in validate_gate(bad, ticket(), selected())
    wrong = dict(gate)
    wrong["allowed_probe_type"] = "ROW_SCAN"
    assert "allowed_probe_type" in validate_gate(wrong, ticket(), selected())


def test_stage8991_design_validation_rejects_open_authority_or_footer_access() -> None:
    assert validate_design(card()) == []
    bad = card()
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_design(bad)
    opened = card()
    opened["metrics"]["footer_access_authorized_now"] = True
    assert "footer_access_authorized_now" in validate_design(opened)
