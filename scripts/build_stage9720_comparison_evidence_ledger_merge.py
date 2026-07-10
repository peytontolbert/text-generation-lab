#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

try:
    from build_stage9719_multilingual_comparison_evidence_bundle_contract import merge_bundle_into_record
except ModuleNotFoundError:
    from scripts.build_stage9719_multilingual_comparison_evidence_bundle_contract import merge_bundle_into_record  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9720
NAME = "stage9720_comparison_evidence_ledger_merge"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
SOURCE_TEMPLATES = ROOT / "runs/local/artifacts/stage9719_multilingual_comparison_evidence_bundle_contract/multilingual_comparison_evidence_bundle_templates.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MERGED_LEDGER = OUT_DIR / "comparison_evidence_merged_ledger.json"
AUDIT = OUT_DIR / "comparison_evidence_ledger_merge_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_COMPARISON_EVIDENCE_LEDGER_MERGE_STAGE9720.md"
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


def merge_records(
    contract: dict[str, Any],
    ledger: dict[str, Any],
    bundles: list[dict[str, Any]],
) -> dict[str, Any]:
    source_records = ledger.get("records") if isinstance(ledger, dict) else []
    if not isinstance(source_records, list):
        source_records = []
    record_map = {str(record.get("cell_key") or ""): dict(record) for record in source_records}
    failures: list[str] = []
    merged_count = 0
    unknown_bundles: list[str] = []
    for bundle in bundles:
        cell_key = str(bundle.get("cell_key") or "")
        record = record_map.get(cell_key)
        if not record:
            unknown_bundles.append(cell_key)
            continue
        record_map[cell_key] = merge_bundle_into_record(bundle, record, contract)
        merged_count += 1
    if unknown_bundles:
        failures.append("unknown_bundle_cell_keys_present")
    records = list(record_map.values())
    claim_ready = [record for record in records if record.get("claim_ready") is True]
    blocked = [record for record in records if record.get("claim_ready") is not True]
    status_counts = Counter(str(record.get("claim_status") or "unknown") for record in records)
    mode_claim_ready = Counter(str(record.get("mode") or "") for record in claim_ready)
    language_claim_ready = Counter(str(record.get("language_family") or "") for record in claim_ready)
    skill_claim_ready = Counter(str(record.get("skill_area") or "") for record in claim_ready)
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "merged_bundle_count": merged_count,
        "unknown_bundle_cell_keys": unknown_bundles,
        "metrics": {
            "records": len(records),
            "claim_ready_cells": len(claim_ready),
            "blocked_cells": len(blocked),
            "status_counts": dict(sorted(status_counts.items())),
            "mode_claim_ready_counts": dict(sorted(mode_claim_ready.items())),
            "language_claim_ready_counts": dict(sorted(language_claim_ready.items())),
            "skill_claim_ready_counts": dict(sorted(skill_claim_ready.items())),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    contract = load_json(SOURCE_CONTRACT)
    ledger = load_json(SOURCE_LEDGER)
    bundles = load_jsonl(SOURCE_TEMPLATES)
    merged = merge_records(contract, ledger, bundles)
    MERGED_LEDGER.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit = {
        "passed": merged["passed"],
        "failures": merged["failures"],
        "merged_bundle_count": merged["merged_bundle_count"],
        "unknown_bundle_cell_keys": merged["unknown_bundle_cell_keys"],
        "claim_ready_cells": merged["metrics"]["claim_ready_cells"],
        "blocked_cells": merged["metrics"]["blocked_cells"],
        "status_counts": merged["metrics"]["status_counts"],
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Replace template-only Stage9719 bundles with real same-surface comparison bundles, then rerun Stage9720 "
        "to measure how many Stage9718 cells become genuinely claim-ready."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": merged["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "merged_bundle_count": merged["merged_bundle_count"],
            "claim_ready_cells": merged["metrics"]["claim_ready_cells"],
            "blocked_cells": merged["metrics"]["blocked_cells"],
            "status_counts": merged["metrics"]["status_counts"],
            "failures": merged["failures"],
        },
        "artifacts": {
            "merged_ledger": str(MERGED_LEDGER.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized the comparison-evidence ingest path that merges populated Stage9719 bundles into the Stage9718 acceptance ledger.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9720 Comparison Evidence Ledger Merge",
        "",
        f"Passed: `{summary['passed']}`",
        f"Merged bundles: `{summary['metrics']['merged_bundle_count']}`",
        f"Claim-ready cells: `{summary['metrics']['claim_ready_cells']}`",
        f"Blocked cells: `{summary['metrics']['blocked_cells']}`",
        "",
        "This stage ingests Stage9719 comparison bundles and merges them into the Stage9718 acceptance ledger. Template-only bundles should keep cells blocked; only real passing bundles can make a cell claim-ready.",
        "",
        "No Gemma, harness, runtime, scoring, training, source/body emission, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "merged_bundle_count": merged["merged_bundle_count"],
        "claim_ready_cells": merged["metrics"]["claim_ready_cells"],
        "blocked_cells": merged["metrics"]["blocked_cells"],
        "failures": merged["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if merged["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
