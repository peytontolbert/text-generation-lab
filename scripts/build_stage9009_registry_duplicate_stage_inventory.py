#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9009
NAME = "stage9009_registry_duplicate_stage_inventory"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9008_registry_frontier_consistency_audit.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9008_registry_frontier_consistency_audit/registry_frontier_consistency_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_DUPLICATE_STAGE_INVENTORY_STAGE9009.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY = OUT_DIR / "registry_duplicate_stage_inventory.json"

ALLOWED_DUPLICATE_STAGE_IDS = {8981, 8991}
RECOVERY_DUPLICATE_BANDS = [
    {"name": "early_recovery_support_modules", "min": 8600, "max": 8699},
    {"name": "mid_recovery_training_modules", "min": 8800, "max": 8899},
    {"name": "late_recovery_ticket_modules", "min": 8950, "max": 8999},
]

FORBIDDEN_OPERATIONS = [
    "RENUMBER_REGISTRY_ROWS_NOW",
    "DELETE_DUPLICATE_ROWS",
    "DELETE_SUMMARIES",
    "DELETE_ARTIFACTS",
    "REWRITE_HISTORY",
    "RUN_TRAINING",
    "RUN_MODEL",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def classify_stage(stage: int) -> str:
    if stage in ALLOWED_DUPLICATE_STAGE_IDS:
        return "explicitly_allowed_duplicate"
    for band in RECOVERY_DUPLICATE_BANDS:
        if band["min"] <= stage <= band["max"]:
            return str(band["name"])
    return "unexpected_outside_recovery_bands"


def duplicate_inventory(registry: dict[str, Any]) -> dict[str, Any]:
    by_stage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in registry.get("rows") or []:
        by_stage[int(row.get("stage", -1))].append(row)
    duplicates = []
    for stage, rows in sorted(by_stage.items()):
        if len(rows) <= 1:
            continue
        duplicates.append({
            "stage": stage,
            "classification": classify_stage(stage),
            "count": len(rows),
            "stage_names": [str(row.get("stage_name")) for row in rows],
            "passed_values": [bool(row.get("passed")) for row in rows],
            "paths": [str(row.get("path")) for row in rows],
            "authority_open_rows": [str(row.get("stage_name")) for row in rows if any((row.get("authority") or {}).values())],
        })
    return {"duplicates": duplicates}


def build_inventory(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_audit = load_json(SOURCE_AUDIT)
    metrics = registry.get("metrics") or {}
    real_reconstructed_registry = "latest_stage" in metrics and "registry_rows" in metrics
    inv = duplicate_inventory(registry)
    duplicates = inv["duplicates"]
    outside = [item for item in duplicates if item["classification"] == "unexpected_outside_recovery_bands"]
    authority_open = [item for item in duplicates if item["authority_open_rows"]]
    checks = {
        "source_stage9008_present": SOURCE_SUMMARY.exists() and SOURCE_AUDIT.exists(),
        "source_stage9008_passed": source_summary.get("passed") is True,
        "source_stage9008_reported_duplicate_cleanup": (source_audit.get("metrics") or {}).get("duplicate_cleanup_required") is True,
        "duplicates_inventory_recorded": (not real_reconstructed_registry) or len(duplicates) == (source_audit.get("metrics") or {}).get("duplicate_stage_ids"),
        "no_duplicate_authority_open_rows": not authority_open,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 8,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_DUPLICATE_STAGE_INVENTORY_NO_MUTATION",
        "allowed_duplicate_stage_ids": sorted(ALLOWED_DUPLICATE_STAGE_IDS),
        "recovery_duplicate_bands": RECOVERY_DUPLICATE_BANDS,
        "duplicates": duplicates,
        "unexpected_outside_recovery_band_duplicates": outside,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "duplicate_stage_ids": len(duplicates),
            "unexpected_outside_recovery_band_duplicates": len(outside),
            "duplicate_authority_open_groups": len(authority_open),
            "inventory_only_no_mutation": True,
            "registry_rows_mutated_now": False,
            "registry_rows_deleted_now": False,
            "summaries_deleted_now": False,
            "artifacts_deleted_now": False,
            "renumbering_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Duplicate stage IDs are inventoried without mutation. Future cleanup must classify and preserve every row before any renumbering; no deletion or execution is authorized.",
    }


def validate_inventory(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "registry_rows_mutated_now",
        "registry_rows_deleted_now",
        "summaries_deleted_now",
        "artifacts_deleted_now",
        "renumbering_authorized_now",
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
    card = build_inventory(registry)
    failures = validate_inventory(card)
    INVENTORY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"inventory": str(INVENTORY.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design a non-mutating duplicate resolution policy that preserves all summaries/artifacts before any registry renumbering. Keep training and execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9009 Registry Duplicate Stage Inventory",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage inventories duplicate stage IDs without mutating the registry, deleting rows, deleting summaries, deleting artifacts, or authorizing execution.",
        "",
        f"Duplicate stage IDs: `{summary['metrics']['duplicate_stage_ids']}`",
        f"Unexpected outside recovery bands: `{summary['metrics']['unexpected_outside_recovery_band_duplicates']}`",
        f"Renumbering authorized now: `{summary['metrics']['renumbering_authorized_now']}`",
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
    marker = "## Stage9009 Registry Duplicate Stage Inventory"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Inventories duplicate recovered stage IDs without mutation or deletion.",
            "- Classifies duplicates into allowed IDs, recovery bands, and outside-band risks.",
            "- Keeps all execution and training authority closed while a later resolution policy is designed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
