from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8992_parquet_footer_metadata_execution_gate_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_ASSERTIONS,
    REQUIRED_OUTPUTS,
    audit_gate,
    validate_audit,
)


def gate() -> dict[str, object]:
    return {
        "gate_state": "DESIGNED_NOT_GRANTED",
        "allowed_probe_type": "PARQUET_FOOTER_SCHEMA_METADATA_ONLY",
        "selected_candidate_ids": ["c1"],
        "output_dir": "runs/local/artifacts/x",
        "required_outputs": list(REQUIRED_OUTPUTS),
        "forbidden_operations": [
            "DATASET_ROW_SCAN", "DATASET_ROW_MATERIALIZATION", "PARQUET_BATCH_MATERIALIZATION",
            "PARQUET_DATA_PAGE_READ", "REPOSITORY_SOURCE_BODY_READ", "ARXIV_WRITE",
            "TRAINING", "MINING", "MODEL_EXECUTION", "RUNTIME_EXECUTION", "NETWORK_UPLOAD",
        ],
        "required_runtime_assertions": list(REQUIRED_ASSERTIONS),
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "batch_materialization_allowed": False,
        "footer_access_authorized_now": False,
        "execution_authorized": False,
        "training_authorized": False,
        "model_execution_authorized": False,
        "runtime_authorized": False,
    }


def ticket() -> dict[str, object]:
    return {"selected_candidate_ids": ["c1"]}


def card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "missing_outputs": 0,
            "missing_forbidden_operations": 0,
            "missing_runtime_assertions": 0,
            "false_flag_failures": 0,
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


def test_stage8992_audits_complete_not_granted_gate() -> None:
    result = audit_gate(gate(), ticket())
    assert result["selected_ids_match_ticket"] is True
    assert result["missing_outputs"] == []
    assert result["missing_forbidden_operations"] == []
    assert result["missing_runtime_assertions"] == []
    assert result["false_flag_failures"] == []


def test_stage8992_audit_catches_missing_output_and_execution_flag() -> None:
    bad = gate()
    bad["required_outputs"] = []
    bad["execution_authorized"] = True
    result = audit_gate(bad, ticket())
    assert result["missing_outputs"]
    assert "execution_authorized" in result["false_flag_failures"]


def test_stage8992_validate_rejects_grant_or_open_authority() -> None:
    assert validate_audit(card()) == []
    granted = card()
    granted["metrics"]["gate_granted"] = True
    assert "gate_granted" in validate_audit(granted)
    opened = card()
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
