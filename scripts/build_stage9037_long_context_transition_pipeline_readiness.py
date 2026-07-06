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
STAGE = 9037
NAME = "stage9037_long_context_transition_pipeline_readiness"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_TRANSITION_PIPELINE_READINESS_STAGE9037.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "long_context_transition_pipeline_readiness.json"

REQUIRED_FILES = [
    "docs/LONG_CONTEXT_TRANSITION_DATASET_SPEC.md",
    "scripts/long_context_common.py",
    "scripts/long_context_chunk_catalog.py",
    "scripts/long_context_entity_linker.py",
    "scripts/long_context_program_builder.py",
    "scripts/long_context_example_renderer.py",
    "scripts/long_context_shortcut_audit.py",
    "scripts/build_stage8800_long_context_transition_dataset.py",
    "tests/test_long_context_transition_pipeline.py",
]

REQUIRED_PIPELINE_STEPS = [
    "chunk_catalog",
    "entity_linking",
    "latent_transition_program_builder",
    "long_context_example_renderer",
    "shortcut_quality_audit",
]

FORBIDDEN_OPERATIONS = [
    "SCAN_ARXIV_NOW",
    "SCAN_REPOSITORY_LIBRARY_NOW",
    "MATERIALIZE_LONG_CONTEXT_DATASET_NOW",
    "WRITE_TO_ARXIV",
    "RUN_MODEL",
    "RUN_TRAINING",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    checks = {
        "required_files_present": not missing,
        "pipeline_steps_recorded": len(REQUIRED_PIPELINE_STEPS) == 5,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 8,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_TRANSITION_PIPELINE_READINESS_NO_DATA_SCAN",
        "required_files": REQUIRED_FILES,
        "missing_files": missing,
        "required_pipeline_steps": REQUIRED_PIPELINE_STEPS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_files": len(REQUIRED_FILES),
            "missing_files": len(missing),
            "pipeline_steps": len(REQUIRED_PIPELINE_STEPS),
            "readiness_audit_only": True,
            "arxiv_scan_attempted": False,
            "repository_library_scan_attempted": False,
            "long_context_dataset_materialized_now": False,
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
        "decision": "Recovered a local long-context transition dataset utility pipeline, but this stage is readiness-only and authorizes no corpus scan, mining, training, or /arxiv write.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "arxiv_scan_attempted",
        "repository_library_scan_attempted",
        "long_context_dataset_materialized_now",
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
        "next_best_step": "Add an explicit no-data-scan execution ticket before using the long-context pipeline on /arxiv or repository-library corpora.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9037 Long-Context Transition Pipeline Readiness",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage indexes the recovered long-context transition utility pipeline. It does not scan `/arxiv`, scan repository-library corpora, materialize datasets, train, run models, or write backups.",
                "",
                f"Pipeline steps: `{summary['metrics']['pipeline_steps']}`",
                f"Missing files: `{summary['metrics']['missing_files']}`",
                f"Data mining authorized: `{summary['metrics']['data_mining_authorized']}`",
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
