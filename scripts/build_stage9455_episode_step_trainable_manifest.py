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
STAGE = 9455
NAME = "stage9455_episode_step_trainable_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9454_episode_step_head_support_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9446_episode_step_suffix_repair_manifest/episode_step_suffix_repair_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "episode_step_trainable_manifest.jsonl"
CARD = OUT_DIR / "episode_step_trainable_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_TRAINABLE_MANIFEST_STAGE9455.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EPISODE_LOSSES = {
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
}
FORBIDDEN = {"decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def safe_episode_transition(transition: dict) -> dict:
    state_t = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
    action_t = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
    prefix = str(state_t.get("active_generation_prefix_span") or "")
    safe_state = {
        "active_generation_prefix_span": prefix,
        "prefix_token_bucket": "short" if len(prefix.split()) <= 8 else "medium",
        "bridge_error_family": state_t.get("bridge_error_family", "unknown"),
        "route": state_t.get("route", "unknown"),
        "suffix_prior_available": bool(state_t.get("suffix_choice_prior_confidence")),
    }
    safe_action = {
        "action": action_t.get("action", "unknown"),
        "emission_surface_family": "bounded_suffix_repair",
    }
    return {
        "state_t": safe_state,
        "action_t": safe_action,
        "observation_t": transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {},
        "reward_or_verifier": transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {},
        "state_t_plus_1": transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {},
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    base_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict] = []
    split_counts = Counter()
    outcome_counts = Counter()
    loss_counts = Counter()
    authority_rows = 0
    forbidden_loss_rows = 0
    target_text_input_rows = 0
    for index, base in enumerate(base_rows):
        row = json.loads(json.dumps(base))
        row["row_id"] = f"stage9455_episode_step_trainable_{index:04d}"
        row["source_stage9446_row_id"] = base.get("row_id")
        row["objective_family"] = "episode_step_structured_supervision"
        row["route"] = "KEEP_EPISODE_STEP_STRUCTURED"
        transition = safe_episode_transition(row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {})
        row["episode_transition"] = transition
        state_t = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
        next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        # Explicit labels are in the target/next-state side only. They are not copied into state_t/action_t.
        row["loss_mask"] = {key: False for key in [
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
        ]}
        for key in EPISODE_LOSSES:
            row["loss_mask"][key] = True
        row["authority"] = dict(AUTHORITY_CLOSED)
        row["training_candidate"] = {
            "episode_step_structured_supervision": True,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
            "model_execution_authorized_now": False,
        }
        rows.append(row)
        split_counts[str(row.get("split"))] += 1
        outcome_counts[str(next_state.get("repair_outcome"))] += 1
        for key, value in row["loss_mask"].items():
            loss_counts[key] += int(bool(value))
        authority_rows += int(any(bool(v) for v in row["authority"].values()))
        forbidden_loss_rows += int(any(bool(row["loss_mask"].get(key)) for key in FORBIDDEN))
        target_text_input_rows += int(bool(next_state.get("decoder_text")) and str(next_state.get("decoder_text")) == str(state_t.get("active_generation_prefix_span")))

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9454_not_passed")
    if len(rows) != 50:
        failures.append("unexpected_row_count")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows_present")
    if target_text_input_rows:
        failures.append("target_text_copied_to_state_rows")
    for key in EPISODE_LOSSES:
        if loss_counts.get(key) != len(rows):
            failures.append(f"episode_loss_count_mismatch:{key}")
    card = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9454_episode_step_head_support_audit",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "authority_rows": authority_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "target_text_input_rows": target_text_input_rows,
        "decoder_ce_rows": loss_counts.get("decoder_ce", 0),
        "denoise_ce_rows": loss_counts.get("denoise_ce", 0),
        "runtime_reward_rows": loss_counts.get("runtime_reward", 0),
        "model_execution_authorized_next": False,
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
        "decision": "Built a trainable episode-step structured-head manifest; model execution remains closed pending shortcut and preexecution audits.",
        "next_best_step": "Audit Stage9455 for target leakage, shortcut baselines, split balance, and decoder/denoise/runtime closure.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9455 Episode-Step Trainable Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Splits: `{dict(sorted(split_counts.items()))}`",
        f"Outcomes: `{dict(sorted(outcome_counts.items()))}`",
        "",
        "Only episode-step structured losses are enabled. Decoder CE, denoise CE, runtime reward, model execution, and promotion remain closed.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "loss_counts": {key: loss_counts.get(key, 0) for key in sorted(EPISODE_LOSSES)}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
