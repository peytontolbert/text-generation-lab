#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8974
NAME = "stage8974_metadata_inventory_route_selector"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_INVENTORY_ROUTE_SELECTOR_STAGE8974.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8973_arxiv_metadata_only_preflight.json"
DATASET_INV = ROOT / "runs/local/artifacts/stage8973_arxiv_metadata_only_preflight/dataset_file_inventory_metadata_only.jsonl"
REPO_INV = ROOT / "runs/local/artifacts/stage8973_arxiv_metadata_only_preflight/repository_root_inventory_metadata_only.jsonl"

DATASET_CARD = OUT_DIR / "dataset_route_card_metadata_only.json"
REPO_CARD = OUT_DIR / "repository_route_card_metadata_only.json"
DECISION_CARD = OUT_DIR / "metadata_inventory_route_selector_decision_card.json"

DATASET_PRIORITY_NAMES = [
    "100m_swe_research_timeline",
    "repo_graph",
    "software_maintainer",
    "agentkernel",
    "swe",
]

REPOSITORY_PRIORITY_NAMES = [
    "agentkernel",
    "text-generation-lab",
    "repository_library",
    "parameter-golf",
    "code",
    "compiler",
]

DATASET_EXT_ROUTES = {
    ".parquet": "PARQUET_TABLE_CANDIDATE",
    ".jsonl": "JSONL_MANIFEST_CANDIDATE",
    ".json": "JSON_METADATA_CANDIDATE",
    ".csv": "CSV_TABLE_CANDIDATE",
    ".arrow": "ARROW_TABLE_CANDIDATE",
}

FORBIDDEN_NEXT_ACTIONS = [
    "read_dataset_rows_without_route_card_audit",
    "read_repository_source_body_without_source_body_ticket",
    "write_to_arxiv",
    "start_mining",
    "start_training",
    "load_checkpoint",
    "runtime_execution",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def dataset_route(row: dict[str, Any]) -> str:
    rel = str(row.get("relative_path", "")).lower()
    name = str(row.get("name", "")).lower()
    ext = str(row.get("extension", "")).lower()
    text = f"{rel}/{name}"
    if any(token in text for token in DATASET_PRIORITY_NAMES):
        return "NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE"
    if ext in DATASET_EXT_ROUTES:
        return DATASET_EXT_ROUTES[ext]
    return "HOLD_UNKNOWN_METADATA_ONLY"


def repository_route(row: dict[str, Any]) -> str:
    name = str(row.get("name", "")).lower()
    if any(token in name for token in REPOSITORY_PRIORITY_NAMES):
        return "PRIORITY_SOFTWARE_REPOSITORY_CANDIDATE"
    return "REPOSITORY_ROOT_METADATA_ONLY"


def summarize_routes(rows: Iterable[dict[str, Any]], router) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    extensions: Counter[str] = Counter()
    for row in rows:
        route = router(row)
        counts[route] += 1
        rel = str(row.get("relative_path") or row.get("name") or "")
        if len(examples[route]) < 10:
            examples[route].append(rel)
        if row.get("extension"):
            extensions[str(row["extension"])] += 1
    return {
        "route_counts": dict(sorted(counts.items())),
        "route_examples": dict(sorted(examples.items())),
        "extension_counts": dict(extensions.most_common(25)),
    }


def build_selector(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    dataset_rows = read_jsonl(DATASET_INV)
    repo_rows = read_jsonl(REPO_INV)
    dataset_card = summarize_routes(dataset_rows, dataset_route)
    repo_card = summarize_routes(repo_rows, repository_route)
    decision = {
        "selector_completed": True,
        "metadata_only": True,
        "dataset_rows_loaded": False,
        "repository_source_bodies_loaded": False,
        "training_or_mining_authorized": False,
        "recommended_next": "Run selector audit, then design a zero-row schema/header preflight for selected dataset candidates only if explicitly authorized.",
        "forbidden_next_actions": FORBIDDEN_NEXT_ACTIONS,
    }
    checks = {
        "source_stage8973_passed": source.get("passed") is True,
        "dataset_inventory_present": DATASET_INV.exists(),
        "repository_inventory_present": REPO_INV.exists(),
        "dataset_inventory_rows_present": len(dataset_rows) > 0,
        "repository_inventory_rows_present": len(repo_rows) > 0,
        "metadata_only_decision": decision["metadata_only"] is True,
        "dataset_rows_not_loaded": decision["dataset_rows_loaded"] is False,
        "repository_source_bodies_not_loaded": decision["repository_source_bodies_loaded"] is False,
        "training_or_mining_closed": decision["training_or_mining_authorized"] is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8973_or_8974": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8973, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_INVENTORY_ROUTE_SELECTOR",
        "dataset_card": dataset_card,
        "repository_card": repo_card,
        "decision_card": decision,
        "checks": checks,
        "metrics": {
            "dataset_inventory_rows_seen": len(dataset_rows),
            "repository_inventory_rows_seen": len(repo_rows),
            "dataset_routes": len(dataset_card["route_counts"]),
            "repository_routes": len(repo_card["route_counts"]),
            "named_dataset_candidates": dataset_card["route_counts"].get("NAMED_SOFTWARE_MAINTAINER_DATASET_CANDIDATE", 0),
            "priority_repository_candidates": repo_card["route_counts"].get("PRIORITY_SOFTWARE_REPOSITORY_CANDIDATE", 0),
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
        "decision": "Metadata inventory route selector completed using only Stage8973 metadata artifacts. It selects candidate dataset and repository routes without reading row bodies or source bodies and without authorizing mining/training.",
    }


def validate_selector(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8973, STAGE}:
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
    card = build_selector(registry)
    failures = validate_selector(card, registry)
    DATASET_CARD.write_text(json.dumps(card["dataset_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPO_CARD.write_text(json.dumps(card["repository_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DECISION_CARD.write_text(json.dumps(card["decision_card"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            "dataset_route_card": str(DATASET_CARD.relative_to(ROOT)),
            "repository_route_card": str(REPO_CARD.relative_to(ROOT)),
            "decision_card": str(DECISION_CARD.relative_to(ROOT)),
        },
        "decision": card["decision"],
        "next_best_step": "Audit the metadata route selector, then design a zero-row dataset schema/header preflight for selected candidates. Do not read dataset rows or repository source bodies yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8974 Metadata Inventory Route Selector",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage routes Stage8973 metadata inventory entries only. It does not touch `/arxiv`, read dataset rows, read repository source bodies, mine, train, or execute runtime.",
        "",
        f"Dataset inventory rows seen: `{summary['metrics']['dataset_inventory_rows_seen']}`",
        f"Repository inventory rows seen: `{summary['metrics']['repository_inventory_rows_seen']}`",
        f"Named dataset candidates: `{summary['metrics']['named_dataset_candidates']}`",
        f"Priority repository candidates: `{summary['metrics']['priority_repository_candidates']}`",
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
    marker = "## Stage8974 Metadata Inventory Route Selector"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8974 routes Stage8973 metadata inventory entries into candidate dataset/repository buckets without touching /arxiv or reading bodies. It keeps mining and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
