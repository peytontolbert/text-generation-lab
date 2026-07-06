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
NAME = "stage8977_zero_row_candidate_selector"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ZERO_ROW_CANDIDATE_SELECTOR_STAGE8977.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8976_zero_row_schema_preflight_design.json"
DESIGN = ROOT / "runs/local/artifacts/stage8976_zero_row_schema_preflight_design/zero_row_schema_preflight_design.json"
DATASET_INV = ROOT / "runs/local/artifacts/stage8973_arxiv_metadata_only_preflight/dataset_file_inventory_metadata_only.jsonl"
SELECTED = OUT_DIR / "selected_schema_candidate_paths_metadata_only.jsonl"
POLICY = OUT_DIR / "zero_row_candidate_selector_policy_card.json"
DECISION = OUT_DIR / "zero_row_candidate_selector_decision_card.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def is_named_candidate(row: dict[str, Any]) -> bool:
    text = f"{row.get('relative_path', '')}/{row.get('name', '')}".lower()
    return any(token in text for token in ["100m_swe_research_timeline", "repo_graph", "software_maintainer", "agentkernel", "swe"])


def is_parquet_candidate(row: dict[str, Any]) -> bool:
    return str(row.get("extension", "")).lower() == ".parquet"


def select_candidates(rows: list[dict[str, Any]], *, named_limit: int, parquet_limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for route_name, predicate, limit in [
        ("NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE", is_named_candidate, named_limit),
        ("PARQUET_TABLE_CANDIDATE", is_parquet_candidate, parquet_limit),
    ]:
        count = 0
        for row in rows:
            key = str(row.get("relative_path") or row.get("name") or "")
            if count >= limit:
                break
            if key in seen or not predicate(row):
                continue
            seen.add(key)
            count += 1
            selected.append({
                "selection_route": route_name,
                "relative_path": row.get("relative_path"),
                "name": row.get("name"),
                "extension": row.get("extension"),
                "size_bytes": row.get("size_bytes"),
                "is_file": row.get("is_file"),
                "is_symlink": row.get("is_symlink"),
                "metadata_only": True,
                "dataset_rows_loaded": False,
                "schema_or_header_read": False,
            })
    return selected


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_selector(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    design = load_json(DESIGN)
    inventory = read_jsonl(DATASET_INV)
    limits = design.get("candidate_limits") or {}
    selected = select_candidates(
        inventory,
        named_limit=int(limits.get("named_software_maintainer_dataset_candidates", 0)),
        parquet_limit=int(limits.get("parquet_candidates", 0)),
    )
    route_counts: dict[str, int] = {}
    for row in selected:
        route_counts[row["selection_route"]] = route_counts.get(row["selection_route"], 0) + 1
    policy = {
        "metadata_only": True,
        "selected_from_stage8973_inventory": True,
        "schema_or_header_read_performed": False,
        "dataset_rows_loaded": False,
        "repository_source_bodies_loaded": False,
        "jsonl_selected": False,
        "candidate_file_opened": False,
        "write_to_arxiv": False,
    }
    decision = {
        "selector_completed": True,
        "selected_candidates": len(selected),
        "route_counts": route_counts,
        "next_best_step": "Audit selected path metadata, then require a separate explicit ticket before any parquet footer schema access.",
    }
    checks = {
        "source_stage8976_passed": source.get("passed") is True,
        "design_present": DESIGN.exists(),
        "inventory_present": DATASET_INV.exists(),
        "inventory_rows_present": len(inventory) > 0,
        "selected_candidates_present": len(selected) > 0,
        "selected_jsonl_absent": not any(str(row.get("extension", "")).lower() == ".jsonl" for row in selected),
        "metadata_only_policy_true": policy["metadata_only"] is True,
        "candidate_files_not_opened": policy["candidate_file_opened"] is False,
        "schema_or_header_not_read": policy["schema_or_header_read_performed"] is False,
        "dataset_rows_not_loaded": policy["dataset_rows_loaded"] is False,
        "repository_source_bodies_not_loaded": policy["repository_source_bodies_loaded"] is False,
        "arxiv_write_closed": policy["write_to_arxiv"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8976_or_8977": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8976, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ZERO_ROW_CANDIDATE_SELECTOR",
        "selected_candidates": selected,
        "policy": policy,
        "decision_card": decision,
        "checks": checks,
        "metrics": {
            "inventory_rows_seen": len(inventory),
            "selected_candidates": len(selected),
            "selected_named_candidates": route_counts.get("NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE", 0),
            "selected_parquet_candidates": route_counts.get("PARQUET_TABLE_CANDIDATE", 0),
            "selected_jsonl_candidates": 0,
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
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
        "decision": "Zero-row candidate selector emitted selected path metadata only from existing inventory artifacts. It did not open candidate files, read schemas/headers/rows, read repository bodies, or authorize mining/training.",
    }


def validate_selector(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8976, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "candidate_file_opened",
        "schema_or_header_read_performed",
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
    card = build_selector(registry)
    failures = validate_selector(card, registry)
    write_jsonl(SELECTED, card["selected_candidates"])
    POLICY.write_text(json.dumps(card["policy"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DECISION.write_text(json.dumps(card["decision_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card_for_disk = {key: value for key, value in card.items() if key != "selected_candidates"}
    (OUT_DIR / "zero_row_candidate_selector.json").write_text(json.dumps(card_for_disk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {
            "selected_candidates": str(SELECTED.relative_to(ROOT)),
            "policy_card": str(POLICY.relative_to(ROOT)),
            "decision_card": str(DECISION.relative_to(ROOT)),
        },
        "decision": card["decision"],
        "next_best_step": "Audit selected candidate metadata. A separate explicit ticket is required before any parquet footer schema access or dataset-body read.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8977 Zero-Row Candidate Selector",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage selects candidate path metadata from existing Stage8973 inventory artifacts only. It does not open selected files, read schemas, read headers, parse rows, read repository source bodies, mine, train, or touch `/arxiv`.",
        "",
        f"Selected candidates: `{summary['metrics']['selected_candidates']}`",
        f"Selected named candidates: `{summary['metrics']['selected_named_candidates']}`",
        f"Selected parquet candidates: `{summary['metrics']['selected_parquet_candidates']}`",
        f"Selected JSONL candidates: `{summary['metrics']['selected_jsonl_candidates']}`",
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
    marker = "## Stage8977 Zero-Row Candidate Selector"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8977 selects metadata-only candidate paths for a future schema preflight. It opens no selected files and keeps row/source-body reads, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
