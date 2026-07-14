#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10436
NAME = "stage10436_repaired_v27_strict_overlay"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OVERLAY_JSON = OUT_DIR / "repaired_v27_strict_overlay.json"
OVERLAY_JSONL = OUT_DIR / "repaired_v27_strict_overlay.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
REWRITE_OVERLAYS_JSONL = ROOT / "runs/local/artifacts/stage10435_reviewed_v27_strict_leak_rewrite_helper/reviewed_v27_strict_leak_rewrite_overlays.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    strict_rows = load_jsonl(STRICT_ROWS_JSONL)
    overlay_rows = {row["row_id"]: row for row in load_jsonl(REWRITE_OVERLAYS_JSONL)}
    repaired_rows: list[dict[str, Any]] = []
    repaired_count = 0
    for row in strict_rows:
        row_id = str(row["row_id"])
        updated = dict(row)
        overlay = overlay_rows.get(row_id)
        if overlay:
            updated["prompt_text"] = overlay["rewritten_prompt_text"]
            updated["input_text"] = overlay["rewritten_prompt_text"]
            updated["repair_overlay_metadata"] = {
                "rewrite_strategy": overlay["rewrite_strategy"],
                "slot_map": overlay["slot_map"],
                "overlay_stage": STAGE,
            }
            repaired_count += 1
        repaired_rows.append(updated)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_strict_manifest": display(STRICT_ROWS_JSONL),
        "rewrite_overlay_source": display(REWRITE_OVERLAYS_JSONL),
        "summary": {
            "strict_rows": len(repaired_rows),
            "repaired_rows": repaired_count,
        },
        "outputs": {
            "overlay_json": display(OVERLAY_JSON),
            "overlay_rows": display(OVERLAY_JSONL),
        },
        "claim_boundary": [
            "This is a draft repaired strict overlay only.",
            "It preserves row IDs, gold labels, and strict split membership.",
            "It must be re-audited before it can replace the live v2.7 strict package.",
        ],
    }
    write_json(OVERLAY_JSON, payload)
    write_jsonl(OVERLAY_JSONL, repaired_rows)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
