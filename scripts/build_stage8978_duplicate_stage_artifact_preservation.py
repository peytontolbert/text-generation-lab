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
STAGE = 8978
NAME = "stage8978_duplicate_stage_artifact_preservation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DUPLICATE_STAGE_ARTIFACT_PRESERVATION_STAGE8978.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "duplicate_stage_artifact_preservation.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8977_zero_row_candidate_selector.json"

PRESERVED_PATHS = [
    "docs/superseded/ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_STAGE8976.md",
    "docs/superseded/ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_AUDIT_STAGE8977.md",
    "scripts/superseded/build_stage8976_zero_row_schema_header_preflight_design.py",
    "scripts/superseded/build_stage8977_zero_row_schema_header_preflight_design_audit.py",
    "tests/superseded/test_zero_row_schema_header_preflight_design_stage8976.py",
    "tests/superseded/test_zero_row_schema_header_preflight_design_audit_stage8977.py",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/runs_summaries/stage8976_zero_row_schema_header_preflight_design.json",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/runs_summaries/stage8977_zero_row_schema_header_preflight_design_audit.json",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/stage8976_zero_row_schema_header_preflight_design",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/stage8977_zero_row_schema_header_preflight_design_audit",
]

ACTIVE_PATHS_THAT_SHOULD_NOT_EXIST = [
    "runs/summaries/stage8976_zero_row_schema_header_preflight_design.json",
    "runs/summaries/stage8977_zero_row_schema_header_preflight_design_audit.json",
    "scripts/build_stage8976_zero_row_schema_header_preflight_design.py",
    "scripts/build_stage8977_zero_row_schema_header_preflight_design_audit.py",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def path_exists(path: str) -> bool:
    return (ROOT / path).exists()


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    missing_preserved = [path for path in PRESERVED_PATHS if not path_exists(path)]
    active_conflicts = [path for path in ACTIVE_PATHS_THAT_SHOULD_NOT_EXIST if path_exists(path)]
    checks = {
        "source_stage8977_active_passed": source.get("passed") is True,
        "preserved_paths_present": not missing_preserved,
        "active_duplicate_conflict_paths_absent": not active_conflicts,
        "preservation_under_superseded_or_artifacts": all(path.startswith(("docs/superseded/", "scripts/superseded/", "tests/superseded/", "runs/local/artifacts/superseded_duplicate_stage_artifacts/")) for path in PRESERVED_PATHS),
        "no_delete_performed_by_stage": True,
        "training_and_mining_closed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8977_or_8978": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8977, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DUPLICATE_STAGE_ARTIFACT_PRESERVATION",
        "preserved_paths": PRESERVED_PATHS,
        "missing_preserved_paths": missing_preserved,
        "active_duplicate_conflict_paths": active_conflicts,
        "checks": checks,
        "metrics": {
            "preserved_paths": len(PRESERVED_PATHS),
            "missing_preserved_paths": len(missing_preserved),
            "active_duplicate_conflict_paths": len(active_conflicts),
            "delete_or_cleanup_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "schema_or_header_read_performed": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Duplicate Stage8976/8977 schema-header design artifacts were preserved under superseded paths outside active runs/summaries and script roots. Active registry frontier remains the zero-row candidate selector lineage.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8977, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "delete_or_cleanup_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "schema_or_header_read_performed",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"preservation_card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit selected candidate metadata from Stage8977, then require a separate explicit ticket before any parquet footer schema access.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8978 Duplicate Stage Artifact Preservation",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Duplicate Stage8976/8977 schema-header design artifacts were preserved under superseded paths instead of being deleted or left in active stage locations.",
        "",
        f"Preserved paths: `{summary['metrics']['preserved_paths']}`",
        f"Missing preserved paths: `{summary['metrics']['missing_preserved_paths']}`",
        f"Active duplicate conflict paths: `{summary['metrics']['active_duplicate_conflict_paths']}`",
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8978 Duplicate Stage Artifact Preservation"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8978 preserves duplicate Stage8976/8977 schema-header design artifacts under superseded paths and keeps the active zero-row candidate selector lineage unambiguous.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
