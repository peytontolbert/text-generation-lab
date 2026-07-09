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
STAGE = 9490
NAME = "stage9490_phase_aware_episode_verifier_manifest"
SOURCE_OBSERVE = ROOT / "runs/local/artifacts/stage9484_target_prefix_observe_phase_manifest/target_prefix_observe_phase_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9489_full_episode_observe_prefix_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9490_phase_aware_episode_verifier_manifest"
MANIFEST = OUT_DIR / "phase_aware_episode_verifier_manifest.jsonl"
CARD = OUT_DIR / "phase_aware_episode_verifier_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHASE_AWARE_EPISODE_VERIFIER_MANIFEST_STAGE9490.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

VERIFIER_LOSSES = {
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_OBSERVE)
    rows: list[dict] = []
    failures: list[str] = []

    for index, row in enumerate(source_rows):
        patched = copy.deepcopy(row)
        transition = patched.get("episode_transition") if isinstance(patched.get("episode_transition"), dict) else {}
        observation = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
        next_state = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
        generated = str(observation.get("generated_text") or "")
        reference = str(next_state.get("decoder_text") or "")

        patched["row_id"] = f"stage9490_observe_verifier_{index:04d}"
        patched["source_stage9484_row_id"] = row.get("row_id")
        patched["objective_family"] = "episode_observe_phase_verifier_normalization"
        patched["route"] = "KEEP_EPISODE_OBSERVE_PHASE_VERIFIER"
        patched["source_kind"] = "stage9484_observe_phase_verifier_relabel"
        loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
        for key in list(loss_mask):
            loss_mask[key] = key in VERIFIER_LOSSES
        patched["loss_mask"] = loss_mask
        patched["model_input"] = {
            "observe_phase": True,
            "verifier_normalization_phase": True,
            "generated_output_preview": generated,
            "reference_output_preview": reference,
            "generated_output_chars": len(generated),
            "reference_output_chars": len(reference),
            "generation_stopped_on_eos": bool(observation.get("stopped_on_eos")),
            "short_or_junk_observed": bool(observation.get("short_or_junk")),
            "degenerate_repetition_observed": bool(observation.get("degenerate_repetition")),
            "residual_reason_count_observed": len(observation.get("residual_reasons") or []),
            "verifier_source": str(verifier.get("verifier_source") or ""),
        }
        anti_cheat = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
        anti_cheat.update({
            "generated_and_reference_text_visible_for_observe_phase_verifier": True,
            "primitive_verifier_observations_visible": True,
            "failure_type_label_hidden_from_encoder": True,
            "repair_outcome_label_hidden_from_encoder": True,
            "step_value_label_hidden_from_encoder": True,
            "boundary_match_label_hidden_from_encoder": True,
            "target_prefix_match_label_hidden_from_encoder": True,
            "reward_hidden_from_encoder": True,
        })
        patched["anti_cheat"] = anti_cheat
        patched["stage9490_design_note"] = "All verifier-derived episode labels are trained on observe-phase rows with generated/reference and primitive verifier observations visible."
        rows.append(patched)

    if source_summary.get("safety_passed") is not True and source_summary.get("passed") is not False:
        failures.append("source_stage9489_safety_status_unexpected")
    row_ids = [row.get("row_id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        failures.append("duplicate_row_ids")
    authority_rows = [
        row.get("row_id")
        for row in rows
        if any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED)
    ]
    if authority_rows:
        failures.append("authority_rows_present")

    loss_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    for row in rows:
        split = str(row.get("split", "other"))
        split_counts[split] += 1
        transition = row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}
        obs = transition.get("observation_t") if isinstance(transition.get("observation_t"), dict) else {}
        nxt = transition.get("state_t_plus_1") if isinstance(transition.get("state_t_plus_1"), dict) else {}
        verifier = transition.get("reward_or_verifier") if isinstance(transition.get("reward_or_verifier"), dict) else {}
        for key, value in (row.get("loss_mask") or {}).items():
            if value:
                loss_counts[key] += 1
        label_counts[f"{split}::boundary::{obs.get('boundary_next_token_match')}"] += 1
        label_counts[f"{split}::target_prefix::{obs.get('target_prefix_match')}"] += 1
        label_counts[f"{split}::failure::{verifier.get('failure_type')}"] += 1
        label_counts[f"{split}::outcome::{nxt.get('repair_outcome')}"] += 1
        label_counts[f"{split}::value::{1.0 if float(verifier.get('reward') or 0.0) >= 0.5 else 0.0}"] += 1

    expected_loss_counts = {key: len(rows) for key in sorted(VERIFIER_LOSSES)}
    if dict(sorted(loss_counts.items())) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward"]):
        failures.append("forbidden_decoder_denoise_or_runtime_loss")

    card = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "label_counts": dict(sorted(label_counts.items())),
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:20],
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_observe_manifest": str(SOURCE_OBSERVE.relative_to(ROOT)),
        "source_stage9489": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "design_note": "Phase-aware verifier manifest: all five episode verifier labels move to observe-phase rows with visible generated/reference evidence and primitive verifier observations.",
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
        "artifacts": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "card": str(CARD.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built phase-aware observe/verifier manifest for all episode verifier labels after Stage9489 showed pre-action verifier labels were not clean policy targets.",
        "next_best_step": "Run Stage9491 contract-only target-100M preflight for phase-aware episode verifier normalization; do not execute until it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9490 Phase-Aware Episode Verifier Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Loss counts: `{card['loss_counts']}`",
        "",
        "All five episode verifier labels are now observe-phase verifier-normalization targets. Generated/reference output evidence and primitive verifier observations are visible; final labels remain hidden.",
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = bool(reg_rows)
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(reg_rows),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "rows": len(rows),
        "split_counts": card["split_counts"],
        "loss_counts": card["loss_counts"],
        "failures": failures,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
