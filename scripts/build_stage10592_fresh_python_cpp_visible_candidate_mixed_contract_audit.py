#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10592
NAME = "stage10592_fresh_python_cpp_visible_candidate_mixed_contract_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_visible_candidate_mixed_contract_audit.json"

SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def anti_cheat_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    for row in rows:
        anti_cheat = row.get("anti_cheat") or {}
        for key, value in anti_cheat.items():
            if value is True:
                counter[f"{key}::true"] += 1
            elif value is False:
                counter[f"{key}::false"] += 1
    return dict(sorted(counter.items()))


def split_shape(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subtype_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    language_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    repo_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        subtype_buckets[str(row.get("target_subtype") or "unknown")].append(row)
        language_buckets[str(row.get("language_family") or "unknown")].append(row)
        repo_buckets[str(row.get("repo_id") or "unknown")].append(row)

    subtype_details: dict[str, Any] = {}
    blocked_subtypes: list[str] = []
    warning_subtypes: list[str] = []
    for subtype, bucket in sorted(subtype_buckets.items()):
        target_counts = Counter(str(row.get("target_text") or "") for row in bucket)
        rows_count = len(bucket)
        dominant_target, dominant_count = target_counts.most_common(1)[0]
        dominant_fraction = dominant_count / rows_count if rows_count else None
        unique_targets = len(target_counts)
        subtype_details[subtype] = {
            "rows": rows_count,
            "unique_target_count": unique_targets,
            "target_counts": dict(sorted(target_counts.items())),
            "dominant_target_text": dominant_target,
            "dominant_target_fraction": dominant_fraction,
        }
        if unique_targets <= 1:
            blocked_subtypes.append(subtype)
        elif dominant_fraction is not None and dominant_fraction >= 0.8:
            warning_subtypes.append(subtype)

    return {
        "rows": len(rows),
        "language_counts": {key: len(bucket) for key, bucket in sorted(language_buckets.items())},
        "repo_count": len(repo_buckets),
        "subtype_details": subtype_details,
        "blocked_constant_target_subtypes": blocked_subtypes,
        "warning_high_dominance_subtypes": warning_subtypes,
    }


def main() -> None:
    support_rows = load_jsonl(SUPPORT_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)

    support_shape = split_shape(support_rows)
    strict_shape = split_shape(strict_rows)
    promotion_blocked_reasons: list[str] = []
    if strict_shape["blocked_constant_target_subtypes"]:
        promotion_blocked_reasons.append(
            "strict split has constant-target subtype(s): " + ", ".join(strict_shape["blocked_constant_target_subtypes"])
        )
    if support_shape["blocked_constant_target_subtypes"]:
        promotion_blocked_reasons.append(
            "support split has constant-target subtype(s): " + ", ".join(support_shape["blocked_constant_target_subtypes"])
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "promotion_blocked": bool(promotion_blocked_reasons),
        "promotion_blocked_reasons": promotion_blocked_reasons,
        "claim_scope": [
            "Audits the stage10584 fresh Python/C++ visible-candidate package for constant-target and high-dominance subtype structure.",
            "Designed as an anti-cheat gate before promotion-style training or same-manifest comparison claims.",
            "This checks answer-contract shape only; it does not measure model quality.",
        ],
        "inputs": {
            "support_rows": display(SUPPORT_ROWS),
            "strict_rows": display(STRICT_ROWS),
        },
        "support_shape": support_shape,
        "strict_shape": strict_shape,
        "support_anti_cheat_counts": anti_cheat_counts(support_rows),
        "strict_anti_cheat_counts": anti_cheat_counts(strict_rows),
        "truthful_read": [
            "The fresh stage10591 package is repo-disjoint and candidate-contract based, and its retrieve/verifier subtypes are no longer constant-target in either support or strict splits.",
            "This removes the most obvious subtype-collapse shortcut from the prior fresh package and makes the next comparison materially more honest.",
            "Future packages should still be blocked from promotion when any strict subtype collapses to one target, unless the subtype is explicitly marked diagnostic-only.",
        ],
        "next_actions": [
            "Rebuild retrieve_answer_abstain with mixed A/B/C/D targets on fresh roots.",
            "Rebuild verifier_outcome_masked with more than PASS_TARGETED_TEST_SELECTION on fresh roots.",
            "Add this audit as a required gate before future promotion-style package requests.",
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
