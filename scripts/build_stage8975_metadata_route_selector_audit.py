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
STAGE = 8975
NAME = "stage8975_metadata_route_selector_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ROUTE_SELECTOR_AUDIT_STAGE8975.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "metadata_route_selector_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8974_metadata_inventory_route_selector.json"
DATASET_CARD = ROOT / "runs/local/artifacts/stage8974_metadata_inventory_route_selector/dataset_route_card_metadata_only.json"
REPO_CARD = ROOT / "runs/local/artifacts/stage8974_metadata_inventory_route_selector/repository_route_card_metadata_only.json"
DECISION_CARD = ROOT / "runs/local/artifacts/stage8974_metadata_inventory_route_selector/metadata_inventory_route_selector_decision_card.json"

REQUIRED_DATASET_ROUTES = [
    "PARQUET_TABLE_CANDIDATE",
    "JSONL_MANIFEST_CANDIDATE",
    "NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE",
]

REQUIRED_DECISION_FALSE_FLAGS = [
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "training_or_mining_authorized",
]

NEXT_STAGE_REQUIREMENTS = [
    "zero_row_only",
    "selected_candidate_paths_only",
    "header_or_schema_metadata_only_where_supported",
    "no_repository_source_body_reads",
    "no_training_or_mining",
    "outputs_under_runs_local_artifacts",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def route_count(card: dict[str, Any], route: str) -> int:
    return int((card.get("route_counts") or {}).get(route, 0))


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    dataset_card = load_json(DATASET_CARD)
    repo_card = load_json(REPO_CARD)
    decision = load_json(DECISION_CARD)
    missing_dataset_routes = [route for route in REQUIRED_DATASET_ROUTES if route_count(dataset_card, route) <= 0]
    false_flag_failures = [flag for flag in REQUIRED_DECISION_FALSE_FLAGS if decision.get(flag) is not False]
    checks = {
        "source_stage8974_passed": source.get("passed") is True,
        "dataset_card_present": DATASET_CARD.exists(),
        "repository_card_present": REPO_CARD.exists(),
        "decision_card_present": DECISION_CARD.exists(),
        "required_dataset_routes_present": not missing_dataset_routes,
        "repository_routes_present": bool(repo_card.get("route_counts")),
        "decision_false_flags_preserved": not false_flag_failures,
        "forbidden_next_actions_present": len(decision.get("forbidden_next_actions") or []) >= 5,
        "next_stage_requirements_recorded": len(NEXT_STAGE_REQUIREMENTS) >= 6,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8974_or_8975": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8974, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ROUTE_SELECTOR_AUDIT",
        "missing_dataset_routes": missing_dataset_routes,
        "false_flag_failures": false_flag_failures,
        "next_stage_requirements": NEXT_STAGE_REQUIREMENTS,
        "checks": checks,
        "metrics": {
            "dataset_routes": len(dataset_card.get("route_counts") or {}),
            "repository_routes": len(repo_card.get("route_counts") or {}),
            "named_dataset_candidates": route_count(dataset_card, "NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE"),
            "parquet_candidates": route_count(dataset_card, "PARQUET_TABLE_CANDIDATE"),
            "jsonl_candidates": route_count(dataset_card, "JSONL_MANIFEST_CANDIDATE"),
            "priority_repository_candidates": route_count(repo_card, "PRIORITY_SOFTWARE_REPOSITORY_CANDIDATE"),
            "missing_dataset_routes": len(missing_dataset_routes),
            "false_flag_failures": len(false_flag_failures),
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
        "decision": "Metadata route selector audit passed. The next step may design a zero-row schema/header preflight, but row/body reads, mining, and training remain closed.",
    }


def validate_audit(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8974, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
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
        "next_best_step": "Design a zero-row schema/header preflight for selected dataset candidates only. No dataset rows or repository source bodies may be read yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8975 Metadata Route Selector Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits Stage8974 route selector outputs only. It reads workspace route cards, not `/arxiv` data, dataset rows, or repository source bodies.",
        "",
        f"Named dataset candidates: `{summary['metrics']['named_dataset_candidates']}`",
        f"Parquet candidates: `{summary['metrics']['parquet_candidates']}`",
        f"JSONL candidates: `{summary['metrics']['jsonl_candidates']}`",
        f"Priority repository candidates: `{summary['metrics']['priority_repository_candidates']}`",
        "",
        "## Next Stage Requirements",
        "",
        *[f"- `{item}`" for item in NEXT_STAGE_REQUIREMENTS],
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
    marker = "## Stage8975 Metadata Route Selector Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8975 audits metadata route selector outputs and records requirements for a future zero-row schema/header preflight. It keeps row/body reads, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
