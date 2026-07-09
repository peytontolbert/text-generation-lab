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
STAGE = 9493
NAME = "stage9493_per_head_verifier_curriculum_queue"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9490_phase_aware_episode_verifier_manifest/phase_aware_episode_verifier_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9492_phase_aware_episode_verifier_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9493_per_head_verifier_curriculum_queue"
MANIFEST = OUT_DIR / "per_head_verifier_curriculum_queue.jsonl"
CARD = OUT_DIR / "per_head_verifier_curriculum_queue_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PER_HEAD_VERIFIER_CURRICULUM_QUEUE_STAGE9493.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

HEADS = [
    "episode_boundary_match_ce",
    "episode_failure_type_ce",
    "episode_repair_outcome_ce",
    "episode_step_value_mse",
    "episode_target_prefix_match_ce",
]


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
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows: list[dict] = []
    failures: list[str] = []

    for source_index, row in enumerate(source_rows):
        for head in HEADS:
            patched = copy.deepcopy(row)
            head_name = head.removesuffix("_ce").removesuffix("_mse")
            patched["row_id"] = f"stage9493_{head_name}_{source_index:04d}"
            patched["source_stage9490_row_id"] = row.get("row_id")
            patched["objective_family"] = f"episode_verifier_per_head_{head_name}"
            patched["route"] = "KEEP_EPISODE_VERIFIER_PER_HEAD"
            patched["source_kind"] = "stage9490_per_head_split"
            loss_mask = patched.get("loss_mask") if isinstance(patched.get("loss_mask"), dict) else {}
            for key in list(loss_mask):
                loss_mask[key] = key == head
            patched["loss_mask"] = loss_mask
            model_input = patched.get("model_input") if isinstance(patched.get("model_input"), dict) else {}
            model_input["per_head_curriculum_target"] = head_name
            model_input["per_head_curriculum_phase"] = True
            patched["model_input"] = model_input
            patched["stage9493_design_note"] = "Per-head verifier row: isolate one observe-phase verifier head to avoid multi-head majority/default collapse before rejoin."
            rows.append(patched)

    source_metrics = source_summary.get("metrics") if isinstance(source_summary.get("metrics"), dict) else {}
    if source_metrics.get("safety_passed") is not True:
        failures.append("source_stage9492_not_safety_passed")
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
    if any((row.get("loss_mask") or {}).get(key) for row in rows for key in ["decoder_ce", "denoise_ce", "runtime_reward"]):
        failures.append("forbidden_decoder_denoise_or_runtime_loss")

    split_counts = Counter(str(row.get("split", "other")) for row in rows)
    loss_counts: Counter[str] = Counter()
    per_head_split: Counter[str] = Counter()
    for row in rows:
        enabled = [key for key, value in (row.get("loss_mask") or {}).items() if value]
        if len(enabled) != 1:
            failures.append(f"row_not_single_head:{row.get('row_id')}")
        else:
            loss_counts[enabled[0]] += 1
            per_head_split[f"{row.get('split')}::{enabled[0]}"] += 1
    expected_loss_counts = {head: len(source_rows) for head in HEADS}
    if dict(sorted(loss_counts.items())) != expected_loss_counts:
        failures.append("unexpected_loss_counts")

    card = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "source_rows": len(source_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "expected_loss_counts": expected_loss_counts,
        "per_head_split_counts": dict(sorted(per_head_split.items())),
        "authority_rows": len(authority_rows),
        "authority_row_ids": authority_rows[:20],
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "source_stage9492": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "design_note": "Per-head verifier curriculum queue after Stage9492 showed multi-head observe verifier normalization collapses toward majority/default classes.",
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
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Queued per-head observe-phase verifier curriculum rows so each verifier head can be learned and audited before another multi-head rejoin.",
        "next_best_step": "Run contract-only preflight for one isolated verifier head at a time, starting with episode_boundary_match or episode_failure_type; do not rejoin all heads until isolated probes pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9493 Per-Head Verifier Curriculum Queue",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Loss counts: `{card['loss_counts']}`",
        "",
        "Each row enables exactly one verifier loss. This is a queue for isolated probes, not a model-execution authorization.",
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "split_counts": card["split_counts"], "loss_counts": card["loss_counts"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
