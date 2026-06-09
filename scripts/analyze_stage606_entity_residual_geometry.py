#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DETAILS = (
    ROOT
    / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage602_stage601_entity_field_balanced_replay_lr3e6_steps200"
    / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_details.jsonl"
)
ARTIFACT = ROOT / "runs/local/artifacts/stage606_entity_residual_geometry.json"
DOC = ROOT / "docs/stage606_entity_residual_geometry.md"
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def key_values(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KEY_VALUE_RE.findall(str(text or ""))}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = [float(row["score_margin"]) for row in rows]
    return {
        "rows": len(rows),
        "by_target_field": dict(Counter(row["query_keys"].get("field", "") for row in rows).most_common()),
        "by_predicted_field": dict(Counter(row["predicted_keys"].get("field", "") for row in rows).most_common()),
        "same_domain": sum(row["query_keys"].get("domain") == row["predicted_keys"].get("domain") for row in rows),
        "same_entity": sum(row["query_keys"].get("entity") == row["predicted_keys"].get("entity") for row in rows),
        "same_field": sum(row["query_keys"].get("field") == row["predicted_keys"].get("field") for row in rows),
        "same_answer_string": sum(str(row["expected_content"]) in str(row["predicted_doc"]) for row in rows),
        "rank_counts": dict(Counter(int(row["rank"]) for row in rows).most_common(12)),
        "score_margin": {
            "min": min(margins) if margins else None,
            "median": statistics.median(margins) if margins else None,
            "max": max(margins) if margins else None,
        },
    }


def main() -> None:
    entity_rows: list[dict[str, Any]] = []
    exact_misses: list[dict[str, Any]] = []
    answer_misses: list[dict[str, Any]] = []
    for detail in iter_jsonl(DETAILS):
        if str(detail.get("operation", "") or "") != "entity_context":
            continue
        row = dict(detail)
        row["query_keys"] = key_values(str(detail.get("query", "") or ""))
        row["expected_keys"] = key_values(str(detail.get("expected_doc", "") or ""))
        row["predicted_keys"] = key_values(str(detail.get("predicted_doc", "") or ""))
        entity_rows.append(row)
        if not bool(detail.get("top1")):
            exact_misses.append(row)
        if not bool(detail.get("answer_top1")):
            answer_misses.append(row)

    hard_examples = sorted(answer_misses, key=lambda row: float(row["score_margin"]))[:12]
    close_examples = sorted(answer_misses, key=lambda row: abs(float(row["score_margin"])))[:12]
    summary = {
        "artifact_kind": "stage606_entity_residual_geometry",
        "source_details": str(DETAILS.relative_to(ROOT)),
        "scope": "Stage602 on Stage601 field-level entity-context eval surface",
        "entity_rows": len(entity_rows),
        "exact_misses": summarize(exact_misses),
        "answer_misses": summarize(answer_misses),
        "hard_answer_miss_examples": [
            {
                "source_id": row["source_id"],
                "rank": row["rank"],
                "score_margin": row["score_margin"],
                "query_keys": row["query_keys"],
                "expected_content": row["expected_content"],
                "predicted_source_id": row["predicted_source_id"],
                "predicted_keys": row["predicted_keys"],
            }
            for row in hard_examples
        ],
        "close_answer_miss_examples": [
            {
                "source_id": row["source_id"],
                "rank": row["rank"],
                "score_margin": row["score_margin"],
                "query_keys": row["query_keys"],
                "expected_content": row["expected_content"],
                "predicted_source_id": row["predicted_source_id"],
                "predicted_keys": row["predicted_keys"],
            }
            for row in close_examples
        ],
        "decision": "entity_residual_geometry_mapped",
        "finding": (
            "The remaining entity_context failures are mostly cross-field and cross-entity binding errors, not just exposure "
            "deficits. Among answer misses, same-field predictions are a minority, and the model often predicts high-frequency "
            "tool/capital/owner fields for priority/status/currency targets. The next schema should strengthen field role "
            "binding or add a deterministic field selector before neural entity-value resolution."
        ),
    }
    ARTIFACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        f"""# Stage606 Entity Residual Geometry

Artifact: `runs/local/artifacts/stage606_entity_residual_geometry.json`

## Result

Stage606 analyzes Stage602's remaining `entity_context` failures on the Stage601 field-level eval surface.

- Entity rows: `{summary['entity_rows']}`
- Exact misses: `{summary['exact_misses']['rows']}`
- Answer misses: `{summary['answer_misses']['rows']}`
- Answer misses with same predicted field: `{summary['answer_misses']['same_field']}`
- Answer misses with same predicted entity: `{summary['answer_misses']['same_entity']}`
- Answer misses with same predicted domain: `{summary['answer_misses']['same_domain']}`
- Answer miss median score margin: `{summary['answer_misses']['score_margin']['median']}`

## Decision

`entity_residual_geometry_mapped`

## Finding

{summary['finding']}
""",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
