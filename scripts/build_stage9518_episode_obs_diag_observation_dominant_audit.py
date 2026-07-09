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
STAGE = 9518
NAME = "stage9518_episode_obs_diag_observation_dominant_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9517_episode_obs_diag_observation_dominant_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9517_episode_obs_diag_observation_dominant_manifest/episode_obs_diag_observation_dominant_manifest.jsonl"
CARD = ROOT / "runs/local/artifacts/stage9517_episode_obs_diag_observation_dominant_manifest/episode_obs_diag_observation_dominant_manifest_card.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9518_episode_obs_diag_observation_dominant_audit"
AUDIT = OUT_DIR / "episode_obs_diag_observation_dominant_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OBSERVATION_DOMINANT_AUDIT_STAGE9518.md"
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
    card = load_json(CARD)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9517_summary_not_passed")
    if card.get("passed") is not True:
        failures.append("stage9517_card_not_passed")
    if len(rows) != 58:
        failures.append("unexpected_row_count")

    split_counts = Counter()
    loss_counts = Counter()
    language_counts = Counter()
    route_counts = Counter()
    authority_rows: list[str] = []
    forbidden_rows: list[str] = []
    effective_leak_rows: list[str] = []
    neutralization_fail_rows: list[str] = []
    missing_obs_rows: list[str] = []
    required_obs = {"obs_prefix_relation", "obs_boundary_relation", "obs_residual_reason_count", "obs_diag_observation_dominant_phase"}
    for row in rows:
        row_id = row.get("row_id")
        split_counts[row.get("split")] += 1
        language_counts[row.get("language_family")] += 1
        route_counts[row.get("route")] += 1
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row_id)
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        for loss in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]:
            if loss_mask.get(loss):
                forbidden_rows.append(row_id)
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row_id)
        if not required_obs.issubset(model_input):
            missing_obs_rows.append(row_id)
        transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
        state = transition.get("state_t") if isinstance(transition.get("state_t"), dict) else {}
        action = transition.get("action_t") if isinstance(transition.get("action_t"), dict) else {}
        if row.get("language_family") != "neutral_observation_diagnosis" or state.get("route") != "OBSERVATION_DIAGNOSIS_ONLY" or action.get("action") != "OBSERVE_VERIFIER_STATE":
            neutralization_fail_rows.append(row_id)

    expected_losses = {
        "episode_failure_type_ce": 58,
        "episode_repair_outcome_ce": 58,
        "episode_step_value_mse": 58,
    }
    if dict(loss_counts) != expected_losses:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_rows:
        failures.append("forbidden_loss_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_labels_in_model_input")
    if neutralization_fail_rows:
        failures.append("neutralization_fail_rows")
    if missing_obs_rows:
        failures.append("missing_observation_features")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "route_counts": dict(sorted(route_counts.items())),
        "authority_rows": authority_rows,
        "forbidden_rows": forbidden_rows,
        "effective_leak_rows": effective_leak_rows,
        "neutralization_fail_rows": neutralization_fail_rows,
        "missing_obs_rows": missing_obs_rows,
        "decision": "Observation-dominant diagnosis manifest is ready for contract-only preflight.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "promotion_ready": False,
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
        "decision": audit["decision"],
        "next_best_step": "Run contract-only target-100M preflight for Stage9517 with max rows 46/6/6 and no decoder, denoise, runtime, checkpoint export, or promotion authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9518 Episode Observation Diagnosis Observation-Dominant Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Rows: `{len(rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        audit["decision"],
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "rows": len(rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
