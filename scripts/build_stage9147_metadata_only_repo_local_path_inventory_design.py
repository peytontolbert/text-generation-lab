#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9145_route_card_input_candidate_locator_design import (
        ALLOWED_SEARCH_ROOTS,
        FORBIDDEN_SEARCH_ROOTS,
        REQUIRED_CANDIDATE_TYPES,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9145_route_card_input_candidate_locator_design import (  # type: ignore
        ALLOWED_SEARCH_ROOTS,
        FORBIDDEN_SEARCH_ROOTS,
        REQUIRED_CANDIDATE_TYPES,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9147
NAME = "stage9147_metadata_only_repo_local_path_inventory_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9146 = ROOT / "runs/summaries/stage9146_route_card_input_candidate_locator_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_REPO_LOCAL_PATH_INVENTORY_DESIGN_STAGE9147.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "metadata_only_repo_local_path_inventory_design.json"

INVENTORY_OUTPUT_FIELDS = [
    "candidate_type",
    "path",
    "relative_path",
    "extension",
    "stage_hint",
    "path_allowed",
    "content_read",
    "row_count_read",
]

SEARCH_PATTERNS = {
    "objective_rows_jsonl": ["*objective*.jsonl", "*rows*.jsonl", "*manifest*.jsonl"],
    "judge_rows_jsonl": ["*judge*.jsonl", "*judged*.jsonl"],
    "junk_ranker_rows_jsonl": ["*ranker*.jsonl", "*ranked*.jsonl", "*junk*.jsonl"],
    "shortcut_baseline_card_json": ["*shortcut*baseline*.json", "*shortcut*.json"],
    "counterfactual_obligation_card_json": ["*counterfactual*obligation*.json", "*counterfactual*.json"],
    "source_lineage_card_json": ["*source*lineage*.json", "*lineage*.json"],
}

INVENTORY_RULES = [
    "list_paths_only",
    "do_not_open_candidate_files",
    "do_not_count_jsonl_rows",
    "do_not_parse_json",
    "exclude_forbidden_roots",
    "repo_local_relative_paths_only",
    "write_inventory_under_runs_local_artifacts",
    "no_ticket_instance_creation",
    "no_route_card_materialization",
    "no_training_or_runtime",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9146)
    checks = {
        "source_stage9146_passed": source.get("passed") is True,
        "allowed_roots_reused": set(ALLOWED_SEARCH_ROOTS) == {"runs/local/artifacts", "runs/summaries"},
        "forbidden_roots_reused": "/arxiv" in FORBIDDEN_SEARCH_ROOTS and "/data" in FORBIDDEN_SEARCH_ROOTS,
        "candidate_types_reused": set(REQUIRED_CANDIDATE_TYPES).issubset(set(SEARCH_PATTERNS)),
        "inventory_output_fields_recorded": len(INVENTORY_OUTPUT_FIELDS) >= 8,
        "inventory_rules_recorded": len(INVENTORY_RULES) >= 10,
        "registry_frontier_stage9146": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9146,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_REPO_LOCAL_PATH_INVENTORY_DESIGN_NO_EXECUTION",
        "allowed_search_roots": list(ALLOWED_SEARCH_ROOTS),
        "forbidden_search_roots": list(FORBIDDEN_SEARCH_ROOTS),
        "required_candidate_types": list(REQUIRED_CANDIDATE_TYPES),
        "search_patterns": dict(SEARCH_PATTERNS),
        "inventory_output_fields": list(INVENTORY_OUTPUT_FIELDS),
        "inventory_rules": list(INVENTORY_RULES),
        "checks": checks,
        "metrics": {
            "inventory_output_fields": len(INVENTORY_OUTPUT_FIELDS),
            "inventory_rules": len(INVENTORY_RULES),
            "candidate_types": len(REQUIRED_CANDIDATE_TYPES),
            "path_inventory_design_created": True,
            "path_inventory_executed": False,
            "path_inventory_materialized": False,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "ticket_instance_materialized": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed a metadata-only repo-local path inventory. This stage does not execute the inventory, read file contents, parse JSON, count JSONL rows, access /arxiv, create a ticket instance, materialize route cards, or open training/runtime.",
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in design["checks"].items() if value is not True]
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9146, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in INVENTORY_OUTPUT_FIELDS:
        if field not in design.get("inventory_output_fields", []):
            failures.append(f"missing_inventory_output_field:{field}")
    for rule in INVENTORY_RULES:
        if rule not in design.get("inventory_rules", []):
            failures.append(f"missing_inventory_rule:{rule}")
    for candidate_type in REQUIRED_CANDIDATE_TYPES:
        if candidate_type not in design.get("search_patterns", {}):
            failures.append(f"missing_search_pattern:{candidate_type}")
    for key in [
        "path_inventory_executed",
        "path_inventory_materialized",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "ticket_instance_materialized",
        "real_input_authorized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if design["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if design["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry)
    failures = validate_design(design, registry)
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **design["metrics"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": design["decision"] if not failures else "Metadata-only repo-local path inventory design failed.",
        "next_best_step": "Audit metadata-only repo-local path inventory design before implementing the inventory runner.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9147 Metadata-Only Repo-Local Path Inventory Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designed a path-listing inventory only. It does not execute or read candidate file contents.",
        "",
        f"Next: {summary['next_best_step']}",
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
