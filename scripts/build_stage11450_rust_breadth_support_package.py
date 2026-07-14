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
STAGE = 11450
NAME = "stage11450_rust_breadth_support_package"
OUT = ART / NAME
SUMMARY = OUT / "rust_breadth_support_package.json"
AUDIT = OUT / "rust_breadth_support_package_audit.json"
TRAIN = OUT / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = OUT / "agentkernel_lite_encdec_validation.jsonl"
STRICT = OUT / "agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = OUT / "semantic_candidate_residual_bank.jsonl"
ADDED = OUT / "added_rust_breadth_support_rows.jsonl"
SKIPPED = OUT / "skipped_rust_breadth_support_rows.jsonl"

BASE = ART / "stage11442_targeted_residual_role_support_package"
BASE_TRAIN = BASE / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_RESIDUAL = BASE / "semantic_candidate_residual_bank.jsonl"
ROOT_AUDIT = ART / "stage11449_rust_materialized_support_readiness_audit_v2/rust_materialized_support_root_audit.jsonl"

SOURCE_FILES = [
    ART / "stage11407_partial_candle_rust_train_support_rows/partial_candle_rust_train_support_rows.jsonl",
    ART / "stage11410_rust_verifier_log_backed_partial_support/rust_verifier_log_backed_partial_support_rows.jsonl",
    ART / "stage11413_non_candle_rust_verifier_log_backed_support/non_candle_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11417_third_family_rust_verifier_log_backed_support/third_family_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11420_perftree_rust_build_verifier_backed_support/perftree_rust_build_verifier_backed_support_rows.jsonl",
    ART / "stage11428_codex_rs_selected_test_support_rows/codex_rs_selected_test_support_rows.jsonl",
    ART / "stage11429_selected_test_rust_support_package/added_selected_test_rust_support_rows.jsonl",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def text(value: Any) -> str:
    return "" if value is None else str(value)


def row_id(row: dict[str, Any]) -> str:
    return text(row.get("row_id") or row.get("semantic_key") or row.get("input_text"))


def root_key(row: dict[str, Any]) -> str:
    return text(row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_row_id") or row.get("row_id"))


def repo_family(row: dict[str, Any]) -> str:
    return text(row.get("repo_family") or row.get("repo_id") or "unknown")


def language(row: dict[str, Any]) -> str:
    return text(row.get("language_family") or row.get("language") or "unknown")


def target_value(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    return text(row.get("semantic_target_value") or source.get("gold_value") or row.get("target_value") or row.get("decoder_text") or "unknown")


def counts_by(rows: list[dict[str, Any]], key_fn) -> dict[str, int]:
    return dict(sorted(Counter(key_fn(row) for row in rows).items()))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_train = read_jsonl(BASE_TRAIN)
    validation = read_jsonl(BASE_VALIDATION)
    strict = read_jsonl(BASE_STRICT)
    residual = read_jsonl(BASE_RESIDUAL)

    admitted_roots = {
        row["root_lineage_key"]
        for row in read_jsonl(ROOT_AUDIT)
        if row.get("admitted_for_train_support") is True
    }
    all_candidates: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for source_path in SOURCE_FILES:
        rows = [
            row
            for row in read_jsonl(source_path)
            if language(row) == "rust" and root_key(row) in admitted_roots
        ]
        source_counts[rel(source_path)] = len(rows)
        all_candidates.extend(rows)

    base_ids = {row_id(row) for row in base_train}
    protected_roots = {
        "validation": {root_key(row) for row in validation},
        "strict": {root_key(row) for row in strict},
        "residual": {root_key(row) for row in residual},
    }
    seen_added: set[str] = set()
    added: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in all_candidates:
        rid = row_id(row)
        rkey = root_key(row)
        reasons: list[str] = []
        if rid in base_ids:
            reasons.append("already_in_base_train")
        if rid in seen_added:
            reasons.append("duplicate_candidate_row_id")
        for split, roots in protected_roots.items():
            if rkey in roots:
                reasons.append(f"root_overlap_{split}")
        if row.get("train_support_only") is not True:
            reasons.append("not_train_support_only")
        if row.get("strict_eval_eligible") is True:
            reasons.append("strict_eval_eligible")
        if reasons:
            skipped.append(
                {
                    "row_id": rid,
                    "root_lineage_key": rkey,
                    "repo_family": repo_family(row),
                    "semantic_target_value": target_value(row),
                    "skip_reasons": reasons,
                }
            )
            continue
        seen_added.add(rid)
        added.append(row)

    train = base_train + added
    train_ids = [row_id(row) for row in train]
    duplicate_train_ids = sorted(item for item, count in Counter(train_ids).items() if count > 1)
    added_roots = {root_key(row) for row in added}
    added_repos = {repo_family(row) for row in added}
    root_overlap = {
        split: sorted(added_roots & roots)
        for split, roots in protected_roots.items()
    }
    passed = (
        len(added_roots) >= 7
        and len(added_repos) >= 3
        and not duplicate_train_ids
        and not any(root_overlap.values())
    )

    audit = {
        "source_counts": source_counts,
        "rows": {
            "base_train": len(base_train),
            "candidate_rows_from_admitted_roots": len(all_candidates),
            "added_rows": len(added),
            "skipped_rows": len(skipped),
            "final_train": len(train),
            "validation": len(validation),
            "strict": len(strict),
            "residual": len(residual),
        },
        "roots": {
            "admitted_roots_from_stage11449": len(admitted_roots),
            "added_roots": len(added_roots),
            "added_repo_families": len(added_repos),
        },
        "added_by_repo_family": counts_by(added, repo_family),
        "added_by_target_value": counts_by(added, target_value),
        "final_train_by_language": counts_by(train, language),
        "final_train_by_repo_family": counts_by(train, repo_family),
        "root_overlap": root_overlap,
        "duplicate_train_row_ids": duplicate_train_ids,
        "skipped_reason_counts": dict(sorted(Counter(reason for row in skipped for reason in row["skip_reasons"]).items())),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "rust_breadth_support_package_ready" if passed else "rust_breadth_support_package_failed_gate",
        "counts": audit["rows"],
        "added_support": audit["roots"],
        "quality_gate": {
            "minimum_added_roots_met": len(added_roots) >= 7,
            "minimum_added_repo_breadth_met": len(added_repos) >= 3,
            "no_duplicate_train_row_ids": not duplicate_train_ids,
            "no_added_root_overlap_validation": not root_overlap["validation"],
            "no_added_root_overlap_strict": not root_overlap["strict"],
            "no_added_root_overlap_residual": not root_overlap["residual"],
            "ready_for_probe_request": passed,
        },
        "policy": {
            "base_runtime_lineage": "stage11442_train_package_used_by_stage11444_selected_runtime_path",
            "use_for_training_only_if_probe_request_also_passes": True,
            "diagnostic_build_verifier_only_roots_excluded": True,
        },
        "source_artifacts": {
            "base_package": rel(BASE / "targeted_residual_role_support_package.json"),
            "stage11449_root_audit": rel(ROOT_AUDIT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "audit": rel(AUDIT),
            "train": rel(TRAIN),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual": rel(RESIDUAL),
            "added": rel(ADDED),
            "skipped": rel(SKIPPED),
        },
    }
    write_jsonl(TRAIN, train)
    write_jsonl(VALIDATION, validation)
    write_jsonl(STRICT, strict)
    write_jsonl(RESIDUAL, residual)
    write_jsonl(ADDED, added)
    write_jsonl(SKIPPED, skipped)
    write_json(AUDIT, audit)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
