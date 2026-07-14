#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10488
NAME = "stage10488_deleaked_python_verifier_anti_cheat_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "deleaked_python_verifier_anti_cheat_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ROWS_JSONL = ROOT / "runs/local/artifacts/stage10487_deleaked_python_verifier_support_package/deleaked_python_verifier_support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def prompt_body(row: dict[str, Any]) -> str:
    text = str(row.get("prompt_text") or row.get("input_text") or "")
    return text.split("\nOptions:\n", 1)[0]


def target_value(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return str(source.get("gold_value") or row.get("gold_value") or "")


def main() -> None:
    support_rows = load_jsonl(ROWS_JSONL)
    strict_rows = load_jsonl(STRICT_ROWS)

    strict_row_ids = {str(row.get("row_id") or "") for row in strict_rows}
    strict_root_ids = {str(row.get("source_root_id") or row.get("source_bundle_id") or "") for row in strict_rows}

    exact_overlap = sorted(str(row.get("row_id") or "") for row in support_rows if str(row.get("row_id") or "") in strict_row_ids)
    root_overlap = sorted(
        str(row.get("row_id") or "")
        for row in support_rows
        if str(row.get("source_root_id") or row.get("source_bundle_id") or "") in strict_root_ids
    )
    prompt_leak = sorted(
        str(row.get("row_id") or "")
        for row in support_rows
        if (target_value(row) and target_value(row) in prompt_body(row))
    )
    non_verifier = sorted(
        str(row.get("row_id") or "")
        for row in support_rows
        if str(row.get("task_type") or "") != "verifier_outcome"
    )

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not exact_overlap and not root_overlap and not prompt_leak and not non_verifier,
        "decision": "deleaked_python_verifier_anti_cheat_classified",
        "claim_scope": [
            "Audit the de-leaked Python verifier support lane against strict-overlay leakage and prompt target leakage.",
            "If this passes, the Python residual lane is honest enough for a promotable residual-support execution request.",
        ],
        "source_artifacts": {
            "support_rows": display(ROWS_JSONL),
            "strict_overlay": display(STRICT_ROWS),
        },
        "checks": {
            "exact_row_overlap": {"passed": not exact_overlap, "rows": exact_overlap},
            "root_overlap": {"passed": not root_overlap, "rows": root_overlap},
            "prompt_target_leak": {"passed": not prompt_leak, "rows": prompt_leak},
            "verifier_only_lane": {"passed": not non_verifier, "rows": non_verifier},
        },
        "next_allowed_use": {
            "promotable_python_run_allowed": not exact_overlap and not root_overlap and not prompt_leak and not non_verifier,
        },
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": audit["passed"],
            "decision": audit["decision"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
