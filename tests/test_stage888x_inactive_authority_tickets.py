from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUTHORITY_KEYS = {
    "model_execution_authorized_next",
    "decoder_ce_training_authorized_next",
    "denoise_ce_training_authorized_next",
    "runtime_authorized",
    "source_emission_authorized",
    "body_emission_authorized",
    "gemma_execution_authorized_next",
    "harness_execution_authorized_next",
    "scoring_authorized_next",
    "controller_complete_merge_authorized_next",
    "promotion_ready",
}


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def assert_authority_closed(payload: dict) -> None:
    authority = payload.get("authority") or {}
    missing = AUTHORITY_KEYS - set(authority)
    assert not missing
    assert not any(bool(authority[key]) for key in AUTHORITY_KEYS)


def test_stage8890_inactive_ticket_cannot_execute_or_train() -> None:
    ticket = load_json("runs/local/artifacts/stage8886_stage8890_inactive_execution_ticket_design/stage8890_inactive_execution_ticket.json")
    assert ticket["ticket_status"] == "DRAFT_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["command_materialized"] is False
    assert "command" not in ticket
    assert ticket["allowed_operations"] == []
    assert set(ticket["denied_operations"]) >= {
        "load_checkpoint",
        "run_forward",
        "decode_tokens",
        "compute_decoder_ce",
        "compute_denoise_ce",
        "run_runtime",
        "call_gemma",
        "score_output",
        "emit_source_body",
        "promote_model",
    }
    assert ticket["allowed_loss_weights"] == {
        "structured_aux_weight": 1.0,
        "decoder_ce_weight": 0.0,
        "denoise_weight": 0.0,
    }
    assert ticket["checkpoint_scope"]["final_checkpoint_export"] is False
    assert set(ticket["checkpoint_scope"]["cleanup_forbidden_paths"]) >= {"/", "/data", "/arxiv", str(ROOT)}


def test_stage8890_ticket_gate_summary_keeps_authority_closed() -> None:
    summary = load_json("runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json")
    assert summary["passed"] is True
    assert_authority_closed(summary)
    metrics = summary["metrics"]
    assert metrics["gate_failures"] == 0
    assert metrics["allowed_operations"] == 0
    assert metrics["command_materialized"] is False
    assert metrics["execution_authorized_now"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False


def test_metadata_inventory_inactive_ticket_reads_nothing_and_protects_arxiv() -> None:
    ticket = load_json("runs/local/artifacts/stage8889_metadata_inventory_inactive_ticket_gate/metadata_inventory_inactive_ticket.json")
    assert ticket["ticket_status"] == "DRAFT_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["repository_walks_now"] == 0
    assert ticket["commit_reads_now"] == 0
    assert ticket["diff_body_reads_now"] == 0
    assert ticket["patch_body_reads_now"] == 0
    assert ticket["source_body_reads_now"] == 0
    assert ticket["training_rows_now"] == 0
    assert all(value == 0 for value in ticket["future_caps_require_new_ticket"].values())
    assert "/arxiv" in ticket["forbidden_roots_without_explicit_ticket"]
    assert_authority_closed(ticket)


def test_stage8889_summary_and_registry_frontier_are_closed() -> None:
    summary = load_json("runs/summaries/stage8889_metadata_inventory_inactive_ticket_gate.json")
    registry = load_json("runs/local/artifacts/reconstructed_stage_registry.json")
    assert summary["passed"] is True
    assert_authority_closed(summary)
    assert summary["metrics"]["repository_walks_now"] == 0
    assert summary["metrics"]["commit_reads_now"] == 0
    assert summary["metrics"]["training_rows_now"] == 0
    assert registry["metrics"]["latest_stage"] == 8889
    assert registry["metrics"]["latest_stage_name"] == "stage8889_metadata_inventory_inactive_ticket_gate"
    assert registry["metrics"]["authority_counts"] == {key: 0 for key in AUTHORITY_KEYS}
