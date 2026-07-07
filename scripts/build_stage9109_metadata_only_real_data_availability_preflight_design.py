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
STAGE = 9109
NAME = "stage9109_metadata_only_real_data_availability_preflight_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9108 = ROOT / "runs/summaries/stage9108_central_graph_gap_walk_remaining_trainer_blockers.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_REAL_DATA_AVAILABILITY_PREFLIGHT_DESIGN_STAGE9109.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PLAN = OUT_DIR / "metadata_only_real_data_availability_preflight_design.json"

PROTECTED_ROOTS = [
    "/arxiv",
    "/arxiv/datasets",
    "/arxiv/repositories",
]

FUTURE_METADATA_ONLY_STEPS = [
    "verify_arxiv_roots_exist_without_writing",
    "inventory_dataset_files_by_name_size_extension_mtime_only",
    "inventory_repository_roots_by_name_size_mtime_only",
    "count_candidate_dataset_files_without_opening_rows",
    "count_repository_root_entries_without_reading_source_bodies",
    "record_expected_dataset_families_without_sampling_rows",
    "record_expected_repository_library_roots_without_source_body_reads",
    "write_outputs_only_under_runs_local_artifacts",
    "require_source_output_ticket_before_body_reads",
    "require_route_card_materialization_ticket_before_compiler_handoff",
]

FORBIDDEN_IN_THIS_STAGE = [
    "stat_arxiv_paths_now",
    "read_dataset_rows",
    "read_dataset_parquet_groups",
    "read_repository_source_body",
    "write_to_arxiv",
    "delete_or_cleanup_arxiv",
    "start_mining",
    "materialize_route_cards",
    "translate_route_to_loss",
    "invoke_trainer_contract_only",
    "execute_training",
    "network_upload",
]

REQUIRED_FUTURE_OUTPUTS = [
    "arxiv_root_metadata_card.json",
    "dataset_file_inventory_metadata_only.jsonl",
    "repository_root_inventory_metadata_only.jsonl",
    "protected_path_policy_card.json",
    "source_output_ticket_requirement_card.json",
    "real_data_availability_preflight_decision_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_plan(registry: dict[str, Any]) -> dict[str, Any]:
    s9108 = load_json(SOURCE_9108)
    checks = {
        "source_stage9108_passed": s9108.get("passed") is True,
        "protected_roots_declared": len(PROTECTED_ROOTS) == 3 and "/arxiv" in PROTECTED_ROOTS,
        "future_metadata_steps_declared": len(FUTURE_METADATA_ONLY_STEPS) >= 10,
        "forbidden_operations_declared": len(FORBIDDEN_IN_THIS_STAGE) >= 12,
        "future_outputs_declared": len(REQUIRED_FUTURE_OUTPUTS) >= 6,
        "no_arxiv_access_performed": True,
        "no_training_or_mining_authorized": True,
        "registry_frontier_stage9108": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9108,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_REAL_DATA_AVAILABILITY_PREFLIGHT_DESIGN_NO_ARXIV_ACCESS",
        "protected_roots": PROTECTED_ROOTS,
        "future_metadata_only_steps": FUTURE_METADATA_ONLY_STEPS,
        "forbidden_in_this_stage": FORBIDDEN_IN_THIS_STAGE,
        "required_future_outputs": REQUIRED_FUTURE_OUTPUTS,
        "checks": checks,
        "metrics": {
            "protected_roots": len(PROTECTED_ROOTS),
            "future_metadata_steps": len(FUTURE_METADATA_ONLY_STEPS),
            "forbidden_operations": len(FORBIDDEN_IN_THIS_STAGE),
            "required_future_outputs": len(REQUIRED_FUTURE_OUTPUTS),
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Metadata-only real-data availability preflight is designed but not executed. This stage does not stat /arxiv, read dataset rows, read repository source bodies, mine data, materialize route cards, invoke trainer contract-only mode, train, clean, or upload anything.",
    }


def validate_plan(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9108, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in PROTECTED_ROOTS:
        if required not in card.get("protected_roots", []):
            failures.append(f"missing_protected_root:{required}")
    for forbidden in ["read_dataset_rows", "read_repository_source_body", "write_to_arxiv", "delete_or_cleanup_arxiv", "execute_training"]:
        if forbidden not in card.get("forbidden_in_this_stage", []):
            failures.append(f"missing_forbidden_operation:{forbidden}")
    for key in [
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_plan(registry)
    failures = validate_plan(card, registry)
    PLAN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"preflight_plan": str(PLAN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Metadata-only real-data availability preflight design failed.",
        "next_best_step": "Audit metadata-only real-data availability preflight design negative cases without /arxiv access.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9109 Metadata-Only Real-Data Availability Preflight Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a design stage only. It does not stat `/arxiv`, read rows, read repository source bodies, write to `/arxiv`, mine, train, clean, or upload.",
        "",
        "Future metadata-only steps:",
        "",
        *[f"- `{step}`" for step in FUTURE_METADATA_ONLY_STEPS],
        "",
        "Forbidden in this stage:",
        "",
        *[f"- `{item}`" for item in FORBIDDEN_IN_THIS_STAGE],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9109 Metadata-Only Real-Data Availability Preflight Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9109 designs a future metadata-only availability preflight for /arxiv/datasets and /arxiv/repositories without performing /arxiv access. It preserves /arxiv as backup storage and keeps data rows, repository source bodies, route cards, route-to-loss translation, trainer invocation, cleanup, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
