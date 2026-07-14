#!/usr/bin/env python3
"""Mine explicit Python verifier-transition supply with root/row overlap checks."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
OUT_DIR = ARTIFACTS / "stage11152_explicit_verifier_transition_supply_audit"
CURRENT_PACKAGE_DIRS = [
    ARTIFACTS / "stage11131_evidence_item_support_package",
    ARTIFACTS / "stage11146_singleton_strict_quarantine_successor",
]
SPLIT_FILES = [
    "agentkernel_lite_encdec_train.jsonl",
    "agentkernel_lite_encdec_validation.jsonl",
    "agentkernel_lite_encdec_strict_eval.jsonl",
    "agentkernel_lite_encdec_stress_eval.jsonl",
]

TRANSITION_MARKERS = ("FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "NOT_EXERCISED")
MAX_SCAN_BYTES = 100_000_000


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return


def root_key(row: dict[str, Any]) -> str | None:
    for key in ("source_root_id", "root_id", "source_bundle_id", "bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def load_protected() -> tuple[set[str], set[str]]:
    roots: set[str] = set()
    rows: set[str] = set()
    for base in CURRENT_PACKAGE_DIRS:
        for name in SPLIT_FILES:
            path = base / name
            if not path.exists():
                continue
            for row in read_jsonl(path):
                if row.get("row_id"):
                    rows.add(str(row["row_id"]))
                rk = root_key(row)
                if rk:
                    roots.add(rk)
    return roots, rows


def iter_files() -> Iterable[Path]:
    for path in sorted(ARTIFACTS.glob("stage*/**/*.jsonl")):
        try:
            if path.stat().st_size <= MAX_SCAN_BYTES:
                yield path
        except OSError:
            continue


def classify(row: dict[str, Any], protected_roots: set[str], protected_rows: set[str]) -> list[str]:
    blockers: list[str] = []
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    options = row.get("opaque_options")
    if row.get("language_family") != "python":
        blockers.append("not_python")
    if row.get("task_type") != "verifier_outcome_semantic_transition":
        blockers.append("not_verifier_transition")
    if not isinstance(options, list) or len(options) < 3:
        blockers.append("insufficient_options")
    if not any(marker in text for marker in TRANSITION_MARKERS):
        blockers.append("missing_transition_marker")
    if "Verifier target ledger:" not in text:
        blockers.append("missing_verifier_target_ledger")
    if "TODO_" in text or "PLACEHOLDER" in text:
        blockers.append("placeholder_text")
    if not row.get("selected_test_anchor"):
        blockers.append("missing_selected_test_anchor")
    rk = root_key(row)
    if not rk:
        blockers.append("missing_root_key")
    elif rk in protected_roots:
        blockers.append("root_already_in_current_package")
    rid = row.get("row_id")
    if rid and str(rid) in protected_rows:
        blockers.append("row_already_in_current_package")
    return blockers


def compact(row: dict[str, Any], source: Path) -> dict[str, Any]:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    return {
        "source_artifact": str(source.relative_to(ROOT)),
        "row_id": row.get("row_id"),
        "source_root_id": root_key(row),
        "source_bundle_id": row.get("source_bundle_id"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "task_type": row.get("task_type"),
        "target_text": row.get("target_text"),
        "option_count": len(options),
        "option_values": [opt.get("value") for opt in options if isinstance(opt, dict)],
        "selected_test_anchor": bool(row.get("selected_test_anchor")),
        "verifier_anchor": bool(row.get("verifier_anchor")),
        "train_support_only": bool(row.get("train_support_only")),
        "strict_eval_eligible": bool(row.get("strict_eval_eligible")),
        "prompt_prefix": text[:1000],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_roots, protected_rows = load_protected()
    accepted: list[dict[str, Any]] = []
    rejected_counts = Counter()
    seen_rows: set[str] = set()
    scanned_files = 0
    scanned_rows = 0

    for path in iter_files():
        scanned_files += 1
        for row in read_jsonl(path):
            scanned_rows += 1
            blockers = classify(row, protected_roots, protected_rows)
            if "not_python" in blockers or "not_verifier_transition" in blockers:
                continue
            if blockers:
                rejected_counts.update(blockers)
                continue
            rid = str(row.get("row_id") or "")
            if rid in seen_rows:
                rejected_counts.update(["duplicate_row_id_in_scan"])
                continue
            seen_rows.add(rid)
            accepted.append(compact(row, path))

    by_repo = Counter(str(r.get("repo_family") or r.get("repo_id") or "unknown") for r in accepted)
    by_target = Counter(str(r.get("target_text")) for r in accepted)
    by_source = Counter(r["source_artifact"] for r in accepted)
    summary = {
        "stage": 11152,
        "stage_name": "explicit_verifier_transition_supply_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "scan_root": str(ARTIFACTS.relative_to(ROOT)),
            "protected_package_dirs": [str(p.relative_to(ROOT)) for p in CURRENT_PACKAGE_DIRS],
        },
        "scan_metrics": {
            "scanned_files": scanned_files,
            "scanned_rows": scanned_rows,
            "protected_roots": len(protected_roots),
            "protected_rows": len(protected_rows),
        },
        "candidate_metrics": {
            "accepted_rows": len(accepted),
            "accepted_unique_roots": len({r["source_root_id"] for r in accepted if r.get("source_root_id")}),
            "accepted_by_repo_family": dict(sorted(by_repo.items())),
            "accepted_by_target": dict(sorted(by_target.items())),
            "accepted_by_source_top20": dict(by_source.most_common(20)),
            "rejected_reason_counts": dict(sorted(rejected_counts.items())),
        },
        "decision": "review_queue_only" if accepted else "no_new_explicit_verifier_transition_supply",
        "next_best_step": (
            "Review accepted rows for true transition semantics and build a "
            "small support package only if they are root-disjoint, non-leaky, "
            "and not broad file/test-list artifacts."
        ),
        "outputs": {
            "accepted_candidates_jsonl": str((OUT_DIR / "accepted_explicit_verifier_transition_candidates.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "explicit_verifier_transition_supply_audit.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "accepted_explicit_verifier_transition_candidates.jsonl").open("w") as f:
        for row in accepted:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "explicit_verifier_transition_supply_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
