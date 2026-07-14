#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10882
NAME = "stage10882_quarantined_v27_comparison_successor_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "quarantined_v27_comparison_successor_audit.json"
ROWS_JSONL = OUT_DIR / "quarantined_v27_comparison_successor_rows.jsonl"

BASE_ROWS = ARTIFACTS / "stage10424_reviewed_multilingual_v27_comparison_audit" / "reviewed_multilingual_v27_comparison_rows.jsonl"
QUARANTINE = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor" / "evidence_alias_quarantine_successor.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def exact(rows: list[dict[str, Any]], key: str) -> float:
    return sum(1 for row in rows if bool(row.get(key))) / len(rows) if rows else 0.0


def main() -> None:
    base_rows = load_jsonl(BASE_ROWS)
    quarantine = load_json(QUARANTINE)
    blocked = set(quarantine["metrics"]["blocked_row_ids"])
    kept_rows = [row for row in base_rows if str(row.get("row_id")) not in blocked]

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in kept_rows:
        by_language[str(row.get("language_family") or "unknown")].append(row)

    per_language = {}
    wins_100m = wins_gemma = ties = 0
    for language, rows in sorted(by_language.items()):
        hundred = exact(rows, "hundred_m_correct")
        gemma = exact(rows, "gemma12b_correct")
        if hundred > gemma:
            verdict = "100m_better"
            wins_100m += 1
        elif gemma > hundred:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            verdict = "tie"
            ties += 1
        per_language[language] = {
            "rows": len(rows),
            "hundred_m_exact": hundred,
            "gemma_exact": gemma,
            "delta_100m_minus_gemma": hundred - gemma,
            "verdict": verdict,
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "quarantined_v27_comparison_successor_audited",
        "claim_scope": [
            "Recompute the reviewed multilingual v2.7 same-manifest 100M-vs-Gemma comparison after removing aliased evidence rows flagged by the stage10880 anti-cheat audit.",
            "Preserve the original row-level 100M and Gemma outputs; only the anti-cheat row filter changes.",
        ],
        "source_comparison_rows": rel(BASE_ROWS),
        "source_quarantine": rel(ARTIFACTS / "stage10881_evidence_alias_quarantine_successor" / "evidence_alias_quarantine_successor.json"),
        "metrics": {
            "rows_original": len(base_rows),
            "rows_kept": len(kept_rows),
            "rows_quarantined": len(base_rows) - len(kept_rows),
            "strict_exact_100m": exact(kept_rows, "hundred_m_correct"),
            "strict_exact_gemma": exact(kept_rows, "gemma12b_correct"),
            "strict_delta_100m_minus_gemma": exact(kept_rows, "hundred_m_correct") - exact(kept_rows, "gemma12b_correct"),
            "language_wins_100m": wins_100m,
            "language_wins_gemma": wins_gemma,
            "language_ties": ties,
        },
        "per_language": per_language,
        "quarantined_rows": sorted(blocked & {str(row.get("row_id")) for row in base_rows}),
        "next_best_step": "Use this quarantined comparison as the honest reviewed-v2.7 headline until Rust evidence coverage is replenished with a fresh non-aliased reviewed root, then rerun the same-manifest comparison.",
    }

    write_json(AUDIT_JSON, payload)
    write_jsonl(ROWS_JSONL, kept_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
