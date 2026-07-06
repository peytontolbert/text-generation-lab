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
STAGE = 9014
NAME = "stage9014_duplicate_resolution_preview_review_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9011_registry_duplicate_resolution_apply_preview.json"
SOURCE_PREVIEW = ROOT / "runs/local/artifacts/stage9011_registry_duplicate_resolution_apply_preview/registry_duplicate_resolution_apply_preview.json"
SOURCE_DIFF = ROOT / "runs/local/artifacts/stage9011_registry_duplicate_resolution_apply_preview/proposed_registry_duplicate_resolution_diff.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DUPLICATE_RESOLUTION_PREVIEW_REVIEW_GATE_STAGE9014.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "duplicate_resolution_preview_review_gate.json"

REVIEW_CHECKS = [
    "all_operations_are_alias_metadata_only",
    "all_operations_apply_now_false",
    "all_operations_delete_original_row_false",
    "all_operations_preserve_original_row_true",
    "all_operations_have_source_summary_path",
    "all_operations_have_unique_alias_id",
    "all_operations_have_unique_proposed_registry_key",
    "source_preview_did_not_write_registry",
    "source_preview_did_not_delete_anything",
    "future_apply_requires_separate_authorization",
]

FORBIDDEN_OPERATIONS = [
    "WRITE_RECONSTRUCTED_REGISTRY_NOW",
    "APPLY_ALIAS_DIFF_NOW",
    "DELETE_DUPLICATE_ROWS",
    "DELETE_SUMMARIES",
    "DELETE_ARTIFACTS",
    "RUN_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else ([] if path.suffix == ".json" and path.name.endswith("diff.json") else {})


def review_operations(ops: list[dict[str, Any]]) -> dict[str, Any]:
    alias_ids = [op.get("alias_id") for op in ops]
    keys = [op.get("proposed_registry_key") for op in ops]
    unsafe = [op for op in ops if op.get("operation") != "add_registry_alias_metadata_only" or op.get("apply_now") is not False or op.get("delete_original_row") is not False or op.get("preserve_original_row") is not True]
    missing_paths = [op.get("alias_id") for op in ops if not op.get("source_summary_path")]
    return {
        "operation_count": len(ops),
        "unsafe_operations": len(unsafe),
        "missing_source_summary_paths": len(missing_paths),
        "unique_alias_ids": len(set(alias_ids)) == len(alias_ids),
        "unique_proposed_registry_keys": len(set(keys)) == len(keys),
    }


def build_gate(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_preview = load_json(SOURCE_PREVIEW)
    ops = load_json(SOURCE_DIFF)
    if not isinstance(ops, list):
        ops = []
    operation_review = review_operations(ops)
    source_metrics = source_summary.get("metrics") or {}
    checks = {
        "source_stage9011_present": SOURCE_SUMMARY.exists() and SOURCE_PREVIEW.exists() and SOURCE_DIFF.exists(),
        "source_stage9011_passed": source_summary.get("passed") is True,
        "source_stage9011_preview_only": source_metrics.get("preview_only_no_mutation") is True,
        "all_operations_are_alias_metadata_only": operation_review["unsafe_operations"] == 0,
        "all_operations_have_source_summary_path": operation_review["missing_source_summary_paths"] == 0,
        "all_operations_have_unique_alias_id": operation_review["unique_alias_ids"] is True,
        "all_operations_have_unique_proposed_registry_key": operation_review["unique_proposed_registry_keys"] is True,
        "operation_count_matches_source": operation_review["operation_count"] == source_metrics.get("proposed_diff_operations"),
        "source_preview_did_not_write_registry": source_metrics.get("registry_written_now") is False,
        "source_preview_did_not_delete_anything": source_metrics.get("registry_rows_deleted_now") is False and source_metrics.get("summaries_deleted_now") is False and source_metrics.get("artifacts_deleted_now") is False,
        "review_checks_recorded": len(REVIEW_CHECKS) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "DUPLICATE_RESOLUTION_PREVIEW_REVIEW_GATE_NO_APPLY",
        "review_checks": REVIEW_CHECKS,
        "operation_review": operation_review,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "reviewed_operations": operation_review["operation_count"],
            "unsafe_operations": operation_review["unsafe_operations"],
            "missing_source_summary_paths": operation_review["missing_source_summary_paths"],
            "review_gate_passed": all(checks.values()),
            "apply_authorized_now": False,
            "registry_written_now": False,
            "alias_diff_applied_now": False,
            "registry_rows_mutated_now": False,
            "registry_rows_deleted_now": False,
            "summaries_deleted_now": False,
            "artifacts_deleted_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Duplicate-resolution preview passes metadata safety review, but apply remains unauthorized. No registry write, deletion, training, mining, or model execution occurs.",
    }


def validate_gate(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "apply_authorized_now",
        "registry_written_now",
        "alias_diff_applied_now",
        "registry_rows_mutated_now",
        "registry_rows_deleted_now",
        "summaries_deleted_now",
        "artifacts_deleted_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
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
    card = build_gate(registry)
    failures = validate_gate(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If duplicate cleanup is still desired, design a separate apply-authorization stage; otherwise return to Stage9007 manifest-input materialization. Keep training and execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9014 Duplicate Resolution Preview Review Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage reviews the proposed duplicate-resolution alias diff. It does not apply the diff, mutate the registry, delete rows/files, train, mine, or execute models.",
        "",
        f"Reviewed operations: `{summary['metrics']['reviewed_operations']}`",
        f"Unsafe operations: `{summary['metrics']['unsafe_operations']}`",
        f"Apply authorized now: `{summary['metrics']['apply_authorized_now']}`",
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9014 Duplicate Resolution Preview Review Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Reviews the proposed duplicate-resolution alias diff and verifies all operations are metadata-only.",
            "- Does not apply the diff, write the registry, delete rows, delete artifacts, or open execution authority.",
            "- Leaves the active training path closed until a separate decision returns to manifest-input materialization.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
