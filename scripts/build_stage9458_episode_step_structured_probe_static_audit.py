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
STAGE = 9458
NAME = "stage9458_episode_step_structured_probe_static_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9457_episode_step_structured_probe_wrapper_design.json"
PREFLIGHT_DIR = ROOT / "runs/local/artifacts/stage9458_episode_step_structured_probe_static_preflight"
CONTRACT = PREFLIGHT_DIR / "probe_contract_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_STRUCTURED_PROBE_STATIC_AUDIT_STAGE9458.md"
AUDIT = PREFLIGHT_DIR / "stage9458_static_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EPISODE_LOSSES = {
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
}
REQUIRED_ARTIFACTS = [
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
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(CONTRACT)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9457_not_passed")
    if contract.get("passed") is not True:
        failures.append("trainer_contract_preflight_not_passed")
    if contract.get("mode") != "episode_step_structured_probe":
        failures.append("unexpected_trainer_mode")
    if contract.get("rows") != 50:
        failures.append("unexpected_row_count")
    if contract.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    if contract.get("unsafe_loss_rows") != 0:
        failures.append("unsafe_loss_rows_present")
    if contract.get("authority_rows") != 0:
        failures.append("authority_rows_present")
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    for key in EPISODE_LOSSES:
        if loss_counts.get(key) != 50:
            failures.append(f"episode_loss_count_mismatch:{key}")
    for forbidden in ["decoder_ce", "denoise_ce", "runtime_reward"]:
        if loss_counts.get(forbidden, 0) != 0:
            failures.append(f"forbidden_loss_reopened:{forbidden}")
    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (PREFLIGHT_DIR / name).exists()]
    if missing_artifacts:
        failures.append("missing_required_telemetry_artifacts")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9457_episode_step_structured_probe_wrapper_design",
        "preflight_contract": str(CONTRACT.relative_to(ROOT)),
        "mode": contract.get("mode"),
        "rows": contract.get("rows"),
        "split_counts": contract.get("split_counts"),
        "loss_counts": loss_counts,
        "missing_required_telemetry_artifacts": missing_artifacts,
        "model_execution_attempted": contract.get("model_execution_attempted"),
        "unsafe_loss_rows": contract.get("unsafe_loss_rows"),
        "authority_rows": contract.get("authority_rows"),
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Static trainer preflight for episode_step_structured_probe passed without model execution.",
        "next_best_step": "Build the explicit execution-authorization review card for a tiny episode-step structured probe under trellis; do not execute until that review passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9458 Episode-Step Structured Probe Static Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Mode: `{audit['mode']}`",
        f"Rows: `{audit['rows']}`",
        f"Unsafe loss rows: `{audit['unsafe_loss_rows']}`",
        f"Authority rows: `{audit['authority_rows']}`",
        f"Model execution attempted: `{audit['model_execution_attempted']}`",
        "",
        "This is a no-execution static preflight. The trainer now accepts `episode_step_structured_probe` and restricts it to episode-step structured losses only.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
