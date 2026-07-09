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
STAGE = 9487
NAME = "stage9487_full_episode_with_observe_prefix_manifest"
SOURCE_FULL = ROOT / "runs/local/artifacts/stage9455_episode_step_trainable_manifest/episode_step_trainable_manifest.jsonl"
SOURCE_PREFIX = ROOT / "runs/local/artifacts/stage9484_target_prefix_observe_phase_manifest/target_prefix_observe_phase_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9486_target_prefix_observe_phase_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9487_full_episode_with_observe_prefix_manifest"
MANIFEST = OUT_DIR / "full_episode_with_observe_prefix_manifest.jsonl"
CARD = OUT_DIR / "full_episode_with_observe_prefix_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_EPISODE_WITH_OBSERVE_PREFIX_MANIFEST_STAGE9487.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

PRE_ACTION_LOSSES = {
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
}
OBSERVE_PREFIX_LOSS = "episode_target_prefix_match_ce"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def loss_counts(rows: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("loss_mask") or {}).items():
            if value:
                counts[key] += 1
    return dict(sorted(counts.items()))


def split_counts(rows: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("split", "other")) for row in rows).items()))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    full_rows = load_jsonl(SOURCE_FULL)
    prefix_rows = load_jsonl(SOURCE_PREFIX)

    rows: list[dict] = []
    failures: list[str] = []

    for index, row in enumerate(full_rows):
        patched = copy.deepcopy(row)
        patched["row_id"] = f"stage9487_pre_action_{index:04d}"
        patched["source_stage9455_row_id"] = row.get("row_id")
        patched["objective_family"] = "episode_step_pre_action_structured_supervision"
        patched["route"] = "KEEP_EPISODE_STEP_PRE_ACTION_STRUCTURED"
        patched["source_kind"] = "stage9455_prefix_loss_removed"
        loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
        for key in list(loss_mask):
            loss_mask[key] = key in PRE_ACTION_LOSSES
        patched["loss_mask"] = loss_mask
        anti_cheat = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
        anti_cheat["target_prefix_loss_removed_from_pre_action_row"] = True
        anti_cheat["target_prefix_supervised_only_on_observe_phase_rows"] = True
        patched["anti_cheat"] = anti_cheat
        patched["stage9487_design_note"] = "Pre-action row trains boundary/failure/outcome/value only; target-prefix moved to observe-phase verifier rows."
        rows.append(patched)

    for index, row in enumerate(prefix_rows):
        patched = copy.deepcopy(row)
        patched["row_id"] = f"stage9487_observe_prefix_{index:04d}"
        patched["source_stage9484_row_id"] = row.get("row_id")
        patched["objective_family"] = "episode_step_observe_phase_target_prefix_verifier"
        patched["route"] = "KEEP_EPISODE_STEP_OBSERVE_PREFIX_VERIFIER"
        patched["source_kind"] = "stage9484_observe_prefix_rejoin"
        loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
        for key in list(loss_mask):
            loss_mask[key] = key == OBSERVE_PREFIX_LOSS
        patched["loss_mask"] = loss_mask
        anti_cheat = patched.get("anti_cheat") if isinstance(patched.get("anti_cheat"), dict) else {}
        anti_cheat["generated_and_reference_text_visible_for_observe_phase_verifier"] = True
        anti_cheat["target_prefix_match_label_hidden_from_encoder"] = True
        anti_cheat["target_prefix_supervised_only_on_observe_phase_rows"] = True
        patched["anti_cheat"] = anti_cheat
        patched["stage9487_design_note"] = "Observe-phase row trains target-prefix relation using visible generated/reference evidence."
        rows.append(patched)

    row_ids = [row.get("row_id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        failures.append("duplicate_row_ids")
    if source_summary.get("passed") is not True:
        failures.append("source_stage9486_not_passed")
    authority_rows = [
        row.get("row_id")
        for row in rows
        if any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED)
    ]
    if authority_rows:
        failures.append("authority_rows_present")
    loss = loss_counts(rows)
    expected_loss = {
        "episode_boundary_match_ce": 50,
        "episode_failure_type_ce": 50,
        "episode_repair_outcome_ce": 50,
        "episode_step_value_mse": 50,
        "episode_target_prefix_match_ce": 66,
    }
    if loss != expected_loss:
        failures.append("unexpected_loss_counts")
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward"]):
        failures.append("forbidden_decoder_denoise_or_runtime_loss")

    label_by_split_language: Counter[str] = Counter()
    phase_by_split: Counter[str] = Counter()
    for row in rows:
        split = str(row.get("split", "other"))
        phase = str(row.get("objective_family", "unknown"))
        phase_by_split[f"{split}::{phase}"] += 1
        if (row.get("loss_mask") or {}).get(OBSERVE_PREFIX_LOSS):
            obs = (row.get("episode_transition") or {}).get("observation_t") or {}
            label_by_split_language[f"{split}::{row.get('language_family')}::{obs.get('target_prefix_match')}"] += 1

    card = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "source_full_rows": len(full_rows),
        "source_observe_prefix_rows": len(prefix_rows),
        "split_counts": split_counts(rows),
        "phase_by_split": dict(sorted(phase_by_split.items())),
        "loss_counts": loss,
        "expected_loss_counts": expected_loss,
        "observe_prefix_label_by_split_language": dict(sorted(label_by_split_language.items())),
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:20],
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_full_manifest": str(SOURCE_FULL.relative_to(ROOT)),
        "source_observe_prefix_manifest": str(SOURCE_PREFIX.relative_to(ROOT)),
        "design_note": "Full episode-step rejoin manifest: four pre-action heads remain on Stage9455 rows, while target-prefix moves to Stage9484 observe/verifier-phase rows.",
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
        "decision": "Composed full episode-step structured manifest with target-prefix supervision moved from pre-action rows to observe-phase verifier rows.",
        "next_best_step": "Run Stage9488 contract-only target-100M preflight for the full episode-step observe-prefix rejoin manifest; do not execute until it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9487 Full Episode With Observe-Prefix Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Loss counts: `{card['loss_counts']}`",
        "",
        "This manifest keeps the four pre-action episode heads on Stage9455 rows and moves `episode_target_prefix_match_ce` onto observe/verifier-phase rows with visible generated/reference evidence.",
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
        "loss_counts": loss,
        "failures": failures,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
