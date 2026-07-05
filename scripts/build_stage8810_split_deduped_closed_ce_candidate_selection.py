#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from split_deduped_closed_ce_candidate_selector import AUTHORITY_CLOSED, build_card, read_jsonl, select_rows, write_jsonl  # noqa: E402

STAGE = 8810
NAME = "stage8810_split_deduped_closed_ce_candidate_selection"
MANIFEST = ROOT / "runs/local/artifacts/stage8806_source_backed_decoder_target_materialization_controls/source_backed_decoder_target_materialization_controls.jsonl"
TARGET_STORE = ROOT / "runs/local/artifacts/stage8806_source_backed_decoder_target_materialization_controls/source_backed_decoder_target_store.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SPLIT_DEDUPED_CLOSED_CE_CANDIDATE_SELECTION_STAGE8810.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_split_deduped_closed_ce_candidate_selector.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    target_store = read_jsonl(TARGET_STORE)
    rows = select_rows(read_jsonl(MANIFEST), target_store)
    out_path = OUT_DIR / "split_deduped_closed_ce_candidate_selection.jsonl"
    card_path = OUT_DIR / "split_deduped_closed_ce_candidate_selection_card.json"
    write_jsonl(out_path, rows)
    metrics = build_card(rows, target_store)
    failures: list[str] = []
    if test.returncode != 0:
        failures.append("unit_tests_failed")
    expected = {
        "rows": 504,
        "selected_candidate_rows": 120,
        "blocked_rows": 384,
        "training_loss_rows": 0,
        "authority_rows": 0,
        "decoder_ce_eligible_now_rows": 0,
        "selected_target_ref_unique_rows": 120,
        "selected_target_hash_unique_rows": 120,
        "target_text_copied_to_manifest_rows": 0,
    }
    for key, value in expected.items():
        if metrics.get(key) != value:
            failures.append(f"metric_mismatch:{key}:{metrics.get(key)}!={value}")
    metrics["failures"] = failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, **metrics},
        "artifacts": {
            "manifest": str(out_path.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_materialization_manifest": str(MANIFEST.relative_to(ROOT)),
            "source_target_store": str(TARGET_STORE.relative_to(ROOT)),
            "builder": "scripts/split_deduped_closed_ce_candidate_selector.py",
            "tests": "tests/test_split_deduped_closed_ce_candidate_selector.py",
        },
        "decision": "Selected a split-deduped closed bounded decoder CE candidate set with no decoder CE authority or loss rows." if not failures else "Split-deduped closed CE candidate selection failed.",
        "next_best_step": "Audit split-deduped closed CE candidate selection, then decide whether to rematerialize eval/strict targets or keep this as train-only candidate support.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8810 Split-Deduped Closed CE Candidate Selection",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Selected candidate rows: `{metrics['selected_candidate_rows']}`",
        f"Blocked rows: `{metrics['blocked_rows']}`",
        f"Selected split counts: `{metrics['selected_split_counts']}`",
        f"Selected target hash unique rows: `{metrics['selected_target_hash_unique_rows']}`",
        f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        f"Training loss rows: `{metrics['training_loss_rows']}`",
        "",
        "This is a closed selector only. It does not enable decoder CE or model execution. It reveals that the currently safe deduped set is train-only under the recovered duplicated target store.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
