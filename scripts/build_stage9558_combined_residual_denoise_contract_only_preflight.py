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
STAGE = 9558
NAME = "stage9558_combined_residual_denoise_contract_only_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9557_combined_residual_denoise_manifest_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9556_combined_residual_denoise_manifest/combined_residual_denoise_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "combined_residual_denoise_contract_only_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMBINED_RESIDUAL_DENOISE_CONTRACT_ONLY_PREFLIGHT_STAGE9558.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_TELEMETRY = ["loss_by_step.jsonl", "eval_loss_by_checkpoint.jsonl", "row_field_logits.jsonl", "row_field_losses.jsonl", "row_token_loss.jsonl", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json", "sample_generation_audit.json", "feature_ablation_attribution.jsonl", "activation_patch_recovery.jsonl", "module_delta_norms.json", "failure_bucket_card.json", "cleanup_proof.json"]


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
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9557_not_passed")
    if not rows:
        failures.append("missing_manifest_rows")
    enabled_losses = Counter(loss for row in rows for loss, enabled in (row.get("loss_mask") or {}).items() if enabled)
    candidate_rows = [row for row in rows if (row.get("residual_denoise_contract") or {}).get("candidate_for_future_denoise_ce")]
    holdout_rows = [row for row in rows if (row.get("residual_denoise_contract") or {}).get("rare_holdout")]
    authority_rows = [row.get("row_id") for row in rows if any((row.get("authority") or {}).values())]
    if len(rows) != 44 or len(candidate_rows) != 41 or len(holdout_rows) != 3:
        failures.append("row_partition_mismatch")
    if enabled_losses:
        failures.append("enabled_losses_present")
    if authority_rows:
        failures.append("authority_rows_present")
    preflight = {
        "passed": not failures,
        "failures": failures,
        "mode": "residual_denoise_probe_contract_only",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": sha256(MANIFEST),
        "rows": len(rows),
        "candidate_rows": len(candidate_rows),
        "rare_holdout_rows": len(holdout_rows),
        "enabled_losses": dict(sorted(enabled_losses.items())),
        "loss_counts_current": dict(sorted(enabled_losses.items())),
        "future_authorized_loss_if_separate_ticket_passes": "denoise_ce_only",
        "decoder_ce_rows_current": 0,
        "denoise_ce_rows_current": 0,
        "runtime_reward_rows_current": 0,
        "authority_rows": authority_rows,
        "execution_authorized_for_next_stage": False,
        "execution_command_emitted": False,
        "model_execution_attempted": False,
        "required_future_telemetry": REQUIRED_TELEMETRY,
        "blockers_before_execution": [
            "explicit_execution_authorization_review_passed",
            "future_loss_mask_reopen_changes_denoise_ce_only",
            "future_preexecution_command_has_no_placeholders",
            "safe_cleanup_contract_asserted",
            "telemetry_artifact_gate_declared",
        ],
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
    }
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": preflight["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **preflight}, "artifacts": {"preflight": str(PREFLIGHT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": "Ran contract-only preflight over the combined residual-denoise manifest. Current losses remain closed and no execution is authorized.", "next_best_step": "Audit Stage9558, then if execution is still desired build a separate explicit loss-mask reopen and execution-authorization stage for denoise CE only.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage9558 Combined Residual Denoise Contract-Only Preflight", "", f"Passed: `{preflight['passed']}`", f"Rows: `{len(rows)}`", f"Current denoise CE rows: `{preflight['denoise_ce_rows_current']}`", "Execution authorized for next stage: `False`", "", "This preflight does not reopen denoise CE. It only locks the manifest and blockers for a future authorization stage.", ""]))
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": preflight["passed"], "rows": len(rows), "denoise_ce_rows_current": 0, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
