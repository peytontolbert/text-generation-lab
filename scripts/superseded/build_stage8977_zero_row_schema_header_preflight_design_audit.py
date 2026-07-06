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
STAGE = 8977
NAME = "stage8977_zero_row_schema_header_preflight_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_AUDIT_STAGE8977.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "zero_row_schema_header_preflight_design_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8976_zero_row_schema_header_preflight_design.json"
SOURCE_DESIGN = ROOT / "runs/local/artifacts/stage8976_zero_row_schema_header_preflight_design/zero_row_schema_header_preflight_design.json"
SOURCE_SELECTED = ROOT / "runs/local/artifacts/stage8976_zero_row_schema_header_preflight_design/selected_candidate_paths_metadata_only.json"

REQUIRED_FORBIDDEN_ACTIONS = [
    "read_jsonl_first_line",
    "materialize_parquet_batch",
    "load_dataset_rows",
    "read_repository_source_body",
    "start_training",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    design = load_json(SOURCE_DESIGN)
    selected = load_json(SOURCE_SELECTED)
    selected_rows = selected if isinstance(selected, list) else []
    forbidden = design.get("forbidden_prefight_actions") or []
    selected_route_set = {row.get("route") for row in selected_rows}
    selected_extensions = {row.get("extension") for row in selected_rows}
    checks = {
        "source_stage8976_passed": source.get("passed") is True,
        "source_design_present": SOURCE_DESIGN.exists(),
        "source_selected_present": SOURCE_SELECTED.exists(),
        "selected_rows_present": len(selected_rows) >= 6,
        "selected_routes_cover_core": {"NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE", "PARQUET_TABLE_CANDIDATE", "JSONL_MANIFEST_CANDIDATE"}.issubset(selected_route_set),
        "selected_extensions_cover_parquet_jsonl": {".parquet", ".jsonl"}.issubset(selected_extensions),
        "forbidden_actions_cover_row_reads": all(item in forbidden for item in REQUIRED_FORBIDDEN_ACTIONS),
        "no_arxiv_files_opened_now": (source.get("metrics") or {}).get("arxiv_files_opened_now") == 0,
        "no_schema_probe_executed_now": (source.get("metrics") or {}).get("schema_probe_executed_now") is False,
        "no_header_probe_executed_now": (source.get("metrics") or {}).get("header_probe_executed_now") is False,
        "no_dataset_rows_loaded": (source.get("metrics") or {}).get("dataset_rows_loaded") is False,
        "no_repository_source_bodies_loaded": (source.get("metrics") or {}).get("repository_source_bodies_loaded") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8976_or_8977": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8976, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_AUDIT",
        "source_stage_name": "stage8976_zero_row_schema_header_preflight_design",
        "selected_routes": sorted(str(route) for route in selected_route_set),
        "selected_extensions": sorted(str(ext) for ext in selected_extensions),
        "checks": checks,
        "metrics": {
            "selected_rows": len(selected_rows),
            "selected_routes": len(selected_route_set),
            "selected_extensions": len(selected_extensions),
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
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The zero-row schema/header preflight design is internally consistent and still design-only. The next runner must remain dry-run/no-file-open unless a future explicit ticket permits metadata-only file access.",
    }


def validate_audit(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8976, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("arxiv_files_opened_now") != 0:
        failures.append("arxiv_files_opened_now")
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
    card = build_audit(registry)
    failures = validate_audit(card, registry)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Implement a dry-run preflight runner contract that reads only Stage8976 selected-candidate metadata and still opens no /arxiv files.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8977 Zero-Row Schema/Header Preflight Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits the exact Stage8976 design artifacts by name to avoid ambiguity from same-number historical rows. It opens no `/arxiv` files, loads no rows, reads no source bodies, and executes no schema/header probes.",
        "",
        f"Selected rows: `{summary['metrics']['selected_rows']}`",
        f"Selected routes: `{summary['metrics']['selected_routes']}`",
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
    marker = "## Stage8977 Zero-Row Schema/Header Preflight Design Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8977 audits Stage8976 zero-row preflight design artifacts by exact stage name and keeps /arxiv file access, row loads, source-body reads, schema/header probes, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
