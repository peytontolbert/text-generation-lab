#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9560
NAME = "stage9560_residual_denoise_loss_mask_reopen_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9559_combined_residual_denoise_contract_only_preflight_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9556_combined_residual_denoise_manifest/combined_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CANDIDATE_MANIFEST = OUT_DIR / "residual_denoise_loss_mask_reopen_candidate_manifest.jsonl"
DESIGN_CARD = OUT_DIR / "residual_denoise_loss_mask_reopen_design_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_LOSS_MASK_REOPEN_DESIGN_STAGE9560.md"
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


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


def proposed_loss_mask(row: dict, candidate: bool) -> dict:
    mask = {key: False for key in (row.get("loss_mask") or {})}
    if candidate:
        mask["denoise_ce"] = True
    else:
        mask["denoise_ce"] = False
    mask["decoder_ce"] = False
    mask["runtime_reward"] = False
    mask["structured_aux"] = False
    return mask


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9559_not_passed")
    if not rows:
        failures.append("missing_source_manifest")

    candidate_rows: list[dict] = []
    holdout_rows: list[dict] = []
    proposed_rows: list[dict] = []
    forbidden_input_rows: list[str] = []
    current_enabled_losses = Counter()
    proposed_enabled_losses = Counter()

    for row in rows:
        row_id = row.get("row_id", "")
        contract = row.get("residual_denoise_contract") or {}
        candidate = bool(contract.get("candidate_for_future_denoise_ce"))
        holdout = bool(contract.get("rare_holdout"))
        if candidate:
            candidate_rows.append(row)
        if holdout:
            holdout_rows.append(row)
        for loss, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                current_enabled_losses[loss] += 1
        model_input = row.get("model_input") or {}
        leaked = sorted(FORBIDDEN_MODEL_INPUT_KEYS.intersection(model_input))
        if leaked:
            forbidden_input_rows.append(row_id)
        proposed = dict(row)
        proposed["source_stage9560_design_only"] = True
        proposed["loss_mask_current"] = row.get("loss_mask") or {}
        proposed["loss_mask_proposed_after_future_authorization"] = proposed_loss_mask(row, candidate)
        proposed["loss_mask"] = row.get("loss_mask") or {}
        proposed["residual_denoise_loss_mask_reopen_design"] = {
            "stage": STAGE,
            "design_only": True,
            "execution_authorized_now": False,
            "denoise_ce_authorized_now": False,
            "future_denoise_ce_candidate": candidate,
            "rare_holdout": holdout,
            "decoder_ce_must_remain_false": True,
            "runtime_reward_must_remain_false": True,
        }
        proposed_rows.append(proposed)
        for loss, enabled in proposed["loss_mask_proposed_after_future_authorization"].items():
            if enabled:
                proposed_enabled_losses[loss] += 1

    if len(rows) != 44 or len(candidate_rows) != 41 or len(holdout_rows) != 3:
        failures.append("row_partition_mismatch")
    if current_enabled_losses:
        failures.append("current_losses_already_enabled")
    if dict(proposed_enabled_losses) != {"denoise_ce": 41}:
        failures.append("proposed_loss_mask_not_denoise_only")
    if forbidden_input_rows:
        failures.append("forbidden_label_keys_in_model_input")
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    if authority_rows:
        failures.append("authority_rows_present")

    with CANDIDATE_MANIFEST.open("w") as f:
        for row in proposed_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    design_card = {
        "passed": not failures,
        "failures": failures,
        "design_only": True,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "source_manifest_sha256": sha256(SOURCE_MANIFEST),
        "candidate_manifest": str(CANDIDATE_MANIFEST.relative_to(ROOT)),
        "candidate_manifest_sha256": sha256(CANDIDATE_MANIFEST),
        "rows": len(rows),
        "future_denoise_ce_candidate_rows": len(candidate_rows),
        "rare_holdout_rows": len(holdout_rows),
        "current_enabled_losses": dict(sorted(current_enabled_losses.items())),
        "proposed_enabled_losses_after_future_authorization": dict(sorted(proposed_enabled_losses.items())),
        "denoise_ce_rows_current": 0,
        "decoder_ce_rows_current": 0,
        "runtime_reward_rows_current": 0,
        "proposed_denoise_ce_rows_after_future_authorization": proposed_enabled_losses.get("denoise_ce", 0),
        "proposed_decoder_ce_rows_after_future_authorization": proposed_enabled_losses.get("decoder_ce", 0),
        "proposed_runtime_reward_rows_after_future_authorization": proposed_enabled_losses.get("runtime_reward", 0),
        "forbidden_input_rows": forbidden_input_rows,
        "authority_rows": authority_rows,
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
    DESIGN_CARD.write_text(json.dumps(design_card, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design_card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design_card},
        "artifacts": {
            "candidate_manifest": str(CANDIDATE_MANIFEST.relative_to(ROOT)),
            "design_card": str(DESIGN_CARD.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Designed a future denoise-CE-only loss-mask reopen over the 41 residual-denoise candidate rows. Current CE authority remains closed and no execution command is emitted.",
        "next_best_step": "Audit Stage9560, then require a separate execution-authorization review before any tiny residual-denoise probe can run.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9560 Residual Denoise Loss-Mask Reopen Design",
                "",
                f"Passed: `{design_card['passed']}`",
                f"Rows: `{len(rows)}`",
                f"Future denoise CE candidate rows: `{len(candidate_rows)}`",
                f"Rare holdout rows: `{len(holdout_rows)}`",
                f"Current denoise CE rows: `{design_card['denoise_ce_rows_current']}`",
                f"Proposed denoise CE rows after future authorization: `{design_card['proposed_denoise_ce_rows_after_future_authorization']}`",
                "",
                "This is a design-only stage. It does not authorize execution and it does not reopen current losses.",
                "The proposed future loss mask enables `denoise_ce` only for candidate rows; decoder CE, runtime reward, and structured auxiliary losses remain closed.",
                "",
            ]
        )
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": design_card["passed"],
                "rows": len(rows),
                "future_denoise_ce_candidate_rows": len(candidate_rows),
                "proposed_enabled_losses_after_future_authorization": dict(sorted(proposed_enabled_losses.items())),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
