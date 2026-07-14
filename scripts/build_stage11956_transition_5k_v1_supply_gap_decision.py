#!/usr/bin/env python3
"""Decision artifact for Transition-5K-v1 package readiness."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11956
NAME = "stage11956_transition_5k_v1_supply_gap_decision"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_v1_supply_gap_decision.json"

PACKAGE = ART / "stage11955_transition_5k_v1_multisource_package/transition_5k_v1_multisource_package.json"
ADMITTED = ART / "stage11955_transition_5k_v1_multisource_package/admitted_source_rows.jsonl"
REJECTED = ART / "stage11955_transition_5k_v1_multisource_package/rejected_source_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    package = read_json(PACKAGE)
    admitted = read_jsonl(ADMITTED)
    rejected = read_jsonl(REJECTED)
    counts = package["counts"]
    language_counts = Counter(counts.get("language_record_counts") or {})
    status_counts = Counter(counts.get("verifier_status_counts") or {})

    target_records = 1250
    target_min_language = 250
    target_status = 500
    language_deficits = {
        lang: max(0, target_min_language - language_counts.get(lang, 0))
        for lang in ("c_cpp", "python", "rust", "web_js_ts_html")
    }
    status_deficits = {
        status: max(0, target_status - status_counts.get(status, 0))
        for status in (
            "PASS_CURRENT_BUILD",
            "PASS_CURRENT_BUILD_AND_RUN",
            "PASS_CURRENT_STATE",
            "PASS_TO_PASS",
            "VERIFIER_REMOVED",
            "FAIL_TO_PASS",
            "FAIL_TO_FAIL",
            "NOT_EXERCISED",
            "INSUFFICIENT_EVIDENCE",
        )
    }

    rejected_by_lang_reason: dict[str, Counter[str]] = defaultdict(Counter)
    rejected_by_source: Counter[str] = Counter()
    for row in rejected:
        lang = str(row.get("language_family") or "unknown")
        rejected_by_source[str(row.get("source_path") or "unknown")] += 1
        for reason in row.get("failures") or []:
            rejected_by_lang_reason[lang][str(reason)] += 1

    admitted_by_source = Counter(str(row.get("source_artifact") or "unknown") for row in admitted)
    admitted_old_overlap = sum(1 for row in admitted if row.get("old_transition_root_overlap"))
    new_source_needed = max(0, target_records - counts.get("admitted_records", 0))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "do_not_train_transition_5k_v1_as_frontier_package_yet",
        "reason": [
            "Stage11955 is clean but under-scale: 615 records / 2460 rows / 120 roots.",
            "Transition-5K minimum was 1250 records / 5000 projected rows / 250+ roots.",
            "Current supply is dominated by web rows and duplicated source rows; C/C++ and Python are below minimum language floor.",
            "Verifier-status coverage is badly imbalanced; PASS_CURRENT_BUILD, BUILD_AND_RUN, VERIFIER_REMOVED, and negative/failure statuses are far below target.",
        ],
        "package_passed": bool(package.get("passed")),
        "counts": counts,
        "deficits": {
            "additional_records_needed_for_5k_floor": new_source_needed,
            "additional_projected_rows_needed_for_5k_floor": max(0, 5000 - counts.get("projected_rows", 0)),
            "language_record_deficits_to_250_floor": language_deficits,
            "verifier_status_deficits_to_500_floor": status_deficits,
            "unique_root_deficit_to_250_floor": max(0, 250 - counts.get("unique_roots", 0)),
        },
        "quality_signals": {
            "projection_failure_count": package["audits"].get("projection_failure_count"),
            "duplicate_row_id_count": package["audits"].get("duplicate_row_id_count"),
            "root_split_violation_count": package["audits"].get("root_split_violation_count"),
            "pre_options_target_value_leak_count": package["audits"].get("pre_options_target_value_leak_count"),
            "old_transition_overlap_records": admitted_old_overlap,
        },
        "rejection_analysis": {
            "rejection_reason_counts": package["audits"].get("rejection_reason_counts"),
            "rejected_by_language_reason": {
                lang: dict(counter.most_common())
                for lang, counter in sorted(rejected_by_lang_reason.items())
            },
            "top_rejected_sources": dict(rejected_by_source.most_common(20)),
            "top_admitted_sources": dict(admitted_by_source.most_common(20)),
        },
        "next_required_work": [
            {
                "stage": "transition_5k_source_supply_v2",
                "goal": "materialize at least 635 additional clean records from new roots, not duplicate source-row copies",
                "minimum": {
                    "c_cpp_records": ">=250 total",
                    "python_records": ">=250 total",
                    "rust_records": ">=250 total",
                    "unique_roots": ">=250 total",
                    "projected_rows": ">=5000 total",
                },
            },
            {
                "stage": "verifier_status_balancing",
                "goal": "create or mine transition records with scarce verifier statuses",
                "minimum": {
                    "PASS_CURRENT_BUILD": "raise from 6 toward 500",
                    "PASS_CURRENT_BUILD_AND_RUN": "raise from 42 toward 500",
                    "VERIFIER_REMOVED": "raise from 36 toward 500",
                    "FAIL_TO_FAIL_OR_NOT_EXERCISED_OR_INSUFFICIENT": "materialize negative verifier states; currently near absent",
                },
            },
            {
                "stage": "train_request_after_supply_only",
                "gate": "Do not train a Transition-5K frontier probe until the package passes scale, split, leak, and balance gates.",
            },
        ],
        "source_artifacts": {
            "package": rel(PACKAGE),
            "admitted": rel(ADMITTED),
            "rejected": rel(REJECTED),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "additional_records_needed": new_source_needed,
                "language_deficits": language_deficits,
                "status_deficits": status_deficits,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
