#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11098
NAME = "stage11098_fresh_family_materialized_rows_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_materialized_rows_audit.json"

ROWS_JSON = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "fresh_family_materialized_rows.json"
SCOREABLE_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "scoreable_support_rows.jsonl"
EVIDENCE_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "evidence_candidate_rows.jsonl"
VERIFIER_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "verifier_support_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def main() -> None:
    rows_summary = load_json(ROWS_JSON)
    scoreable_rows = load_jsonl(SCOREABLE_ROWS)
    evidence_rows = load_jsonl(EVIDENCE_ROWS)
    verifier_rows = load_jsonl(VERIFIER_ROWS)

    evidence_gold_values = Counter(
        str((row.get("standalone_projection_source") or {}).get("gold_value") or "missing")
        for row in evidence_rows
    )
    evidence_gold_sources = Counter(
        str((row.get("standalone_projection_source") or {}).get("gold_value_source") or "missing")
        for row in evidence_rows
    )
    non_opaque_evidence_rows = [
        str(row.get("row_id") or "")
        for row in evidence_rows
        if not bool((row.get("anti_cheat") or {}).get("opaque_labels"))
    ]
    missing_shuffle_rows = [
        str(row.get("row_id") or "")
        for row in evidence_rows + verifier_rows
        if not bool((row.get("anti_cheat") or {}).get("deterministic_option_shuffle"))
    ]
    singleton_verifier_rows = [
        str(row.get("row_id") or "")
        for row in verifier_rows
        if len(list(row.get("opaque_options") or [])) < 2
    ]
    candidate_rows_in_train = [
        str(row.get("row_id") or "")
        for row in evidence_rows
        if str(row.get("split") or "") == "train"
    ]

    passed = not (
        non_opaque_evidence_rows
        or missing_shuffle_rows
        or singleton_verifier_rows
        or candidate_rows_in_train
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "claim_scope": [
            "Audit the stage11097 fresh-family materialized rows for option-order hygiene, candidate-vs-support separation, and heuristic evidence skew visibility.",
        ],
        "source_artifacts": {
            "rows_summary": rel(ROWS_JSON),
            "scoreable_rows": rel(SCOREABLE_ROWS),
            "evidence_rows": rel(EVIDENCE_ROWS),
            "verifier_rows": rel(VERIFIER_ROWS),
        },
        "metrics": {
            "scoreable_support_rows": len(scoreable_rows),
            "evidence_candidate_rows": len(evidence_rows),
            "verifier_support_rows": len(verifier_rows),
            "evidence_gold_values": dict(sorted(evidence_gold_values.items())),
            "evidence_gold_sources": dict(sorted(evidence_gold_sources.items())),
            "evidence_by_language": count_by(evidence_rows, "language_family"),
            "verifier_by_language": count_by(verifier_rows, "language_family"),
        },
        "findings": [
            "Evidence rows are intentionally separated from train support until their heuristic gold values receive stricter review.",
            "Verifier support rows should be immediately usable if they preserve opaque options and multi-option competition.",
            "The current package is useful only if candidate rows stay out of train and all bounded rows retain deterministic shuffle metadata.",
        ],
        "blocking_issues": {
            "non_opaque_evidence_rows": non_opaque_evidence_rows,
            "missing_shuffle_rows": missing_shuffle_rows,
            "singleton_verifier_rows": singleton_verifier_rows,
            "candidate_rows_in_train": candidate_rows_in_train,
        },
        "row_snapshot": rows_summary.get("metrics"),
        "next_best_step": "Merge only the support-eligible rows into the next train package and keep the evidence candidates in a review lane until explicit anti-cheat adjudication passes.",
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
