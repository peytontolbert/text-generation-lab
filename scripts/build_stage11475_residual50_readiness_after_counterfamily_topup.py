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

STAGE = 11475
NAME = "stage11475_residual50_readiness_after_counterfamily_topup"
OUT = ART / NAME
SUMMARY = OUT / "residual50_readiness_after_counterfamily_topup.json"
READY_ROWS = OUT / "residual50_ready_python_cpp_rows.jsonl"
WORK_ITEMS = OUT / "residual50_remaining_work_items.jsonl"

STAGE11205_ADMITTED = ART / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"
STAGE11474_ADMITTED = ART / "stage11474_residual50_python_cpp_counterfamily_topup/admitted_residual50_python_cpp_counterfamily_rows.jsonl"
RUST_ROOT_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"
RUST_STRICT_REPLACEMENTS = ART / "stage11193_rust_external_graph_replacement_rows/rust_replacement_strict_candidate_rows.jsonl"


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


def gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or row.get("semantic_target_value") or "unknown")


def evidence_status(rows: list[dict[str, Any]], language: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("language_family") == language]
    roots_by_role: dict[str, set[str]] = defaultdict(set)
    rows_by_role = Counter()
    for row in selected:
        role = gold_value(row)
        roots_by_role[role].add(str(row.get("root_id") or row.get("source_root_id") or row.get("row_id")))
        rows_by_role[role] += 1
    positive_roots = len(roots_by_role.get("verifier_and_test_constraint", set()))
    counter_roots = len(roots_by_role.get("candidate_change_surface", set()))
    return {
        "family_id": f"{language}_evidence_verifier_constraint_vs_candidate_surface",
        "language_family": language,
        "rows": len(selected),
        "rows_by_role": dict(sorted(rows_by_role.items())),
        "roots_by_role": {role: len(roots) for role, roots in sorted(roots_by_role.items())},
        "positive_roots": positive_roots,
        "counter_roots": counter_roots,
        "missing_positive_roots": max(0, 10 - positive_roots),
        "missing_counter_roots": max(0, 10 - counter_roots),
        "residual50_ready": positive_roots >= 10 and counter_roots >= 10,
    }


def rust_status(root_rows: list[dict[str, Any]], strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = [row for row in root_rows if row.get("admitted_for_train_support")]
    exact_roots = []
    counter_roots = []
    for row in admitted:
        values = set(row.get("semantic_target_values") or [])
        flags = row.get("role_flags") or {}
        if flags.get("has_symptom_or_call_path") or "SYMPTOM_OR_CALL_PATH_ANALOGUE" in values:
            exact_roots.append(row)
        if "SUPPORTING_CANDIDATE_CHANGE_SURFACE" in values or flags.get("has_candidate_change_surface"):
            counter_roots.append(row)
    return {
        "family_id": "rust_symptom_call_path_vs_candidate_surface",
        "language_family": "rust",
        "train_support_roots": len(admitted),
        "repo_families": len({row.get("repo_family") for row in admitted}),
        "positive_roots": len({row.get("root_lineage_key") for row in exact_roots}),
        "counter_roots": len({row.get("root_lineage_key") for row in counter_roots}),
        "missing_positive_roots": max(0, 10 - len({row.get("root_lineage_key") for row in exact_roots})),
        "missing_counter_roots": max(0, 10 - len({row.get("root_lineage_key") for row in counter_roots})),
        "residual50_ready": len({row.get("root_lineage_key") for row in exact_roots}) >= 10
        and len({row.get("root_lineage_key") for row in counter_roots}) >= 10,
        "reserved_eval_replacement_rows": len(strict_rows),
        "reserved_eval_replacements_are_train_forbidden": any(
            (row.get("anti_cheat") or {}).get("not_train_support") for row in strict_rows
        ),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    py_cpp_rows = iter_jsonl(STAGE11205_ADMITTED) + iter_jsonl(STAGE11474_ADMITTED)
    rust_rows = iter_jsonl(RUST_ROOT_AUDIT)
    rust_replacements = iter_jsonl(RUST_STRICT_REPLACEMENTS)

    statuses = [
        evidence_status(py_cpp_rows, "python"),
        evidence_status(py_cpp_rows, "c_cpp"),
        rust_status(rust_rows, rust_replacements),
    ]
    work_items = [
        {
            "priority": "P0",
            "family_id": "rust_symptom_call_path_vs_candidate_surface",
            "action": "materialize_exact_symptom_or_call_path_analogue_roots",
            "needed_roots": statuses[2]["missing_positive_roots"],
            "candidate_source_pool": rel(RUST_ROOT_AUDIT),
            "do_not_train_on": rel(RUST_STRICT_REPLACEMENTS),
            "acceptance": [
                ">=10 train-support Rust roots with exact symptom_or_call_path analogue role",
                "candidate_change_surface remains present as hard negative",
                "selected-test/verifier anchor remains present",
                "no reserved/eval row lineage is used as train support",
            ],
        }
    ] if not statuses[2]["residual50_ready"] else []

    ready_rows = [
        row
        for row in py_cpp_rows
        if row.get("language_family") in {"python", "c_cpp"}
        and gold_value(row) in {"candidate_change_surface", "verifier_and_test_constraint"}
    ]
    write_jsonl(READY_ROWS, ready_rows)
    write_jsonl(WORK_ITEMS, work_items)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "python_cpp_residual50_ready_rust_symptom_call_path_missing"
        if statuses[0]["residual50_ready"] and statuses[1]["residual50_ready"] and not statuses[2]["residual50_ready"]
        else "residual50_readiness_incomplete",
        "family_status": statuses,
        "readiness": {
            "families_ready": sum(1 for status in statuses if status["residual50_ready"]),
            "families_total": len(statuses),
            "can_run_full_residual50_promotable_probe": all(status["residual50_ready"] for status in statuses),
            "can_run_python_cpp_controlled_diagnostic": statuses[0]["residual50_ready"] and statuses[1]["residual50_ready"],
        },
        "work_items": work_items,
        "source_artifacts": {
            "stage11205_admitted": rel(STAGE11205_ADMITTED),
            "stage11474_admitted": rel(STAGE11474_ADMITTED),
            "rust_root_audit": rel(RUST_ROOT_AUDIT),
            "rust_strict_replacements": rel(RUST_STRICT_REPLACEMENTS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "ready_python_cpp_rows": rel(READY_ROWS),
            "remaining_work_items": rel(WORK_ITEMS),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
