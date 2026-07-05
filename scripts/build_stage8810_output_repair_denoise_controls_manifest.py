#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from output_repair_denoise_controls_builder import AUTHORITY_CLOSED, REQUIRED_GATE_KEYS, build_rows

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8810
NAME = "stage8810_output_repair_denoise_controls_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OUTPUT_REPAIR_DENOISE_CONTROLS_MANIFEST_STAGE8810.md"


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_rows = read_rows(SOURCE)
    rows = build_rows(source_rows)
    manifest = OUT_DIR / "output_repair_denoise_controls_manifest.jsonl"
    card_path = OUT_DIR / "output_repair_denoise_controls_card.json"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    route_counts = Counter(row["clean_state"]["output_repair_action"] for row in rows)
    gate_counts = Counter(row["clean_state"]["denoise_gate_decision"] for row in rows)
    split_counts = Counter(row.get("split") for row in rows)
    missing_gate_rows = [row["row_id"] for row in rows if not all((row.get("gate_status") or {}).get(k) is True for k in REQUIRED_GATE_KEYS)]
    authority_rows = [row["row_id"] for row in rows if any((row.get("authority") or {}).values())]
    loss_rows = [row["row_id"] for row in rows if any((row.get("loss_mask") or {}).values())]
    raw_rows = [row["row_id"] for row in rows if any((row.get("anti_cheat") or {}).get(k) for k in ["raw_source_included", "raw_decoder_text_included", "raw_patch_body_included", "bad_output_text_in_encoder", "target_text_in_encoder", "target_label_in_id", "source_row_id_in_model_input"])]
    denoise_now = [row["row_id"] for row in rows if row["clean_state"].get("denoise_ce_eligible_now") is True]
    failures = []
    if len(rows) != 360:
        failures.append("row_count_changed")
    if any(v != 72 for v in route_counts.values()) or len(route_counts) != 5:
        failures.append("repair_route_balance_failed")
    if split_counts != Counter({"train": 120, "eval": 120, "strict": 120}):
        failures.append("split_balance_failed")
    if missing_gate_rows:
        failures.append("missing_gate_status")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if loss_rows:
        failures.append("loss_rows_nonzero")
    if raw_rows:
        failures.append("raw_or_target_visible_rows")
    if denoise_now:
        failures.append("denoise_ce_eligible_now_rows_nonzero")
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(rows),
        "source_rows": len(source_rows),
        "repair_action_counts": dict(sorted(route_counts.items())),
        "denoise_gate_decision_counts": dict(sorted(gate_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "complete_gate_status_rows": len(rows) - len(missing_gate_rows),
        "missing_gate_status_rows": len(missing_gate_rows),
        "authority_rows": len(authority_rows),
        "loss_rows": len(loss_rows),
        "denoise_ce_rows": 0,
        "decoder_ce_rows": 0,
        "denoise_ce_eligible_now_rows": len(denoise_now),
        "raw_or_target_visible_rows": len(raw_rows),
        "failures": failures,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "card": str(card_path.relative_to(ROOT)),
            "source_manifest": str(SOURCE.relative_to(ROOT)),
            "builder": "scripts/output_repair_denoise_controls_builder.py",
            "tests": "tests/test_output_repair_denoise_controls_builder.py",
        },
        "decision": "Built output repair/denoise controls with recovered gates and all CE/runtime authorities closed." if not failures else "Output repair/denoise controls manifest failed.",
        "next_best_step": "Run shortcut/gate audit, then attach output repair/denoise controls to the central graph. Do not enable denoise CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8810 Output Repair Denoise Controls Manifest",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Complete gate-status rows: `{metrics['complete_gate_status_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "This is a closed control surface only. Denoise CE remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
