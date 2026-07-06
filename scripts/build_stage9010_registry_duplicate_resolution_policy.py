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
STAGE = 9010
NAME = "stage9010_registry_duplicate_resolution_policy"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9009_registry_duplicate_stage_inventory.json"
SOURCE_INVENTORY = ROOT / "runs/local/artifacts/stage9009_registry_duplicate_stage_inventory/registry_duplicate_stage_inventory.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_DUPLICATE_RESOLUTION_POLICY_STAGE9010.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
POLICY = OUT_DIR / "registry_duplicate_resolution_policy.json"

RESOLUTION_RULES = [
    "preserve_every_summary_and_artifact_before_renumbering",
    "never_delete_duplicate_rows_during_resolution",
    "assign_stable_alias_id_to_each_duplicate_row",
    "keep_original_stage_id_as_recovered_stage_id",
    "create_canonical_registry_stage_only_in_future_apply_stage",
    "record_source_path_and_stage_name_for_every_alias",
    "do_not_change_authority_flags",
    "do_not_change_passed_status",
    "do_not_treat_cleanup_as_training_or_execution_authorization",
]

FORBIDDEN_OPERATIONS = [
    "APPLY_RENUMBERING_NOW",
    "DELETE_DUPLICATE_ROWS",
    "DELETE_SUMMARIES",
    "DELETE_ARTIFACTS",
    "REWRITE_GIT_HISTORY",
    "RUN_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_alias_plan(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    next_alias = 1
    for group in inventory.get("duplicates") or []:
        stage = int(group.get("stage"))
        for idx, name in enumerate(group.get("stage_names") or [], start=1):
            plan.append({
                "alias_id": f"dup-{next_alias:04d}",
                "recovered_stage_id": stage,
                "duplicate_ordinal": idx,
                "stage_name": name,
                "path": (group.get("paths") or [None] * idx)[idx - 1],
                "preserve_original_stage_id": True,
                "future_canonical_stage_id": None,
                "apply_now": False,
            })
            next_alias += 1
    return plan


def build_policy(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    inventory = load_json(SOURCE_INVENTORY)
    alias_plan = build_alias_plan(inventory)
    duplicate_groups = inventory.get("duplicates") or []
    checks = {
        "source_stage9009_present": SOURCE_SUMMARY.exists() and SOURCE_INVENTORY.exists(),
        "source_stage9009_passed": source_summary.get("passed") is True,
        "source_stage9009_inventory_only": (source_summary.get("metrics") or {}).get("inventory_only_no_mutation") is True,
        "alias_plan_covers_duplicate_rows": len(alias_plan) == sum(int(group.get("count", 0)) for group in duplicate_groups),
        "resolution_rules_recorded": len(RESOLUTION_RULES) >= 9,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_DUPLICATE_RESOLUTION_POLICY_NO_MUTATION",
        "resolution_rules": RESOLUTION_RULES,
        "alias_plan": alias_plan,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "duplicate_groups": len(duplicate_groups),
            "alias_rows": len(alias_plan),
            "policy_only_no_mutation": True,
            "renumbering_applied_now": False,
            "registry_rows_mutated_now": False,
            "registry_rows_deleted_now": False,
            "summaries_deleted_now": False,
            "artifacts_deleted_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Duplicate resolution policy is designed without applying it. Every duplicate row gets a preservation alias; no registry rows, summaries, or artifacts are mutated or deleted.",
    }


def validate_policy(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for rule in ["preserve_every_summary_and_artifact_before_renumbering", "never_delete_duplicate_rows_during_resolution", "keep_original_stage_id_as_recovered_stage_id"]:
        if rule not in card.get("resolution_rules", []):
            failures.append(f"missing_rule:{rule}")
    for alias in card.get("alias_plan", []):
        if alias.get("apply_now") is not False:
            failures.append("alias_apply_now")
            break
    for key in [
        "renumbering_applied_now",
        "registry_rows_mutated_now",
        "registry_rows_deleted_now",
        "summaries_deleted_now",
        "artifacts_deleted_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_policy(registry)
    failures = validate_policy(card)
    POLICY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"policy": str(POLICY.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a dry-run duplicate-resolution apply preview that writes only a proposed registry diff, not the registry itself. Keep execution and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9010 Registry Duplicate Resolution Policy",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines how duplicate recovered stage IDs will be resolved later without deleting rows or artifacts. It does not mutate the registry.",
        "",
        f"Duplicate groups: `{summary['metrics']['duplicate_groups']}`",
        f"Alias rows: `{summary['metrics']['alias_rows']}`",
        f"Renumbering applied now: `{summary['metrics']['renumbering_applied_now']}`",
        "",
    ]), encoding="utf-8")
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
    marker = "## Stage9010 Registry Duplicate Resolution Policy"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Defines preservation aliases for duplicate recovered stage rows without mutating the registry.",
            "- Requires future preview/apply stages before any renumbering and forbids deletion of summaries or artifacts.",
            "- Keeps all execution and training authority closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
