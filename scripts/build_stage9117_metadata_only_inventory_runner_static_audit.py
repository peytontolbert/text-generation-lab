#!/usr/bin/env python3
from __future__ import annotations

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
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9115_metadata_only_inventory_runner_contract_design import (  # type: ignore
        FORBIDDEN_RUNTIME_ACTIONS,
        REQUIRED_CLI_FLAGS,
        REQUIRED_RUNTIME_ASSERTIONS,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9117
NAME = "stage9117_metadata_only_inventory_runner_static_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9116 = ROOT / "runs/summaries/stage9116_metadata_only_inventory_runner_contract_audit.json"
RUNNER = ROOT / "scripts/metadata_only_inventory_runner.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_INVENTORY_RUNNER_STATIC_AUDIT_STAGE9117.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_only_inventory_runner_static_audit.json"

FORBIDDEN_SOURCE_PATTERNS = [
    "shutil.rmtree",
    "os.remove",
    "os.unlink",
    ".unlink(",
    ".rmdir(",
    "subprocess",
    "requests",
    "urllib",
    "torch",
    "train_agentkernel",
    "git push",
    "huggingface_hub",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9116)
    text = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""
    checks = {
        "source_stage9116_passed": source.get("passed") is True,
        "runner_present": RUNNER.exists(),
        "required_cli_flags_present": all(flag in text for flag in REQUIRED_CLI_FLAGS),
        "runtime_assertion_terms_present": all(term in text for term in [
            "ARXIV_DATASETS",
            "ARXIV_REPOSITORIES",
            "RUNS_LOCAL_ARTIFACTS",
            "metadata_only_flag_required",
            "row_reads_not_disabled",
            "source_body_reads_not_disabled",
            "arxiv_writes_not_disabled",
            "symlink_follow_not_disabled",
            "ticket_audit_not_passed",
        ]),
        "follow_symlinks_false_present": "follow_symlinks=False" in text,
        "forbidden_source_patterns_absent": not any(pattern in text for pattern in FORBIDDEN_SOURCE_PATTERNS),
        "contract_forbidden_actions_recorded": len(FORBIDDEN_RUNTIME_ACTIONS) >= 13,
        "contract_runtime_assertions_recorded": len(REQUIRED_RUNTIME_ASSERTIONS) >= 11,
        "registry_frontier_stage9116": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9116,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "required_cli_flags": len(REQUIRED_CLI_FLAGS),
            "required_runtime_assertions": len(REQUIRED_RUNTIME_ASSERTIONS),
            "forbidden_runtime_actions": len(FORBIDDEN_RUNTIME_ACTIONS),
            "forbidden_source_patterns": len(FORBIDDEN_SOURCE_PATTERNS),
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
        "decision": "Metadata-only inventory runner implementation passes static audit. The runner is still not executed; real inventory remains blocked until a separate execution authorization stage.",
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = list(audit.get("failures", []))
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9116, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
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
    ]:
        if audit["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    audit["passed"] = not failures
    audit["failures"] = failures
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Metadata-only inventory runner static audit failed.",
        "next_best_step": "Design a no-execution runner implementation audit or execution authorization review; do not run inventory yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9117 Metadata-Only Inventory Runner Static Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Static-audits `scripts/metadata_only_inventory_runner.py`. The runner is not executed in this stage.",
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
