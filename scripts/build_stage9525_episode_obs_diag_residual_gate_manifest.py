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
STAGE = 9525
NAME = "stage9525_episode_obs_diag_residual_gate_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9521_episode_obs_diag_minimal_context_manifest/episode_obs_diag_minimal_context_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9524_episode_obs_diag_minimal_context_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_residual_gate_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_residual_gate_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_RESIDUAL_GATE_MANIFEST_STAGE9525.md"
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


def residual_gate(model_input: dict) -> dict[str, object]:
    prefix = model_input.get("obs_prefix_relation")
    boundary = model_input.get("obs_boundary_relation")
    count = model_input.get("obs_residual_reason_count")
    any_residual = bool(count) or prefix != "prefix_match" or boundary != "boundary_match"
    if not any_residual:
        alignment = "clean_success_observation"
    elif boundary == "boundary_miss":
        alignment = "boundary_residual_observation"
    elif prefix == "prefix_miss":
        alignment = "prefix_residual_observation"
    else:
        alignment = "other_residual_observation"
    if model_input.get("obs_has_boundary_next_token_miss_reason"):
        failure_family = "prefix_and_boundary_miss_evidence"
    elif model_input.get("obs_has_target_prefix_miss_reason"):
        failure_family = "prefix_miss_evidence"
    elif any_residual:
        failure_family = "residual_evidence"
    else:
        failure_family = "no_residual_evidence"
    return {
        "obs_diag_residual_gate_patch_phase": True,
        "obs_any_residual_reason": any_residual,
        "obs_all_alignment_passed": not any_residual,
        "obs_alignment_status": alignment,
        "obs_failure_evidence_family": failure_family,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if not rows:
        failures.append("missing_source_rows")
    if source_summary.get("metrics", {}).get("safety_passed") is not True:
        failures.append("stage9524_not_safe")
    wrong_ids = {
        row.get("row_id")
        for row in source_summary.get("metrics", {}).get("wrong_rows", [])
        if isinstance(row, dict)
    }

    output_rows: list[dict] = []
    split_counts = Counter()
    language_counts = Counter()
    alignment_counts = Counter()
    wrong_source_counts = Counter()
    loss_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    missing_gate_rows: list[str] = []
    stale_focus_rows: list[str] = []
    for idx, row in enumerate(rows):
        out = copy.deepcopy(row)
        out["row_id"] = f"stage9525_obs_diag_resgate_{idx:04d}"
        out["source_stage9521_row_id"] = row.get("row_id")
        out["source_stage9524_wrong_row"] = row.get("row_id") in wrong_ids
        out["objective_family"] = "episode_observation_diagnosis_residual_gate"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_RESIDUAL_GATE"
        out["authority"] = dict(AUTHORITY_CLOSED)

        model_input = dict(out.get("model_input") or {})
        # The prior repair-focus marker was tied to older eval-only failures. Keep
        # residual evidence tied to observation facts, not historical row identity.
        model_input["obs_diag_repair_focus_source"] = False
        model_input.update(residual_gate(model_input))
        out["model_input"] = model_input
        out["training_candidate"] = {
            **(out.get("training_candidate") or {}),
            "residual_gate_patch_phase": True,
            "stage9524_wrong_row_source": out["source_stage9524_wrong_row"],
            "stale_eval_focus_marker_removed_from_model_input": True,
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
        if not model_input.get("obs_diag_residual_gate_patch_phase") or model_input.get("obs_alignment_status") is None:
            missing_gate_rows.append(out["row_id"])
        if model_input.get("obs_diag_repair_focus_source"):
            stale_focus_rows.append(out["row_id"])
        split_counts[out.get("split")] += 1
        language_counts[out.get("language_family")] += 1
        alignment_counts[model_input.get("obs_alignment_status")] += 1
        wrong_source_counts[str(out["source_stage9524_wrong_row"])] += 1
        output_rows.append(out)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(TRAINABLE_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if missing_gate_rows:
        failures.append("missing_residual_gate_rows")
    if stale_focus_rows:
        failures.append("stale_focus_rows_in_model_input")
    if wrong_source_counts.get("True") != 2:
        failures.append("unexpected_stage9524_wrong_source_count")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "alignment_counts": dict(sorted(alignment_counts.items())),
        "stage9524_wrong_source_counts": dict(sorted(wrong_source_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "missing_gate_rows": missing_gate_rows,
        "stale_focus_rows": stale_focus_rows,
        "contract": {
            "effective_labels_outside_model_input": not effective_leak_rows,
            "residual_gate_derived_from_observation_features": True,
            "stale_eval_focus_marker_removed": not stale_focus_rows,
            "decoder_denoise_runtime_closed": not forbidden_loss_rows,
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
        "decision": "Built residual-gate diagnosis rows from Stage9521 with stale eval-only focus markers removed and observation-derived alignment gates added.",
        "next_best_step": "Audit Stage9525 for leakage, loss closure, residual-gate coverage, and preflight readiness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9525 Episode Observation Diagnosis Residual-Gate Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Alignment counts: `{dict(alignment_counts)}`",
        f"Stage9524 wrong source counts: `{dict(wrong_source_counts)}`",
        "",
        "This patch keeps minimal context but adds observation-derived residual gates and removes the stale eval-only repair-focus marker from model input.",
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
