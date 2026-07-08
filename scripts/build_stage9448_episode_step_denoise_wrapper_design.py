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
STAGE = 9448
NAME = "stage9448_episode_step_denoise_wrapper_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9447_episode_step_suffix_repair_manifest_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9446_episode_step_suffix_repair_manifest/episode_step_suffix_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "episode_step_denoise_wrapper_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_DENOISE_WRAPPER_DESIGN_STAGE9448.md"
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
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9447_not_passed")
    if len(rows) != 50:
        failures.append("unexpected_manifest_row_count")

    design = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9447_episode_step_suffix_repair_manifest_audit",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "wrapper_mode": "episode_step_denoise_contract_only",
        "execution_authorized": False,
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "required_trainer_semantics": {
            "accept_episode_step_transition_schema": "episode_step_suffix_transition_v1",
            "contract_only_default": True,
            "max_steps": 0,
            "all_training_weights_zero": True,
            "loss_masks_must_be_closed": True,
            "decoder_ce_must_be_zero": True,
            "runtime_reward_must_be_zero": True,
            "target_suffix_choice_must_not_be_serialized_in_state_t_or_action_t": True,
            "target_text_must_not_be_serialized_in_model_input": True,
            "required_artifacts": [
                "episode_step_contract_audit.json",
                "episode_step_loss_mask_audit.json",
                "target_leak_audit.json",
                "wrapper_static_command.json",
            ],
        },
        "future_training_gate_if_authorized_later": {
            "target_prefix_match_rate": 1.0,
            "boundary_next_token_match_rate": 1.0,
            "contentful_rate": 1.0,
            "short_or_junk_rows": 0,
            "degenerate_repetition_rows": 0,
            "unterminated_rows": 0,
            "internal_leak_rows": 0,
            "decoder_ce_rows": 0,
        },
        "blocked_until": [
            "trainer accepts episode_step_* schema in contract-only mode",
            "trainer can emit episode-step target leak audit",
            "separate preexecution stage explicitly authorizes any model execution",
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
        "decision": "Designed a no-execution episode-step denoise wrapper; no training or model execution is authorized.",
        "next_best_step": "Audit Stage9448 wrapper design, then patch trainer contract-only support for episode_step_denoise_contract_only if the audit passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9448 Episode-Step Denoise Wrapper Design",
        "",
        f"Passed: `{design['passed']}`",
        "",
        "This is a no-execution wrapper design for the episode-step suffix repair manifest. It does not authorize model execution, denoise CE, decoder CE, runtime, Gemma, harness, hidden scoring, source/body emission, or promotion.",
        "",
        "The next safe step is a wrapper audit and then a trainer contract-only patch if needed.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "execution_authorized": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
