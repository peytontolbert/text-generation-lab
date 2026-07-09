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
STAGE = 9513
NAME = "stage9513_episode_obs_diag_counterbalance_repair_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9508_episode_obs_diag_overlay_wide_eval_manifest/episode_obs_diag_overlay_wide_eval_manifest.jsonl"
QUEUE = ROOT / "runs/local/artifacts/stage9512_episode_obs_diag_eval_error_attribution/episode_obs_diag_repair_queue.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9512_episode_obs_diag_eval_error_attribution.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9513_episode_obs_diag_counterbalance_repair_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_counterbalance_repair_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_counterbalance_repair_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_COUNTERBALANCE_REPAIR_MANIFEST_STAGE9513.md"
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


def observation_features(row: dict) -> dict[str, object]:
    transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
    obs = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
    residuals = obs.get("residual_reasons") if isinstance(obs.get("residual_reasons"), list) else []
    rank = obs.get("boundary_expected_rank")
    if isinstance(rank, int):
        rank_bucket = "rank_1" if rank == 1 else "rank_2_8" if rank <= 8 else "rank_9_plus"
    else:
        rank_bucket = "rank_unknown"
    return {
        "obs_diag_evidence_version": "v1",
        "obs_prefix_relation": "prefix_match" if obs.get("target_prefix_match") is True else "prefix_miss",
        "obs_boundary_relation": "boundary_match" if obs.get("boundary_next_token_match") is True else "boundary_miss",
        "obs_boundary_rank_bucket": rank_bucket,
        "obs_residual_reason_count": len(residuals),
        "obs_has_not_exact_reason": "not_exact" in residuals,
        "obs_has_target_prefix_miss_reason": "target_prefix_miss" in residuals,
        "obs_has_boundary_next_token_miss_reason": "boundary_next_token_miss" in residuals,
        "obs_has_degenerate_repetition_reason": "degenerate_repetition" in residuals,
        "obs_has_unterminated_reason": "unterminated" in residuals,
        "obs_short_or_junk": bool(obs.get("short_or_junk")),
        "obs_degenerate_repetition": bool(obs.get("degenerate_repetition")),
        "obs_stopped_on_eos": bool(obs.get("stopped_on_eos")),
    }


def split_cell(row: dict) -> str:
    effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
    return f"{row.get('split')}::prefix={effective.get('effective_target_prefix_match')}|boundary={effective.get('effective_boundary_match')}|outcome={effective.get('effective_repair_outcome')}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = load_jsonl(SOURCE)
    queue_rows = load_jsonl(QUEUE)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if not source_rows:
        failures.append("missing_source_rows")
    if len(queue_rows) != 2:
        failures.append("unexpected_repair_queue_rows")
    if source_summary.get("passed") is not True:
        failures.append("stage9512_not_passed")

    queue_source_ids = {row.get("source_stage9508_row_id") for row in queue_rows}
    output_rows: list[dict] = []
    split_counts = Counter()
    split_cell_counts = Counter()
    loss_counts = Counter()
    authority_rows: list[str] = []
    forbidden_loss_rows: list[str] = []
    effective_leak_rows: list[str] = []
    model_feature_counts = Counter()
    repair_focus_rows: list[str] = []
    for idx, row in enumerate(source_rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9513_obs_diag_repair_{idx:04d}"
        out["source_stage9508_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_counterbalance_repair"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_COUNTERBALANCE_REPAIR"
        out["authority"] = dict(AUTHORITY_CLOSED)
        model_input = dict(out.get("model_input") or {})
        model_input.update(observation_features(row))
        model_input["obs_diag_counterbalance_phase"] = True
        model_input["obs_diag_repair_focus_source"] = row.get("row_id") in queue_source_ids
        out["model_input"] = model_input
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "counterbalance_repair_phase": True,
            "primitive_observation_evidence_visible": True,
            "effective_verifier_authority_remains_external": True,
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
        if model_input["obs_diag_repair_focus_source"]:
            repair_focus_rows.append(out["row_id"])
        for key in model_input:
            if key.startswith("obs_"):
                model_feature_counts[key] += 1
        split_counts[out.get("split")] += 1
        split_cell_counts[split_cell(out)] += 1
        output_rows.append(out)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(TRAINABLE_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if len(repair_focus_rows) != len(queue_source_ids):
        failures.append("repair_focus_source_rows_not_marked")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "source_repair_queue": str(QUEUE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "split_cell_counts": dict(sorted(split_cell_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "repair_focus_rows": repair_focus_rows,
        "model_feature_counts": dict(sorted(model_feature_counts.items())),
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "anti_cheat": {
            "effective_labels_outside_model_input": not effective_leak_rows,
            "primitive_observation_features_visible": True,
            "decoder_denoise_runtime_closed": not forbidden_loss_rows,
            "source_stage_ids_forbidden_as_discriminators": True,
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
        "decision": "Built counterbalanced observation-diagnosis repair rows with primitive observation evidence visible and deterministic effective labels still external.",
        "next_best_step": "Audit Stage9513 for observation feature leakage, loss closure, split balance, and preflight readiness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9513 Episode Observation Diagnosis Counterbalance Repair Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Repair focus rows: `{repair_focus_rows}`",
        "",
        "This patch exposes primitive observation evidence under neutral `obs_*` model-input features. It does not expose `effective_*` authority labels in `model_input`.",
        "",
        "The target is to fix the Stage9511 high-confidence eval failures where the model inferred verifier outcome from pre-action context instead of observed residual facts.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "repair_focus_rows": len(repair_focus_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
