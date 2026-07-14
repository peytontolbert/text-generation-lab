#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11046
NAME = "stage11046_priority_evidence_bounded_candidate_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "priority_evidence_bounded_candidate_audit.json"

CANDIDATE_ROWS = ARTIFACTS / "stage11045_priority_evidence_bounded_candidate_conversion" / "bounded_candidate_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    rows = load_jsonl(CANDIDATE_ROWS)
    failures: list[str] = []
    gold_option_only = 0
    role_counts = Counter()

    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        options = [item for item in row.get("opaque_options") or [] if isinstance(item, dict)]
        values = [str(item.get("value") or "") for item in options]
        labels = [str(item.get("label") or "") for item in options]
        role_counts.update(values)

        if len(set(values)) < 4:
            failures.append(f"non_unique_option_values::{row['row_id']}")
        if len(set(labels)) != len(labels):
            failures.append(f"non_unique_option_labels::{row['row_id']}")
        if "verifier_and_test_constraint" in prompt.split("Options:", 1)[0]:
            gold_option_only += 1
        if "localchunk_" in prompt:
            failures.append(f"opaque_chunk_leak::{row['row_id']}")
        if "dataset_" in prompt or "sess_trace_" in prompt:
            failures.append(f"raw_handle_leak::{row['row_id']}")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "decision": "priority_evidence_bounded_candidates_audited" if not failures else "priority_evidence_bounded_candidates_need_cleanup",
        "claim_scope": [
            "Audit the stage11045 bounded candidate rows for obvious leakage, option collapse, and prompt-target shortcut risk.",
        ],
        "metrics": {
            "row_count": len(rows),
            "rows_with_gold_role_mentioned_pre_options": gold_option_only,
            "option_value_counts": dict(sorted(role_counts.items())),
            "failure_count": len(failures),
        },
        "failures": failures,
        "next_best_step": (
            "If this audit passes, score the reserved candidate slice on these rows next."
            if not failures
            else "Remove prompt-side gold role mentions or raw handle leakage before using these rows."
        ),
        "source_artifacts": {
            "candidate_rows": rel(CANDIDATE_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
