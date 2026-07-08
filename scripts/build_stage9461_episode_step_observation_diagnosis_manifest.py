#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9461
NAME = "stage9461_episode_step_observation_diagnosis_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9460_episode_step_target_100m_tiny_probe_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "episode_step_observation_diagnosis_manifest.jsonl"
CARD = OUT_DIR / "episode_step_observation_diagnosis_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_OBSERVATION_DIAGNOSIS_MANIFEST_STAGE9461.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAIN_LOSSES = {
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_step_value_mse",
}
DISABLED_EPISODE_LOSSES = {
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}
FORBIDDEN = {"decoder_ce", "denoise_ce", "runtime_reward"}
TARGET_TEXT_KEYS = {
    "generated_text",
    "decoder_text",
    "target_suffix_choice",
    "residual_reasons",
    "failure_type",
    "repair_outcome",
    "reward",
}
ALL_LOSSES = [
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
    "symbol_binding_ce",
    "edit_localization_ce",
    "patch_operator_ce",
    "verifier_repair_ce",
    "suffix_choice_ce",
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def bucket_rank(value: object) -> str:
    try:
        parsed = int(value)
    except Exception:
        return "unknown"
    if parsed <= 1:
        return "rank_1"
    if parsed <= 3:
        return "rank_2_to_3"
    return "rank_gt_3"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict] = []
    split_counts = Counter()
    loss_counts = Counter()
    outcome_counts = Counter()
    state_leak_rows: list[str] = []
    authority_rows = 0
    forbidden_loss_rows = 0
    for index, base in enumerate(base_rows):
        row = json.loads(json.dumps(base))
        row["row_id"] = f"stage9461_episode_obs_diag_{index:04d}"
        row["source_stage9455_row_id"] = base.get("row_id")
        row["objective_family"] = "episode_step_observation_diagnosis"
        row["route"] = "KEEP_EPISODE_OBSERVATION_DIAGNOSIS"
        transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
        observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
        next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        row["state"] = {
            "diagnosis_surface": "verifier_observation_to_episode_outcome",
            "raw_boundary_token_passed": bool(observation.get("boundary_next_token_match")),
            "raw_prefix_alignment_passed": bool(observation.get("target_prefix_match")),
            "raw_repetition_detected": bool(observation.get("degenerate_repetition")),
            "raw_short_or_junk_detected": bool(observation.get("short_or_junk")),
            "raw_eos_stopped": bool(observation.get("stopped_on_eos")),
            "raw_boundary_rank_bucket": bucket_rank(observation.get("boundary_expected_rank")),
        }
        row["loss_mask"] = {key: False for key in ALL_LOSSES}
        for key in TRAIN_LOSSES:
            row["loss_mask"][key] = True
        row["training_candidate"] = {
            "episode_step_observation_diagnosis": True,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
            "boundary_prefix_match_losses_disabled_to_avoid_raw_observation_copying": True,
        }
        row["authority"] = dict(AUTHORITY_CLOSED)
        state_blob = json.dumps(row.get("state"), sort_keys=True)
        if any(key in state_blob for key in TARGET_TEXT_KEYS):
            state_leak_rows.append(row["row_id"])
        rows.append(row)
        split_counts[str(row.get("split"))] += 1
        outcome_counts[str(next_state.get("repair_outcome"))] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(bool(value))
        authority_rows += int(any(bool(value) for value in row["authority"].values()))
        forbidden_loss_rows += int(any(bool(row["loss_mask"].get(key)) for key in FORBIDDEN))
    failures: list[str] = []
    if source.get("passed") is not False or source.get("metrics", {}).get("safety_passed") is not True:
        failures.append("source_stage9460_expected_safe_quality_failure_not_present")
    if len(rows) != 50:
        failures.append("unexpected_row_count")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows_present")
    if state_leak_rows:
        failures.append("state_target_text_leak_rows_present")
    for key in TRAIN_LOSSES:
        if loss_counts.get(key) != len(rows):
            failures.append(f"train_loss_count_mismatch:{key}")
    for key in DISABLED_EPISODE_LOSSES:
        if loss_counts.get(key, 0) != 0:
            failures.append(f"raw_observation_copy_loss_enabled:{key}")
    card = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9460_episode_step_target_100m_tiny_probe_audit",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "train_losses": sorted(TRAIN_LOSSES),
        "disabled_episode_losses": sorted(DISABLED_EPISODE_LOSSES),
        "authority_rows": authority_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "state_target_text_leak_rows": len(state_leak_rows),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    write_jsonl(MANIFEST, rows)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built an observation-conditioned episode-step diagnosis manifest after Stage9460 showed pre-action state alone was insufficient for strict residual diagnosis.",
        "next_best_step": "Run a no-execution trainer preflight for the observation diagnosis manifest; no target-100M execution until that contract passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9461 Episode-Step Observation Diagnosis Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Train losses: `{sorted(TRAIN_LOSSES)}`",
        f"Disabled losses: `{sorted(DISABLED_EPISODE_LOSSES)}`",
        "",
        "This manifest changes the task from pre-action outcome guessing to verifier-observation diagnosis. It exposes neutral raw observation booleans and buckets, but not generated text, residual reason labels, decoder text, target suffix, reward, failure_type, or repair_outcome as input.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "loss_counts": {key: loss_counts.get(key, 0) for key in sorted(TRAIN_LOSSES)}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
