#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from bounded_decoder_ce_package_gate_builder import AUTHORITY_CLOSED, REQUIRED_GATE_KEYS, build_rows

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8802
NAME = "stage8802_closed_bounded_decoder_ce_package_gate"
SOURCE = ROOT / "runs/local/artifacts/stage8797_bounded_decoder_argument_controls_manifest/bounded_decoder_argument_controls_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLOSED_BOUNDED_DECODER_CE_PACKAGE_GATE_STAGE8802.md"


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = read_rows(SOURCE)
    rows = build_rows(source_rows)
    manifest_path = OUT_DIR / "closed_bounded_decoder_ce_package_gate_manifest.jsonl"
    card_path = OUT_DIR / "closed_bounded_decoder_ce_package_gate_card.json"
    manifest_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    gate_counts = Counter(row["clean_state"]["ce_gate_decision"] for row in rows)
    split_counts = Counter(row.get("split") for row in rows)
    arg_counts = Counter(row["clean_state"].get("bounded_argument_type") for row in rows)
    missing_gate_rows = [row["row_id"] for row in rows if not all((row.get("gate_status") or {}).get(key) is True for key in REQUIRED_GATE_KEYS)]
    authority_rows = [row["row_id"] for row in rows if any((row.get("authority") or {}).values())]
    loss_rows = [row["row_id"] for row in rows if any((row.get("loss_mask") or {}).values())]
    decoder_ce_rows = [row["row_id"] for row in rows if (row.get("loss_mask") or {}).get("decoder_ce") is True]
    raw_rows = [row["row_id"] for row in rows if any((row.get("anti_cheat") or {}).get(k) for k in ["raw_source_included", "raw_decoder_text_included", "raw_patch_body_included", "target_text_in_encoder", "target_label_in_id", "source_row_id_in_model_input"])]
    eligible_now = [row["row_id"] for row in rows if row["clean_state"].get("decoder_ce_eligible_now") is True]

    failures = []
    if len(rows) != 504:
        failures.append("row_count_changed")
    if missing_gate_rows:
        failures.append("missing_gate_status")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if loss_rows:
        failures.append("loss_mask_rows_nonzero")
    if decoder_ce_rows:
        failures.append("decoder_ce_rows_nonzero")
    if raw_rows:
        failures.append("raw_or_target_visible_rows")
    if eligible_now:
        failures.append("decoder_ce_eligible_now_rows_nonzero")
    if gate_counts.get("CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT") != 360:
        failures.append("candidate_count_unexpected")
    if gate_counts.get("CE_BLOCK_LONG_OUTPUT_UNDER_CURRENT_DECODER_BUDGET") != 72:
        failures.append("hold_count_unexpected")
    if gate_counts.get("CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING") != 72:
        failures.append("retrieve_count_unexpected")

    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(rows),
        "source_rows": len(source_rows),
        "gate_decision_counts": dict(sorted(gate_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "bounded_argument_type_counts": dict(sorted(arg_counts.items())),
        "complete_gate_status_rows": len(rows) - len(missing_gate_rows),
        "missing_gate_status_rows": len(missing_gate_rows),
        "authority_rows": len(authority_rows),
        "loss_mask_rows": len(loss_rows),
        "decoder_ce_rows": len(decoder_ce_rows),
        "raw_or_target_visible_rows": len(raw_rows),
        "decoder_ce_eligible_now_rows": len(eligible_now),
        "failures": failures,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest_path.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/bounded_decoder_ce_package_gate_builder.py",
            "tests": "tests/test_bounded_decoder_ce_package_gate_builder.py",
        },
        "decision": "Built closed bounded decoder CE package gate. It identifies future CE candidates but authorizes no CE/training/runtime." if not failures else "Closed bounded decoder CE package gate failed.",
        "next_best_step": "Audit the closed CE gate, then attach it to the central graph before any target materialization or tiny probe discussion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8802 Closed Bounded Decoder CE Package Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Future candidate rows needing source-backed target text: `{metrics['gate_decision_counts'].get('CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT', 0)}`",
        f"Long-output blocked rows: `{metrics['gate_decision_counts'].get('CE_BLOCK_LONG_OUTPUT_UNDER_CURRENT_DECODER_BUDGET', 0)}`",
        f"Retrieve-more blocked rows: `{metrics['gate_decision_counts'].get('CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING', 0)}`",
        f"Decoder CE rows: `{metrics['decoder_ce_rows']}`",
        f"Loss-mask rows: `{metrics['loss_mask_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "This is a gate, not training data. Decoder CE remains closed because target text is not yet source-backed/materialized under current gates.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
