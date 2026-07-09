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
STAGE = 9517
NAME = "stage9517_episode_obs_diag_observation_dominant_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9513_episode_obs_diag_counterbalance_repair_manifest/episode_obs_diag_counterbalance_repair_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9516_episode_obs_diag_counterbalance_repair_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9517_episode_obs_diag_observation_dominant_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_observation_dominant_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_observation_dominant_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OBSERVATION_DOMINANT_MANIFEST_STAGE9517.md"
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = load_jsonl(SOURCE)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if not source_rows:
        failures.append("missing_source_rows")
    if source_summary.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9516_not_safe_failure_source")

    output_rows: list[dict] = []
    split_counts = Counter()
    loss_counts = Counter()
    authority_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    effective_leak_rows: list[str] = []
    neutralization_fail_rows: list[str] = []
    obs_counts = Counter()
    for idx, row in enumerate(source_rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9517_obs_diag_obsdom_{idx:04d}"
        out["source_stage9513_row_id"] = row.get("row_id")
        out["language_family"] = "neutral_observation_diagnosis"
        out["objective_family"] = "episode_observation_diagnosis_observation_dominant"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_OBSERVATION_DOMINANT"
        out["authority"] = dict(AUTHORITY_CLOSED)
        transition = out.get("episode_transition") if isinstance(out.get("episode_transition"), dict) else {}
        transition["state_t"] = {
            "active_generation_prefix_span": "neutralized_for_observation_diagnosis",
            "bridge_error_family": "neutralized_for_observation_diagnosis",
            "prefix_token_bucket": "neutralized",
            "route": "OBSERVATION_DIAGNOSIS_ONLY",
            "suffix_prior_available": "neutralized",
        }
        transition["action_t"] = {
            "action": "OBSERVE_VERIFIER_STATE",
            "emission_surface_family": "neutralized_for_observation_diagnosis",
        }
        out["episode_transition"] = transition
        model_input = dict(out.get("model_input") or {})
        model_input["obs_diag_observation_dominant_phase"] = True
        model_input["surface_priors_neutralized"] = True
        out["model_input"] = model_input
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "observation_dominant_phase": True,
            "language_and_surface_priors_neutralized": True,
            "primitive_observation_evidence_visible": True,
            "model_execution_authorized_now": False,
            "decoder_ce_closed": True,
            "denoise_ce_closed": True,
            "runtime_reward_closed": True,
        }
        loss_mask = dict(out.get("loss_mask") or {})
        for loss in TRAINABLE_LOSSES:
            loss_mask[loss] = True
        for loss in FORBIDDEN_LOSSES:
            loss_mask[loss] = False
        out["loss_mask"] = loss_mask
        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        if any(loss_mask.get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(out["row_id"])
        if any((out.get("authority") or {}).values()):
            authority_rows.append(out["row_id"])
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(out["row_id"])
        if out.get("language_family") != "neutral_observation_diagnosis" or transition.get("state_t", {}).get("route") != "OBSERVATION_DIAGNOSIS_ONLY":
            neutralization_fail_rows.append(out["row_id"])
        for key in ["obs_prefix_relation", "obs_boundary_relation", "obs_residual_reason_count"]:
            obs_counts[f"{key}::{model_input.get(key)}"] += 1
        split_counts[out.get("split")] += 1
        output_rows.append(out)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(TRAINABLE_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if authority_rows:
        failures.append("authority_rows_present")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if neutralization_fail_rows:
        failures.append("neutralization_fail_rows")

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
        "obs_counts": dict(sorted(obs_counts.items())),
        "authority_rows": authority_rows,
        "forbidden_loss_rows": forbidden_loss_rows,
        "effective_leak_rows": effective_leak_rows,
        "neutralization_fail_rows": neutralization_fail_rows,
        "contract": {
            "language_family_neutralized": True,
            "episode_state_action_surface_neutralized": True,
            "primitive_observation_features_visible": True,
            "effective_labels_outside_model_input": True,
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
        "decision": "Built observation-dominant diagnosis rows to force failure/outcome/value learning from primitive observation evidence rather than surface/language priors.",
        "next_best_step": "Audit Stage9517, then run contract-only target-100M preflight if neutralization and loss checks pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9517 Episode Observation Diagnosis Observation-Dominant Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This manifest neutralizes language and pre-action surface priors so diagnosis heads must rely on primitive `obs_*` verifier evidence.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
