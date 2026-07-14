#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "stage10384_language_conditioned_variant_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
VARIANT_AUDIT = ROOT / "runs/local/artifacts/stage10383_option_text_variant_audit/option_text_variant_audit.json"


def _language_from_row_id(row_id: str) -> str:
    parts = row_id.split("::")
    for language in ("python", "rust", "c_cpp", "web_js_ts_html"):
        if language in parts:
            return language
    return "unknown"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = json.loads(VARIANT_AUDIT.read_text(encoding="utf-8"))
    raw = audit["results"]["raw_value"]
    role = audit["results"]["task_role_templated"]

    raw_misses = {row["row_id"]: row for row in raw["misses"]}
    role_misses = {row["row_id"]: row for row in role["misses"]}
    row_ids = set(raw_misses) | set(role_misses)

    combined_misses = []
    for row_id in sorted(row_ids):
        language = _language_from_row_id(row_id)
        miss = role_misses.get(row_id) if language == "rust" else raw_misses.get(row_id)
        if miss is not None:
            combined_misses.append(
                {
                    "row_id": row_id,
                    "language_family": language,
                    "selected_variant": "task_role_templated" if language == "rust" else "raw_value",
                    "pred": miss["pred"],
                    "target": miss["target"],
                }
            )

    rows = int(raw["rows"])
    correct = rows - len(combined_misses)
    payload = {
        "stage_name": NAME,
        "baseline_variant": "raw_value",
        "conditional_policy": {
            "rust": "task_role_templated",
            "python": "raw_value",
            "c_cpp": "raw_value",
            "web_js_ts_html": "raw_value",
        },
        "baseline_accuracy": raw["accuracy"],
        "baseline_correct": raw["correct"],
        "combined_accuracy": correct / rows,
        "combined_correct": correct,
        "rows": rows,
        "combined_misses": combined_misses,
    }
    out_path = OUT_DIR / "language_conditioned_variant_audit.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
