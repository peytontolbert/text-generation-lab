#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9475
NAME = "stage9475_episode_obs_diag_best_state_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9474_episode_obs_diag_balanced_order_probe_audit.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9475_episode_obs_diag_best_state_target_100m_contract_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
AUDIT = PREFLIGHT_DIR / "stage9475_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_BEST_STATE_PREFLIGHT_AUDIT_STAGE9475.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
ENABLED = {"episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"}
DISABLED = {"episode_boundary_match_ce", "episode_target_prefix_match_ce", "decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    failures: list[str] = []

    if source.get("passed") is not True:
        failures.append("source_stage9474_not_passed")
    selected = source.get("selected_checkpoint_proxy") if isinstance(source.get("selected_checkpoint_proxy"), dict) else {}
    if not selected and isinstance(source.get("metrics"), dict):
        selected = source["metrics"].get("selected_checkpoint_proxy") if isinstance(source["metrics"].get("selected_checkpoint_proxy"), dict) else {}
    if selected.get("step") not in {24, 48, 56, 64, 88}:
        failures.append("source_stage9474_missing_joint_exact_interval")
    if selected.get("eval_joint") != 1.0 or selected.get("strict_joint") != 1.0:
        failures.append("source_stage9474_selected_interval_not_joint_exact")
    if contract.get("passed") is not True:
        failures.append("target_100m_contract_preflight_not_passed")
    if contract.get("probe_scale") != "target_100m":
        failures.append("contract_not_target_100m")
    if contract.get("mode") != "episode_step_structured_probe":
        failures.append("unexpected_mode")
    if contract.get("rows") != 58:
        failures.append("unexpected_row_count")
    if contract.get("split_counts") != {"eval": 1, "other": 0, "strict_eval": 1, "train": 56}:
        failures.append("unexpected_split_counts")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted_in_preflight")
    if contract.get("unsafe_loss_rows") != 0 or contract.get("authority_rows") != 0:
        failures.append("unsafe_or_authority_rows_present")

    weights = contract.get("weights") if isinstance(contract.get("weights"), dict) else {}
    if weights.get("eval_interval") != 8:
        failures.append("eval_interval_not_enabled")
    if weights.get("restore_best_structured_state") is not True:
        failures.append("best_state_restore_not_enabled")
    if weights.get("decoder_ce_weight") != 0 or weights.get("denoise_weight") != 0 or weights.get("structured_aux_weight") != 1:
        failures.append("unexpected_probe_weights")

    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target_100m_tokenizer_not_locked")

    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    for key in ENABLED:
        if loss_counts.get(key) != 58:
            failures.append(f"enabled_loss_count_mismatch:{key}")
    for key in DISABLED:
        if loss_counts.get(key, 0) != 0:
            failures.append(f"disabled_loss_open:{key}")

    next_authorized = not failures
    authority = {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": next_authorized}
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9474_episode_obs_diag_balanced_order_probe_audit",
        "source_selected_checkpoint_proxy": selected,
        "preflight_contract": str(CONTRACT.relative_to(ROOT)),
        "probe_scale": contract.get("probe_scale"),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "caps": contract.get("caps"),
        "weights": weights,
        "manifest_sha256": contract.get("manifest_sha256"),
        "loss_counts": loss_counts,
        "tokenizer_contract": tokenizer,
        "best_state_restore_required_next": True,
        "execution_authorized_for_next_stage": next_authorized,
        "model_execution_authorized_next": next_authorized,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": authority,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": authority,
        "metrics": {**authority, **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Authorized only the next target-100M balanced-order observation-diagnosis probe with in-memory best-state restore if this preflight passes.",
        "next_best_step": "Run Stage9476 best-state-restored balanced-order observation-diagnosis probe under trellis, then audit final eval/strict exactness and best_structured_state_selection.json.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9475 Episode Observation Diagnosis Best-State Preflight Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Execution authorized for next stage: `{next_authorized}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Eval interval: `{weights.get('eval_interval')}`",
        f"Restore best structured state: `{weights.get('restore_best_structured_state')}`",
        "",
        "This stage authorizes only Stage9476 target-100M structured execution with in-memory best-state restore. It does not authorize decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": authority, "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "execution_authorized_for_next_stage": next_authorized, "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
