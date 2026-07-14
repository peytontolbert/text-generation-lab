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

STAGE = 11473
NAME = "stage11473_residual50_inventory_and_build_request"
OUT = ART / NAME
SUMMARY = OUT / "residual50_inventory_and_build_request.json"
CANDIDATES = OUT / "residual50_candidate_inventory.jsonl"
WORK_ITEMS = OUT / "residual50_build_work_items.jsonl"

CONTRACT = ART / "stage11472_controlled_residual_lab_contract/controlled_residual_lab_contract.json"
PY_CPP_EVIDENCE_ROWS = ART / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"
RUST_ROOT_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"
RUST_STRICT_REPLACEMENTS = ART / "stage11193_rust_external_graph_replacement_rows/rust_replacement_strict_candidate_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def gold_value(row: dict[str, Any]) -> str | None:
    source = row.get("standalone_projection_source") or {}
    return source.get("gold_value") or row.get("semantic_target_value")


def summarize_evidence_rows(rows: list[dict[str, Any]], language: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("language_family") == language]
    roots_by_role: dict[str, set[str]] = defaultdict(set)
    rows_by_role = Counter()
    candidate_records: list[dict[str, Any]] = []
    for row in selected:
        role = gold_value(row) or "unknown"
        root_id = row.get("root_id") or row.get("source_root_id") or row.get("row_id")
        rows_by_role[role] += 1
        roots_by_role[role].add(str(root_id))
        candidate_records.append(
            {
                "family_id": f"{language}_evidence_verifier_constraint_vs_candidate_surface",
                "language_family": language,
                "root_id": root_id,
                "repo_family": row.get("repo_family"),
                "row_id": row.get("row_id"),
                "role": role,
                "admit_role": "residual50_train_analogue_candidate",
                "source_artifact": rel(PY_CPP_EVIDENCE_ROWS),
            }
        )
    return {
        "rows": len(selected),
        "unique_roots": len({row.get("root_id") for row in selected}),
        "rows_by_role": dict(sorted(rows_by_role.items())),
        "roots_by_role": {role: len(roots) for role, roots in sorted(roots_by_role.items())},
        "candidate_records": candidate_records,
    }


def summarize_rust_roots(rows: list[dict[str, Any]], strict_replacements: list[dict[str, Any]]) -> dict[str, Any]:
    train_roots = [row for row in rows if row.get("admitted_for_train_support")]
    role_counts = Counter()
    exact_symptom_roots: set[str] = set()
    candidate_records: list[dict[str, Any]] = []
    for row in train_roots:
        values = set(row.get("semantic_target_values") or [])
        flags = row.get("role_flags") or {}
        root_id = str(row.get("root_lineage_key"))
        for value in values:
            role_counts[value] += 1
        if flags.get("has_symptom_or_call_path") or "SYMPTOM_OR_CALL_PATH_ANALOGUE" in values:
            exact_symptom_roots.add(root_id)
        candidate_records.append(
            {
                "family_id": "rust_symptom_call_path_vs_candidate_surface",
                "language_family": "rust",
                "root_id": root_id,
                "repo_family": row.get("repo_family"),
                "rows": row.get("rows"),
                "semantic_target_values": sorted(values),
                "role_flags": flags,
                "admit_role": "rust_source_supply_repair_candidate",
                "source_artifact": rel(RUST_ROOT_AUDIT),
                "blockers": [
                    "missing_exact_symptom_or_call_path_analogue"
                ]
                if root_id not in exact_symptom_roots
                else [],
            }
        )
    reserved_roots = {
        row.get("row_id"): row.get("repo_family")
        for row in strict_replacements
        if row.get("anti_cheat", {}).get("not_train_support")
    }
    return {
        "train_support_roots": len(train_roots),
        "repo_families": len({row.get("repo_family") for row in train_roots}),
        "semantic_target_value_root_counts": dict(sorted(role_counts.items())),
        "exact_symptom_call_path_train_roots": len(exact_symptom_roots),
        "reserved_eval_replacement_rows": len(reserved_roots),
        "reserved_eval_replacements_are_train_forbidden": bool(reserved_roots),
        "candidate_records": candidate_records,
    }


def family_status(
    family_id: str,
    positive_roots: int,
    counter_roots: int,
    required_positive_roots: int = 10,
    required_counter_roots: int = 10,
) -> dict[str, Any]:
    missing_positive = max(0, required_positive_roots - positive_roots)
    missing_counter = max(0, required_counter_roots - counter_roots)
    return {
        "family_id": family_id,
        "positive_roots": positive_roots,
        "counter_roots": counter_roots,
        "required_positive_roots": required_positive_roots,
        "required_counter_roots": required_counter_roots,
        "missing_positive_roots": missing_positive,
        "missing_counter_roots": missing_counter,
        "residual50_ready": missing_positive == 0 and missing_counter == 0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = load_json(CONTRACT)
    evidence_rows = iter_jsonl(PY_CPP_EVIDENCE_ROWS)
    rust_roots = iter_jsonl(RUST_ROOT_AUDIT)
    rust_replacements = iter_jsonl(RUST_STRICT_REPLACEMENTS)

    python = summarize_evidence_rows(evidence_rows, "python")
    cpp = summarize_evidence_rows(evidence_rows, "c_cpp")
    rust = summarize_rust_roots(rust_roots, rust_replacements)

    candidate_inventory = (
        python["candidate_records"]
        + cpp["candidate_records"]
        + rust["candidate_records"]
    )

    py_status = family_status(
        "python_evidence_verifier_constraint_vs_candidate_surface",
        positive_roots=python["roots_by_role"].get("verifier_and_test_constraint", 0),
        counter_roots=python["roots_by_role"].get("candidate_change_surface", 0),
    )
    cpp_status = family_status(
        "cpp_evidence_verifier_constraint_vs_candidate_surface",
        positive_roots=cpp["roots_by_role"].get("verifier_and_test_constraint", 0),
        counter_roots=cpp["roots_by_role"].get("candidate_change_surface", 0),
    )
    rust_status = family_status(
        "rust_symptom_call_path_vs_candidate_surface",
        positive_roots=rust["exact_symptom_call_path_train_roots"],
        counter_roots=min(
            rust["semantic_target_value_root_counts"].get("SUPPORTING_CANDIDATE_CHANGE_SURFACE", 0),
            rust["train_support_roots"],
        ),
    )

    work_items = [
        {
            "priority": "P0",
            "family_id": "python_evidence_verifier_constraint_vs_candidate_surface",
            "action": "materialize_more_candidate_change_surface_counterfamily_roots",
            "needed_roots": py_status["missing_counter_roots"],
            "why": "Verifier/test constraint positives are sufficient, but counterfamily roots are below the Residual-50 balance target.",
            "do_not_train_on": "frozen residual miss rows",
        },
        {
            "priority": "P0",
            "family_id": "cpp_evidence_verifier_constraint_vs_candidate_surface",
            "action": "materialize_more_candidate_change_surface_counterfamily_roots",
            "needed_roots": cpp_status["missing_counter_roots"],
            "why": "C/C++ verifier/test positives are sufficient, but candidate-surface counterfamily roots are below target.",
            "do_not_train_on": "frozen residual miss rows",
        },
        {
            "priority": "P0",
            "family_id": "rust_symptom_call_path_vs_candidate_surface",
            "action": "materialize_exact_symptom_or_call_path_analogue_roots",
            "needed_roots": rust_status["missing_positive_roots"],
            "why": "Rust has selected-test/source-backed supply, but not exact trainable symptom/call-path analogue roots for the frozen residual family.",
            "candidate_source_pool": rel(RUST_ROOT_AUDIT),
            "do_not_train_on": rel(RUST_STRICT_REPLACEMENTS),
        },
    ]
    work_items = [item for item in work_items if item.get("needed_roots", 0) > 0]

    statuses = [py_status, cpp_status, rust_status]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "residual50_not_ready_build_queue_created"
        if any(not status["residual50_ready"] for status in statuses)
        else "residual50_ready_for_controlled_probe_request",
        "contract": rel(CONTRACT),
        "source_artifacts": {
            "python_cpp_evidence_rows": rel(PY_CPP_EVIDENCE_ROWS),
            "rust_root_audit": rel(RUST_ROOT_AUDIT),
            "rust_strict_replacements": rel(RUST_STRICT_REPLACEMENTS),
        },
        "family_status": statuses,
        "inventory_summary": {
            "python": {
                "rows": python["rows"],
                "unique_roots": python["unique_roots"],
                "rows_by_role": python["rows_by_role"],
                "roots_by_role": python["roots_by_role"],
            },
            "c_cpp": {
                "rows": cpp["rows"],
                "unique_roots": cpp["unique_roots"],
                "rows_by_role": cpp["rows_by_role"],
                "roots_by_role": cpp["roots_by_role"],
            },
            "rust": {
                key: value
                for key, value in rust.items()
                if key != "candidate_records"
            },
        },
        "residual_lab_readiness": {
            "families_ready": sum(1 for status in statuses if status["residual50_ready"]),
            "families_total": len(statuses),
            "can_run_promotable_probe_now": all(status["residual50_ready"] for status in statuses),
            "can_run_partial_diagnostic": True,
            "partial_diagnostic_scope": [
                "python/c_cpp evidence verifier-constraint positives",
                "rust source-supply repair candidates only; not exact family training yet",
            ],
        },
        "work_items": work_items,
        "notes": [
            "Stage11205 gives enough Python/C++ verifier_and_test_constraint positives for Residual-50, but both languages are short two candidate_change_surface counterfamily roots.",
            "Stage11453 gives Rust selected-test/source-backed supply, but the exact residual family is symptom_or_call_path_vs_candidate_surface; current train-support roots need role materialization before promotion.",
            "Stage11193 Rust replacements remain eval/reserved rows and are explicitly not train support.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "candidate_inventory": rel(CANDIDATES),
            "work_items": rel(WORK_ITEMS),
        },
    }

    write_json(SUMMARY, payload)
    write_jsonl(CANDIDATES, candidate_inventory)
    write_jsonl(WORK_ITEMS, work_items)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")

    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "family_status": statuses,
                "work_items": len(work_items),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
