#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from golden_locked_eval_suite import validate_suite
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.golden_locked_eval_suite import validate_suite  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9686
NAME = "stage9686_golden_locked_eval_suite_validation"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9685_locked_multilingual_task_pack_skeleton.json"
SOURCE_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"
SOURCE_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
VALIDATION = OUT_DIR / "v27_golden_locked_eval_suite_validation.json"
EXCLUSION_AUDIT = OUT_DIR / "v27_locked_source_exclusion_enforcement_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_GOLDEN_LOCKED_EVAL_SUITE_VALIDATION_STAGE9686.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    suite = load_json(SOURCE_PACKS)
    packs = suite.get("benchmark_packs") if isinstance(suite, dict) else []
    if not isinstance(packs, list):
        packs = []
    validation = validate_suite(packs)

    exclusions = load_jsonl(SOURCE_EXCLUSIONS)
    locked_source_ids = set(validation.get("locked_source_ids") or [])
    excluded_source_ids = {str(row.get("source_id") or "") for row in exclusions if row.get("blocked_from_training") is True}
    missing_exclusions = sorted(locked_source_ids - excluded_source_ids)
    extra_exclusions = sorted(excluded_source_ids - locked_source_ids)
    bad_exclusion_rows = [
        row for row in exclusions
        if row.get("blocked_from_training") is not True or row.get("reason") != "locked_eval_source_never_mined_into_training"
    ]

    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9685_not_passed")
    if validation.get("passed") is not True:
        failures.append("golden_locked_eval_validation_failed")
    if validation.get("metrics", {}).get("packs") != 72:
        failures.append("pack_count_not_72")
    if validation.get("metrics", {}).get("train_eligible_packs") != 0:
        failures.append("train_eligible_locked_packs_present")
    if validation.get("metrics", {}).get("promotion_only_packs") != 72:
        failures.append("promotion_only_count_not_72")
    if missing_exclusions:
        failures.append("missing_locked_source_exclusions")
    if extra_exclusions:
        failures.append("extra_locked_source_exclusions")
    if bad_exclusion_rows:
        failures.append("bad_exclusion_rows")
    authority_rows = [pack.get("task_pack_id") for pack in packs if any((pack.get("authority") or {}).values())]
    if authority_rows:
        failures.append("authority_rows_present")

    exclusion_audit = {
        "passed": not (missing_exclusions or extra_exclusions or bad_exclusion_rows),
        "exclusion_rows": len(exclusions),
        "locked_source_ids": len(locked_source_ids),
        "excluded_source_ids": len(excluded_source_ids),
        "missing_exclusions": missing_exclusions,
        "extra_exclusions": extra_exclusions,
        "bad_exclusion_rows": bad_exclusion_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }
    validation["stage"] = STAGE
    validation["stage_name"] = NAME
    validation["authority"] = dict(AUTHORITY_CLOSED)
    validation["failures"] = failures
    validation["passed"] = not failures
    VALIDATION.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    EXCLUSION_AUDIT.write_text(json.dumps(exclusion_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Build Stage9687 locked eval train-exclusion guard hook for curriculum compilers, then run a no-training "
        "negative fixture proving locked source IDs cannot enter train manifests."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "packs": validation.get("metrics", {}).get("packs", 0),
            "passed_packs": validation.get("metrics", {}).get("passed_packs", 0),
            "failed_packs": validation.get("metrics", {}).get("failed_packs", 0),
            "train_eligible_packs": validation.get("metrics", {}).get("train_eligible_packs", 0),
            "promotion_only_packs": validation.get("metrics", {}).get("promotion_only_packs", 0),
            "locked_source_ids": validation.get("metrics", {}).get("locked_source_ids", 0),
            "exclusion_rows": len(exclusions),
            "missing_exclusions": len(missing_exclusions),
            "extra_exclusions": len(extra_exclusions),
            "authority_rows": len(authority_rows),
        },
        "artifacts": {
            "doc": str(DOC.relative_to(ROOT)),
            "exclusion_audit": str(EXCLUSION_AUDIT.relative_to(ROOT)),
            "validation": str(VALIDATION.relative_to(ROOT)),
        },
        "decision": "Validated the Stage9685 locked multilingual eval skeleton and its train-exclusion list.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9686 Golden Locked Eval Suite Validation",
        "",
        f"Passed: `{summary['passed']}`",
        f"Packs: `{summary['metrics']['packs']}`",
        f"Passed packs: `{summary['metrics']['passed_packs']}`",
        f"Train-eligible packs: `{summary['metrics']['train_eligible_packs']}`",
        f"Promotion-only packs: `{summary['metrics']['promotion_only_packs']}`",
        f"Locked source IDs: `{summary['metrics']['locked_source_ids']}`",
        f"Missing exclusions: `{summary['metrics']['missing_exclusions']}`",
        f"Extra exclusions: `{summary['metrics']['extra_exclusions']}`",
        "",
        "All locked eval packs remain promotion-only and blocked from training.",
        "",
        "No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "packs": summary["metrics"]["packs"],
        "train_eligible_packs": summary["metrics"]["train_eligible_packs"],
        "missing_exclusions": summary["metrics"]["missing_exclusions"],
        "extra_exclusions": summary["metrics"]["extra_exclusions"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
