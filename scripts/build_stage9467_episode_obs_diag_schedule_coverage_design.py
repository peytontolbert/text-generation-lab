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
STAGE = 9467
NAME = "stage9467_episode_obs_diag_schedule_coverage_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9466_episode_obs_diag_micro_target_100m_probe_audit.json"
FULL_MANIFEST = ROOT / "runs/local/artifacts/stage9461_episode_step_observation_diagnosis_manifest/episode_step_observation_diagnosis_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "episode_obs_diag_schedule_coverage_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_SCHEDULE_COVERAGE_DESIGN_STAGE9467.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(FULL_MANIFEST)
    train_rows = [row for row in rows if row.get("split") == "train"]
    batch_size = 2
    max_steps = 96
    full_cycles = (max_steps * batch_size) // max(1, len(train_rows))
    failures: list[str] = []
    if source.get("passed") is not True or source.get("metrics", {}).get("quality_passed") is not True:
        failures.append("source_stage9466_micro_overfit_not_passed")
    if len(rows) != 50 or len(train_rows) != 48:
        failures.append("unexpected_full_manifest_shape")
    if full_cycles < 4:
        failures.append("insufficient_train_exposure_cycles")
    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9466_episode_obs_diag_micro_target_100m_probe_audit",
        "manifest": str(FULL_MANIFEST.relative_to(ROOT)),
        "mode": "episode_step_structured_probe",
        "probe_scale": "target_100m",
        "row_caps": {"train": 48, "eval": 1, "strict_eval": 1, "total": 50},
        "batch_size": batch_size,
        "max_steps": max_steps,
        "train_exposure_cycles": full_cycles,
        "allowed_losses": ["episode_failure_type_ce", "episode_repair_outcome_ce", "episode_step_value_mse"],
        "disabled_losses_expected_zero": ["episode_boundary_match_ce", "episode_target_prefix_match_ce", "decoder_ce", "denoise_ce", "runtime_reward"],
        "pass_gate": {
            "eval_joint_proxy_exact": 1.0,
            "strict_joint_proxy_exact": 1.0,
            "strict_loss_max": 0.10,
            "high_confidence_wrong_rows": 0,
            "runtime_executed": False,
            "final_checkpoint_exported": False,
        },
        "decision_basis": "Stage9466 proved representation learnability under balanced repeated support; Stage9467 restores the full 50-row manifest but requires enough deterministic training steps to cover all 48 train rows four times.",
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": dict(AUTHORITY_CLOSED),
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
        "decision": "Designed the full-manifest schedule-coverage retry; execution remains closed pending target-100M contract preflight.",
        "next_best_step": "Run Stage9468 target-100M contract-only preflight for the 96-step full-manifest schedule-coverage probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9467 Episode Observation Diagnosis Schedule Coverage Design",
        "",
        f"Passed: `{design['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Train rows: `{len(train_rows)}`",
        f"Max steps: `{max_steps}`",
        f"Train exposure cycles: `{full_cycles}`",
        "",
        design["decision_basis"],
        "",
        "Only structured episode diagnosis losses are allowed. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "max_steps": max_steps, "train_exposure_cycles": full_cycles}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
