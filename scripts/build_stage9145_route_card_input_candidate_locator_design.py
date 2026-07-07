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
STAGE = 9145
NAME = "stage9145_route_card_input_candidate_locator_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9144 = ROOT / "runs/summaries/stage9144_real_route_card_input_ticket_instance_blocker_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_INPUT_CANDIDATE_LOCATOR_DESIGN_STAGE9145.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "route_card_input_candidate_locator_design.json"

ALLOWED_SEARCH_ROOTS = [
    "runs/local/artifacts",
    "runs/summaries",
]

REQUIRED_CANDIDATE_TYPES = [
    "objective_rows_jsonl",
    "judge_rows_jsonl",
    "junk_ranker_rows_jsonl",
    "shortcut_baseline_card_json",
    "counterfactual_obligation_card_json",
    "source_lineage_card_json",
]

FORBIDDEN_SEARCH_ROOTS = [
    "/",
    "/data",
    "/arxiv",
    "/home",
    "/tmp",
]

LOCATOR_RULES = [
    "metadata_only_path_listing",
    "repo_local_roots_only",
    "no_file_content_reads",
    "no_dataset_row_reads",
    "no_source_body_reads",
    "no_decoder_target_reads",
    "no_arxiv_reads",
    "no_route_card_materialization",
    "no_loss_mask_materialization",
    "no_trainer_or_model_execution",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9144)
    checks = {
        "source_stage9144_passed": source.get("passed") is True,
        "allowed_search_roots_recorded": len(ALLOWED_SEARCH_ROOTS) >= 2,
        "required_candidate_types_recorded": len(REQUIRED_CANDIDATE_TYPES) >= 6,
        "forbidden_search_roots_recorded": len(FORBIDDEN_SEARCH_ROOTS) >= 5,
        "locator_rules_recorded": len(LOCATOR_RULES) >= 10,
        "registry_frontier_stage9144": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9144,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROUTE_CARD_INPUT_CANDIDATE_LOCATOR_DESIGN_NO_SCAN_NO_READ",
        "allowed_search_roots": list(ALLOWED_SEARCH_ROOTS),
        "required_candidate_types": list(REQUIRED_CANDIDATE_TYPES),
        "forbidden_search_roots": list(FORBIDDEN_SEARCH_ROOTS),
        "locator_rules": list(LOCATOR_RULES),
        "checks": checks,
        "metrics": {
            "allowed_search_roots": len(ALLOWED_SEARCH_ROOTS),
            "required_candidate_types": len(REQUIRED_CANDIDATE_TYPES),
            "forbidden_search_roots": len(FORBIDDEN_SEARCH_ROOTS),
            "locator_rules": len(LOCATOR_RULES),
            "candidate_locator_designed": True,
            "candidate_locator_executed": False,
            "path_inventory_materialized": False,
            "file_content_read": False,
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
        "decision": "Designed a metadata-only candidate locator for future route-card input paths. No scan, file content read, dataset row load, /arxiv access, ticket instance, route-card materialization, loss-mask materialization, compiler handoff, training, runtime, cleanup, or model execution was opened.",
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in design["checks"].items() if value is not True]
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9144, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for root in ALLOWED_SEARCH_ROOTS:
        if root not in design.get("allowed_search_roots", []):
            failures.append(f"missing_allowed_search_root:{root}")
    for root in FORBIDDEN_SEARCH_ROOTS:
        if root not in design.get("forbidden_search_roots", []):
            failures.append(f"missing_forbidden_search_root:{root}")
    for candidate_type in REQUIRED_CANDIDATE_TYPES:
        if candidate_type not in design.get("required_candidate_types", []):
            failures.append(f"missing_candidate_type:{candidate_type}")
    for rule in LOCATOR_RULES:
        if rule not in design.get("locator_rules", []):
            failures.append(f"missing_locator_rule:{rule}")
    for key in [
        "candidate_locator_executed",
        "path_inventory_materialized",
        "file_content_read",
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
        "decision": design["decision"] if not failures else "Route-card input candidate locator design failed.",
        "next_best_step": "Audit candidate locator design before implementing a metadata-only repo-local path inventory.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9145 Route-Card Input Candidate Locator Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designed a metadata-only locator for future route-card input path candidates. It does not scan or read files.",
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
