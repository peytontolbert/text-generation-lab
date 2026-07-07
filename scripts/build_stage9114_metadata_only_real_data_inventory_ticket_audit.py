#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9113_metadata_only_real_data_inventory_ticket_design import (
        FORBIDDEN_FUTURE_OPERATIONS,
        PROTECTED_ROOTS,
        REQUIRED_OUTPUTS,
        build_ticket,
        validate_ticket,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9113_metadata_only_real_data_inventory_ticket_design import (  # type: ignore
        FORBIDDEN_FUTURE_OPERATIONS,
        PROTECTED_ROOTS,
        REQUIRED_OUTPUTS,
        build_ticket,
        validate_ticket,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9114
NAME = "stage9114_metadata_only_real_data_inventory_ticket_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9113 = ROOT / "runs/summaries/stage9113_metadata_only_real_data_inventory_ticket_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_REAL_DATA_INVENTORY_TICKET_AUDIT_STAGE9114.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_only_real_data_inventory_ticket_audit.json"

REJECT_METRICS = [
    "arxiv_access_performed",
    "arxiv_stat_performed",
    "dataset_file_names_read_now",
    "repository_root_names_read_now",
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
    "network_upload_performed",
    "cleanup_authorized_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9112) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_ticket(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in REJECT_METRICS:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_root = copy.deepcopy(base)
    missing_root["protected_roots"].remove("/arxiv")
    cases["missing_protected_arxiv_root"] = missing_root

    missing_forbidden = copy.deepcopy(base)
    missing_forbidden["forbidden_future_operations"].remove("read_repository_source_bodies")
    cases["missing_repository_source_body_forbidden"] = missing_forbidden

    missing_output = copy.deepcopy(base)
    missing_output["required_outputs"].remove("protected_path_policy_card.json")
    cases["missing_protected_path_policy_output"] = missing_output

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_ticket(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9113)
    base = build_ticket(registry())
    base_failures = validate_ticket(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9113_present": SOURCE_9113.exists(),
        "source_stage9113_passed": source.get("passed") is True,
        "base_ticket_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "protected_roots_recorded": set(PROTECTED_ROOTS).issubset(set(base["protected_roots"])),
        "forbidden_future_operations_recorded": len(FORBIDDEN_FUTURE_OPERATIONS) >= 16,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 8,
        "no_arxiv_access_now": base["metrics"]["arxiv_access_performed"] is False and base["metrics"]["arxiv_stat_performed"] is False,
        "no_row_or_source_body_reads_now": base["metrics"]["dataset_rows_loaded"] is False and base["metrics"]["repository_source_bodies_loaded"] is False,
        "authority_closed": not any(base["authority"].values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "protected_roots": len(PROTECTED_ROOTS),
            "forbidden_future_operations": len(FORBIDDEN_FUTURE_OPERATIONS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_file_names_read_now": False,
            "repository_root_names_read_now": False,
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
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Metadata-only real-data inventory ticket rejects unsafe variants before any inventory: current /arxiv access/stat, file-name reads, row reads, parquet group reads, source-body reads, /arxiv writes, mining, route-card materialization, route-to-loss translation, trainer/model paths, training losses, uploads, cleanup, missing guard rails, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9113, STAGE}:
        audit["failures"].append(f"unexpected_registry_frontier:{latest}")
        audit["passed"] = False
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Metadata-only real-data inventory ticket audit failed.",
        "next_best_step": "Design the metadata-only inventory runner contract; it may list names/metadata only after a separate audit passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9114 Metadata-Only Real Data Inventory Ticket Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9113 ticket with negative cases. No `/arxiv` access, file-name reads, row reads, source-body reads, trainer paths, uploads, cleanup, or training are performed.",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {**(registry_json.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
