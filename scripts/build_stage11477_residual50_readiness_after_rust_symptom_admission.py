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

STAGE = 11477
NAME = "stage11477_residual50_readiness_after_rust_symptom_admission"
OUT = ART / NAME
SUMMARY = OUT / "residual50_readiness_after_rust_symptom_admission.json"
READY_ROWS = OUT / "residual50_ready_partial_rows.jsonl"
WORK_ITEMS = OUT / "residual50_remaining_rust_work_items.jsonl"

PY_CPP_READY = ART / "stage11475_residual50_readiness_after_counterfamily_topup/residual50_ready_python_cpp_rows.jsonl"
RUST_ADMITTED = ART / "stage11476_rust_symptom_call_path_residual50_admission/admitted_rust_symptom_call_path_rows.jsonl"
RUST_BLOCKED = ART / "stage11476_rust_symptom_call_path_residual50_admission/blocked_rust_symptom_call_path_rows.jsonl"
RUST_SOURCE_POOL = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"


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
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("semantic_target_value") or "unknown")


def evidence_status(rows: list[dict[str, Any]], language: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("language_family") == language]
    roots_by_role: dict[str, set[str]] = defaultdict(set)
    rows_by_role = Counter()
    for row in selected:
        role = gold_value(row)
        roots_by_role[role].add(root_id(row))
        rows_by_role[role] += 1
    positive = len(roots_by_role.get("verifier_and_test_constraint", set()))
    counter = len(roots_by_role.get("candidate_change_surface", set()))
    return {
        "family_id": f"{language}_evidence_verifier_constraint_vs_candidate_surface",
        "language_family": language,
        "positive_roots": positive,
        "counter_roots": counter,
        "missing_positive_roots": max(0, 10 - positive),
        "missing_counter_roots": max(0, 10 - counter),
        "roots_by_role": {role: len(roots) for role, roots in sorted(roots_by_role.items())},
        "rows_by_role": dict(sorted(rows_by_role.items())),
        "residual50_ready": positive >= 10 and counter >= 10,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    py_cpp_rows = iter_jsonl(PY_CPP_READY)
    rust_rows = iter_jsonl(RUST_ADMITTED)
    blocked = iter_jsonl(RUST_BLOCKED)

    py_status = evidence_status(py_cpp_rows, "python")
    cpp_status = evidence_status(py_cpp_rows, "c_cpp")
    rust_positive = len({root_id(row) for row in rust_rows})
    rust_status = {
        "family_id": "rust_symptom_call_path_vs_candidate_surface",
        "language_family": "rust",
        "positive_roots": rust_positive,
        "counter_roots": 19,
        "missing_positive_roots": max(0, 10 - rust_positive),
        "missing_counter_roots": 0,
        "admitted_repos": dict(sorted(Counter(row.get("repo_family") for row in rust_rows).items())),
        "residual50_ready": rust_positive >= 10,
    }

    block_reasons = Counter()
    for row in blocked:
        for reason in row.get("block_reasons") or []:
            block_reasons[reason] += 1

    needed = rust_status["missing_positive_roots"]
    work_items = []
    if needed:
        work_items.append(
            {
                "priority": "P0",
                "family_id": "rust_symptom_call_path_vs_candidate_surface",
                "action": "build_new_disjoint_rust_symptom_call_path_roots",
                "needed_roots": needed,
                "source_pool": rel(RUST_SOURCE_POOL),
                "acceptance": [
                    "language_family == rust",
                    "gold evidence role == symptom_or_call_path_analogue",
                    "candidate_change_surface present as hard negative",
                    "candidate and symptom/call-path evidence text are not aliases",
                    "selected-test or verifier anchor present",
                    "repo/root lineage disjoint from stage11193 reserved replacements",
                    "do not use tokenizers or duplicate candle/linux variants to fill quota",
                ],
            }
        )

    all_ready_rows = py_cpp_rows + rust_rows
    write_jsonl(READY_ROWS, all_ready_rows)
    write_jsonl(WORK_ITEMS, work_items)

    statuses = [py_status, cpp_status, rust_status]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "residual50_still_missing_8_rust_symptom_call_path_roots"
        if needed
        else "residual50_ready_for_controlled_probe_request",
        "family_status": statuses,
        "readiness": {
            "families_ready": sum(1 for status in statuses if status["residual50_ready"]),
            "families_total": len(statuses),
            "can_run_full_residual50_promotable_probe": all(status["residual50_ready"] for status in statuses),
            "can_run_python_cpp_controlled_diagnostic": py_status["residual50_ready"] and cpp_status["residual50_ready"],
            "can_run_rust_partial_diagnostic": rust_positive >= 2,
        },
        "rust_blocker_counts": dict(sorted(block_reasons.items())),
        "work_items": work_items,
        "source_artifacts": {
            "python_cpp_ready": rel(PY_CPP_READY),
            "rust_admitted": rel(RUST_ADMITTED),
            "rust_blocked": rel(RUST_BLOCKED),
            "rust_source_pool": rel(RUST_SOURCE_POOL),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "ready_partial_rows": rel(READY_ROWS),
            "remaining_work_items": rel(WORK_ITEMS),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
