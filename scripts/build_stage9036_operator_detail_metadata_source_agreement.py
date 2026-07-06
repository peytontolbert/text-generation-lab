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
STAGE = 9036
NAME = "stage9036_operator_detail_metadata_source_agreement"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9035_SUMMARY = ROOT / "runs/summaries/stage9035_operator_detail_recovery_ticket_contract.json"
SOURCE_9035_CONTRACT = ROOT / "runs/local/artifacts/stage9035_operator_detail_recovery_ticket_contract/operator_detail_recovery_ticket_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_DETAIL_METADATA_SOURCE_AGREEMENT_STAGE9036.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AGREEMENT = OUT_DIR / "operator_detail_metadata_source_agreement.json"

APPROVED_METADATA_SOURCE_CLASSES = [
    {
        "source_class": "recovered_stage_summaries",
        "allowed_examples": [
            "runs/summaries/stage8703_low_level_training_concept_session_grep.json",
            "runs/summaries/stage9033_operator_detail_seed_catalog.json",
            "runs/summaries/stage9034_operator_detail_seed_gap_matrix.json",
        ],
        "allowed_use": "stage names, metrics, operator IDs, operator names, layer labels, reason-code names, and already summarized metadata.",
        "forbidden_use": "copying raw embedded session text, source code bodies, row bodies, generated patches, or hidden payloads.",
    },
    {
        "source_class": "recovered_artifact_summaries",
        "allowed_examples": [
            "runs/local/artifacts/stage8718_operator_codelength_interface_readiness/operator_inventory.json",
            "runs/local/artifacts/stage9033_operator_detail_seed_catalog/operator_detail_seed_catalog.json",
        ],
        "allowed_use": "operator/category inventories, codelength field names, opaque detail refs, coverage counts, and hashes.",
        "forbidden_use": "training row materialization or raw payload expansion.",
    },
    {
        "source_class": "human_authored_metadata_patch",
        "allowed_examples": ["future reviewed operator_detail_metadata_patch.jsonl"],
        "allowed_use": "manual symbolic metadata for inputs, outputs, confidence semantics, failure modes, label source refs, and metric names.",
        "forbidden_use": "unreviewed model-generated detail fields or raw source/session excerpts.",
    },
    {
        "source_class": "existing_docs_metadata_only",
        "allowed_examples": ["docs/*.md with explicit recovery-stage references"],
        "allowed_use": "short metadata facts already summarized in docs with provenance.",
        "forbidden_use": "bulk importing documentation prose as operator detail payload.",
    },
]

FORBIDDEN_SOURCE_CLASSES = [
    "raw_codex_session_text",
    "raw_repository_source_body",
    "raw_row_body_text",
    "hidden_or_locked_eval_payload",
    "model_generated_operator_detail_without_audit",
    "runtime_output_payload",
    "gemma_or_teacher_output_without_verifier",
]

FUTURE_REQUIRED_PROOFS = [
    "source_class_recorded_per_detail_field",
    "source_path_or_stage_ref_recorded_per_detail_field",
    "raw_payload_absence_scan_passed",
    "detail_hash_present_for_recovered_rows",
    "operator_id_category_match_stage9033_seed",
    "training_ready_status_stays_false_until_full_audit",
]

FORBIDDEN_OPERATIONS = [
    "INSTANTIATE_OPERATOR_DETAIL_TICKET_NOW",
    "RECOVER_OPERATOR_DETAILS_NOW",
    "READ_RAW_SESSION_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "READ_ROW_BODY_TEXT",
    "MATERIALIZE_OPERATOR_DETAIL_PATCH_NOW",
    "MATERIALIZE_TRAINING_ROWS_NOW",
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "MATERIALIZE_MANIFEST_NOW",
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


def build_agreement(registry: dict[str, Any]) -> dict[str, Any]:
    s9035 = load_json(SOURCE_9035_SUMMARY)
    c9035 = load_json(SOURCE_9035_CONTRACT)
    approved_names = {row["source_class"] for row in APPROVED_METADATA_SOURCE_CLASSES}
    ticket_sources = set(c9035.get("allowed_metadata_sources") or [])
    checks = {
        "source_stage9035_present": SOURCE_9035_SUMMARY.exists() and SOURCE_9035_CONTRACT.exists(),
        "source_stage9035_passed": s9035.get("passed") is True,
        "approved_source_classes_recorded": len(APPROVED_METADATA_SOURCE_CLASSES) >= 4,
        "forbidden_source_classes_recorded": len(FORBIDDEN_SOURCE_CLASSES) >= 7,
        "future_required_proofs_recorded": len(FUTURE_REQUIRED_PROOFS) >= 6,
        "ticket_allowed_sources_not_empty": bool(ticket_sources),
        "source_classes_are_metadata_only": all("raw" not in name for name in approved_names),
        "raw_payload_sources_forbidden": {"raw_codex_session_text", "raw_repository_source_body", "raw_row_body_text"}.issubset(FORBIDDEN_SOURCE_CLASSES),
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 17,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_DETAIL_METADATA_SOURCE_AGREEMENT_NO_EXECUTION",
        "approved_metadata_source_classes": APPROVED_METADATA_SOURCE_CLASSES,
        "forbidden_source_classes": FORBIDDEN_SOURCE_CLASSES,
        "future_required_proofs": FUTURE_REQUIRED_PROOFS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "approved_metadata_source_classes": len(APPROVED_METADATA_SOURCE_CLASSES),
            "forbidden_source_classes": len(FORBIDDEN_SOURCE_CLASSES),
            "future_required_proofs": len(FUTURE_REQUIRED_PROOFS),
            "metadata_source_agreement_only": True,
            "operator_detail_ticket_instantiated_now": False,
            "operator_details_recovered_now": False,
            "operator_detail_patch_materialized_now": False,
            "raw_session_text_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "training_rows_materialized_now": False,
            "judge_executed_now": False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
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
        "decision": "Metadata-only source classes are agreed for future operator-detail recovery; no ticket is instantiated and no raw payloads are read.",
    }


def validate_agreement(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for forbidden in ["raw_codex_session_text", "raw_repository_source_body", "raw_row_body_text"]:
        if forbidden not in card.get("forbidden_source_classes", []):
            failures.append(f"missing_forbidden_source:{forbidden}")
    for key in [
        "operator_detail_ticket_instantiated_now",
        "operator_details_recovered_now",
        "operator_detail_patch_materialized_now",
        "raw_session_text_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "training_rows_materialized_now",
        "judge_executed_now",
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "trainer_dry_run_execution_authorized_now",
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
    card = build_agreement(registry)
    failures = validate_agreement(card)
    AGREEMENT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"agreement": str(AGREEMENT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Only after this source agreement, instantiate a metadata-only operator-detail recovery ticket; keep raw payloads, mining, and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9036 Operator Detail Metadata Source Agreement",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage agrees metadata-only source classes for future operator-detail recovery. It does not instantiate the ticket, recover details, read raw payloads, materialize rows, run a judge, compile a manifest, train, mine, or write `/arxiv`.",
                "",
                f"Approved metadata source classes: `{summary['metrics']['approved_metadata_source_classes']}`",
                f"Forbidden source classes: `{summary['metrics']['forbidden_source_classes']}`",
                f"Operator details recovered now: `{summary['metrics']['operator_details_recovered_now']}`",
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
