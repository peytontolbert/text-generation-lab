#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9504
NAME = "stage9504_episode_obs_diag_overlay_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9472_episode_obs_diag_balanced_order_manifest/episode_obs_diag_balanced_order_manifest.jsonl"
SOURCE_CARD = ROOT / "runs/local/artifacts/stage9472_episode_obs_diag_balanced_order_manifest/episode_obs_diag_balanced_order_manifest_card.json"
STAGE9476 = ROOT / "runs/summaries/stage9476_episode_obs_diag_best_state_probe_audit.json"
STAGE9503 = ROOT / "runs/summaries/stage9503_verifier_overlay_rejoin_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9504_episode_obs_diag_overlay_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_overlay_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_overlay_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OVERLAY_MANIFEST_STAGE9504.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TRAINABLE_LOSSES = {
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
}
FORBIDDEN_LOSSES = {
    "decoder_ce",
    "denoise_ce",
    "runtime_reward",
    "episode_boundary_match_ce",
    "episode_target_prefix_match_ce",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def effective_verifier(row: dict) -> dict[str, object]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    reward = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
    next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
    return {
        "effective_boundary_match": observation.get("boundary_next_token_match"),
        "effective_target_prefix_match": observation.get("target_prefix_match"),
        "effective_failure_type": reward.get("failure_type"),
        "effective_repair_outcome": next_state.get("repair_outcome"),
        "effective_step_value": reward.get("reward"),
        "effective_step_passed": reward.get("step_passed"),
        "authority_source": "deterministic_verifier_overlay",
        "learned_heads_authority": "telemetry_only",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source_rows = load_jsonl(SOURCE)
    source_card = load_json(SOURCE_CARD)
    stage9476 = load_json(STAGE9476)
    stage9503 = load_json(STAGE9503)
    failures: list[str] = []
    if not source_rows:
        failures.append("missing_source_rows")
    if source_card.get("passed") is not True:
        failures.append("stage9472_card_not_passed")
    if stage9476.get("passed") is not True:
        failures.append("stage9476_best_state_probe_not_passed")
    if stage9503.get("passed") is not True:
        failures.append("stage9503_overlay_audit_not_passed")

    output_rows: list[dict] = []
    split_counts = Counter()
    loss_counts = Counter()
    cell_counts = Counter()
    missing_effective_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    for idx, row in enumerate(source_rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9504_obs_diag_overlay_{idx:04d}"
        out["source_stage9472_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_overlay"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_WITH_VERIFIER_OVERLAY"
        out["effective_verifier"] = effective_verifier(row)
        out["authority"] = dict(AUTHORITY_CLOSED)
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "learned_verifier_heads_authority": "telemetry_only",
            "deterministic_verifier_overlay_available": True,
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
        loss_mask = dict(out.get("loss_mask") or {})
        for key in FORBIDDEN_LOSSES:
            loss_mask[key] = False
        for key in TRAINABLE_LOSSES:
            loss_mask[key] = True
        out["loss_mask"] = loss_mask
        for key, enabled in loss_mask.items():
            if enabled:
                loss_counts[key] += 1
        if any(loss_mask.get(key) for key in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(out["row_id"])
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        effective = out["effective_verifier"]
        if any(value is None for value in effective.values() if not isinstance(value, str)):
            missing_effective_rows.append(out["row_id"])
        model_input = out.get("model_input") if isinstance(out.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        cell_counts[f"prefix={effective.get('effective_target_prefix_match')}|outcome={effective.get('effective_repair_outcome')}"] += 1
        output_rows.append(out)

    expected_loss_counts = {key: len(output_rows) for key in sorted(TRAINABLE_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_trainable_loss_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if missing_effective_rows:
        failures.append("missing_effective_verifier_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "cell_counts": dict(sorted(cell_counts.items())),
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "missing_effective_rows": missing_effective_rows,
        "effective_leak_rows": effective_leak_rows,
        "source_evidence": {
            "stage9476_best_state_probe_passed": stage9476.get("passed"),
            "stage9503_overlay_audit_passed": stage9503.get("passed"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **card},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Rebuilt the trainable observation-diagnosis manifest with deterministic verifier overlay metadata and only failure/outcome/value losses enabled.",
        "next_best_step": "Audit Stage9504 for trainable loss closure, overlay leakage, authority closure, and preflight readiness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9504 Episode Observation Diagnosis Overlay Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This manifest restores the trainable observation-diagnosis heads that previously passed best-state selection, while attaching deterministic verifier overlay metadata outside `model_input`.",
        "",
        "Enabled losses are limited to `episode_failure_type_ce`, `episode_repair_outcome_ce`, and `episode_step_value_mse`. Boundary and target-prefix remain deterministic effective verifier facts, not learned authority.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "loss_counts": dict(loss_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
