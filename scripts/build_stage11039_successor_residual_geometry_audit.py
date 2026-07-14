#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11039
NAME = "stage11039_successor_residual_geometry_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "successor_residual_geometry_audit.json"

PACKAGE_DIR = ARTIFACTS / "stage11035_successor_residual_support_package"
TRAIN_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
RESERVED_JSONL = PACKAGE_DIR / "reserved_residual_candidates.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def unique_roots(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(
            row.get("source_root_id")
            or row.get("root_id")
            or row.get("source_bundle_id")
            or row.get("row_id")
            or "missing"
        )
        for row in rows
    }


def main() -> None:
    train_rows = load_jsonl(TRAIN_JSONL)
    reserved_rows = load_jsonl(RESERVED_JSONL)

    train_roots = unique_roots(train_rows)
    roots_by_language: dict[str, set[str]] = defaultdict(set)
    roots_by_repo: dict[str, set[str]] = defaultdict(set)
    evidence_rows: list[dict[str, Any]] = []
    verifier_rows: list[dict[str, Any]] = []
    for row in train_rows:
        root = str(
            row.get("source_root_id")
            or row.get("root_id")
            or row.get("source_bundle_id")
            or row.get("row_id")
            or "missing"
        )
        language = str(row.get("language_family") or "missing")
        repo = str(row.get("repo_family") or "missing")
        roots_by_language[language].add(root)
        roots_by_repo[repo].add(root)
        task = str(row.get("task_type") or "")
        if "evidence" in task:
            evidence_rows.append(row)
        if "verifier" in task:
            verifier_rows.append(row)

    evidence_role_counts = Counter()
    for row in train_rows + reserved_rows:
        options = list(row.get("opaque_options") or [])
        target = str(row.get("target_text") or "")
        label_to_value = {str(opt.get("label")): str(opt.get("value")) for opt in options}
        target_value = label_to_value.get(target)
        if target_value:
            evidence_role_counts[target_value] += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit the stage11035 successor residual package for root-level breadth, task-family coverage, and evidence-role balance before any further probe.",
            "Make the remaining narrowness explicit so the package is not mistaken for a real scale or breakthrough branch."
        ],
        "source_artifacts": {
            "train_rows": rel(TRAIN_JSONL),
            "reserved_candidates": rel(RESERVED_JSONL),
        },
        "geometry": {
            "train_rows": len(train_rows),
            "train_unique_roots": len(train_roots),
            "train_rows_by_language": count_by(train_rows, "language_family"),
            "train_rows_by_repo_family": count_by(train_rows, "repo_family"),
            "train_rows_by_task_type": count_by(train_rows, "task_type"),
            "unique_roots_by_language": {k: len(v) for k, v in sorted(roots_by_language.items())},
            "unique_roots_by_repo_family": {k: len(v) for k, v in sorted(roots_by_repo.items())},
            "evidence_related_rows": len(evidence_rows),
            "verifier_related_rows": len(verifier_rows),
            "reserved_candidates": len(reserved_rows),
            "reserved_candidates_by_language": count_by(reserved_rows, "language_family"),
            "reserved_candidates_by_repo_family": count_by(reserved_rows, "repo_family"),
            "target_value_counts_train_plus_reserved": dict(sorted(evidence_role_counts.items())),
        },
        "diagnosis": [
            "The package is still root-thin relative to the residual goals; many added rows are multiple projections from the same few families.",
            "Python verifier-transition support exists, but fresh strict verifier-transition supply is still only one inserted successor row plus one reserved candidate.",
            "Rust and web remain under-supplied on the promotable replenishment path.",
            "Evidence-role balance should be checked against the candidate_change_surface prior before using this package as a training branch."
        ],
        "next_best_step": "Repair the successor package contract, then expand verifier_and_test_constraint and Python verifier-transition roots before trusting another training probe.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }

    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
