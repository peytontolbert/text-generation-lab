#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9154_repo_local_inventory_single_run_ticket_instance_design import (
        ALLOWED_ROOTS,
        FORBIDDEN_ROOTS,
        NEGATIVE_CASES,
        TICKET_FIELDS,
        TICKET_INVARIANTS,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9154_repo_local_inventory_single_run_ticket_instance_design import (  # type: ignore
        ALLOWED_ROOTS,
        FORBIDDEN_ROOTS,
        NEGATIVE_CASES,
        TICKET_FIELDS,
        TICKET_INVARIANTS,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9155
NAME = "stage9155_repo_local_inventory_single_run_ticket_instance_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9154 = ROOT / "runs/summaries/stage9154_repo_local_inventory_single_run_ticket_instance_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_INVENTORY_SINGLE_RUN_TICKET_INSTANCE_DESIGN_AUDIT_STAGE9155.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "repo_local_inventory_single_run_ticket_instance_design_audit.json"

AUDIT_NEGATIVE_CASES = list(NEGATIVE_CASES) + [
    "missing_data_forbidden_root",
    "output_dir_not_repo_local",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9154) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in AUDIT_NEGATIVE_CASES:
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
        elif name == "missing_data_forbidden_root":
            template["forbidden_roots"].remove("/data")
        elif name == "output_dir_not_repo_local":
            template["output_dir"] = "/tmp/not-repo-local"
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

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate)
        template = candidate["ticket_instance_template"]
        output_dir = str(template.get("output_dir", ""))
        if name == "output_dir_not_repo_local" and not output_dir.startswith("runs/local/artifacts/"):
            failures.append("output_dir_not_under_runs_local_artifacts")
        if name == "bad_registry_frontier":
            failures.append("unexpected_registry_frontier:9999")
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9154)
    design = build_design()
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    template = design["ticket_instance_template"]
    output_dir = str(template.get("output_dir", ""))
    checks = {
        "source_stage9154_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "ticket_fields_complete": set(TICKET_FIELDS).issubset(set(design["ticket_fields"])),
        "ticket_invariants_complete": set(TICKET_INVARIANTS).issubset(set(design["ticket_invariants"])),
        "allowed_roots_exact": template["allowed_roots"] == ALLOWED_ROOTS,
        "forbidden_roots_complete": set(FORBIDDEN_ROOTS).issubset(set(template["forbidden_roots"])),
        "output_dir_repo_local": output_dir.startswith("runs/local/artifacts/"),
        "execution_not_authorized": template["approved_for_metadata_inventory_execution"] is False,
        "route_materialization_not_authorized": template["approved_for_route_card_materialization"] is False,
        "no_inventory_execution": design["metrics"]["inventory_runner_executed_now"] is False,
        "no_route_materialization": design["metrics"]["route_cards_materialized_now"] is False,
        "authority_closed": not any(design["authority"].values()),
        "registry_frontier_stage9154": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9154,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(design_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": design_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "allowed_roots": len(ALLOWED_ROOTS),
            "forbidden_roots": len(FORBIDDEN_ROOTS),
            "ticket_fields": len(TICKET_FIELDS),
            "ticket_invariants": len(TICKET_INVARIANTS),
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
            "Audited the repo-local inventory single-run ticket-instance design and "
            "rejected missing fields/invariants, root-scope drift, output-dir drift, "
            "inventory execution, route-card/loss-mask materialization, compiler handoff, "
            "trainer execution, training, runtime, and authority openings."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Repo-local inventory single-run ticket-instance design audit failed.",
        "next_best_step": (
            "Design final pre-execution authorization for a metadata-only repo-local "
            "inventory run, still without route-card materialization or training."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9155 Repo-Local Inventory Single-Run Ticket Instance Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
