#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_strict_unique_target_gap_builder import AUTHORITY_CLOSED, build_card, build_gap_rows  # noqa: E402
from scripts.split_deduped_closed_ce_candidate_selector import read_jsonl, write_jsonl  # noqa: E402

STAGE = 8817
NAME = "stage8817_eval_strict_unique_target_gap_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage8810_split_deduped_closed_ce_candidate_selection/split_deduped_closed_ce_candidate_selection.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_STRICT_UNIQUE_TARGET_GAP_MANIFEST_STAGE8817.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_eval_strict_unique_target_gap_builder.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    rows = build_gap_rows(read_jsonl(SOURCE))
    manifest = OUT_DIR / "eval_strict_unique_target_gap_manifest.jsonl"
    card_path = OUT_DIR / "eval_strict_unique_target_gap_card.json"
    write_jsonl(manifest, rows)
    metrics = build_card(rows)
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    expected = {
        "rows": 240,
        "authority_rows": 0,
        "loss_rows": 0,
        "decoder_ce_eligible_now_rows": 0,
        "raw_or_target_visible_rows": 0,
        "complete_gate_status_rows": 240,
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            failures.append(f"metric_mismatch:{key}:{metrics.get(key)}!={value}")
    if metrics.get("split_counts") != {"eval": 120, "strict": 120}:
        failures.append(f"bad_split_counts:{metrics.get('split_counts')}")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, **metrics},
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_selection_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/eval_strict_unique_target_gap_builder.py",
            "tests": "tests/test_eval_strict_unique_target_gap_builder.py",
        },
        "decision": "Materialized eval/strict unique-target gap rows from split-duplicate CE candidates with all authority and losses closed." if not failures else "Eval/strict unique target gap manifest failed.",
        "next_best_step": "Attach eval/strict unique-target gap to graph, then design split-unique eval/strict target materialization or heldout evaluation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8817 Eval/Strict Unique Target Gap Manifest",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Split counts: `{metrics['split_counts']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        "",
        "These rows make the missing eval/strict target materialization explicit. They are not training rows and do not enable decoder CE.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
