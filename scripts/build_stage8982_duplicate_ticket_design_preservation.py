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
STAGE = 8982
NAME = "stage8982_duplicate_ticket_design_preservation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DUPLICATE_TICKET_DESIGN_PRESERVATION_STAGE8982.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "duplicate_ticket_design_preservation.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8981_parquet_footer_metadata_ticket_design.json"

PRESERVED_PATHS = [
    "docs/superseded/PARQUET_FOOTER_METADATA_ACCESS_TICKET_DESIGN_STAGE8981.md",
    "scripts/superseded/build_stage8981_parquet_footer_metadata_access_ticket_design.py",
    "tests/superseded/test_parquet_footer_metadata_access_ticket_design_stage8981.py",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/runs_summaries/stage8981_parquet_footer_metadata_access_ticket_design.json",
    "runs/local/artifacts/superseded_duplicate_stage_artifacts/stage8981_parquet_footer_metadata_access_ticket_design",
]

ACTIVE_CONFLICT_PATHS = [
    "docs/PARQUET_FOOTER_METADATA_ACCESS_TICKET_DESIGN_STAGE8981.md",
    "scripts/build_stage8981_parquet_footer_metadata_access_ticket_design.py",
    "tests/test_parquet_footer_metadata_access_ticket_design_stage8981.py",
    "runs/summaries/stage8981_parquet_footer_metadata_access_ticket_design.json",
    "runs/local/artifacts/stage8981_parquet_footer_metadata_access_ticket_design",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    missing = [path for path in PRESERVED_PATHS if not (ROOT / path).exists()]
    conflicts = [path for path in ACTIVE_CONFLICT_PATHS if (ROOT / path).exists()]
    checks = {
        "source_stage8981_passed": source.get("passed") is True,
        "preserved_paths_present": not missing,
        "active_conflicts_absent": not conflicts,
        "preserved_under_superseded": all(path.startswith(("docs/superseded/", "scripts/superseded/", "tests/superseded/", "runs/local/artifacts/superseded_duplicate_stage_artifacts/")) for path in PRESERVED_PATHS),
        "no_delete_performed_by_stage": True,
        "no_footer_access_performed": True,
        "training_and_mining_closed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8981_or_8982": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8981, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DUPLICATE_TICKET_DESIGN_PRESERVATION",
        "preserved_paths": PRESERVED_PATHS,
        "missing_preserved_paths": missing,
        "active_conflict_paths": conflicts,
        "checks": checks,
        "metrics": {
            "preserved_paths": len(PRESERVED_PATHS),
            "missing_preserved_paths": len(missing),
            "active_conflict_paths": len(conflicts),
            "delete_or_cleanup_performed": False,
            "parquet_footer_access_performed": False,
            "candidate_file_opened": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
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
        "decision": "Duplicate Stage8981 parquet-footer access-ticket design artifacts were preserved under superseded paths. Active frontier remains the inactive parquet-footer metadata ticket design lineage.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8981, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "delete_or_cleanup_performed",
        "parquet_footer_access_performed",
        "candidate_file_opened",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
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
        "next_best_step": "Audit the active Stage8981 inactive ticket schema, then require a later active ticket before parquet footer metadata access.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8982 Duplicate Ticket Design Preservation",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Duplicate Stage8981 parquet-footer access-ticket design artifacts were preserved under superseded paths, not deleted or left in active locations.",
        "",
        f"Preserved paths: `{summary['metrics']['preserved_paths']}`",
        f"Active conflict paths: `{summary['metrics']['active_conflict_paths']}`",
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
    marker = "## Stage8982 Duplicate Ticket Design Preservation"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8982 preserves duplicate Stage8981 parquet-footer ticket design artifacts under superseded paths and keeps the active ticket lineage unambiguous.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
