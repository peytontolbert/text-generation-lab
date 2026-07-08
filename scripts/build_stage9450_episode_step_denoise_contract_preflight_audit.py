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
STAGE = 9450
NAME = "stage9450_episode_step_denoise_contract_preflight_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9449_episode_step_denoise_wrapper_design_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9450_episode_step_denoise_contract_preflight"
CONTRACT = RUN_DIR / "probe_contract_audit.json"
AUDIT = RUN_DIR / "stage9450_episode_step_denoise_contract_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_DENOISE_CONTRACT_PREFLIGHT_AUDIT_STAGE9450.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = (
    ".agentkernel_probe_output",
    "probe_contract_audit.json",
    "cleanup_proof.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9449_not_passed")
    if contract.get("passed") is not True:
        failures.append("trainer_contract_not_passed")
    if contract.get("mode") != "episode_step_denoise_contract_only":
        failures.append("wrong_mode")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    if contract.get("caps", {}).get("max_steps") != 0:
        failures.append("max_steps_not_zero")
    if any(float(value or 0.0) != 0.0 for key, value in contract.get("weights", {}).items() if key != "eos_loss_weight"):
        failures.append("training_weight_nonzero")
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    if any(int(value or 0) != 0 for value in loss_counts.values()):
        failures.append("loss_count_nonzero")
    if contract.get("authority_rows") != 0:
        failures.append("authority_rows_present")
    if contract.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_loss_rows_present")
    if cleanup.get("cleanup_executed") is not False:
        failures.append("unexpected_cleanup_execution")
    if missing:
        failures.append("required_artifacts_missing")
    audit = {
        "passed": not failures,
        "failures": failures,
        "missing_artifacts": missing,
        "source_stage": "stage9449_episode_step_denoise_wrapper_design_audit",
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "loss_counts": loss_counts,
        "authority_rows": contract.get("authority_rows"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "max_steps": contract.get("caps", {}).get("max_steps"),
        "weights": contract.get("weights"),
        "implementation": contract.get("implementation"),
        "probe_scale": contract.get("probe_scale"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Trainer contract-only support accepts episode-step suffix repair rows with all losses closed and no model execution.",
        "next_best_step": "Design a guarded episode-step denoise training objective that decides which fields become trainable; do not execute until a separate preexecution stage authorizes it.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9450 Episode-Step Denoise Contract Preflight Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Mode: `{audit['mode']}`",
        f"Model execution attempted: `{audit['model_execution_attempted']}`",
        f"Unsafe loss rows: `{audit['unsafe_loss_rows']}`",
        f"Authority rows: `{audit['authority_rows']}`",
        "",
        "This confirms trainer contract-only support for the episode-step schema. It does not authorize denoise training or decoder CE.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "mode": audit["mode"], "rows": audit["rows"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
