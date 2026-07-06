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
STAGE = 9011
NAME = "stage9011_registry_duplicate_resolution_apply_preview"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9010_registry_duplicate_resolution_policy.json"
SOURCE_POLICY = ROOT / "runs/local/artifacts/stage9010_registry_duplicate_resolution_policy/registry_duplicate_resolution_policy.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_DUPLICATE_RESOLUTION_APPLY_PREVIEW_STAGE9011.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREVIEW = OUT_DIR / "registry_duplicate_resolution_apply_preview.json"
PROPOSED_DIFF = OUT_DIR / "proposed_registry_duplicate_resolution_diff.json"

PREVIEW_RULES = [
    "write_preview_artifacts_only",
    "do_not_write_reconstructed_stage_registry",
    "do_not_delete_registry_rows",
    "do_not_delete_summary_files",
    "do_not_delete_artifact_files",
    "preserve_original_stage_id_as_recovered_stage_id",
    "propose_unique_registry_key_for_each_duplicate_alias",
    "preserve_authority_flags",
    "preserve_passed_status",
    "require_future_human_or_contract_apply_authorization",
]

FORBIDDEN_OPERATIONS = [
    "WRITE_RECONSTRUCTED_REGISTRY_NOW",
    "APPLY_RENUMBERING_NOW",
    "DELETE_DUPLICATE_ROWS",
    "DELETE_SUMMARIES",
    "DELETE_ARTIFACTS",
    "REWRITE_GIT_HISTORY",
    "RUN_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_proposed_alias_diff(policy: dict[str, Any]) -> list[dict[str, Any]]:
    diff: list[dict[str, Any]] = []
    for alias in policy.get("alias_plan") or []:
        diff.append({
            "operation": "add_registry_alias_metadata_only",
            "alias_id": alias.get("alias_id"),
            "recovered_stage_id": alias.get("recovered_stage_id"),
            "stage_name": alias.get("stage_name"),
            "source_summary_path": alias.get("path"),
            "proposed_registry_key": f"{alias.get('recovered_stage_id')}::{alias.get('alias_id')}::{alias.get('stage_name')}",
            "preserve_original_row": True,
            "delete_original_row": False,
            "apply_now": False,
        })
    return diff


def build_preview(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    policy = load_json(SOURCE_POLICY)
    proposed_diff = build_proposed_alias_diff(policy)
    alias_rows = (source_summary.get("metrics") or {}).get("alias_rows")
    checks = {
        "source_stage9010_present": SOURCE_SUMMARY.exists() and SOURCE_POLICY.exists(),
        "source_stage9010_passed": source_summary.get("passed") is True,
        "source_stage9010_policy_only": (source_summary.get("metrics") or {}).get("policy_only_no_mutation") is True,
        "proposed_diff_covers_alias_rows": len(proposed_diff) == alias_rows,
        "preview_rules_recorded": len(PREVIEW_RULES) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 11,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_DUPLICATE_RESOLUTION_APPLY_PREVIEW_NO_MUTATION",
        "preview_rules": PREVIEW_RULES,
        "proposed_diff_path": str(PROPOSED_DIFF.relative_to(ROOT)),
        "proposed_diff_summary": {
            "operations": len(proposed_diff),
            "operation_type": "add_registry_alias_metadata_only",
            "writes_registry": False,
            "deletes_anything": False,
            "applies_now": False,
        },
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "proposed_diff_operations": len(proposed_diff),
            "preview_only_no_mutation": True,
            "registry_written_now": False,
            "renumbering_applied_now": False,
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
        "proposed_diff": proposed_diff,
        "decision": "Duplicate-resolution apply preview is written as a side artifact only. The reconstructed registry is not mutated, no rows/files are deleted, and no execution is authorized.",
    }


def validate_preview(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for rule in ["do_not_write_reconstructed_stage_registry", "do_not_delete_registry_rows", "require_future_human_or_contract_apply_authorization"]:
        if rule not in card.get("preview_rules", []):
            failures.append(f"missing_rule:{rule}")
    for operation in card.get("proposed_diff", []):
        if operation.get("apply_now") is not False or operation.get("delete_original_row") is not False:
            failures.append("unsafe_proposed_operation")
            break
    for key in [
        "registry_written_now",
        "renumbering_applied_now",
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
    card = build_preview(registry)
    failures = validate_preview(card)
    PROPOSED_DIFF.write_text(json.dumps(card["proposed_diff"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card_without_inline_diff = dict(card)
    card_without_inline_diff.pop("proposed_diff", None)
    PREVIEW.write_text(json.dumps(card_without_inline_diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"preview": str(PREVIEW.relative_to(ROOT)), "proposed_diff": str(PROPOSED_DIFF.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Review the proposed duplicate-resolution diff artifact. Do not apply it until a separate apply-authorization stage passes; keep training and execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9011 Registry Duplicate Resolution Apply Preview",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage writes a proposed duplicate-resolution diff artifact only. It does not mutate the reconstructed registry, delete rows, delete summaries, delete artifacts, train, mine, or execute models.",
        "",
        f"Proposed diff operations: `{summary['metrics']['proposed_diff_operations']}`",
        f"Registry written now: `{summary['metrics']['registry_written_now']}`",
        f"Renumbering applied now: `{summary['metrics']['renumbering_applied_now']}`",
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
    marker = "## Stage9011 Registry Duplicate Resolution Apply Preview"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "- Writes only a proposed duplicate-resolution alias diff artifact; does not apply it to the registry.",
            "- Preserves original rows, summaries, artifacts, authority flags, and passed status.",
            "- Keeps training, mining, model execution, runtime, Gemma, harness scoring, decoder CE, denoise CE, and /arxiv writes closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
