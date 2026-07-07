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
STAGE = 9138
NAME = "stage9138_real_route_card_input_authorization_gate_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9137 = ROOT / "runs/summaries/stage9137_synthetic_route_card_materializer_smoke_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_AUTHORIZATION_GATE_DESIGN_STAGE9138.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "real_route_card_input_authorization_gate_design.json"

REQUIRED_TICKET_FIELDS = [
    "objective_rows_path",
    "judge_rows_path",
    "junk_ranker_rows_path",
    "shortcut_baseline_card_path",
    "counterfactual_obligation_card_path",
    "source_lineage_card_path",
    "max_rows",
    "allowed_input_root",
    "output_dir",
    "dry_run_only",
    "no_source_bodies",
    "no_decoder_targets",
    "no_trainer_execution",
    "path_validation_required",
    "schema_validation_required",
    "authority",
]

REQUIRED_PREFLIGHT_CHECKS = [
    "all_paths_under_repo_local_artifacts_or_explicit_workspace",
    "no_arxiv_path_without_separate_authorization",
    "input_files_exist",
    "jsonl_rows_have_row_id",
    "judge_ranker_objective_row_ids_join",
    "source_lineage_rows_join",
    "shortcut_card_passed_or_blocks",
    "counterfactual_card_passed_or_blocks",
    "no_source_body_fields_present",
    "no_decoder_target_text_fields_present",
    "authority_closed",
    "row_cap_enforced",
    "outputs_repo_local",
]

FORBIDDEN_INPUT_FIELDS = [
    "source_body",
    "body",
    "raw_source",
    "source_text",
    "decoder_text",
    "decoder_target",
    "target_text",
    "hidden_reference",
    "locked_eval_text",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9137)
    checks = {
        "source_stage9137_passed": source.get("passed") is True,
        "required_ticket_fields_recorded": len(REQUIRED_TICKET_FIELDS) >= 16,
        "required_preflight_checks_recorded": len(REQUIRED_PREFLIGHT_CHECKS) >= 13,
        "forbidden_input_fields_recorded": len(FORBIDDEN_INPUT_FIELDS) >= 9,
        "registry_frontier_stage9137": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9137,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REAL_ROUTE_CARD_INPUT_AUTHORIZATION_GATE_DESIGN_NO_INPUT_LOADING",
        "required_ticket_fields": list(REQUIRED_TICKET_FIELDS),
        "required_preflight_checks": list(REQUIRED_PREFLIGHT_CHECKS),
        "forbidden_input_fields": list(FORBIDDEN_INPUT_FIELDS),
        "checks": checks,
        "metrics": {
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_preflight_checks": len(REQUIRED_PREFLIGHT_CHECKS),
            "forbidden_input_fields": len(FORBIDDEN_INPUT_FIELDS),
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
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
        "decision": "Designed the authorization gate required before real judge/ranker route-card inputs may be read. This stage does not authorize or load real inputs.",
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in design["checks"].items() if value is not True]
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9137, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for field in REQUIRED_TICKET_FIELDS:
        if field not in design.get("required_ticket_fields", []):
            failures.append(f"missing_ticket_field:{field}")
    for check in REQUIRED_PREFLIGHT_CHECKS:
        if check not in design.get("required_preflight_checks", []):
            failures.append(f"missing_preflight_check:{check}")
    for field in FORBIDDEN_INPUT_FIELDS:
        if field not in design.get("forbidden_input_fields", []):
            failures.append(f"missing_forbidden_input_field:{field}")
    for key in [
        "real_input_authorized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "dataset_rows_loaded",
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
        "decision": design["decision"] if not failures else "Real route-card input authorization gate design failed.",
        "next_best_step": "Audit real route-card input authorization gate design before creating a real input ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9138 Real Route-Card Input Authorization Gate Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a design-only gate before any real judge/ranker route-card inputs may be read.",
        "",
        "Key preflight checks:",
        "",
        *[f"- `{item}`" for item in REQUIRED_PREFLIGHT_CHECKS],
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
