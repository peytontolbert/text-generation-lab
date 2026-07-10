#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10033
NAME = "stage10033_python_cpp_fresh_root_scaffold_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "python_cpp_fresh_root_scaffold_packet.json"
SCAFFOLD_ROWS = OUT_DIR / "python_cpp_fresh_root_scaffold_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_CPP_FRESH_ROOT_SCAFFOLD_PACKET_STAGE10033.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage10032_python_cpp_fresh_root_builder_workbook/python_cpp_fresh_root_builder_workbook.json"

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

LOSS_MASK = {
    "surface_role_ce": False,
    "repair_surface_ce": False,
    "build_mode_ce": False,
    "allowed_import_policy_ce": False,
    "blocked_import_policy_ce": False,
    "repo_dependency_policy_ce": False,
    "action_sequence_ce": False,
    "file_plan_ce": False,
    "symbol_binding_ce": False,
    "edit_localization_ce": True,
    "patch_operator_ce": False,
    "verifier_repair_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
}

LABEL_TO_SIGNAL = {
    "A": "symbol_owner_visible",
    "B": "config_driven_behavior",
    "C": "file_level_responsibility_only",
    "D": "stale_or_malformed_test_expectation",
    "E": "startup_or_entrypoint_behavior",
}

LABEL_TO_EVIDENCE = {
    "A": "A visible call or definition points to the symbol that owns the behavior.",
    "B": "Visible configuration evidence controls the failing behavior.",
    "C": "The visible failure is localized to a file-level responsibility but no specific symbol is available.",
    "D": "The source behavior is valid, but the visible test expectation is stale or malformed.",
    "E": "The visible failure occurs through startup or command entry behavior.",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scaffold_row(task: dict[str, Any], index: int) -> dict[str, Any]:
    label = str(task.get("target_label") or "")
    language = str(task.get("language_family") or "")
    root_stub = f"fresh_root::{language}::{label}::{index + 1}"
    file_extension = "py" if language == "python" else "cc"
    return {
        "row_id": f"stage10033_{root_stub}::positive_original",
        "split": "strict_eval",
        "objective_family": "source_heldout_edit_localization_fresh_root_scaffold",
        "route": "FILL_WITH_NEW_INDEPENDENT_ROOT",
        "authority": dict(AUTHORITY_CLOSED),
        "loss_mask": dict(LOSS_MASK),
        "gate_status": {
            "source_inventory_lineage": True,
            "source_provenance": True,
            "golden_locked_eval_suite": True,
            "schema_drift_detector": True,
            "contamination_leakage_detector": True,
            "drift_canary_regression_monitor": True,
        },
        "source_backed": True,
        "source_stage": "stage10033_fresh_root_scaffold_packet",
        "source_row_ref": {
            "seed_task_id": task.get("task_id"),
            "seed_root_case_ids": task.get("seed_root_case_ids"),
            "source_row_id_in_model_input": False,
        },
        "semantic_key": f"strict_eval:{language}:fill_me::{label}::{index + 1}",
        "source_lineage": {
            "locked_eval_source": True,
            "train_eligible_lineage": False,
            "raw_source_in_model_input": False,
            "required_new_source_root": True,
        },
        "graph_input": {
            "opaque_graph_id": "FILL_ME_NEW_OPAQUE_GRAPH_ID",
            "query_node_type": "maintainer_localization_query",
            "edge_family_count": "FILL_ME",
            "candidate_node_count": "FILL_ME",
            "candidate_family_id": "FILL_ME_NEW_CANDIDATE_FAMILY",
            "source_graph_materialized": False,
        },
        "query": {
            "query_kind": "maintainer_localization_query",
            "query_node_id": "FILL_ME_NEW_QUERY_NODE_ID",
            "query_node_id_is_opaque": True,
        },
        "corrupted_state": {
            "task_family": "edit_localization",
            "language": language,
            "file_extension": file_extension,
            "task_observation": "FILL_ME_NEW_INDEPENDENT_BEHAVIOR_CHECK_FAILURE",
            "visible_locality_evidence": LABEL_TO_EVIDENCE.get(label, "FILL_ME_VISIBLE_LOCALITY_EVIDENCE"),
            "locality_signal": LABEL_TO_SIGNAL.get(label, "FILL_ME_LOCALITY_SIGNAL"),
            "neutral_context_bits": {
                "config_visible": True,
                "entrypoint_visible": True,
                "symbol_names_visible": False,
                "tests_visible": True,
            },
            "budget": {
                "decoder_budget_ok": False,
                "max_files": 2,
                "max_symbols": 2,
            },
        },
        "input_state": {
            "task_observation": "FILL_ME_NEW_INDEPENDENT_BEHAVIOR_CHECK_FAILURE",
            "visible_locality_evidence": LABEL_TO_EVIDENCE.get(label, "FILL_ME_VISIBLE_LOCALITY_EVIDENCE"),
            "file_extension": file_extension,
            "context_config_visible": True,
            "context_entrypoint_visible": True,
            "context_symbol_names_visible": False,
            "context_tests_visible": True,
        },
        "clean_state": {
            "edit_localization": label,
            "edit_localization_target": label,
            "edit_localization_target_hidden": "TARGET_SYMBOL",
            "action_sequence": ["BIND_SYMBOL", "READ_SYMBOL", "PLAN_PATCH"],
            "file_plan": "localize target through visible evidence and keep patch bounded",
        },
        "target": {
            "decoder_text": label,
            "edit_localization": label,
            "target_ref": label,
        },
        "anti_cheat": {
            "raw_source_included": False,
            "raw_symbol_names_in_model_input": False,
            "target_label_in_id": False,
            "target_path_in_model_input": False,
            "source_row_id_in_model_input": False,
            "target_label_literals_in_prompt_surface": False,
            "visible_locality_evidence_lifted": True,
            "requires_shortcut_audit_before_training": True,
            "requires_recovered_gate_status_before_compiler": True,
            "requires_expert_maintainer_review_before_promotion": True,
            "requires_fresh_source_root": True,
        },
        "choice_permutation_stage": "FILL_ME",
        "choice_permutation_map": "FILL_ME_OPAQUE_CHOICE_MAP",
        "choice_permutation_order": "FILL_ME_OPAQUE_CHOICE_ORDER",
        "counterfactual_root_row_id": root_stub,
        "counterfactual_role": "positive_original",
        "counterfactual_required_obligations": [
            "POSITIVE_ORIGINAL",
            "SOURCE_HELDOUT",
            "EXPERT_MAINTAINER_REVIEW_REQUIRED",
            "ANTI_CHEAT_REVIEW_REQUIRED",
        ],
        "builder_requirements": task.get("builder_requirements"),
        "signoff_checks": task.get("signoff_checks"),
    }


def build_packet() -> dict[str, Any]:
    workbook = load_json(WORKBOOK)
    tasks = workbook.get("tasks") if isinstance(workbook.get("tasks"), list) else []
    scaffold_rows = [scaffold_row(task, index) for index, task in enumerate(tasks)]
    failures: list[str] = []
    if len(tasks) != 6:
        failures.append("workbook_tasks_not_6")
    if len(scaffold_rows) != 6:
        failures.append("scaffold_rows_not_6")
    write_jsonl(SCAFFOLD_ROWS, scaffold_rows)
    packet = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "tasks": len(tasks),
            "scaffold_rows": len(scaffold_rows),
            "languages": sorted({str(task.get("language_family") or "") for task in tasks}),
        },
        "inputs": {
            "builder_workbook": display(WORKBOOK),
        },
        "notes": [
            "Each scaffold row is a fill-in template for one fresh independent heldout root family.",
            "Populate only with new source roots not present in any current train or heldout manifest.",
            "Keep the visible-evidence contract and opaque-choice anti-cheat fields intact.",
        ],
    }
    PACKET.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    next_step = (
        "Fill these six scaffold rows into real fresh independent Python/C++ heldout roots, then merge them into the heldout manifest and rerun the deduped same-manifest comparison."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "scaffold_rows": display(SCAFFOLD_ROWS), "doc": display(DOC)},
        "decision": "Materialized a schema-aligned scaffold packet for the six unresolved Python/C++ fresh-root families so dataset builders can instantiate new heldout rows without re-deriving the edit-localization row contract.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10033 Python Cpp Fresh Root Scaffold Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Scaffold rows: `{built['metrics']['scaffold_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
