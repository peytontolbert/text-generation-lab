#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9115_metadata_only_inventory_runner_contract_design import (
        FORBIDDEN_RUNTIME_ACTIONS,
        REQUIRED_CLI_FLAGS,
        REQUIRED_RUNTIME_ASSERTIONS,
        build_contract,
        validate_contract,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9115_metadata_only_inventory_runner_contract_design import (  # type: ignore
        FORBIDDEN_RUNTIME_ACTIONS,
        REQUIRED_CLI_FLAGS,
        REQUIRED_RUNTIME_ASSERTIONS,
        build_contract,
        validate_contract,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9116
NAME = "stage9116_metadata_only_inventory_runner_contract_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9115 = ROOT / "runs/summaries/stage9115_metadata_only_inventory_runner_contract_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_INVENTORY_RUNNER_CONTRACT_AUDIT_STAGE9116.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_only_inventory_runner_contract_audit.json"

REJECT_METRICS = [
    "runner_executed_now",
    "arxiv_access_performed",
    "arxiv_stat_performed",
    "dataset_file_names_read_now",
    "repository_root_names_read_now",
    "dataset_rows_loaded",
    "dataset_parquet_groups_read",
    "repository_source_bodies_loaded",
    "arxiv_write_authorized",
    "data_mining_authorized",
    "trainer_executed_now",
    "model_forward_attempted",
    "training_authorized",
    "network_upload_performed",
    "cleanup_authorized_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9114) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_contract(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in REJECT_METRICS:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_flag = copy.deepcopy(base)
    missing_flag["required_cli_flags"].remove("--metadata-only")
    cases["missing_metadata_only_flag"] = missing_flag

    missing_assertion = copy.deepcopy(base)
    missing_assertion["required_runtime_assertions"].remove("source_body_reads_disabled")
    cases["missing_source_body_disabled_assertion"] = missing_assertion

    missing_forbidden = copy.deepcopy(base)
    missing_forbidden["forbidden_runtime_actions"].remove("open_source_file_for_body")
    cases["missing_source_body_forbidden_action"] = missing_forbidden

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_contract(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9115)
    base = build_contract(registry())
    base_failures = validate_contract(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9115_present": SOURCE_9115.exists(),
        "source_stage9115_passed": source.get("passed") is True,
        "base_contract_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_cli_flags_recorded": len(REQUIRED_CLI_FLAGS) >= 10,
        "required_runtime_assertions_recorded": len(REQUIRED_RUNTIME_ASSERTIONS) >= 11,
        "forbidden_runtime_actions_recorded": len(FORBIDDEN_RUNTIME_ACTIONS) >= 13,
        "no_runner_execution_now": base["metrics"]["runner_executed_now"] is False,
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
            "required_cli_flags": len(REQUIRED_CLI_FLAGS),
            "required_runtime_assertions": len(REQUIRED_RUNTIME_ASSERTIONS),
            "forbidden_runtime_actions": len(FORBIDDEN_RUNTIME_ACTIONS),
            "runner_executed_now": False,
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_file_names_read_now": False,
            "repository_root_names_read_now": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Metadata-only inventory runner contract rejects unsafe variants before implementation/execution: missing CLI guard flags, missing runtime assertions, missing forbidden actions, runner execution, /arxiv access/stat, name reads, row reads, parquet group reads, source-body reads, writes, mining, trainer/model paths, training, uploads, cleanup, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9115, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Metadata-only inventory runner contract audit failed.",
        "next_best_step": "Implement the metadata-only inventory runner, but do not execute it until a separate runner implementation audit passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9116 Metadata-Only Inventory Runner Contract Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9115 runner contract with negative cases. The runner is not implemented or executed here.",
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
