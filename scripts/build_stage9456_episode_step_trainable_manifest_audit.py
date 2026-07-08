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
STAGE = 9456
NAME = "stage9456_episode_step_trainable_manifest_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9455_episode_step_trainable_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "episode_step_trainable_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_TRAINABLE_MANIFEST_AUDIT_STAGE9456.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EPISODE_LOSSES = {
    "episode_repair_outcome_ce",
    "episode_failure_type_ce",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
    "episode_step_value_mse",
}
FORBIDDEN_LOSSES = {"decoder_ce", "denoise_ce", "runtime_reward"}
TARGET_FIELD_NAMES = {
    "repair_outcome",
    "target_suffix_choice",
    "decoder_text",
    "reward",
    "failure_type",
    "residual_reasons",
    "boundary_next_token_match",
    "target_prefix_match",
}


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
    training_data_source = (ROOT / "legacy_src/agentkernel_lite/training_data.py").read_text()
    failures: list[str] = []
    split_counts = Counter()
    loss_counts = Counter()
    outcome_counts = Counter()
    authority_rows = []
    forbidden_loss_rows = []
    state_action_target_leak_rows = []
    for row in rows:
        row_id = str(row.get("row_id"))
        split_counts[str(row.get("split"))] += 1
        transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
        state_t = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
        action_t = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
        next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        outcome_counts[str(next_state.get("repair_outcome"))] += 1
        state_action_blob = json.dumps({"state_t": state_t, "action_t": action_t}, sort_keys=True)
        for target_key in TARGET_FIELD_NAMES:
            if target_key in state_action_blob:
                state_action_target_leak_rows.append(row_id)
                break
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for key, value in mask.items():
            loss_counts[key] += int(bool(value))
        if any(bool(mask.get(key)) for key in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(row_id)
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        if any(bool(v) for v in authority.values()):
            authority_rows.append(row_id)

    if source.get("passed") is not True:
        failures.append("source_stage9455_not_passed")
    if len(rows) != 50:
        failures.append("unexpected_row_count")
    for key in EPISODE_LOSSES:
        if loss_counts.get(key) != len(rows):
            failures.append(f"episode_loss_count_mismatch:{key}")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows_present")
    if authority_rows:
        failures.append("authority_rows_present")
    if state_action_target_leak_rows:
        failures.append("state_action_target_leak_rows_present")
    if '_append_structured(parts, "episode.state", episode_state)' not in training_data_source:
        failures.append("serializer_missing_episode_state")
    if '_append_structured(parts, "episode.action", episode_action)' not in training_data_source:
        failures.append("serializer_missing_episode_action")
    if '_append_structured(parts, "episode.observation"' in training_data_source or '_append_structured(parts, "episode.next"' in training_data_source:
        failures.append("serializer_exposes_target_side_episode_fields")

    strongest_majority_outcome = max(outcome_counts.values()) / max(1, sum(outcome_counts.values()))
    split_ok = split_counts == Counter({"train": 48, "eval": 1, "strict_eval": 1})
    if not split_ok:
        failures.append("unexpected_split_counts")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9455_episode_step_trainable_manifest",
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "strongest_majority_outcome_baseline": strongest_majority_outcome,
        "loss_counts": dict(sorted(loss_counts.items())),
        "episode_loss_rows": {key: loss_counts.get(key, 0) for key in sorted(EPISODE_LOSSES)},
        "forbidden_loss_rows": len(forbidden_loss_rows),
        "authority_rows": len(authority_rows),
        "state_action_target_leak_rows": len(state_action_target_leak_rows),
        "serializer_exposes_episode_state_action_only": not any(name in failures for name in ["serializer_missing_episode_state", "serializer_missing_episode_action", "serializer_exposes_target_side_episode_fields"]),
        "decoder_ce_reopened": False,
        "denoise_ce_reopened": False,
        "model_execution_authorized_next": False,
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
        "decision": "Audited the episode-step trainable manifest and serializer contract; execution remains closed.",
        "next_best_step": "Design a closed-boundary preexecution wrapper for a tiny episode-step structured probe; do not execute until authorized separately.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9456 Episode-Step Trainable Manifest Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Forbidden loss rows: `{len(forbidden_loss_rows)}`",
        f"State/action target leak rows: `{len(state_action_target_leak_rows)}`",
        f"Majority outcome baseline: `{strongest_majority_outcome:.3f}`",
        "",
        "The serializer exposes only episode state/action fields. Observation, verifier/reward, and next-state targets remain hidden from model input.",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
