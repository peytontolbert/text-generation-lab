#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from heldout_non_ce_decoder_eval_design_builder import AUTHORITY_CLOSED, build_card, build_design_rows

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8820
NAME = "stage8820_heldout_non_ce_decoder_eval_design_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage8817_eval_strict_unique_target_gap_manifest/eval_strict_unique_target_gap_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_NON_CE_DECODER_EVAL_DESIGN_MANIFEST_STAGE8820.md"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_design_rows(read_jsonl(SOURCE))
    manifest = OUT_DIR / "heldout_non_ce_decoder_eval_design_manifest.jsonl"
    card_path = OUT_DIR / "heldout_non_ce_decoder_eval_design_card.json"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = build_card(rows)
    failures = []
    expected = {
        "rows": 240,
        "authority_rows": 0,
        "loss_rows": 0,
        "decoder_ce_eligible_now_rows": 0,
        "probe_ready_rows": 0,
        "raw_or_forbidden_visible_rows": 0,
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            failures.append(f"metric_mismatch:{key}:{metrics.get(key)}!={value}")
    if metrics.get("split_counts") != {"eval": 120, "strict": 120}:
        failures.append("split_counts_not_eval_strict_120_each")
    metrics = {**AUTHORITY_CLOSED, **metrics, "failures": failures}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_gap_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/heldout_non_ce_decoder_eval_design_builder.py",
            "tests": "tests/test_heldout_non_ce_decoder_eval_design_builder.py",
        },
        "decision": "Built heldout non-CE decoder evaluation design for eval/strict duplicate-target rows. It is design-only and not probe-ready until model-output packets exist.",
        "next_best_step": "Attach heldout non-CE eval design to graph, then define future model-output packet schema/telemetry before any probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8820 Heldout Non-CE Decoder Eval Design Manifest",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Split counts: `{metrics['split_counts']}`",
        f"Probe-ready rows: `{metrics['probe_ready_rows']}`",
        f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        "",
        "This design avoids duplicate eval/strict CE targets by requiring future model-output packet checks instead of CE target scoring. It opens no execution or scoring authority.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
