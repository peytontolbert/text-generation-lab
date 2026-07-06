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
STAGE = 8976
NAME = "stage8976_zero_row_schema_preflight_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_SCHEMA_PREFLIGHT_DESIGN_STAGE8976.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "zero_row_schema_preflight_design.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8975_metadata_route_selector_audit.json"
DATASET_ROUTE_CARD = ROOT / "runs/local/artifacts/stage8974_metadata_inventory_route_selector/dataset_route_card_metadata_only.json"

ALLOWED_ZERO_ROW_OPERATIONS = [
    "read_stage8974_metadata_route_card",
    "select_candidate_paths_from_metadata_only",
    "for_parquet_read_footer_schema_only_if_future_ticket_explicitly_authorizes",
    "for_jsonl_read_zero_bytes_or_compression_container_metadata_only",
    "for_json_metadata_read_top_level_keys_only_if_file_is_declared_metadata_not_dataset_rows",
    "write_schema_preflight_outputs_under_runs_local_artifacts_only",
]

FORBIDDEN_ZERO_ROW_OPERATIONS = [
    "read_any_dataset_record",
    "read_jsonl_first_line",
    "read_csv_header_without_explicit_ticket",
    "read_repository_source_body",
    "write_to_arxiv",
    "delete_or_cleanup_arxiv",
    "start_mining",
    "start_training",
    "load_checkpoint",
    "runtime_execution",
    "network_upload",
]

CANDIDATE_LIMITS = {
    "named_software_maintainer_dataset_candidates": 20,
    "parquet_candidates": 20,
    "jsonl_candidates": 0,
    "json_metadata_candidates": 0,
}

REQUIRED_FUTURE_OUTPUTS = [
    "selected_schema_candidate_paths.jsonl",
    "zero_row_schema_policy_card.json",
    "schema_extraction_result_metadata_only.jsonl",
    "schema_preflight_decision_card.json",
]

FUTURE_PASS_GATES = [
    "selected_paths_from_stage8974_metadata_only",
    "dataset_records_read_equals_0",
    "repository_source_bodies_read_equals_0",
    "arxiv_writes_equals_0",
    "schema_outputs_under_runs_local_artifacts",
    "training_and_mining_authority_closed",
    "explicit_ticket_required_for_any_parquet_footer_access",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def available_route_counts(route_card: dict[str, Any]) -> dict[str, int]:
    counts = route_card.get("route_counts") or {}
    return {
        "named_software_maintainer_dataset_candidates": int(counts.get("NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE", 0)),
        "parquet_candidates": int(counts.get("PARQUET_TABLE_CANDIDATE", 0)),
        "jsonl_candidates": int(counts.get("JSONL_MANIFEST_CANDIDATE", 0)),
        "json_metadata_candidates": int(counts.get("JSON_METADATA_CANDIDATE", 0)),
    }


def planned_selection_counts(route_counts: dict[str, int]) -> dict[str, int]:
    return {key: min(route_counts.get(key, 0), limit) for key, limit in CANDIDATE_LIMITS.items()}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    route_card = load_json(DATASET_ROUTE_CARD)
    route_counts = available_route_counts(route_card)
    planned_counts = planned_selection_counts(route_counts)
    checks = {
        "source_stage8975_passed": source.get("passed") is True,
        "dataset_route_card_present": DATASET_ROUTE_CARD.exists(),
        "route_counts_available": any(route_counts.values()),
        "allowed_operations_declared": len(ALLOWED_ZERO_ROW_OPERATIONS) >= 6,
        "forbidden_operations_declared": len(FORBIDDEN_ZERO_ROW_OPERATIONS) >= 10,
        "candidate_limits_declared": bool(CANDIDATE_LIMITS),
        "future_outputs_declared": len(REQUIRED_FUTURE_OUTPUTS) >= 4,
        "future_pass_gates_declared": len(FUTURE_PASS_GATES) >= 7,
        "jsonl_candidates_planned_zero": CANDIDATE_LIMITS["jsonl_candidates"] == 0,
        "no_schema_or_header_read_performed": True,
        "no_dataset_rows_loaded": True,
        "no_repository_source_bodies_loaded": True,
        "training_and_mining_closed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8975_or_8976": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8975, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_SCHEMA_PREFLIGHT_DESIGN",
        "allowed_zero_row_operations": ALLOWED_ZERO_ROW_OPERATIONS,
        "forbidden_zero_row_operations": FORBIDDEN_ZERO_ROW_OPERATIONS,
        "candidate_limits": CANDIDATE_LIMITS,
        "available_route_counts": route_counts,
        "planned_selection_counts": planned_counts,
        "required_future_outputs": REQUIRED_FUTURE_OUTPUTS,
        "future_pass_gates": FUTURE_PASS_GATES,
        "checks": checks,
        "metrics": {
            "available_named_candidates": route_counts["named_software_maintainer_dataset_candidates"],
            "available_parquet_candidates": route_counts["parquet_candidates"],
            "available_jsonl_candidates": route_counts["jsonl_candidates"],
            "planned_named_candidates": planned_counts["named_software_maintainer_dataset_candidates"],
            "planned_parquet_candidates": planned_counts["parquet_candidates"],
            "planned_jsonl_candidates": planned_counts["jsonl_candidates"],
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
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Zero-row schema/header preflight is designed but not executed. Future schema work must select candidates from metadata only and must not read dataset records or repository source bodies.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8975, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "schema_or_header_read_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card, registry)
    DESIGN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"design": str(DESIGN.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Implement a zero-row candidate selector that emits selected path metadata only. Do not read schemas, headers, rows, or repository source bodies until a separate preflight execution ticket exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8976 Zero-Row Schema Preflight Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the future zero-row schema/header preflight only. It does not open candidate dataset files, read schemas, read headers, parse rows, read repository source bodies, mine, train, or touch `/arxiv`.",
        "",
        f"Available named candidates: `{summary['metrics']['available_named_candidates']}`",
        f"Available parquet candidates: `{summary['metrics']['available_parquet_candidates']}`",
        f"Available JSONL candidates: `{summary['metrics']['available_jsonl_candidates']}`",
        f"Planned JSONL candidates for zero-row preflight: `{summary['metrics']['planned_jsonl_candidates']}`",
        "",
        "## Future Pass Gates",
        "",
        *[f"- `{gate}`" for gate in FUTURE_PASS_GATES],
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8976 Zero-Row Schema Preflight Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8976 designs a future zero-row schema/header preflight. It performs no schema/header reads itself and keeps row/source-body reads, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
