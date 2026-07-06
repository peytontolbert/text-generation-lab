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
STAGE = 8993
NAME = "stage8993_post_footer_schema_compatibility_judge_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POST_FOOTER_SCHEMA_COMPATIBILITY_JUDGE_CONTRACT_STAGE8993.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "post_footer_schema_compatibility_judge_contract.json"

SOURCE_SUMMARIES = {
    8985: ROOT / "runs/summaries/stage8985_active_parquet_footer_ticket_instance_audit.json",
    8990: ROOT / "runs/summaries/stage8990_training_return_path_after_footer_gate_contract.json",
}

REQUIRED_INPUT_ARTIFACTS = [
    "parquet_footer_schema_metadata_only.jsonl",
    "footer_access_audit_card.json",
    "selected_candidate_ids.jsonl",
]

SCHEMA_JUDGE_OUTPUT_FIELDS = [
    "candidate_id",
    "relative_path",
    "schema_columns",
    "schema_types",
    "maintainer_relevance_score",
    "required_field_coverage",
    "row_body_required_for_decision",
    "compatible_with_curriculum_compiler",
    "recommended_route",
    "rejection_reasons",
]

COMPATIBILITY_CRITERIA = [
    "has_text_or_trace_like_fields",
    "has_task_or_prompt_like_fields",
    "has_output_or_action_like_fields",
    "has_metadata_ids_for_lineage",
    "no_row_body_needed_for_initial_schema_decision",
    "no_locked_eval_or_hidden_split_markers_in_train_route",
    "can_emit_loss_mask_candidates_only_after_row_judge",
]

RECOMMENDED_ROUTES = [
    "SCHEMA_COMPATIBLE_CANDIDATE_PENDING_ROW_SAMPLE_TICKET",
    "SCHEMA_INSUFFICIENT_NEEDS_DIFFERENT_DATASET",
    "SCHEMA_AMBIGUOUS_NEEDS_HUMAN_REVIEW",
]

FORBIDDEN_JUDGE_ACTIONS = [
    "read_dataset_rows",
    "read_jsonl_first_line",
    "read_repository_source_body",
    "write_to_arxiv",
    "start_mining",
    "start_training",
    "claim_dataset_quality_from_schema_only",
    "emit_training_manifest",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    sources = {stage: load_json(path) for stage, path in SOURCE_SUMMARIES.items()}
    source_passed = {stage: data.get("passed") is True for stage, data in sources.items()}
    checks = {
        "source_summaries_present": all(path.exists() for path in SOURCE_SUMMARIES.values()),
        "source_summaries_passed": all(source_passed.values()),
        "stage8985_ticket_audit_passed": (sources[8985].get("metrics") or {}).get("ticket_audit_passed") is True,
        "stage8990_return_path_records_schema_judge": any(gate.get("gate_id") == "schema_compatibility_judge" for gate in (load_json(ROOT / "runs/local/artifacts/stage8990_training_return_path_after_footer_gate_contract/training_return_path_after_footer_gate_contract.json").get("return_path_gates") or [])),
        "required_input_artifacts_recorded": len(REQUIRED_INPUT_ARTIFACTS) >= 3,
        "schema_judge_output_fields_recorded": len(SCHEMA_JUDGE_OUTPUT_FIELDS) >= 10,
        "compatibility_criteria_recorded": len(COMPATIBILITY_CRITERIA) >= 7,
        "recommended_routes_recorded": len(RECOMMENDED_ROUTES) >= 3,
        "forbidden_actions_recorded": len(FORBIDDEN_JUDGE_ACTIONS) >= 8,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "POST_FOOTER_SCHEMA_COMPATIBILITY_JUDGE_CONTRACT_NO_EXECUTION",
        "source_stage_status": source_passed,
        "required_input_artifacts": REQUIRED_INPUT_ARTIFACTS,
        "schema_judge_output_fields": SCHEMA_JUDGE_OUTPUT_FIELDS,
        "compatibility_criteria": COMPATIBILITY_CRITERIA,
        "recommended_routes": RECOMMENDED_ROUTES,
        "forbidden_judge_actions": FORBIDDEN_JUDGE_ACTIONS,
        "checks": checks,
        "metrics": {
            "required_input_artifacts": len(REQUIRED_INPUT_ARTIFACTS),
            "schema_judge_output_fields": len(SCHEMA_JUDGE_OUTPUT_FIELDS),
            "compatibility_criteria": len(COMPATIBILITY_CRITERIA),
            "recommended_routes": len(RECOMMENDED_ROUTES),
            "forbidden_judge_actions": len(FORBIDDEN_JUDGE_ACTIONS),
            "schema_judge_executed_now": False,
            "footer_access_authorized_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Post-footer schema compatibility judging is specified as a future contract only. It consumes footer metadata artifacts after they exist, but this stage does not execute footer access, judge schemas, load rows, mine data, or train.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "schema_judge_executed_now",
        "footer_access_authorized_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "After footer metadata execution exists, build the schema compatibility judge runner against metadata artifacts only. Do not sample rows yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8993 Post-Footer Schema Compatibility Judge Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future schema compatibility judge that will consume parquet-footer metadata artifacts after they exist. It does not read footers, rows, source bodies, mine data, train, or execute models.",
        "",
        f"Output fields: `{summary['metrics']['schema_judge_output_fields']}`",
        f"Compatibility criteria: `{summary['metrics']['compatibility_criteria']}`",
        "",
    ]), encoding="utf-8")
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
    marker = "## Stage8993 Post-Footer Schema Compatibility Judge Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8993 specifies the post-footer schema compatibility judge contract. It waits for footer metadata artifacts and keeps row reads, source-body reads, mining, training, model execution, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
