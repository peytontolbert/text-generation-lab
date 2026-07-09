#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9508
NAME = "stage9508_episode_obs_diag_overlay_wide_eval_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage9504_episode_obs_diag_overlay_manifest/episode_obs_diag_overlay_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9507_episode_obs_diag_overlay_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9508_episode_obs_diag_overlay_wide_eval_manifest"
MANIFEST = OUT_DIR / "episode_obs_diag_overlay_wide_eval_manifest.jsonl"
CARD = OUT_DIR / "episode_obs_diag_overlay_wide_eval_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_OBS_DIAG_OVERLAY_WIDE_EVAL_MANIFEST_STAGE9508.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

EXPECTED_LOSSES = {
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


def cell_key(row: dict) -> str:
    effective = row.get("effective_verifier") if isinstance(row.get("effective_verifier"), dict) else {}
    return f"prefix={effective.get('effective_target_prefix_match')}|outcome={effective.get('effective_repair_outcome')}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if not rows:
        failures.append("missing_source_rows")
    if source_summary.get("passed") is not True:
        failures.append("stage9507_not_passed")

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cell[cell_key(row)].append(row)
    if sorted(len(v) for v in by_cell.values()) != [29, 29]:
        failures.append("expected_two_balanced_29_row_cells")

    output_rows: list[dict] = []
    split_counts = Counter()
    split_cell_counts = Counter()
    loss_counts = Counter()
    forbidden_loss_rows: list[str] = []
    authority_rows: list[str] = []
    effective_leak_rows: list[str] = []

    # Per cell: 23 train, 3 eval, 3 strict_eval.
    split_plan = ["train"] * 23 + ["eval"] * 3 + ["strict_eval"] * 3
    staged_by_split: dict[str, list[dict]] = {"train": [], "eval": [], "strict_eval": []}
    for ckey in sorted(by_cell):
        cell_rows = sorted(by_cell[ckey], key=lambda row: row.get("source_stage9472_row_id") or row.get("row_id"))
        for row, split in zip(cell_rows, split_plan, strict=True):
            out = copy.deepcopy(row)
            out["source_stage9504_row_id"] = row.get("row_id")
            out["split"] = split
            out["objective_family"] = "episode_observation_diagnosis_overlay_wide_eval"
            out["route"] = "KEEP_EPISODE_OBS_DIAG_OVERLAY_WIDE_EVAL"
            out["authority"] = dict(AUTHORITY_CLOSED)
            out["training_candidate"] = {
                **(out.get("training_candidate") or {}),
                "wide_eval_resplit": True,
                "model_execution_authorized_now": False,
                "decoder_ce_closed": True,
                "denoise_ce_closed": True,
                "runtime_reward_closed": True,
            }
            loss_mask = dict(out.get("loss_mask") or {})
            for loss in EXPECTED_LOSSES:
                loss_mask[loss] = True
            for loss in FORBIDDEN_LOSSES:
                loss_mask[loss] = False
            out["loss_mask"] = loss_mask
            staged_by_split[split].append(out)

    # Preserve alternating train order so small deterministic batches see both cells.
    ordered: list[dict] = []
    train_cells: dict[str, list[dict]] = defaultdict(list)
    for row in staged_by_split["train"]:
        train_cells[cell_key(row)].append(row)
    for i in range(23):
        for ckey in sorted(train_cells):
            ordered.append(train_cells[ckey][i])
    ordered.extend(staged_by_split["eval"])
    ordered.extend(staged_by_split["strict_eval"])

    for idx, row in enumerate(ordered):
        row["row_id"] = f"stage9508_obs_diag_wide_eval_{idx:04d}"
        for loss, enabled in (row.get("loss_mask") or {}).items():
            if enabled:
                loss_counts[loss] += 1
        if any((row.get("loss_mask") or {}).get(loss) for loss in FORBIDDEN_LOSSES):
            forbidden_loss_rows.append(row["row_id"])
        if any((row.get("authority") or {}).values()):
            authority_rows.append(row["row_id"])
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        if any(key.startswith("effective_") for key in model_input):
            effective_leak_rows.append(row["row_id"])
        split_counts[row.get("split")] += 1
        split_cell_counts[f"{row.get('split')}::{cell_key(row)}"] += 1
        output_rows.append(row)

    expected_loss_counts = {loss: len(output_rows) for loss in sorted(EXPECTED_LOSSES)}
    if dict(loss_counts) != expected_loss_counts:
        failures.append("unexpected_loss_counts")
    if forbidden_loss_rows:
        failures.append("forbidden_loss_rows")
    if authority_rows:
        failures.append("authority_rows_present")
    if effective_leak_rows:
        failures.append("effective_verifier_leaked_into_model_input")
    if split_counts != {"eval": 6, "strict_eval": 6, "train": 46}:
        failures.append("unexpected_split_counts")
    if any(count != 3 for key, count in split_cell_counts.items() if key.startswith("eval::") or key.startswith("strict_eval::")):
        failures.append("eval_strict_cell_imbalance")

    MANIFEST.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows))
    card = {
        "passed": not failures,
        "failures": failures,
        "source_manifest": str(SOURCE.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(output_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "split_cell_counts": dict(sorted(split_cell_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "forbidden_loss_rows": forbidden_loss_rows,
        "authority_rows": authority_rows,
        "effective_leak_rows": effective_leak_rows,
        "train_order_contract": "Train rows alternate the two success/residual cells; eval and strict each contain 3 rows per cell.",
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
        "decision": "Built a wide-eval observation-diagnosis overlay manifest with balanced 46/6/6 train/eval/strict splits.",
        "next_best_step": "Audit Stage9508, then run contract-only target-100M preflight if loss/authority/overlay checks pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9508 Episode Observation Diagnosis Overlay Wide-Eval Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{len(output_rows)}`",
        f"Split counts: `{dict(split_counts)}`",
        f"Loss counts: `{dict(loss_counts)}`",
        "",
        "This widens eval/strict coverage from one row each to six rows each while preserving balanced success/residual cells.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"stage": STAGE, "passed": card["passed"], "rows": len(output_rows), "split_counts": dict(split_counts), "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
