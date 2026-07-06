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
STAGE = 8979
NAME = "stage8979_zero_row_preflight_runner_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_PREFLIGHT_RUNNER_CONTRACT_STAGE8979.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "zero_row_preflight_runner_contract.json"
DRY_RUN_ROWS = OUT_DIR / "zero_row_preflight_dry_run_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8977_zero_row_candidate_selector.json"
SELECTED_CANDIDATES = ROOT / "runs/local/artifacts/stage8977_zero_row_candidate_selector/selected_schema_candidate_paths_metadata_only.jsonl"

RUNNER_INPUTS = [
    "stage8976_selected_candidate_metadata_json",
    "candidate_route",
    "relative_path",
    "extension",
    "allowed_zero_row_probe",
]

RUNNER_OUTPUT_FIELDS = [
    "candidate_id",
    "route",
    "relative_path",
    "extension",
    "planned_probe",
    "probe_executed_now",
    "arxiv_file_opened_now",
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "status",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def selected_rows() -> list[dict[str, Any]]:
    return read_jsonl(SELECTED_CANDIDATES)


def build_dry_run_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        ext = str(row.get("extension") or "").lower()
        planned_probe = "future_parquet_footer_schema_ticket_required" if ext == ".parquet" else "metadata_path_only"
        out.append({
            "candidate_id": f"candidate_{idx:04d}",
            "route": row.get("selection_route"),
            "relative_path": row.get("relative_path"),
            "extension": ext,
            "planned_probe": planned_probe,
            "probe_executed_now": False,
            "arxiv_file_opened_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "status": "DRY_RUN_PLANNED_ONLY",
        })
    return out


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    candidates = selected_rows()
    dry_rows = build_dry_run_rows(candidates)
    checks = {
        "source_stage8977_passed": source.get("passed") is True,
        "selected_candidate_metadata_present": SELECTED_CANDIDATES.exists(),
        "selected_candidates_present": len(candidates) >= 6,
        "dry_rows_match_candidates": len(dry_rows) == len(candidates),
        "runner_inputs_recorded": len(RUNNER_INPUTS) >= 5,
        "runner_outputs_recorded": len(RUNNER_OUTPUT_FIELDS) >= 10,
        "all_probes_not_executed_now": all(row["probe_executed_now"] is False for row in dry_rows),
        "no_arxiv_file_opened_now": all(row["arxiv_file_opened_now"] is False for row in dry_rows),
        "no_dataset_rows_loaded": all(row["dataset_rows_loaded"] is False for row in dry_rows),
        "no_repository_source_bodies_loaded": all(row["repository_source_bodies_loaded"] is False for row in dry_rows),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8978_or_8979": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8978, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_PREFLIGHT_RUNNER_CONTRACT_DRY_RUN_ONLY",
        "source_stage": 8977,
        "runner_inputs": RUNNER_INPUTS,
        "runner_output_fields": RUNNER_OUTPUT_FIELDS,
        "checks": checks,
        "metrics": {
            "selected_candidates": len(candidates),
            "dry_run_rows": len(dry_rows),
            "probe_executed_now_rows": 0,
            "arxiv_files_opened_now": 0,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "schema_probe_executed_now": False,
            "header_probe_executed_now": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "dry_run_rows": dry_rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The zero-row preflight runner is recovered as a dry-run contract only. It consumes local Stage8977 selected-candidate metadata and emits planned probe rows without opening /arxiv files, executing probes, loading rows, reading source bodies, mining, training, or running models.",
    }


def validate_contract(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8978, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key, expected in [("probe_executed_now_rows", 0), ("arxiv_files_opened_now", 0)]:
        if card["metrics"].get(key) != expected:
            failures.append(key)
    for key in [
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "schema_probe_executed_now",
        "header_probe_executed_now",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card, registry)
    dry_rows = card.pop("dry_run_rows")
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(DRY_RUN_ROWS, dry_rows)
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
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "dry_run_rows": str(DRY_RUN_ROWS.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit the zero-row dry-run runner contract. If it passes, design a future ticket schema for metadata-only /arxiv file access without row/body reads.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8979 Zero-Row Preflight Runner Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a dry-run runner contract over local Stage8977 selected-candidate metadata. It emits planned probe rows only and opens no `/arxiv` files, executes no probes, loads no rows, reads no source bodies, mines no data, trains nothing, and runs no models.",
        "",
        f"Dry-run rows: `{summary['metrics']['dry_run_rows']}`",
        f"Probe executed rows: `{summary['metrics']['probe_executed_now_rows']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in {NAME, "stage8978_zero_row_preflight_runner_contract"}]
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
    marker = "## Stage8979 Zero-Row Preflight Runner Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8979 defines a dry-run runner contract over local Stage8977 selected-candidate metadata only. It emits planned probe rows while keeping /arxiv file opens, row loads, source-body reads, schema/header probes, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
