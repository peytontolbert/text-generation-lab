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
STAGE = 9533
NAME = "stage9533_episode_obs_diag_python_boundary_upsample_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9525_episode_obs_diag_residual_gate_manifest/episode_obs_diag_residual_gate_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9532_episode_obs_diag_boundary_component_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9533_episode_obs_diag_python_boundary_upsample_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_python_boundary_upsample_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_python_boundary_upsample_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_PYTHON_BOUNDARY_UPSAMPLE_MANIFEST_STAGE9533.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def failure_type_only(row: dict) -> dict:
    out = copy.deepcopy(row)
    loss_mask = dict(out.get("loss_mask") or {})
    loss_mask["episode_failure_type_ce"] = True
    loss_mask["episode_repair_outcome_ce"] = False
    loss_mask["episode_step_value_mse"] = False
    for loss in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce"]:
        loss_mask[loss] = False
    out["loss_mask"] = loss_mask
    out["training_candidate"] = {
        **(out.get("training_candidate") or {}),
        "python_boundary_upsample_phase": True,
        "failure_type_only_focus": True,
        "model_execution_authorized_now": False,
        "decoder_ce_closed": True,
        "denoise_ce_closed": True,
        "runtime_reward_closed": True,
    }
    return out


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
        failures.append("stage9532_not_safe")
    if source_summary.get("metrics", {}).get("regressed_vs_stage9528") is not True:
        failures.append("stage9532_regression_not_recorded")

    output_rows: list[dict] = []
    base_rows: list[dict] = []
    for idx, row in enumerate(rows):
        out = failure_type_only(row)
        out["row_id"] = f"stage9533_obs_diag_pybound_{idx:04d}"
        out["source_stage9525_row_id"] = row.get("row_id")
        out["objective_family"] = "episode_observation_diagnosis_python_boundary_upsample"
        out["route"] = "KEEP_EPISODE_OBS_DIAG_PYTHON_BOUNDARY_UPSAMPLE"
        out["authority"] = dict(AUTHORITY_CLOSED)
        output_rows.append(out)
        base_rows.append(out)

    train_python_boundary = [
        row for row in base_rows
        if row.get("split") == "train"
        and row.get("language_family") == "python"
        and (row.get("model_input") or {}).get("obs_boundary_relation") == "boundary_miss"
    ]
    if len(train_python_boundary) != 4:
        failures.append("unexpected_train_python_boundary_source_count")
    upsample_rows: list[str] = []
    next_idx = len(output_rows)
    for repeat in range(2):
        for source_row in train_python_boundary:
            dup = copy.deepcopy(source_row)
            dup["row_id"] = f"stage9533_obs_diag_pybound_{next_idx:04d}"
            dup["source_stage9533_upsampled_from"] = source_row.get("row_id")
            dup["training_candidate"] = {**(dup.get("training_candidate") or {}), "python_boundary_upsampled_duplicate": True, "upsample_repeat": repeat + 1}
            output_rows.append(dup)
            upsample_rows.append(dup["row_id"])
            next_idx += 1

    split_counts = Counter()
    language_counts = Counter()
    loss_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []
    source_eval_duplicate_rows: list[str] = []
    for row in output_rows:
        split_counts[row.get("split")] += 1
        language_counts[row.get("language_family")] += 1
        if row.get("source_stage9533_upsampled_from") and row.get("split") != "train":
            source_eval_duplicate_rows.append(row.get("row_id"))
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row.get("row_id"))
        loss_mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for loss, enabled in loss_mask.items():
            if enabled:
                loss_counts[loss] += 1
        for loss in ["decoder_ce", "denoise_ce", "runtime_reward", "episode_boundary_match_ce", "episode_target_prefix_match_ce", "episode_repair_outcome_ce", "episode_step_value_mse"]:
            if loss_mask.get(loss):
                forbidden_loss_rows.append(row.get("row_id"))
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row.get("row_id"))

    expected_loss_counts = {"episode_failure_type_ce": len(output_rows)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 54}:
        failures.append("unexpected_split_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if source_eval_duplicate_rows:
        failures.append("upsampled_non_train_rows")
    if len(upsample_rows) != 8:
        failures.append("unexpected_upsample_rows")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "base_rows": len(rows),
        "upsample_rows": upsample_rows,
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "source_eval_duplicate_rows": source_eval_duplicate_rows,
        "contract": {
            "failure_type_only_focus": True,
            "upsample_source_split_train_only": not source_eval_duplicate_rows,
            "effective_labels_outside_model_input": not effective_leak_rows,
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
        "decision": "Built Python boundary-miss upsample rows from train-split examples only, using Stage9525 as the base and training only episode_failure_type_ce.",
        "next_best_step": "Audit Stage9533 for train-only upsample safety, loss closure, and preflight readiness.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9533 Episode Observation Diagnosis Python Boundary Upsample Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Upsample rows: `{len(upsample_rows)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This patch returns to the Stage9525 residual-gate base and upscales only train-split Python boundary-miss examples for a failure-type-only probe.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "upsample_rows": len(upsample_rows), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
