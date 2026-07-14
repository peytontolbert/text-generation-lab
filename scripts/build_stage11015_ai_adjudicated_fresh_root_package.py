#!/usr/bin/env python3
"""Apply a conservative AI adjudication pass to stage11014 materialized rows.

This does not overwrite any original review packet. It produces a derived
package that resolves pending Python successor rows into honest usage classes:
if the review artifacts do not establish unique identifiability, the row
becomes abstention/support material instead of a pseudo-promotable candidate.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
IN_ROWS = ROOT / "runs/local/artifacts/stage11014_fresh_root_materialized_package/fresh_root_materialized_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11015_ai_adjudicated_fresh_root_package"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def adjudicate_python_pending(row: dict[str, Any]) -> dict[str, Any]:
    adjudicated = dict(row)
    adjudicated["ai_adjudication"] = {
        "reviewer_id": "codex-gpt5-ai-review",
        "decision": "abstain_support_only",
        "reasoning": [
            "Expert rubric is still pending and does not establish unique prompt-visible identifiability.",
            "Anti-cheat draft leaves candidate-order/template-prior questions unresolved.",
            "Selected-test metadata is hidden, so verifier anchoring is not visible enough for a promotable singleton claim.",
        ],
        "gold_answer_kind": "abstain",
        "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
    }
    adjudicated["usage_class"] = "ai_adjudicated_abstention_support"
    adjudicated["promotable_now"] = False
    quality = set(adjudicated.get("quality_issues") or [])
    quality.update(
        {
            "ai_review_converted_to_abstention_support",
            "template_prior_risk_unresolved",
            "selected_tests_hidden_from_prompt",
        }
    )
    adjudicated["quality_issues"] = sorted(quality)
    return adjudicated


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(IN_ROWS)
    out_rows: list[dict[str, Any]] = []
    usage_counts = Counter()
    promotable_counts = Counter()
    language_usage = defaultdict(Counter)

    for row in rows:
        new_row = row
        if row.get("language_family") == "python" and row.get("usage_class") == "fresh_candidate_needs_adjudication":
            new_row = adjudicate_python_pending(row)
        out_rows.append(new_row)
        usage_counts[new_row["usage_class"]] += 1
        promotable_counts["promotable" if new_row.get("promotable_now") else "not_promotable"] += 1
        language_usage[new_row["language_family"]][new_row["usage_class"]] += 1

    summary = {
        "stage_id": "stage11015_ai_adjudicated_fresh_root_package",
        "source_stage": "stage11014_fresh_root_materialized_package",
        "row_count": len(out_rows),
        "usage_class_counts": dict(usage_counts),
        "promotable_counts": dict(promotable_counts),
        "language_usage_class_counts": {k: dict(v) for k, v in language_usage.items()},
        "notes": [
            "Pending Python implementation-vs-config rows were conservatively converted to abstention/support because the visible prompt does not yet justify a promotable singleton claim.",
            "This resolves the quality ambiguity without fabricating human signoff or forced gold labels.",
            "Rust reviewed packet rows remain the only immediately scoreable fresh-root lane in this derived package.",
        ],
    }

    (OUT_DIR / "ai_adjudicated_fresh_root_rows.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in out_rows) + "\n"
    )
    (OUT_DIR / "ai_adjudicated_fresh_root_package.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n"
    )


if __name__ == "__main__":
    main()
