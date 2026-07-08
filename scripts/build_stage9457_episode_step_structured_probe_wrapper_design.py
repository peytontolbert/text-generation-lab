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
STAGE = 9457
NAME = "stage9457_episode_step_structured_probe_wrapper_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9456_episode_step_trainable_manifest_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "episode_step_structured_probe_wrapper_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_STRUCTURED_PROBE_WRAPPER_DESIGN_STAGE9457.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EPISODE_LOSSES = [
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
]
REQUIRED_TELEMETRY = [
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9456_not_passed")
    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9456_episode_step_trainable_manifest_audit",
        "new_trainer_mode": "episode_step_structured_probe",
        "manifest": "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl",
        "row_caps": {"train": 48, "eval": 1, "strict_eval": 1, "total": 50},
        "max_steps_cap": 16,
        "required_weights": {"decoder_ce_weight": 0.0, "denoise_weight": 0.0, "structured_aux_weight_min": 1.0},
        "allowed_losses": EPISODE_LOSSES,
        "forbidden_losses": ["decoder_ce", "denoise_ce", "runtime_reward"],
        "required_runtime_assertions": [
            "all rows transition_schema == episode_step_suffix_transition_v1",
            "all enabled losses are episode_* structured losses",
            "decoder_ce_weight == 0",
            "denoise_weight == 0",
            "structured_aux_weight > 0",
            "row caps enforced",
            "authority flags closed for every row",
            "no final checkpoint export",
            "cleanup uses safe_cleanup.py only",
        ],
        "required_telemetry_artifacts": REQUIRED_TELEMETRY,
        "pass_gate": {
            "strict_joint_exact_min": 0.80,
            "strict_joint_exact_must_exceed_majority_baseline_by": 0.10,
            "strict_episode_repair_outcome_exact_min": 0.80,
            "strict_episode_failure_type_exact_min": 0.80,
            "strict_boundary_match_exact_min": 0.80,
            "strict_target_prefix_match_exact_min": 0.80,
            "no_single_class_collapse": True,
            "decoder_delta_norm_max": 0.0,
            "forbidden_artifacts_missing": True,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed a closed-boundary trainable episode-step structured probe wrapper; no execution authority is opened.",
        "next_best_step": "Patch trainer command surface with episode_step_structured_probe mode, then run a static wrapper audit before any execution authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9457 Episode-Step Structured Probe Wrapper Design",
        "",
        f"Passed: `{design['passed']}`",
        "",
        "This design introduces `episode_step_structured_probe` as the future trainable structured-head mode for episode-step supervision.",
        "",
        "Allowed losses:",
        *[f"- `{loss}`" for loss in EPISODE_LOSSES],
        "",
        "Forbidden losses remain `decoder_ce`, `denoise_ce`, and `runtime_reward`. Model execution, checkpoint export, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion remain closed.",
        "",
        "Next: patch the trainer command surface and audit it statically. Do not execute the probe from this stage.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next_best_step": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
