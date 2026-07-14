#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11478
NAME = "stage11478_rust_symptom_call_path_materialization_queue"
OUT = ART / NAME
SUMMARY = OUT / "rust_symptom_call_path_materialization_queue.json"
WORK_ITEMS = OUT / "rust_symptom_call_path_materialization_work_items.jsonl"
SELECTED_ROOTS = OUT / "selected_rust_source_roots_for_symptom_materialization.jsonl"

ROOT_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_root_audit.jsonl"
ROW_AUDIT = ART / "stage11453_rust_materialized_support_readiness_audit_v3/rust_materialized_support_row_audit.jsonl"
RUST_ADMITTED_SYMPTOM = ART / "stage11476_rust_symptom_call_path_residual50_admission/admitted_rust_symptom_call_path_rows.jsonl"
READINESS = ART / "stage11477_residual50_readiness_after_rust_symptom_admission/residual50_readiness_after_rust_symptom_admission.json"

EXCLUDED_REPOS = {"candle", "linux", "tokenizers"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("row_id"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    roots = iter_jsonl(ROOT_AUDIT)
    rows = iter_jsonl(ROW_AUDIT)
    already_admitted = {root_id(row) for row in iter_jsonl(RUST_ADMITTED_SYMPTOM)}
    readiness = load_json(READINESS)
    needed = 8
    for item in readiness.get("work_items") or []:
        if item.get("family_id") == "rust_symptom_call_path_vs_candidate_surface":
            needed = int(item.get("needed_roots") or needed)

    row_count_by_root = Counter(root_id(row) for row in rows)
    values_by_root: dict[str, set[str]] = {}
    for row in rows:
        values_by_root.setdefault(root_id(row), set()).add(str(row.get("semantic_target_value")))

    eligible = []
    blocked = []
    for root in roots:
        rid = root_id(root)
        repo = str(root.get("repo_family") or "unknown")
        values = set(root.get("semantic_target_values") or []) | values_by_root.get(rid, set())
        flags = root.get("role_flags") or {}
        blockers = []
        if not root.get("admitted_for_train_support"):
            blockers.append("not_admitted_for_train_support")
        if root.get("diagnostic_build_verifier_only"):
            blockers.append("build_verifier_only_diagnostic")
        if repo in EXCLUDED_REPOS:
            blockers.append("excluded_repo_family")
        if rid in already_admitted:
            blockers.append("already_has_admitted_symptom_root")
        if not (flags.get("has_candidate_change_surface") or "SUPPORTING_CANDIDATE_CHANGE_SURFACE" in values):
            blockers.append("missing_candidate_change_surface_counter")
        if not (
            flags.get("has_selected_test_constraint")
            or flags.get("has_verifier_log")
            or "DECISIVE_SELECTED_TEST_CONSTRAINT" in values
            or "DECISIVE_VERIFIER_TEST_CONSTRAINT" in values
            or "OBSERVED_VERIFIER_LOG" in values
            or "OBSERVED_VERIFIER_PASS_LOG" in values
            or "OBSERVED_VERIFIER_FAILURE_LOG" in values
        ):
            blockers.append("missing_selected_test_or_verifier_anchor")
        if blockers:
            blocked.append(
                {
                    "root_lineage_key": rid,
                    "repo_family": repo,
                    "blockers": blockers,
                    "semantic_target_values": sorted(values),
                    "rows": root.get("rows"),
                }
            )
        else:
            eligible.append(
                {
                    "root_lineage_key": rid,
                    "repo_family": repo,
                    "semantic_target_values": sorted(values),
                    "role_flags": flags,
                    "rows": row_count_by_root.get(rid, root.get("rows")),
                    "source_artifacts": {
                        "root_audit": rel(ROOT_AUDIT),
                        "row_audit": rel(ROW_AUDIT),
                    },
                }
            )

    # Prefer repo breadth before repeated codex-rs roots.
    selected = []
    repo_counts: Counter[str] = Counter()
    for candidate in sorted(eligible, key=lambda row: (repo_counts[row["repo_family"]], row["repo_family"], row["root_lineage_key"])):
        if len(selected) >= needed:
            break
        if repo_counts[candidate["repo_family"]] >= 4:
            continue
        selected.append(candidate)
        repo_counts[candidate["repo_family"]] += 1
    if len(selected) < needed:
        for candidate in eligible:
            if len(selected) >= needed:
                break
            if candidate in selected:
                continue
            selected.append(candidate)

    work_items = [
        {
            "priority": "P0",
            "family_id": "rust_symptom_call_path_vs_candidate_surface",
            "root_lineage_key": item["root_lineage_key"],
            "repo_family": item["repo_family"],
            "action": "materialize_symptom_or_call_path_evidence_row",
            "required_gold_value": "symptom_or_call_path_analogue",
            "required_hard_negative": "candidate_change_surface",
            "acceptance": [
                "reuse the root's existing changed-source candidate evidence as candidate_change_surface hard negative",
                "derive symptom/call-path evidence from a call path, failing/passing verifier log, selected test body, or execution trace-like source snippet",
                "candidate_change_surface and symptom_or_call_path_analogue text must not be aliases over the same span",
                "preserve selected-test/verifier anchor in the visible packet",
                "opaque options must include candidate_change_surface, verifier/test constraint, symptom_or_call_path_analogue, and insufficient/background alternative",
                "train_support_only true; strict_eval_eligible false",
            ],
            "source_artifacts": item["source_artifacts"],
        }
        for item in selected
    ]

    write_jsonl(SELECTED_ROOTS, selected)
    write_jsonl(WORK_ITEMS, work_items)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": len(work_items) >= needed,
        "decision": "rust_symptom_call_path_materialization_queue_ready"
        if len(work_items) >= needed
        else "rust_symptom_call_path_materialization_queue_short",
        "needed_roots": needed,
        "metrics": {
            "eligible_roots": len(eligible),
            "selected_roots": len(selected),
            "work_items": len(work_items),
            "selected_by_repo": dict(sorted(Counter(item["repo_family"] for item in selected).items())),
            "blocked_roots": len(blocked),
        },
        "policy": {
            "excluded_repos": sorted(EXCLUDED_REPOS),
            "do_not_use_reserved_eval_lineage": True,
            "do_not_use_duplicate_candle_or_linux_variants": True,
            "target_is_materialization_queue_not_training_package": True,
        },
        "source_artifacts": {
            "readiness": rel(READINESS),
            "root_audit": rel(ROOT_AUDIT),
            "row_audit": rel(ROW_AUDIT),
            "already_admitted_symptom": rel(RUST_ADMITTED_SYMPTOM),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "selected_roots": rel(SELECTED_ROOTS),
            "work_items": rel(WORK_ITEMS),
        },
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
