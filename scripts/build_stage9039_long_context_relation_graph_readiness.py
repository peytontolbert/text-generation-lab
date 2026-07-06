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
STAGE = 9039
NAME = "stage9039_long_context_relation_graph_readiness"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9038_SUMMARY = ROOT / "runs/summaries/stage9038_long_context_no_data_scan_ticket.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_RELATION_GRAPH_READINESS_STAGE9039.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "long_context_relation_graph_readiness.json"

REQUIRED_FILES = [
    "scripts/long_context_relation_graph_builder.py",
    "scripts/build_stage8800_long_context_transition_dataset.py",
    "tests/test_long_context_transition_pipeline.py",
    "docs/LONG_CONTEXT_TRANSITION_DATASET_SPEC.md",
]

REQUIRED_EDGE_TYPES = [
    "chunk_mentions_entity",
    "entity_mentioned_by_chunk",
    "entity_co_mention",
    "adjacent_chunk",
    "same_source_chunk",
]

FORBIDDEN_OPERATIONS = [
    "RUN_RELATION_GRAPH_BUILDER_ON_ARXIV_NOW",
    "RUN_RELATION_GRAPH_BUILDER_ON_REPOSITORY_LIBRARY_NOW",
    "MATERIALIZE_LONG_CONTEXT_DATASET_NOW",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "START_TRAINING",
    "RUN_MODEL",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s9038 = load_json(SOURCE_9038_SUMMARY)
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    checks = {
        "source_stage9038_present": SOURCE_9038_SUMMARY.exists(),
        "source_stage9038_passed": s9038.get("passed") is True,
        "required_files_present": not missing,
        "edge_types_recorded": len(REQUIRED_EDGE_TYPES) == 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 7,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_RELATION_GRAPH_READINESS_NO_SCAN",
        "required_files": REQUIRED_FILES,
        "missing_files": missing,
        "required_edge_types": REQUIRED_EDGE_TYPES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_files": len(REQUIRED_FILES),
            "missing_files": len(missing),
            "edge_types": len(REQUIRED_EDGE_TYPES),
            "relation_graph_readiness_only": True,
            "relation_graph_builder_executed_on_corpus_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
            "long_context_dataset_materialized_now": False,
            "training_rows_materialized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recovered long-context relation graph construction as a local utility extension. No corpus scan, dataset materialization, or training is authorized.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "relation_graph_builder_executed_on_corpus_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
        "long_context_dataset_materialized_now",
        "training_rows_materialized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
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
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Keep long-context graph building in fixture/no-data-scan mode until explicit corpus-root authorization exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9039 Long-Context Relation Graph Readiness",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage indexes the relation graph extension for the long-context transition pipeline. It does not scan `/arxiv`, scan repository-library corpora, materialize datasets, train, or write backups.",
                "",
                f"Edge types: `{summary['metrics']['edge_types']}`",
                f"Relation graph corpus execution: `{summary['metrics']['relation_graph_builder_executed_on_corpus_now']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
