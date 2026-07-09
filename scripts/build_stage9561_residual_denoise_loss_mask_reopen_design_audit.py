#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9561
NAME = "stage9561_residual_denoise_loss_mask_reopen_design_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9560_residual_denoise_loss_mask_reopen_design.json"
DESIGN_CARD = ROOT / "runs/local/artifacts/stage9560_residual_denoise_loss_mask_reopen_design/residual_denoise_loss_mask_reopen_design_card.json"
CANDIDATE_MANIFEST = ROOT / "runs/local/artifacts/stage9560_residual_denoise_loss_mask_reopen_design/residual_denoise_loss_mask_reopen_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_loss_mask_reopen_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_LOSS_MASK_REOPEN_DESIGN_AUDIT_STAGE9561.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FORBIDDEN_MODEL_INPUT_KEYS = {
    "target",
    "target_repair_bucket",
    "repair_bucket",
    "failure_type",
    "effective_failure_type",
    "residual_denoise_contract",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
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
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    design = load_json(DESIGN_CARD)
    rows = load_jsonl(CANDIDATE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True or design.get("passed") is not True:
        failures.append("stage9560_not_passed")
    if len(rows) != 44:
        failures.append("candidate_manifest_row_count_mismatch")

    current_enabled = Counter()
    proposed_enabled = Counter()
    candidate_rows = 0
    holdout_rows = 0
    bad_holdout_rows: list[str] = []
    forbidden_input_rows: list[str] = []
    authority_rows: list[str] = []
    execution_open_rows: list[str] = []
    for row in rows:
        row_id = row.get("row_id", "")
        design_contract = row.get("residual_denoise_loss_mask_reopen_design") or {}
        if design_contract.get("future_denoise_ce_candidate"):
            candidate_rows += 1
        if design_contract.get("rare_holdout"):
            holdout_rows += 1
        if design_contract.get("rare_holdout") and (row.get("loss_mask_proposed_after_future_authorization") or {}).get("denoise_ce"):
            bad_holdout_rows.append(row_id)
        for loss, enabled in (row.get("loss_mask_current") or {}).items():
            if enabled:
                current_enabled[loss] += 1
        for loss, enabled in (row.get("loss_mask_proposed_after_future_authorization") or {}).items():
            if enabled:
                proposed_enabled[loss] += 1
        leaked = sorted(FORBIDDEN_MODEL_INPUT_KEYS.intersection(row.get("model_input") or {}))
        if leaked:
            forbidden_input_rows.append(row_id)
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        if design_contract.get("execution_authorized_now") or design_contract.get("denoise_ce_authorized_now"):
            execution_open_rows.append(row_id)

    if candidate_rows != 41 or holdout_rows != 3:
        failures.append("candidate_holdout_partition_mismatch")
    if current_enabled:
        failures.append("current_losses_enabled")
    if dict(proposed_enabled) != {"denoise_ce": 41}:
        failures.append("future_proposed_losses_not_denoise_only")
    if bad_holdout_rows:
        failures.append("holdout_rows_have_future_denoise_ce")
    if forbidden_input_rows:
        failures.append("forbidden_label_keys_in_model_input")
    if authority_rows:
        failures.append("authority_rows_present")
    if execution_open_rows:
        failures.append("execution_or_current_denoise_authority_opened")
    if design.get("execution_authorized_for_next_stage") is not False or design.get("denoise_ce_training_authorized_next") is not False:
        failures.append("design_authorizes_execution_or_training")

    passed = not failures
    audit = {
        "passed": passed,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "design_card": str(DESIGN_CARD.relative_to(ROOT)),
        "candidate_manifest": str(CANDIDATE_MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "future_denoise_ce_candidate_rows": candidate_rows,
        "rare_holdout_rows": holdout_rows,
        "current_enabled_losses": dict(sorted(current_enabled.items())),
        "proposed_enabled_losses_after_future_authorization": dict(sorted(proposed_enabled.items())),
        "denoise_ce_rows_current": 0,
        "decoder_ce_rows_current": 0,
        "runtime_reward_rows_current": 0,
        "proposed_denoise_ce_rows_after_future_authorization": proposed_enabled.get("denoise_ce", 0),
        "proposed_decoder_ce_rows_after_future_authorization": proposed_enabled.get("decoder_ce", 0),
        "proposed_runtime_reward_rows_after_future_authorization": proposed_enabled.get("runtime_reward", 0),
        "bad_holdout_rows": bad_holdout_rows,
        "forbidden_input_rows": forbidden_input_rows,
        "authority_rows": authority_rows,
        "execution_open_rows": execution_open_rows,
        "execution_authorized_for_next_stage": False,
        "execution_command_emitted": False,
        "model_execution_attempted": False,
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited Stage9560: proposed future reopen is denoise-CE-only for 41 candidate rows, rare holdouts remain excluded, current losses and execution remain closed.",
        "next_best_step": "Build a separate residual-denoise execution-authorization review with an explicit safe trainer command, telemetry gates, trellis environment requirement, and cleanup proof before any tiny probe runs.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9561 Residual Denoise Loss-Mask Reopen Design Audit",
                "",
                f"Passed: `{passed}`",
                f"Rows: `{len(rows)}`",
                f"Future denoise CE candidate rows: `{candidate_rows}`",
                f"Rare holdout rows: `{holdout_rows}`",
                f"Current denoise CE rows: `{audit['denoise_ce_rows_current']}`",
                f"Proposed denoise CE rows after future authorization: `{audit['proposed_denoise_ce_rows_after_future_authorization']}`",
                "",
                "No execution is authorized by this audit. The next stage must be an explicit execution-authorization review.",
                "",
            ]
        )
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": passed,
                "rows": len(rows),
                "future_denoise_ce_candidate_rows": candidate_rows,
                "proposed_enabled_losses_after_future_authorization": dict(sorted(proposed_enabled.items())),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
