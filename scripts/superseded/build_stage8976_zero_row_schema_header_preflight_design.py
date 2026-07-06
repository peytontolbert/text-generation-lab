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
STAGE = 8976
NAME = "stage8976_zero_row_schema_header_preflight_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_STAGE8976.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "zero_row_schema_header_preflight_design.json"
SELECTED = OUT_DIR / "selected_candidate_paths_metadata_only.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8975_metadata_route_selector_audit.json"
DATASET_CARD = ROOT / "runs/local/artifacts/stage8974_metadata_inventory_route_selector/dataset_route_card_metadata_only.json"

SELECTED_ROUTES = [
    "NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE",
    "PARQUET_TABLE_CANDIDATE",
    "JSONL_MANIFEST_CANDIDATE",
]

ZERO_ROW_ALLOWED_PROBES = {
    ".parquet": [
        "read_file_footer_metadata_only",
        "extract_schema_without_materializing_batches",
        "extract_row_group_count_without_rows",
    ],
    ".jsonl": [
        "read_filename_size_and_extension_only",
        "defer_header_detection_until_explicit_row_ticket",
    ],
    ".json": [
        "read_filename_size_and_extension_only",
        "defer_body_schema_until_explicit_json_metadata_ticket",
    ],
}

FORBIDDEN_PREFLIGHT_ACTIONS = [
    "read_jsonl_first_line",
    "read_json_body",
    "read_csv_header_if_data_file",
    "materialize_parquet_batch",
    "load_dataset_rows",
    "read_repository_source_body",
    "write_to_arxiv",
    "start_mining",
    "start_training",
    "load_checkpoint",
    "model_execution",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def extension(path: str) -> str:
    return Path(path).suffix.lower()


def route_examples(card: dict[str, Any], route: str, limit: int = 3) -> list[str]:
    examples = ((card.get("route_examples") or {}).get(route) or [])[:limit]
    return [str(item) for item in examples]


def selected_candidates(card: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in SELECTED_ROUTES:
        for rel_path in route_examples(card, route):
            ext = extension(rel_path)
            rows.append({
                "route": route,
                "relative_path": rel_path,
                "extension": ext,
                "allowed_zero_row_probe": ZERO_ROW_ALLOWED_PROBES.get(ext, ["metadata_path_only"]),
                "candidate_selected_from_existing_route_card": True,
                "arxiv_file_opened_now": False,
                "dataset_rows_loaded": False,
                "repository_source_bodies_loaded": False,
                "training_or_mining_authorized": False,
            })
    return rows


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    dataset_card = load_json(DATASET_CARD)
    candidates = selected_candidates(dataset_card)
    routes_present = {row["route"] for row in candidates}
    checks = {
        "source_stage8975_passed": source.get("passed") is True,
        "dataset_route_card_present": DATASET_CARD.exists(),
        "selected_routes_present": all(route in routes_present for route in SELECTED_ROUTES),
        "selected_candidates_present": len(candidates) >= 6,
        "zero_row_allowed_probes_recorded": bool(ZERO_ROW_ALLOWED_PROBES),
        "forbidden_prefight_actions_recorded": len(FORBIDDEN_PREFLIGHT_ACTIONS) >= 10,
        "no_arxiv_files_opened_now": all(row["arxiv_file_opened_now"] is False for row in candidates),
        "no_dataset_rows_loaded": all(row["dataset_rows_loaded"] is False for row in candidates),
        "no_repository_source_bodies_loaded": all(row["repository_source_bodies_loaded"] is False for row in candidates),
        "no_training_or_mining_authorized": all(row["training_or_mining_authorized"] is False for row in candidates),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8975_or_8976": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8975, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_SCHEMA_HEADER_PREFLIGHT_DESIGN_ONLY",
        "source_stage": 8975,
        "selected_routes": SELECTED_ROUTES,
        "zero_row_allowed_probes": ZERO_ROW_ALLOWED_PROBES,
        "forbidden_prefight_actions": FORBIDDEN_PREFLIGHT_ACTIONS,
        "selected_candidates": candidates,
        "checks": checks,
        "metrics": {
            "selected_candidates": len(candidates),
            "selected_routes": len(routes_present),
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
            "network_upload_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Zero-row schema/header preflight is designed but not executed. Selected candidates are copied from existing metadata route cards only; no /arxiv files, dataset rows, repository source bodies, schema probes, mining, training, or runtime execution are opened.",
    }


def validate_design(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8975, STAGE}:
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
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_design(registry)
    failures = validate_design(card, registry)
    selected = card["selected_candidates"]
    DESIGN.write_text(json.dumps({k: v for k, v in card.items() if k != "selected_candidates"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SELECTED.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "selected_candidates": str(SELECTED.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit the zero-row preflight design, then implement a dry-run preflight runner that still does not open /arxiv files unless a future explicit ticket allows metadata-only file access.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8976 Zero-Row Schema/Header Preflight Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs a zero-row schema/header preflight using only existing metadata route cards. It does not open `/arxiv` files, load dataset rows, read repository source bodies, execute schema probes, mine, train, or run models.",
        "",
        f"Selected candidates: `{summary['metrics']['selected_candidates']}`",
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
    marker = "## Stage8976 Zero-Row Schema/Header Preflight Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8976 designs a zero-row schema/header preflight from metadata route cards only. It keeps /arxiv file access, dataset rows, repository source bodies, schema/header probes, mining, training, and runtime closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
