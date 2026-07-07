#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9154
NAME = "stage9154_repo_local_inventory_single_run_ticket_instance_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9153 = ROOT / "runs/summaries/stage9153_route_card_materialization_preflight_quality_gate_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_INVENTORY_SINGLE_RUN_TICKET_INSTANCE_DESIGN_STAGE9154.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "repo_local_inventory_single_run_ticket_instance_design.json"

ALLOWED_ROOTS = [
    "runs/local/artifacts",
    "runs/summaries",
]

FORBIDDEN_ROOTS = [
    "/",
    "/data",
    "/arxiv",
    "/home",
    "/tmp",
]

TICKET_FIELDS = [
    "ticket_schema_version",
    "ticket_kind",
    "ticket_id",
    "created_by_stage",
    "approved_for_metadata_inventory_execution",
    "approved_for_route_card_materialization",
    "allowed_roots",
    "forbidden_roots",
    "search_patterns",
    "max_depth",
    "output_dir",
    "list_paths_only",
    "no_file_content_reads",
    "no_json_parse",
    "no_jsonl_row_count",
    "no_dataset_row_load",
    "no_arxiv_access",
    "no_route_card_materialization",
    "no_loss_mask_materialization",
    "no_compiler_handoff",
    "no_trainer_execution",
    "authority",
]

TICKET_INVARIANTS = [
    "ticket_kind_must_be_repo_local_metadata_inventory_single_run",
    "approved_for_metadata_inventory_execution_false_until_final_audit",
    "approved_for_route_card_materialization_false",
    "allowed_roots_must_equal_repo_local_artifact_roots",
    "forbidden_roots_must_include_arxiv_and_data_outside_repo",
    "list_paths_only_true",
    "file_content_reads_forbidden",
    "json_parse_forbidden",
    "jsonl_row_count_forbidden",
    "dataset_row_load_forbidden",
    "route_card_materialization_forbidden",
    "trainer_execution_forbidden",
    "authority_closed",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "missing_ticket_field",
    "missing_ticket_invariant",
    "allowed_root_missing",
    "arxiv_not_forbidden",
    "execution_authorized_now",
    "route_card_materialization_authorized_now",
    "list_paths_only_disabled",
    "file_content_read_allowed",
    "json_parse_allowed",
    "jsonl_row_count_allowed",
    "dataset_row_load_allowed",
    "inventory_executed_now",
    "route_cards_materialized",
    "loss_masks_materialized",
    "compiler_handoff_ready",
    "trainer_executed",
    "training_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(source_9153: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9153 = source_9153 if source_9153 is not None else load_json(SOURCE_9153)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "repo_local_metadata_inventory_single_run_ticket_instance_design_v1",
        "purpose": (
            "Design the bounded single-run ticket instance shape for a future repo-local "
            "metadata-only inventory over recovery artifacts. This does not authorize "
            "or execute the inventory."
        ),
        "ticket_fields": list(TICKET_FIELDS),
        "ticket_invariants": list(TICKET_INVARIANTS),
        "ticket_instance_template": {
            "ticket_schema_version": "repo_local_metadata_inventory_single_run_v1",
            "ticket_kind": "repo_local_metadata_inventory_single_run",
            "ticket_id": "future-ticket-id-required",
            "created_by_stage": STAGE,
            "approved_for_metadata_inventory_execution": False,
            "approved_for_route_card_materialization": False,
            "allowed_roots": list(ALLOWED_ROOTS),
            "forbidden_roots": list(FORBIDDEN_ROOTS),
            "search_patterns": "reuse scripts.metadata_only_path_inventory.SEARCH_PATTERNS",
            "max_depth": 8,
            "output_dir": f"runs/local/artifacts/{NAME}/future_inventory_output",
            "list_paths_only": True,
            "no_file_content_reads": True,
            "no_json_parse": True,
            "no_jsonl_row_count": True,
            "no_dataset_row_load": True,
            "no_arxiv_access": True,
            "no_route_card_materialization": True,
            "no_loss_mask_materialization": True,
            "no_compiler_handoff": True,
            "no_trainer_execution": True,
            "authority": dict(AUTHORITY_CLOSED),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9153_passed": source_9153.get("passed") is True,
            "ticket_instance_materialized_for_execution": False,
            "metadata_inventory_execution_authorized_now": False,
            "metadata_inventory_execution_authorized_next": False,
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Designed a future single-run repo-local metadata inventory ticket instance. "
            "Execution remains unauthorized; no inventory, route-card materialization, "
            "loss-mask materialization, compiler handoff, trainer path, runtime, or "
            "training is opened."
        ),
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    template = design.get("ticket_instance_template") or {}
    metrics = design.get("metrics") or {}
    if metrics.get("source_stage9153_passed") is not True:
        failures.append("source_stage9153_not_passed")
    for field in TICKET_FIELDS:
        if field not in design.get("ticket_fields", []):
            failures.append(f"missing_ticket_field:{field}")
        if field not in template:
            failures.append(f"missing_template_field:{field}")
    for invariant in TICKET_INVARIANTS:
        if invariant not in design.get("ticket_invariants", []):
            failures.append(f"missing_ticket_invariant:{invariant}")
    if template.get("allowed_roots") != ALLOWED_ROOTS:
        failures.append("allowed_roots_not_exact")
    for root in FORBIDDEN_ROOTS:
        if root not in template.get("forbidden_roots", []):
            failures.append(f"missing_forbidden_root:{root}")
    if template.get("approved_for_metadata_inventory_execution") is not False:
        failures.append("metadata_inventory_execution_authorized_now")
    if template.get("approved_for_route_card_materialization") is not False:
        failures.append("route_card_materialization_authorized_now")
    if template.get("list_paths_only") is not True:
        failures.append("list_paths_only_not_true")
    for key in [
        "no_file_content_reads",
        "no_json_parse",
        "no_jsonl_row_count",
        "no_dataset_row_load",
        "no_arxiv_access",
        "no_route_card_materialization",
        "no_loss_mask_materialization",
        "no_compiler_handoff",
        "no_trainer_execution",
    ]:
        if template.get(key) is not True:
            failures.append(f"{key}_not_true")
    if any((design.get("authority") or {}).values()) or any((template.get("authority") or {}).values()):
        failures.append("authority_open")
    closed_false = [
        "ticket_instance_materialized_for_execution",
        "metadata_inventory_execution_authorized_now",
        "metadata_inventory_execution_authorized_next",
        "inventory_runner_executed_now",
        "metadata_path_inventory_loaded_now",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "route_cards_materialized_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]
    for key in closed_false:
        if metrics.get(key) is not False:
            failures.append(key)
    for key in ["path_inventory_rows_loaded", "candidate_rows_loaded"]:
        if metrics.get(key) != 0:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        template = candidate["ticket_instance_template"]
        if name == "source_stage_missing":
            candidate["metrics"]["source_stage9153_passed"] = False
        elif name == "missing_ticket_field":
            candidate["ticket_fields"].remove("allowed_roots")
        elif name == "missing_ticket_invariant":
            candidate["ticket_invariants"].remove("allowed_roots_must_equal_repo_local_artifact_roots")
        elif name == "allowed_root_missing":
            template["allowed_roots"] = ["runs/summaries"]
        elif name == "arxiv_not_forbidden":
            template["forbidden_roots"].remove("/arxiv")
        elif name == "execution_authorized_now":
            template["approved_for_metadata_inventory_execution"] = True
            candidate["metrics"]["metadata_inventory_execution_authorized_now"] = True
        elif name == "route_card_materialization_authorized_now":
            template["approved_for_route_card_materialization"] = True
        elif name == "list_paths_only_disabled":
            template["list_paths_only"] = False
        elif name == "file_content_read_allowed":
            template["no_file_content_reads"] = False
        elif name == "json_parse_allowed":
            template["no_json_parse"] = False
        elif name == "jsonl_row_count_allowed":
            template["no_jsonl_row_count"] = False
        elif name == "dataset_row_load_allowed":
            template["no_dataset_row_load"] = False
        elif name == "inventory_executed_now":
            candidate["metrics"]["inventory_runner_executed_now"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_executed":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_design(candidate), "rejected": bool(validate_design(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    design = build_design()
    failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "design_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "allowed_roots_exact": design["ticket_instance_template"]["allowed_roots"] == ALLOWED_ROOTS,
        "arxiv_forbidden": "/arxiv" in design["ticket_instance_template"]["forbidden_roots"],
        "execution_not_authorized": design["ticket_instance_template"]["approved_for_metadata_inventory_execution"] is False,
        "route_materialization_not_authorized": design["ticket_instance_template"]["approved_for_route_card_materialization"] is False,
        "authority_closed": not any(design["authority"].values()),
    }
    all_failures = [key for key, value in checks.items() if value is not True]
    all_failures.extend(failures)
    passed = not all_failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": all_failures,
        "design": design,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **design["metrics"],
            "allowed_roots": len(ALLOWED_ROOTS),
            "forbidden_roots": len(FORBIDDEN_ROOTS),
            "ticket_fields": len(TICKET_FIELDS),
            "ticket_invariants": len(TICKET_INVARIANTS),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": design["decision"] if passed else "Repo-local inventory single-run ticket instance design failed validation.",
        "next_best_step": "Audit the Stage9154 ticket-instance design before any inventory execution authorization.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    DESIGN.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9154 Repo-Local Inventory Single-Run Ticket Instance Design",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Designs a future ticket instance for repo-local metadata-only inventory. It does not authorize or execute the inventory.",
        "",
        "Allowed roots:",
        "",
        *[f"- `{item}`" for item in ALLOWED_ROOTS],
        "",
        "Forbidden roots:",
        "",
        *[f"- `{item}`" for item in FORBIDDEN_ROOTS],
        "",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": public_summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": public_summary["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = public_summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": public_summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    raise SystemExit(0 if public_summary["passed"] else 1)


if __name__ == "__main__":
    main()
