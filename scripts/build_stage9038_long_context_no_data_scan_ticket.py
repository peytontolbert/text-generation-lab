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
STAGE = 9038
NAME = "stage9038_long_context_no_data_scan_ticket"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9037_SUMMARY = ROOT / "runs/summaries/stage9037_long_context_transition_pipeline_readiness.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_NO_DATA_SCAN_TICKET_STAGE9038.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "long_context_no_data_scan_ticket.json"

TICKET_REQUIRED_FIELDS = [
    "ticket_id",
    "source_stage",
    "mode",
    "allowed_roots",
    "forbidden_roots",
    "max_files_per_root",
    "max_chars_per_file",
    "output_dir",
    "required_outputs",
    "quality_gates",
    "authority",
]

ALLOWED_ROOT_POLICY = [
    "synthetic_tmp_fixture_only_by_default",
    "repo_local_fixture_only_without_separate_user_approval",
    "explicit_future_ticket_required_for_arxiv_roots",
    "explicit_future_ticket_required_for_repository_library_roots",
]

FORBIDDEN_ROOTS_BY_DEFAULT = [
    "/arxiv",
    "/arxiv/datasets",
    "/arxiv/repositories",
    "/data/repository_library",
    "/data/repository_library/exports/corpus/papers",
]

REQUIRED_OUTPUTS = [
    "chunks.jsonl",
    "source_inventory.json",
    "entities.jsonl",
    "entity_aliases.json",
    "programs.jsonl",
    "examples.jsonl",
    "quality_audits.jsonl",
    "examples_accepted.jsonl",
    "summary.json",
]

QUALITY_GATES = [
    "source_inventory_exists",
    "accepted_examples_recorded",
    "single_chunk_shortcut_audited",
    "last_chunk_shortcut_audited",
    "lexical_topk_shortcut_audited",
    "no_training_rows_exported",
    "no_arxiv_write",
]

FORBIDDEN_OPERATIONS = [
    "RUN_LONG_CONTEXT_PIPELINE_ON_ARXIV_NOW",
    "RUN_LONG_CONTEXT_PIPELINE_ON_REPOSITORY_LIBRARY_NOW",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_ticket(registry: dict[str, Any]) -> dict[str, Any]:
    s9037 = load_json(SOURCE_9037_SUMMARY)
    checks = {
        "source_stage9037_present": SOURCE_9037_SUMMARY.exists(),
        "source_stage9037_passed": s9037.get("passed") is True,
        "ticket_required_fields_recorded": len(TICKET_REQUIRED_FIELDS) >= 11,
        "allowed_root_policy_recorded": len(ALLOWED_ROOT_POLICY) >= 4,
        "forbidden_roots_recorded": len(FORBIDDEN_ROOTS_BY_DEFAULT) >= 5,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 9,
        "quality_gates_recorded": len(QUALITY_GATES) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LONG_CONTEXT_NO_DATA_SCAN_TICKET_NO_EXECUTION",
        "ticket_template": {
            "ticket_id": "future_long_context_synthetic_fixture_or_explicit_root_ticket",
            "source_stage": "stage9037_long_context_transition_pipeline_readiness",
            "mode": "synthetic_fixture_only_by_default",
            "allowed_roots": ALLOWED_ROOT_POLICY,
            "forbidden_roots": FORBIDDEN_ROOTS_BY_DEFAULT,
            "max_files_per_root": 20,
            "max_chars_per_file": 120_000,
            "output_dir": "runs/local/artifacts/long_context_transition_future_ticket",
            "required_outputs": REQUIRED_OUTPUTS,
            "quality_gates": QUALITY_GATES,
            "authority": dict(AUTHORITY_CLOSED),
        },
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "ticket_required_fields": len(TICKET_REQUIRED_FIELDS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "quality_gates": len(QUALITY_GATES),
            "ticket_contract_only": True,
            "long_context_pipeline_executed_now": False,
            "arxiv_scan_authorized_now": False,
            "repository_library_scan_authorized_now": False,
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
        "decision": "Defined a future long-context execution ticket that defaults to synthetic/repo-local fixtures only. No corpus scan or dataset materialization is authorized now.",
    }


def validate_ticket(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    ticket = card.get("ticket_template") or {}
    if any((ticket.get("authority") or {}).values()):
        failures.append("ticket_authority_open")
    for forbidden in FORBIDDEN_ROOTS_BY_DEFAULT:
        if forbidden not in ticket.get("forbidden_roots", []):
            failures.append(f"missing_forbidden_root:{forbidden}")
    for key in [
        "long_context_pipeline_executed_now",
        "arxiv_scan_authorized_now",
        "repository_library_scan_authorized_now",
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
    card = build_ticket(registry)
    failures = validate_ticket(card)
    TICKET.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Use only synthetic/repo-local fixture mode until a separate explicit corpus-root authorization ticket exists.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9038 Long-Context No-Data-Scan Ticket",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage defines a future ticket for long-context pipeline execution. The default is synthetic/repo-local fixtures only; `/arxiv` and repository-library roots remain forbidden without a separate ticket.",
                "",
                f"Required outputs: `{summary['metrics']['required_outputs']}`",
                f"Long-context pipeline executed now: `{summary['metrics']['long_context_pipeline_executed_now']}`",
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
