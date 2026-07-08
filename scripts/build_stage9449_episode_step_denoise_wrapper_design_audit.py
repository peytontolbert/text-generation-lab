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
STAGE = 9449
NAME = "stage9449_episode_step_denoise_wrapper_design_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9448_episode_step_denoise_wrapper_design.json"
DESIGN = ROOT / "runs/local/artifacts/stage9448_episode_step_denoise_wrapper_design/episode_step_denoise_wrapper_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_step_denoise_wrapper_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_DENOISE_WRAPPER_DESIGN_AUDIT_STAGE9449.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    design = load_json(DESIGN)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9448_not_passed")
    if design.get("execution_authorized") is not False:
        failures.append("execution_authorized_in_design")
    if design.get("model_execution_authorized_next") is not False:
        failures.append("model_execution_authorized_next_true")
    if design.get("denoise_ce_training_authorized_next") is not False:
        failures.append("denoise_ce_authorized_next_true")
    if design.get("decoder_ce_training_authorized_next") is not False:
        failures.append("decoder_ce_authorized_next_true")
    semantics = design.get("required_trainer_semantics") if isinstance(design.get("required_trainer_semantics"), dict) else {}
    for key in [
        "accept_episode_step_transition_schema",
        "contract_only_default",
        "all_training_weights_zero",
        "loss_masks_must_be_closed",
        "decoder_ce_must_be_zero",
        "runtime_reward_must_be_zero",
        "target_suffix_choice_must_not_be_serialized_in_state_t_or_action_t",
        "target_text_must_not_be_serialized_in_model_input",
    ]:
        if key not in semantics:
            failures.append(f"missing_semantic_{key}")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9448_episode_step_denoise_wrapper_design",
        "wrapper_mode": design.get("wrapper_mode"),
        "execution_authorized": design.get("execution_authorized"),
        "model_execution_authorized_next": design.get("model_execution_authorized_next"),
        "denoise_ce_training_authorized_next": design.get("denoise_ce_training_authorized_next"),
        "decoder_ce_training_authorized_next": design.get("decoder_ce_training_authorized_next"),
        "required_artifact_count": len(semantics.get("required_artifacts") or []),
        "blocked_until": design.get("blocked_until"),
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Audited the no-execution episode-step wrapper design; execution remains blocked pending trainer contract-only support.",
        "next_best_step": "Patch trainer contract-only support for episode_step_denoise_contract_only, then run a static wrapper preflight with max_steps=0 and all weights zero.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9449 Episode-Step Denoise Wrapper Design Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Wrapper mode: `{audit['wrapper_mode']}`",
        f"Execution authorized: `{audit['execution_authorized']}`",
        "",
        "The next step is trainer contract-only support, not execution.",
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
