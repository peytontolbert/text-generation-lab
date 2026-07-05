from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gate_status_contract import default_gate_status, gate_status_card

AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
LOSS_MASK = {key: False for key in ["surface_role_ce", "repair_surface_ce", "build_mode_ce", "allowed_import_policy_ce", "blocked_import_policy_ce", "repo_dependency_policy_ce", "action_sequence_ce", "file_plan_ce", "symbol_binding_ce", "edit_localization_ce", "patch_operator_ce", "verifier_repair_ce", "decoder_ce", "denoise_ce", "runtime_reward"]}
OPERATORS = {"MODIFY_EXISTING_SYMBOL", "INSERT_FUNCTION", "REPLACE_EXPR", "WRAP_CALL", "ADD_IMPORT", "ADD_TEST_CASE", "UPDATE_CONFIG_FIELD", "CREATE_FILE", "BUILD_ADAPTER", "ROLLBACK_PATCH", "RETRIEVE_MORE", "ABSTAIN_UNSAFE"}


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
        "graph_nodes_source_id": nodes["source_id"], "graph_nodes_lineage_hash": nodes["lineage_hash"],
        "graph_spans_source_id": spans["source_id"], "graph_spans_lineage_hash": spans["lineage_hash"],
        "graph_level_sizes_source_id": levels["source_id"], "graph_level_sizes_lineage_hash": levels["lineage_hash"],
        "locked_eval_source": False, "train_eligible_lineage": True, "raw_source_in_model_input": False,
    }


def build_source_backed_rows(neutral_rows: list[dict[str, Any]], lineage_path: Path) -> list[dict[str, Any]]:
    lin = lineage_records(lineage_path)
    lineage = source_lineage(lin)
    rows: list[dict[str, Any]] = []
    for neutral in neutral_rows:
        clean = dict(neutral.get("clean_state") or {})
        operator = clean.get("patch_operator")
        if operator not in OPERATORS:
            continue
        state = dict(neutral.get("corrupted_state") or {})
        scope = dict(state.get("target_scope_features") or {})
        old_id = str(neutral.get("row_id") or neutral.get("semantic_key") or len(rows))
        row_id = "stage8774_" + opaque(old_id, "row")
        visible_state = {
            "task_family": "patch_operator",
            "language": state.get("language"),
            "file_extension": state.get("file_extension"),
            "localized_edit_need": state.get("localized_edit_need"),
            "operator_signal": state.get("operator_signal"),
            "target_scope_features": scope,
            "budget": state.get("budget"),
        }
        graph_input = {
            "opaque_graph_id": opaque(f"graph:{old_id}", "graph"),
            "target_kind_hint": scope.get("target_kind_hint"),
            "candidate_node_count": 3 + (len(old_id) % 5),
            "edge_family_count": 2 + (len(old_id) % 4),
            "source_graph_materialized": False,
        }
        rows.append({
            "row_id": row_id,
            "split": neutral.get("split"),
            "objective_family": "source_backed_patch_operator",
            "route": "CANDIDATE_NEEDS_AUDIT",
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK),
            "gate_status": default_gate_status(source_inventory_lineage=True, source_provenance=True, golden_locked_eval_suite=True),
            "source_backed": True,
            "source_stage": "stage8774_from_stage8638_with_repo_graph_lineage_controls",
            "source_row_ref": {"source_stage": neutral.get("source_stage"), "source_row_id_hash": opaque(old_id, "srcrow"), "source_row_id_in_model_input": False},
            "semantic_key": f"{neutral.get('split')}:{state.get('language')}:{opaque(old_id, 'sem')}",
            "source_lineage": dict(lineage),
            "graph_input": graph_input,
            "query": {"query_kind": "localized_edit_need", "query_node_id": opaque(f"query:{old_id}", "node"), "query_node_id_is_opaque": True},
            "corrupted_state": visible_state,
            "clean_state": {"patch_operator": operator, "action_sequence": clean.get("action_sequence"), "file_plan": clean.get("file_plan")},
            "anti_cheat": {"raw_source_included": False, "raw_symbol_names_in_model_input": False, "target_label_in_id": False, "patch_body_in_model_input": False, "source_row_id_in_model_input": False, "requires_shortcut_audit_before_training": True, "requires_recovered_gate_status_before_compiler": True},
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ops = Counter((row.get("clean_state") or {}).get("patch_operator") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    languages = Counter((row.get("corrupted_state") or {}).get("language") for row in rows)
    return {
        "rows": len(rows),
        "operators": dict(sorted(ops.items())),
        "splits": dict(sorted(splits.items())),
        "languages": dict(sorted(languages.items())),
        "gate_status": gate_status_card(rows),
        "authority_rows": sum(int(any((row.get("authority") or {}).values())) for row in rows),
        "training_loss_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
    }
