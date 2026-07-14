#!/usr/bin/env python3
"""Build guarded support probe manifest from completed Python/Rust/C++ support quotas."""

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
STAGE = 11880
NAME = "stage11880_source_heldout_support_guarded_probe_package"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_guarded_probe_package.json"
MANIFEST = OUT / "source_heldout_support_guarded_probe_manifest.jsonl"
ADDED_ROWS = OUT / "source_heldout_support_added_train_rows.jsonl"
AUDIT_ROWS = OUT / "source_heldout_support_guarded_probe_audit_rows.jsonl"

BASE = ART / "stage11497_candidate_set_evidence_judgment_head_probe_request/candidate_set_evidence_judgment_head_probe_manifest.jsonl"
GATE = ART / "stage11879_source_heldout_support_supply_status_v33/source_heldout_support_supply_status_v33.json"
PY_SUPPORT = ART / "stage11870_python_verifier_support_combined_audit_v13/python_verifier_support_combined_rows_v13.jsonl"
RUST_SUPPORT = ART / "stage11854_rust_verifier_support_combined_audit_v11/rust_verifier_support_rows_v11.jsonl"
CPP_SUPPORT = ART / "stage11878_cpp_abstain_support_combined_audit_v9/cpp_abstain_support_rows_v9.jsonl"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_split(row: dict[str, Any]) -> str:
    return str(row.get("split") or row.get("package_split") or "")


def row_root(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def option_labels(row: dict[str, Any]) -> set[str]:
    return {str(opt.get("label")) for opt in (row.get("opaque_options") or [])}


def failures_for_support(row: dict[str, Any], seen_row_ids: set[str], eval_roots: set[str], strict_roots: set[str]) -> list[str]:
    failures: list[str] = []
    anti = row.get("anti_cheat") or {}
    opts = row.get("opaque_options") or []
    row_id = str(row.get("row_id") or "")
    root = row_root(row)
    if row_id in seen_row_ids:
        failures.append("duplicate_row_id")
    if row_split(row) != "train":
        failures.append("support_not_train_split")
    if not row.get("train_support_only"):
        failures.append("support_not_train_support_only")
    if row.get("strict_eval_eligible"):
        failures.append("support_strict_eval_eligible")
    if row.get("source_heldout_admissible"):
        failures.append("support_source_heldout_admissible_true")
    if len(opts) < 2:
        failures.append("missing_or_singleton_options")
    if row.get("target_label") not in option_labels(row):
        failures.append("target_label_not_in_options")
    if not row.get("evidence_ledger"):
        failures.append("missing_evidence_ledger")
    if row.get("verifier_anchor") and not row.get("verifier_evidence"):
        failures.append("verifier_anchor_without_verifier_evidence")
    for key in [
        "deterministic_option_shuffle",
        "opaque_labels",
        "target_label_not_visible_before_options",
        "target_value_not_visible_before_options",
        "source_backed_snippets",
    ]:
        if not anti.get(key):
            failures.append(f"anti_cheat_missing_{key}")
    if root in eval_roots:
        failures.append("support_root_overlaps_eval")
    if root in strict_roots:
        failures.append("support_root_overlaps_strict")
    return failures


def main() -> None:
    gate = read_json(GATE)
    if not gate.get("training_probe_ready"):
        raise SystemExit("Stage11879 gate is not training_probe_ready")

    base_rows = read_jsonl(BASE)
    support_sources = {
        "python": PY_SUPPORT,
        "rust": RUST_SUPPORT,
        "c_cpp": CPP_SUPPORT,
    }
    support_rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for name, path in support_sources.items():
        rows = read_jsonl(path)
        source_counts[name] = len(rows)
        for row in rows:
            row = dict(row)
            row["stage11880_support_source"] = name
            support_rows.append(row)

    eval_roots = {row_root(row) for row in base_rows if row_split(row) == "eval"}
    strict_roots = {row_root(row) for row in base_rows if row_split(row) == "strict_eval"}
    seen_row_ids = {str(row.get("row_id") or "") for row in base_rows}
    audited_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    admitted_support: list[dict[str, Any]] = []
    for row in support_rows:
        failures = failures_for_support(row, seen_row_ids, eval_roots, strict_roots)
        seen_row_ids.add(str(row.get("row_id") or ""))
        audit = {
            "row_id": row.get("row_id"),
            "root_id": row.get("root_id"),
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "admitted": not failures,
            "failures": failures,
        }
        audited_rows.append(audit)
        if failures:
            blocked.append(audit)
        else:
            admitted_support.append(row)

    all_rows = base_rows + admitted_support
    split_counts = Counter(row_split(row) for row in all_rows)
    language_counts = Counter(str(row.get("language_family")) for row in all_rows)
    task_counts = Counter(str(row.get("task_type")) for row in all_rows)
    support_language_counts = Counter(str(row.get("language_family")) for row in admitted_support)
    support_repo_counts = Counter(str(row.get("repo_family")) for row in admitted_support)
    support_roots = {row_root(row) for row in admitted_support}

    write_jsonl(MANIFEST, all_rows)
    write_jsonl(ADDED_ROWS, admitted_support)
    write_jsonl(AUDIT_ROWS, audited_rows)

    passed = not blocked and len(admitted_support) == 160 and split_counts.get("eval", 0) == 23 and split_counts.get("strict_eval", 0) == 23
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "guarded_support_probe_manifest_ready" if passed else "guarded_support_probe_manifest_blocked",
        "base_manifest": rel(BASE),
        "gate_artifact": rel(GATE),
        "source_counts": source_counts,
        "row_counts": {
            "base_rows": len(base_rows),
            "added_support_rows": len(admitted_support),
            "blocked_support_rows": len(blocked),
            "manifest_rows": len(all_rows),
            "split_counts": dict(split_counts),
            "language_counts": dict(language_counts),
            "task_counts": dict(task_counts),
        },
        "support_counts": {
            "unique_support_roots": len(support_roots),
            "language_counts": dict(support_language_counts),
            "repo_family_counts": dict(support_repo_counts),
        },
        "guardrails": {
            "eval_rows_preserved": split_counts.get("eval", 0) == 23,
            "strict_rows_preserved": split_counts.get("strict_eval", 0) == 23,
            "support_root_eval_overlap": 0,
            "support_root_strict_overlap": 0,
            "blocked_support_rows": len(blocked),
        },
        "blocked_rows": blocked,
        "same_repo_family_warning": gate.get("support_status", {}).get("cpp_abstain_attractor_support", {}).get("same_repo_family_warning"),
        "claim_boundary": [
            "This is a guarded diagnostic support package, not source-heldout breadth evidence.",
            "Eval and strict rows are the protected Stage11507 manifest rows.",
            "C/C++ quota closure includes multiple same-repo-family google_benchmark support roots.",
            "No model score changes until the probe and postrun audits execute.",
        ],
        "outputs": {
            "summary": rel(SUMMARY),
            "manifest": rel(MANIFEST),
            "added_rows": rel(ADDED_ROWS),
            "audit_rows": rel(AUDIT_ROWS),
        },
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "manifest_rows": len(all_rows),
                "added_support_rows": len(admitted_support),
                "blocked_support_rows": len(blocked),
                "unique_support_roots": len(support_roots),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
