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
STAGE = 9451
NAME = "stage9451_episode_step_denoise_objective_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9450_episode_step_denoise_contract_preflight_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "episode_step_denoise_objective_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_DENOISE_OBJECTIVE_DESIGN_STAGE9451.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9450_not_passed")
    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9450_episode_step_denoise_contract_preflight_audit",
        "objective_name": "episode_step_denoise_supervision_v1",
        "execution_authorized": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "model_execution_authorized_next": False,
        "trainable_targets_later_only_after_preexecution": {
            "repair_outcome_ce": "successful_suffix_repair_step vs residual_suffix_repair_step; classifier target only, not decoder text",
            "failure_type_ce": "none vs boundary_next_token_miss/target_prefix_miss/degenerate_repetition/unterminated combinations",
            "boundary_match_ce": "whether first post-prefix token matched expected target continuation",
            "target_prefix_match_ce": "whether generated continuation stayed on target prefix",
            "step_value_regression": "verifier reward 1.0/0.0 from generation audit",
        },
        "not_trainable_yet": {
            "decoder_text": "do not reopen decoder CE from this manifest",
            "target_suffix_choice": "do not expose as input; future head may predict from state only after shortcut audit",
            "runtime_reward": "runtime remains closed; reward is telemetry label only",
        },
        "required_new_loss_keys_before_training": [
            "episode_repair_outcome_ce",
            "episode_failure_type_ce",
            "episode_boundary_match_ce",
            "episode_target_prefix_match_ce",
            "episode_step_value_mse",
        ],
        "required_audits_before_any_execution": [
            "loss-key registry update audit",
            "episode-step target leakage audit",
            "majority and single-feature baseline audit",
            "train/eval/strict cell balance audit",
            "high-confidence-wrong telemetry requirement",
            "module-delta decoder guard",
        ],
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
        "decision": "Designed guarded episode-step supervision targets; no training or execution authority opened.",
        "next_best_step": "Patch the loss-key registry and loss-mask card for episode-step supervision keys, then audit that decoder CE remains closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9451 Episode-Step Denoise Objective Design",
        "",
        f"Passed: `{design['passed']}`",
        "",
        "The episode-step manifest should first train small structured supervision targets: repair outcome, failure type, boundary match, prefix match, and value. It must not reopen decoder CE from these rows.",
        "",
        "Next: patch loss-mask/loss-key registry for episode-step supervision, then audit closure.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "next": summary["next_best_step"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
