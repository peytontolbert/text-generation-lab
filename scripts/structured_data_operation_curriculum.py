from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

STRUCTURE_OPERATORS = {
    "table": {"inspect_schema", "select_columns", "filter_rows", "group_by", "aggregate", "join", "sort", "validate_constraints"},
    "json": {"read_path", "replace_path", "add_field", "delete_field", "json_patch", "validate_schema", "merge_objects"},
    "graph": {"get_neighbors", "find_path", "topological_sort", "detect_cycle", "rank_nodes", "trace_dependency", "find_impacted_nodes"},
    "ast": {"find_symbol", "rename_symbol", "insert_node", "delete_node", "replace_subtree", "validate_syntax"},
    "log_trace": {"find_first_failure", "classify_failure", "summarize_trace", "recommend_recovery", "extract_error_signature"},
    "workflow": {"transition_state", "check_guard", "rollback", "finish", "repair", "escalate"},
    "memory": {"retrieve", "store", "update", "delete", "deduplicate", "rank_by_relevance", "summarize_old_memory"},
}

REQUIRED_FIELDS = {"structure_type", "state", "schema", "addressing", "task", "operator", "validator"}


def operation_row(
    *,
    row_id: str,
    structure_type: str,
    state: Mapping[str, Any],
    schema: Mapping[str, Any],
    addressing: str,
    task: str,
    operator: str,
    arguments: Mapping[str, Any],
    validator: str,
    split: str = "train",
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "split": split,
        "objective_family": "structured_data_operation_curriculum",
        "route": "KEEP_STRUCTURED",
        "structure_type": structure_type,
        "state": dict(state),
        "schema": dict(schema),
        "addressing": addressing,
        "task": task,
        "operator": operator,
        "arguments": dict(arguments),
        "validator": validator,
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": {
            "surface_role_ce": False,
            "repair_surface_ce": False,
            "build_mode_ce": False,
            "allowed_import_policy_ce": False,
            "blocked_import_policy_ce": False,
            "repo_dependency_policy_ce": False,
            "action_sequence_ce": True,
            "file_plan_ce": False,
            "symbol_binding_ce": False,
            "edit_localization_ce": False,
            "patch_operator_ce": False,
            "verifier_repair_ce": False,
            "decoder_ce": False,
            "denoise_ce": False,
            "runtime_reward": False,
        },
    }


def validate_operation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
    failures.extend(f"missing_field:{field}" for field in missing)
    structure_type = str(row.get("structure_type") or "")
    operator = str(row.get("operator") or "")
    if structure_type not in STRUCTURE_OPERATORS:
        failures.append(f"unknown_structure_type:{structure_type}")
    elif operator not in STRUCTURE_OPERATORS[structure_type]:
        failures.append(f"operator_not_allowed:{structure_type}:{operator}")
    authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    if any(value is True for value in authority.values()):
        failures.append("authority_open")
    loss = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
    for forbidden in ["decoder_ce", "denoise_ce", "runtime_reward"]:
        if loss.get(forbidden) is True:
            failures.append(f"forbidden_loss_enabled:{forbidden}")
    if not isinstance(row.get("state"), dict):
        failures.append("state_not_object")
    if not isinstance(row.get("schema"), dict):
        failures.append("schema_not_object")
    if not str(row.get("addressing") or "").strip():
        failures.append("missing_addressing")
    if not str(row.get("validator") or "").strip():
        failures.append("missing_validator")
    return {
        "row_id": str(row.get("row_id") or ""),
        "passed": not failures,
        "failures": failures,
        "structure_type": structure_type,
        "operator": operator,
        "authority": AUTHORITY_CLOSED,
    }


def build_seed_rows() -> list[dict[str, Any]]:
    return [
        operation_row(
            row_id="table_filter_completed_orders",
            structure_type="table",
            state={"table": "orders", "columns": ["order_id", "customer_id", "amount", "status"]},
            schema={"order_id": "int", "customer_id": "int", "amount": "float", "status": "string"},
            addressing="table.column + row predicate",
            task="Find completed orders before aggregation.",
            operator="filter_rows",
            arguments={"condition": "status == 'completed'"},
            validator="result_rows_all_status_completed",
        ),
        operation_row(
            row_id="json_replace_timeout",
            structure_type="json",
            state={"settings": {"timeout": 10, "retries": 2}},
            schema={"settings.timeout": "int", "settings.retries": "int"},
            addressing="json_pointer",
            task="Set timeout to 30 without changing retries.",
            operator="replace_path",
            arguments={"path": "/settings/timeout", "value": 30},
            validator="json_schema_valid_and_only_timeout_changed",
        ),
        operation_row(
            row_id="graph_impacted_tests",
            structure_type="graph",
            state={"nodes": ["auth.py", "db.py", "test_auth.py"], "edges": [["test_auth.py", "auth.py", "tests"], ["auth.py", "db.py", "calls"]]},
            schema={"node": "file", "edge": ["src", "dst", "relation"]},
            addressing="node_id + edge_type",
            task="Find tests impacted by auth.py.",
            operator="find_impacted_nodes",
            arguments={"changed_node": "auth.py", "relation": "tests"},
            validator="returns_test_auth_py",
        ),
        operation_row(
            row_id="ast_find_symbol",
            structure_type="ast",
            state={"file": "app/auth.py", "symbols": [{"name": "validate_token", "kind": "function"}]},
            schema={"symbol.name": "str", "symbol.kind": "enum"},
            addressing="ast_symbol_id",
            task="Locate validate_token function.",
            operator="find_symbol",
            arguments={"name": "validate_token"},
            validator="symbol_exists_once",
        ),
        operation_row(
            row_id="log_first_failure",
            structure_type="log_trace",
            state={"events": ["start", "db connection refused", "retry failed"]},
            schema={"events": "ordered_strings"},
            addressing="event_index",
            task="Find the first root failure.",
            operator="find_first_failure",
            arguments={"pattern": "failure_or_exception"},
            validator="returns_db_connection_refused",
        ),
        operation_row(
            row_id="workflow_test_failed_repair",
            structure_type="workflow",
            state={"current_state": "validate", "event": "test_failed"},
            schema={"current_state": "enum", "event": "enum"},
            addressing="state_name",
            task="Choose next workflow state after test failure.",
            operator="transition_state",
            arguments={"next_state": "repair"},
            validator="transition_allowed_by_state_machine",
        ),
        operation_row(
            row_id="memory_store_preference",
            structure_type="memory",
            state={"memories": []},
            schema={"memory_type": "enum", "key": "str", "value": "str"},
            addressing="memory_key",
            task="Store durable concise response preference.",
            operator="store",
            arguments={"memory_type": "preference", "key": "response_style", "value": "concise"},
            validator="memory_key_present_once",
        ),
    ]


def curriculum_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    audits = [validate_operation_row(row) for row in rows]
    structure_counts: dict[str, int] = {}
    operator_counts: dict[str, int] = {}
    for audit in audits:
        structure_counts[audit["structure_type"]] = structure_counts.get(audit["structure_type"], 0) + 1
        operator_counts[audit["operator"]] = operator_counts.get(audit["operator"], 0) + 1
    return {
        "rows": len(rows),
        "passed": all(audit["passed"] for audit in audits),
        "structure_counts": dict(sorted(structure_counts.items())),
        "operator_counts": dict(sorted(operator_counts.items())),
        "audit_failures": [audit for audit in audits if not audit["passed"]],
        "audits": audits,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Structured data operation curriculum contract.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else build_seed_rows()
    card = curriculum_card(rows)
    text = json.dumps({"card": card, "rows": rows, "authority": AUTHORITY_CLOSED}, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
