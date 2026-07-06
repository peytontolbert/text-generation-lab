#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9043
NAME = "stage9043_domain_twin_operator_bridge"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_8703 = ROOT / "runs/summaries/stage8703_low_level_training_concept_session_grep.json"
SPINE = ROOT / "docs/MODEL_STACK_SPINE.md"
ACTION_REGISTRY = ROOT / "docs/SOFTWARE_MAINTAINER_ACTION_FEATURE_REGISTRY.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DOMAIN_TWIN_OPERATOR_BRIDGE_STAGE9043.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "domain_twin_operator_bridge.json"

DOMAIN_GRAPH_VARIABLES = [
    "concept_id",
    "concept_name",
    "concept_embedding",
    "edge_types",
    "appears_in_same_repo_as",
    "co_occurs_with",
    "is_subconcept_of_future",
    "cross_domain_connector_future",
    "repo_to_concept_map",
    "paper_to_concept_map",
    "repo_frequency_score",
    "concept_local_degree_score",
    "expert_repo_score",
    "expert_paper_score",
]
TWIN_MEMORY_VARIABLES = [
    "repo_twin_id",
    "paper_twin_id",
    "semantic_summary_scope",
    "episodic_time_window",
    "recency_boost",
    "test_type_weight",
    "doc_type_weight",
    "commit_issue_type_weight",
    "context_dedup_key",
    "semantic_context_limit",
    "episodic_context_limit",
    "consistency_report",
    "uncertainty_flags",
    "evidence_map",
]
OPERATOR_BRIDGE = [
    {"operator": "OP030", "role": "repository_retrieval", "required_metric": "retrieval_recall_at_k", "failure_question": "was_the_right_artifact_retrieved"},
    {"operator": "OP053", "role": "list_aware_candidate_quality", "required_metric": "rerank_mrr_or_pairwise_accuracy", "failure_question": "did_reranker_pick_the_right_candidate"},
    {"operator": "OP048", "role": "verifier_backed_equivalence", "required_metric": "verifier_backed_equivalence_accuracy", "failure_question": "was_test_execution_static_or_dataflow_evidence_available"},
    {"operator": "OP059", "role": "template_infill_slot_completion", "required_metric": "template_slot_accuracy", "failure_question": "were_bidirectional_context_and_slot_constraints_present"},
    {"operator": "OP086", "role": "phase_controller_policy", "required_metric": "phase_routing_accuracy", "failure_question": "did_policy_choose_retrieve_rerank_instantiate_verify_repair_route_or_abstain"},
]
RECOVERED_STAGE_SEQUENCE = [
    "stage1272_failure_decomposition_eval",
    "stage1273_repository_retrieval_candidates_v2",
    "stage1274_list_aware_candidate_quality",
    "stage1275_op048_verifier_rows",
    "stage1276_op059_template_infill_rows",
    "stage1277_phase_controller_policy",
]
CANONICAL_ROW_FIELDS = [
    "task",
    "repo_state",
    "phase",
    "operator_history",
    "retrieved_context_refs",
    "candidate_list_refs",
    "evidence.tests_ref",
    "evidence.execution_ref",
    "evidence.static_analysis_ref",
    "evidence.data_flow_ref",
    "evidence.focal_context_ref",
    "target.next_operator",
    "target.decision",
    "target.selected_candidate",
    "target.reason_code",
]
FORBIDDEN_NOW = [
    "scan_data_repository_library",
    "scan_arxiv",
    "materialize_domain_graph_from_corpus",
    "materialize_repo_twin_memory",
    "materialize_paper_twin_memory",
    "train_operator_bridge",
    "run_retrieval_eval",
    "run_model",
    "run_runtime",
    "write_arxiv",
    "upload_hf",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_8703)
    spine = text(SPINE)
    actions = text(ACTION_REGISTRY)
    checks = {
        "source_stage8703_present": SOURCE_8703.exists(),
        "source_stage8703_passed": source.get("passed") is True,
        "model_stack_spine_present": SPINE.exists(),
        "action_registry_present": ACTION_REGISTRY.exists(),
        "spine_has_retrieval_and_repo_graph_layers": "Cross-encoder reranker" in spine and "Repo graph / GNN" in spine,
        "action_registry_has_core_maintainer_actions": "RETRIEVE_MORE" in actions and "RUN_VERIFIER" in actions,
        "domain_graph_variables_recorded": len(DOMAIN_GRAPH_VARIABLES) >= 14,
        "twin_memory_variables_recorded": len(TWIN_MEMORY_VARIABLES) >= 14,
        "operator_bridge_covers_five_critical_ops": {row["operator"] for row in OPERATOR_BRIDGE} == {"OP030", "OP053", "OP048", "OP059", "OP086"},
        "recovered_stage_sequence_recorded": len(RECOVERED_STAGE_SEQUENCE) == 6,
        "canonical_row_fields_recorded": len(CANONICAL_ROW_FIELDS) >= 15,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DOMAIN_TWIN_OPERATOR_BRIDGE_CONTRACT_ONLY",
        "domain_graph_variables": DOMAIN_GRAPH_VARIABLES,
        "twin_memory_variables": TWIN_MEMORY_VARIABLES,
        "operator_bridge": OPERATOR_BRIDGE,
        "recovered_stage_sequence": RECOVERED_STAGE_SEQUENCE,
        "canonical_row_fields": CANONICAL_ROW_FIELDS,
        "forbidden_now": FORBIDDEN_NOW,
        "checks": checks,
        "metrics": {
            "domain_graph_variables": len(DOMAIN_GRAPH_VARIABLES),
            "twin_memory_variables": len(TWIN_MEMORY_VARIABLES),
            "operator_bridge_rows": len(OPERATOR_BRIDGE),
            "recovered_stage_sequence_rows": len(RECOVERED_STAGE_SEQUENCE),
            "canonical_row_fields": len(CANONICAL_ROW_FIELDS),
            "contract_only": True,
            "domain_graph_materialized_now": False,
            "repo_twin_memory_materialized_now": False,
            "paper_twin_memory_materialized_now": False,
            "operator_bridge_training_authorized_now": False,
            "retrieval_eval_execution_authorized_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "arxiv_write_authorized": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attach recovered DomainGraph/RepoTwin/PaperTwin orchestration and the OP030/OP053/OP048/OP059/OP086 phase bridge to the central maintainer spine without materializing data or opening training.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "domain_graph_materialized_now",
        "repo_twin_memory_materialized_now",
        "paper_twin_memory_materialized_now",
        "operator_bridge_training_authorized_now",
        "retrieval_eval_execution_authorized_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "arxiv_write_authorized",
        "hf_upload_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"bridge": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Use this bridge as a checklist when designing future metadata-only DomainGraph/Twin manifests; do not scan /arxiv or repository_library until a separate active source ticket passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9043 Domain/Twin Operator Bridge",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This contract reconnects recovered DomainGraph, RepoTwin/PaperTwin, episodic/semantic memory, and critical operator-phase work to the 100M maintainer spine.",
        "It is contract-only: no corpus scan, no memory materialization, no retrieval eval execution, no model execution, no training, no `/arxiv` write.",
        "",
        "## Domain Graph Variables",
        "",
        *[f"- `{item}`" for item in DOMAIN_GRAPH_VARIABLES],
        "",
        "## Twin And Memory Variables",
        "",
        *[f"- `{item}`" for item in TWIN_MEMORY_VARIABLES],
        "",
        "## Critical Operator Bridge",
        "",
        *[f"- `{row['operator']}`: `{row['role']}` -> `{row['required_metric']}`" for row in OPERATOR_BRIDGE],
        "",
        "## Recovered Stage Sequence",
        "",
        *[f"- `{item}`" for item in RECOVERED_STAGE_SEQUENCE],
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
