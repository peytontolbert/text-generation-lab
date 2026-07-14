#!/usr/bin/env python3
"""Mine root-disjoint Python verifier-outcome candidates from existing artifacts.

The current frontier is not limited by another small probe; it needs fresh
verifier-transition roots.  This stage scans local JSONL artifacts for bounded
Python verifier rows that are not already represented in the current v2.7
support/eval package, then emits a review queue instead of a train manifest.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
OUT_DIR = ARTIFACTS / "stage11144_fresh_python_verifier_candidate_miner"
CURRENT_PACKAGE_DIR = ARTIFACTS / "stage11131_evidence_item_support_package"

SPLIT_FILES = [
    CURRENT_PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl",
    CURRENT_PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl",
    CURRENT_PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
    CURRENT_PACKAGE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl",
]

MAX_SCAN_BYTES = 80_000_000
MIN_OPTIONS = 3
PLACEHOLDER_MARKERS = ("TODO_", "PLACEHOLDER", "TODO_AFTER")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def root_key(row: dict[str, Any]) -> str | None:
    for key in ("source_root_id", "root_id", "source_bundle_id", "bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def row_key(row: dict[str, Any]) -> str | None:
    value = row.get("row_id")
    return value if isinstance(value, str) and value else None


def load_protected_keys() -> tuple[set[str], set[str]]:
    roots: set[str] = set()
    rows: set[str] = set()
    for path in SPLIT_FILES:
        if not path.exists():
            continue
        for row in read_jsonl(path):
            rk = root_key(row)
            if rk:
                roots.add(rk)
            rid = row_key(row)
            if rid:
                rows.add(rid)
    return roots, rows


def candidate_reasons(row: dict[str, Any], protected_roots: set[str], protected_rows: set[str]) -> list[str]:
    reasons: list[str] = []
    if row.get("language_family") != "python":
        reasons.append("not_python")
    if row.get("task_type") != "verifier_outcome":
        reasons.append("not_verifier_outcome")
    options = row.get("opaque_options")
    if not isinstance(options, list) or len(options) < MIN_OPTIONS:
        reasons.append("insufficient_options")
    if not row.get("selected_test_anchor"):
        reasons.append("missing_selected_test_anchor")
    rk = root_key(row)
    if not rk:
        reasons.append("missing_root_key")
    elif rk in protected_roots:
        reasons.append("root_already_in_current_package")
    rid = row_key(row)
    if rid and rid in protected_rows:
        reasons.append("row_already_in_current_package")
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    if any(marker in text for marker in PLACEHOLDER_MARKERS):
        reasons.append("placeholder_prompt_text")
    if not text.strip():
        reasons.append("missing_input_text")
    target = str(row.get("target_text") or "")
    if not target:
        reasons.append("missing_target")
    return reasons


def compact_row(row: dict[str, Any], source_path: Path) -> dict[str, Any]:
    prompt = str(row.get("input_text") or row.get("prompt_text") or "")
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    return {
        "source_artifact": str(source_path.relative_to(ROOT)),
        "row_id": row.get("row_id"),
        "source_root_id": root_key(row),
        "source_bundle_id": row.get("source_bundle_id"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "target_text": row.get("target_text"),
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "option_count": len(options),
        "option_values": [o.get("value") for o in options[:8] if isinstance(o, dict)],
        "prompt_hash_basis_prefix": prompt[:500],
        "strict_eval_eligible": bool(row.get("strict_eval_eligible")),
        "train_support_only": bool(row.get("train_support_only")),
    }


def iter_candidate_files() -> Iterable[Path]:
    for path in sorted(ARTIFACTS.glob("stage*/**/*.jsonl")):
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
        except OSError:
            continue
        yield path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_roots, protected_rows = load_protected_keys()
    accepted: list[dict[str, Any]] = []
    rejected_counts = Counter()
    scanned_rows = 0
    scanned_files = 0
    seen_candidate_rows: set[str] = set()

    for path in iter_candidate_files():
        scanned_files += 1
        for row in read_jsonl(path):
            scanned_rows += 1
            reasons = candidate_reasons(row, protected_roots, protected_rows)
            if "not_python" in reasons or "not_verifier_outcome" in reasons:
                continue
            if reasons:
                rejected_counts.update(reasons)
                continue
            rid = row_key(row) or json.dumps(compact_row(row, path), sort_keys=True)
            if rid in seen_candidate_rows:
                rejected_counts.update(["duplicate_candidate_row"])
                continue
            seen_candidate_rows.add(rid)
            accepted.append(compact_row(row, path))

    by_repo = Counter(str(r.get("repo_family") or r.get("repo_id") or "unknown") for r in accepted)
    by_target = Counter(str(r.get("target_text")) for r in accepted)
    by_source = Counter(r["source_artifact"] for r in accepted)
    root_count = len({r["source_root_id"] for r in accepted if r.get("source_root_id")})

    summary = {
        "stage": 11144,
        "stage_name": "fresh_python_verifier_candidate_miner",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "current_package_dir": str(CURRENT_PACKAGE_DIR.relative_to(ROOT)),
            "scan_root": str(ARTIFACTS.relative_to(ROOT)),
        },
        "scan_metrics": {
            "scanned_jsonl_files": scanned_files,
            "scanned_jsonl_rows": scanned_rows,
            "protected_roots": len(protected_roots),
            "protected_rows": len(protected_rows),
        },
        "candidate_metrics": {
            "accepted_rows": len(accepted),
            "accepted_unique_roots": root_count,
            "accepted_by_repo_family": dict(sorted(by_repo.items())),
            "accepted_by_target": dict(sorted(by_target.items())),
            "accepted_by_source_artifact_top20": dict(by_source.most_common(20)),
            "rejected_reason_counts": dict(sorted(rejected_counts.items())),
        },
        "decision": "review_queue_only",
        "next_best_step": (
            "Manually/AI-review accepted candidates for true verifier-transition "
            "semantics, target leakage, and root-family novelty before adding any "
            "rows to train support."
        ),
        "outputs": {
            "accepted_candidates_jsonl": str((OUT_DIR / "accepted_python_verifier_candidates.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "fresh_python_verifier_candidate_miner.json").relative_to(ROOT)),
        },
    }

    with (OUT_DIR / "accepted_python_verifier_candidates.jsonl").open("w") as f:
        for row in accepted:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "fresh_python_verifier_candidate_miner.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
