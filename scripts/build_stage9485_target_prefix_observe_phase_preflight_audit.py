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
STAGE = 9485
NAME = "stage9485_target_prefix_observe_phase_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9484_target_prefix_observe_phase_manifest.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9485_target_prefix_observe_phase_target_100m_contract_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
AUDIT = PREFLIGHT_DIR / "stage9485_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGET_PREFIX_OBSERVE_PHASE_PREFLIGHT_AUDIT_STAGE9485.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9484_not_passed")
    if contract.get("passed") is not True:
        failures.append("target_100m_contract_preflight_not_passed")
    if contract.get("probe_scale") != "target_100m" or contract.get("mode") != "episode_step_structured_probe":
        failures.append("unexpected_probe_contract")
    expected_splits = {"eval": 6, "other": 0, "strict_eval": 6, "train": 54}
    if contract.get("rows") != 66 or contract.get("split_counts") != expected_splits:
        failures.append("unexpected_rows_or_splits")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted_in_preflight")
    if contract.get("authority_rows") != 0 or contract.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_or_authority_rows_present")
    if contract.get("final_checkpoint_export_disabled") is not True:
        failures.append("final_checkpoint_export_not_disabled")
    if contract.get("final_model_save_skipped") is not True:
        failures.append("final_model_save_not_skipped")

    weights = contract.get("weights") if isinstance(contract.get("weights"), dict) else {}
    if weights.get("restore_best_structured_state") is not True or weights.get("eval_interval") != 8:
        failures.append("best_state_restore_contract_missing")
    if weights.get("decoder_ce_weight") != 0.0:
        failures.append("decoder_ce_weight_not_zero")
    if weights.get("denoise_weight") != 0.0:
        failures.append("denoise_weight_not_zero")
    if weights.get("structured_aux_weight") != 1.0:
        failures.append("structured_aux_weight_not_one")

    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if loss_counts.get("episode_target_prefix_match_ce") != 66:
        failures.append("target_prefix_loss_count_mismatch")
    for key, value in loss_counts.items():
        if key != "episode_target_prefix_match_ce" and value:
            failures.append(f"forbidden_loss_enabled:{key}")

    tokenizer = contract.get("tokenizer_contract") if isinstance(contract.get("tokenizer_contract"), dict) else {}
    if tokenizer.get("byte_fallback_used_when_unset") is not False:
        failures.append("target_100m_tokenizer_not_locked")

    impl = contract.get("implementation_contract") if isinstance(contract.get("implementation_contract"), dict) else {}
    guard = impl.get("target_implementation_guard") if isinstance(impl.get("target_implementation_guard"), dict) else {}
    if guard.get("selected") != "transformer" or guard.get("allowed_for_recovered_100m_target") is not True:
        failures.append("target_100m_transformer_guard_not_passed")

    next_authorized = not failures
    authority = {**dict(AUTHORITY_CLOSED), "model_execution_authorized_next": next_authorized}
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9484_target_prefix_observe_phase_manifest",
        "preflight_contract": str(CONTRACT.relative_to(ROOT)),
        "probe_scale": contract.get("probe_scale"),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "caps": contract.get("caps"),
        "weights": weights,
        "loss_counts": loss_counts,
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
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "contract": str(CONTRACT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Authorized only Stage9486 observe-phase target-prefix target-100M structured execution if this preflight passes.",
        "next_best_step": "Run Stage9486 observe-phase target-prefix best-state-restored probe under trellis, then audit eval/strict exactness and safety artifacts.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9485 Target-Prefix Observe-Phase Preflight Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Execution authorized for next stage: `{next_authorized}`",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        "",
        "Only the observe-phase target-prefix structured head is open. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": authority,
        "next_best_step": summary["next_best_step"],
    })
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(reg_rows),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "execution_authorized_for_next_stage": next_authorized,
        "failures": failures,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
