#!/usr/bin/env python3
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

STAGE = 11480
NAME = "stage11480_residual50_ready_package_audit"
OUT = ART / NAME
SUMMARY = OUT / "residual50_ready_package_audit.json"
READY_ROWS = OUT / "residual50_ready_rows.jsonl"

PY_CPP_READY = ART / "stage11475_residual50_readiness_after_counterfamily_topup/residual50_ready_python_cpp_rows.jsonl"
RUST_PREVIOUS = ART / "stage11476_rust_symptom_call_path_residual50_admission/admitted_rust_symptom_call_path_rows.jsonl"
RUST_NEW = ART / "stage11479_materialized_rust_symptom_call_path_rows/admitted_materialized_rust_symptom_call_path_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id"))


def gold_value(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return str(source.get("gold_value") or row.get("semantic_target_value") or "unknown")


def family_status(rows: list[dict[str, Any]], family_id: str, language: str, positive_role: str, counter_role: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("language_family") == language]
    roots_by_role: dict[str, set[str]] = defaultdict(set)
    row_counts = Counter()
    for row in selected:
        value = gold_value(row)
        row_counts[value] += 1
        roots_by_role[value].add(root_id(row))
    positive = len(roots_by_role.get(positive_role, set()))
    counter = len(roots_by_role.get(counter_role, set()))
    return {
        "family_id": family_id,
        "language_family": language,
        "positive_role": positive_role,
        "counter_role": counter_role,
        "positive_roots": positive,
        "counter_roots": counter,
        "missing_positive_roots": max(0, 10 - positive),
        "missing_counter_roots": max(0, 10 - counter),
        "rows_by_role": dict(sorted(row_counts.items())),
        "roots_by_role": {role: len(roots) for role, roots in sorted(roots_by_role.items())},
        "residual50_ready": positive >= 10 and counter >= 10,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = iter_jsonl(PY_CPP_READY) + iter_jsonl(RUST_PREVIOUS) + iter_jsonl(RUST_NEW)
    write_jsonl(READY_ROWS, rows)

    statuses = [
        family_status(
            rows,
            "python_evidence_verifier_constraint_vs_candidate_surface",
            "python",
            "verifier_and_test_constraint",
            "candidate_change_surface",
        ),
        family_status(
            rows,
            "c_cpp_evidence_verifier_constraint_vs_candidate_surface",
            "c_cpp",
            "verifier_and_test_constraint",
            "candidate_change_surface",
        ),
        family_status(
            rows,
            "rust_symptom_call_path_vs_candidate_surface",
            "rust",
            "symptom_or_call_path_analogue",
            "candidate_change_surface",
        ),
    ]
    duplicate_roots = [root for root, count in Counter(root_id(row) for row in rows).items() if count > 1]
    rows_missing_options = [
        row.get("row_id")
        for row in rows
        if len(row.get("opaque_options") or (row.get("standalone_projection_source") or {}).get("opaque_options") or []) < 4
    ]
    rows_without_train_support = [
        row.get("row_id")
        for row in rows
        if row.get("strict_eval_eligible") is True or row.get("train_support_only") is False
    ]
    passed = (
        all(status["residual50_ready"] for status in statuses)
        and not rows_missing_options
        and not rows_without_train_support
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "residual50_ready_for_controlled_probe_request"
        if passed
        else "residual50_ready_package_blocked",
        "metrics": {
            "rows": len(rows),
            "unique_roots": len({root_id(row) for row in rows}),
            "duplicate_roots": len(duplicate_roots),
            "rows_by_language": dict(sorted(Counter(row.get("language_family") for row in rows).items())),
            "rows_missing_options": len(rows_missing_options),
            "rows_without_train_support": len(rows_without_train_support),
        },
        "family_status": statuses,
        "probe_contract": {
            "baseline": "stage11444 + encoder_option_retrieval",
            "allowed_next_probe": "controlled diagnostic or promotable residual probe using this package as train-support analogues",
            "promotion_requires": [
                "old canary strict 23/23",
                "filtered strict 22/22",
                "filtered validation >=20/22",
                "old validation >=21/23",
                "frozen residual bank >=6/10",
                "full bounded-choice coverage",
                "selected product scorer encoder_option_retrieval",
            ],
            "do_not_train_on": "frozen residual miss rows",
        },
        "source_artifacts": {
            "python_cpp_ready": rel(PY_CPP_READY),
            "rust_previous": rel(RUST_PREVIOUS),
            "rust_new": rel(RUST_NEW),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "ready_rows": rel(READY_ROWS),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
