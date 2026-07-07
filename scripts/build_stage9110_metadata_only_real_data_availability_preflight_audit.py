#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9109_metadata_only_real_data_availability_preflight_design import (
        FORBIDDEN_IN_THIS_STAGE,
        PROTECTED_ROOTS,
        build_plan,
        validate_plan,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9109_metadata_only_real_data_availability_preflight_design import (  # type: ignore
        FORBIDDEN_IN_THIS_STAGE,
        PROTECTED_ROOTS,
        build_plan,
        validate_plan,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9110
NAME = "stage9110_metadata_only_real_data_availability_preflight_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9109 = ROOT / "runs/summaries/stage9109_metadata_only_real_data_availability_preflight_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_REAL_DATA_AVAILABILITY_PREFLIGHT_AUDIT_STAGE9110.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_only_real_data_availability_preflight_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9108) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_plan(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in [
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
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_root = copy.deepcopy(base)
    missing_root["protected_roots"].remove("/arxiv")
    cases["missing_protected_arxiv_root"] = missing_root

    missing_forbidden = copy.deepcopy(base)
    missing_forbidden["forbidden_in_this_stage"].remove("write_to_arxiv")
    cases["missing_write_to_arxiv_forbidden"] = missing_forbidden

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    return {
        name: {
            "failures": validate_plan(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_plan(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9109)
    base = build_plan(registry())
    base_failures = validate_plan(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9109_present": SOURCE_9109.exists(),
        "source_stage9109_passed": source.get("passed") is True,
        "base_plan_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "protected_roots_recorded": set(PROTECTED_ROOTS).issubset(set(base["protected_roots"])),
        "forbidden_operations_recorded": len(FORBIDDEN_IN_THIS_STAGE) >= 12,
        "no_arxiv_access": base["metrics"]["arxiv_access_performed"] is False and base["metrics"]["arxiv_stat_performed"] is False,
        "no_row_or_source_body_reads": base["metrics"]["dataset_rows_loaded"] is False and base["metrics"]["repository_source_bodies_loaded"] is False,
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
            "forbidden_operations": len(FORBIDDEN_IN_THIS_STAGE),
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
        "decision": "Metadata-only real-data availability preflight design rejects /arxiv access/stat, row reads, parquet group reads, repository source-body reads, /arxiv writes, mining, route-card materialization, route-to-loss translation, trainer invocation, contract-only invocation, model forward, training, decoder CE, uploads, cleanup, missing protected roots, missing forbidden operations, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9109, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Metadata-only real-data availability preflight audit failed.",
        "next_best_step": "Attach metadata-only real-data availability preflight controls to the central graph; do not access /arxiv.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9110 Metadata-Only Real-Data Availability Preflight Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9109 preflight design with negative cases. No `/arxiv` access, rows, source bodies, trainer, cleanup, or training are invoked.",
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
