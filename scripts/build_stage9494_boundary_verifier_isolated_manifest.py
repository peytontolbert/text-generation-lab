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
STAGE = 9494
NAME = "stage9494_boundary_verifier_isolated_manifest"
SOURCE_QUEUE = ROOT / "runs/local/artifacts/stage9493_per_head_verifier_curriculum_queue/per_head_verifier_curriculum_queue.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9493_per_head_verifier_curriculum_queue.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage9494_boundary_verifier_isolated_manifest"
MANIFEST = OUT_DIR / "boundary_verifier_isolated_manifest.jsonl"
CARD = OUT_DIR / "boundary_verifier_isolated_manifest_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDARY_VERIFIER_ISOLATED_MANIFEST_STAGE9494.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

TARGET_LOSS = "episode_boundary_match_ce"


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
    source_rows = load_jsonl(SOURCE_QUEUE)
    rows = [row for row in source_rows if (row.get("loss_mask") or {}).get(TARGET_LOSS)]
    failures: list[str] = []

    if source_summary.get("passed") is not True:
        failures.append("source_stage9493_not_passed")
    if len(rows) != 66:
        failures.append("unexpected_boundary_row_count")
    row_ids = [row.get("row_id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        failures.append("duplicate_row_ids")
    if any(any((row.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for row in rows):
        failures.append("authority_rows_present")

    split_counts = Counter(str(row.get("split", "other")) for row in rows)
    label_counts = Counter()
    loss_counts = Counter()
    for row in rows:
        enabled = [key for key, value in (row.get("loss_mask") or {}).items() if value]
        if enabled != [TARGET_LOSS]:
            failures.append(f"non_isolated_loss:{row.get('row_id')}:{enabled}")
        loss_counts.update(enabled)
        obs = ((row.get("episode_transition") or {}).get("observation_t") or {})
        label_counts[f"{row.get('split')}::{obs.get('boundary_next_token_match')}"] += 1

    expected_splits = {"eval": 6, "strict_eval": 6, "train": 54}
    if dict(sorted(split_counts.items())) != expected_splits:
        failures.append("unexpected_split_counts")

    card = {
        "passed": not failures,
        "failures": failures,
        "rows": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "loss_counts": dict(sorted(loss_counts.items())),
        "target_loss": TARGET_LOSS,
        "authority_rows": 0,
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "source_queue": str(SOURCE_QUEUE.relative_to(ROOT)),
        "design_note": "Isolated boundary verifier objective from Stage9493 per-head queue. Enables only episode_boundary_match_ce.",
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
        "decision": "Built isolated boundary verifier manifest from the per-head queue; no execution authorized by this stage.",
        "next_best_step": "Run Stage9495 contract-only target-100M preflight for isolated boundary verifier probe; do not execute until it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9494 Boundary Verifier Isolated Manifest",
        "",
        f"Passed: `{card['passed']}`",
        f"Rows: `{card['rows']}`",
        f"Splits: `{card['split_counts']}`",
        f"Label counts: `{card['label_counts']}`",
        "",
        "Only `episode_boundary_match_ce` is enabled. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
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
    registry["rows"] = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": len(rows), "split_counts": card["split_counts"], "label_counts": card["label_counts"], "failures": failures}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
