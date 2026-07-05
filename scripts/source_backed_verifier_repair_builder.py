from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gate_status_contract import default_gate_status, gate_status_card

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
LOSS_MASK = {key: False for key in [
    "surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce",
    "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce",
    "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce", "verifier_repair_ce",
    "decoder_ce", "denoise_ce", "runtime_reward",
]}
ACTIONS = {
    "DIAGNOSE_FAILURE", "RERUN_VERIFIER", "LOCALIZE_FAILURE", "REPAIR_SYNTAX",
    "REPAIR_ASSERTION", "REPAIR_IMPORT", "REPAIR_API_CALL", "ROLLBACK_OR_ABSTAIN", "RETRIEVE_MORE",
}


def opaque(value: str, prefix: str = "o") -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def lineage_records(path: Path) -> dict[str, dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))["records"]
    return {str(record["path"]): record for record in records}


def source_lineage(lin_by_path: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nodes = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl"]
    spans = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl"]
    levels = lin_by_path.get("/arxiv/TOLBERT_BRAIN/data/repos/level_sizes_repos.json", nodes)
    return {
        "graph_nodes_source_id": nodes["source_id"],
        "graph_nodes_lineage_hash": nodes["lineage_hash"],
        "graph_spans_source_id": spans["source_id"],
        "graph_spans_lineage_hash": spans["lineage_hash"],
        "graph_level_sizes_source_id": levels["source_id"],
        "graph_level_sizes_lineage_hash": levels["lineage_hash"],
        "locked_eval_source": False,
        "train_eligible_lineage": True,
        "raw_source_in_model_input": False,
    }


def build_source_backed_rows(neutral_rows: list[dict[str, Any]], lineage_path: Path) -> list[dict[str, Any]]:
    lin = lineage_records(lineage_path)
    lineage = source_lineage(lin)
    rows: list[dict[str, Any]] = []
    for neutral in neutral_rows:
        clean = dict(neutral.get("clean_state") or {})
        action = clean.get("verifier_repair_action")
        if action not in ACTIONS:
            continue
        state = dict(neutral.get("corrupted_state") or {})
        packet = dict(state.get("verifier_packet") or {})
        budget = dict(state.get("budget") or {})
        old_id = str(neutral.get("row_id") or neutral.get("semantic_key") or len(rows))
        row_id = "stage8788_" + opaque(old_id, "row")
        visible_state = {
            "task_family": "verifier_repair",
            "language": state.get("language"),
            "file_extension": state.get("file_extension"),
            "patch_context": state.get("patch_context"),
            "verifier_signal": state.get("verifier_signal"),
            "verifier_packet": {
                "log_available": bool(packet.get("log_available")),
                "patch_summary_visible": bool(packet.get("patch_summary_visible")),
                "runtime_execution_authorized": False,
                "source_location_visible": bool(packet.get("source_location_visible")),
                "test_name_visible": bool(packet.get("test_name_visible")),
            },
            "budget": {
                "decoder_budget_ok": False,
                "max_repair_steps": budget.get("max_repair_steps"),
                "runtime_reward_allowed": False,
            },
        }
        graph_input = {
            "opaque_graph_id": opaque(f"graph:{old_id}", "graph"),
            "failure_node_id": opaque(f"failure:{old_id}", "node"),
            "patch_candidate_node_id": opaque(f"patch:{old_id}", "node"),
            "verifier_node_id": opaque(f"verifier:{old_id}", "node"),
            "candidate_node_count": 4 + (len(old_id) % 5),
            "edge_family_count": 3 + (len(old_id) % 4),
            "source_graph_materialized": False,
        }
        rows.append({
            "row_id": row_id,
            "split": neutral.get("split"),
            "objective_family": "source_backed_verifier_repair",
            "route": "CANDIDATE_NEEDS_AUDIT",
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK),
            "gate_status": default_gate_status(
                source_inventory_lineage=True,
                source_provenance=True,
                golden_locked_eval_suite=True,
            ),
            "source_backed": True,
            "source_stage": "stage8788_from_stage8643_with_repo_graph_lineage_controls",
            "source_row_ref": {
                "source_stage": neutral.get("source_stage"),
                "source_row_id_hash": opaque(old_id, "srcrow"),
                "source_row_id_in_model_input": False,
            },
            "semantic_key": f"{neutral.get('split')}:{state.get('language')}:{opaque(old_id, 'sem')}",
            "source_lineage": dict(lineage),
            "graph_input": graph_input,
            "query": {
                "query_kind": "verifier_failure_packet",
                "query_node_id": graph_input["failure_node_id"],
                "query_node_id_is_opaque": True,
            },
            "corrupted_state": visible_state,
            "clean_state": {
                "verifier_repair_action": action,
                "action_sequence": clean.get("action_sequence"),
                "file_plan": clean.get("file_plan"),
            },
            "anti_cheat": {
                "raw_source_included": False,
                "raw_log_body_in_model_input": False,
                "raw_patch_body_in_model_input": False,
                "runtime_output_in_model_input": False,
                "target_label_in_id": False,
                "source_row_id_in_model_input": False,
                "requires_shortcut_audit_before_training": True,
                "requires_recovered_gate_status_before_compiler": True,
            },
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = Counter((row.get("clean_state") or {}).get("verifier_repair_action") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    languages = Counter((row.get("corrupted_state") or {}).get("language") for row in rows)
    return {
        "rows": len(rows),
        "actions": dict(sorted(actions.items())),
        "splits": dict(sorted(splits.items())),
        "languages": dict(sorted(languages.items())),
        "gate_status": gate_status_card(rows),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
    }
