#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11226
NAME = "stage11226_balanced_candidate_validity_support"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_candidate_validity_support.json"
ROWS_JSONL = OUT_DIR / "balanced_candidate_validity_rows.jsonl"
SOURCE_ROWS = ARTIFACTS / "stage11219_evidence_candidate_validity_support/evidence_candidate_validity_rows.jsonl"

POSITIVE_VALUE = "DECISIVE_EVIDENCE_ITEM"
NEGATIVE_VALUE = "DISTRACTOR_OR_INSUFFICIENT_EVIDENCE_ITEM"
HARD_NEGATIVE_PRIORITY = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "algorithmic_background_reference",
    "external_analogue_reference",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def semantic_value(row: dict[str, Any]) -> str:
    return str(((row.get("target") or {}).get("semantic_value")) or ((row.get("standalone_projection_source") or {}).get("gold_value")) or "")


def candidate_role(row: dict[str, Any]) -> str:
    return str(((row.get("target") or {}).get("candidate_role")) or ((row.get("standalone_projection_source") or {}).get("candidate_role")) or "")


def hard_negative(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    negatives = [row for row in rows if semantic_value(row) == NEGATIVE_VALUE]
    if not negatives:
        return None
    by_role = {candidate_role(row): row for row in negatives}
    for role in HARD_NEGATIVE_PRIORITY:
        if role in by_role:
            return by_role[role]
    return sorted(negatives, key=lambda row: str(row.get("row_id") or ""))[0]


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        groups[str(row.get("source_row_id") or row.get("row_id") or "")].append(row)

    out_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for source_row_id, rows in sorted(groups.items()):
        positives = [row for row in rows if semantic_value(row) == POSITIVE_VALUE]
        neg = hard_negative(rows)
        if len(positives) != 1 or neg is None:
            blocked.append(
                {
                    "source_row_id": source_row_id,
                    "positive_count": len(positives),
                    "negative_count": sum(1 for row in rows if semantic_value(row) == NEGATIVE_VALUE),
                }
            )
            continue
        for selected, kind in [(positives[0], "positive"), (neg, "hard_negative")]:
            payload = dict(selected)
            payload["row_id"] = f"stage11226::{selected.get('row_id')}"
            payload["source_candidate_validity_row_id"] = selected.get("row_id")
            payload["balanced_candidate_validity_kind"] = kind
            payload["split"] = "train"
            payload["package_split"] = "train"
            payload["anti_cheat"] = {
                **(payload.get("anti_cheat") or {}),
                "balanced_positive_negative_support": True,
                "one_positive_one_hard_negative_per_source_row": True,
                "train_support_only": True,
            }
            projection = dict(payload.get("standalone_projection_source") or {})
            projection["projection_mode"] = "stage11226_balanced_candidate_validity_support"
            projection["source_candidate_validity_row_id"] = selected.get("row_id")
            projection["balanced_candidate_validity_kind"] = kind
            payload["standalone_projection_source"] = projection
            out_rows.append(payload)

    by_value = Counter(semantic_value(row) for row in out_rows)
    by_language_value = Counter((row.get("language_family"), semantic_value(row)) for row in out_rows)
    by_role_kind = Counter((candidate_role(row), row.get("balanced_candidate_validity_kind")) for row in out_rows)
    by_root: dict[str, int] = defaultdict(int)
    for row in out_rows:
        by_root[str(row.get("root_id") or "")] += 1
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(out_rows) and not blocked and by_value.get(POSITIVE_VALUE) == by_value.get(NEGATIVE_VALUE),
        "decision": "balanced_candidate_validity_support_built",
        "rationale": [
            "Stage11224 showed both 100M runtimes collapsed to the negative class on binary candidate-validity eval.",
            "This package keeps one decisive positive and one hard negative per source evidence row to remove the 1:3 class imbalance.",
        ],
        "counts": {
            "source_candidate_rows": len(source_rows),
            "source_evidence_rows": len(groups),
            "balanced_rows": len(out_rows),
            "unique_roots": len(by_root),
            "blocked_source_rows": len(blocked),
            "by_binary_target": dict(sorted(by_value.items())),
            "by_language_and_binary_target": {f"{lang}::{value}": count for (lang, value), count in sorted(by_language_value.items())},
            "by_candidate_role_and_kind": {f"{role}::{kind}": count for (role, kind), count in sorted(by_role_kind.items())},
        },
        "quality_gates": {
            "positive_negative_balanced": by_value.get(POSITIVE_VALUE) == by_value.get(NEGATIVE_VALUE),
            "one_positive_one_negative_per_source_row": len(out_rows) == len(groups) * 2 and not blocked,
            "train_support_only": True,
            "diagnostic_until_positive_recall_improves": True,
        },
        "blocked": blocked,
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "outputs": {"summary_json": rel(SUMMARY_JSON), "rows_jsonl": rel(ROWS_JSONL)},
    }
    write_jsonl(ROWS_JSONL, out_rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
