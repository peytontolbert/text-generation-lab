#!/usr/bin/env python3
"""Admission audit for stage11154 local verifier-transition review rows."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11155_local_verifier_transition_admission_audit"
ROWS = (
    ROOT
    / "runs/local/artifacts/stage11154_local_repo_verifier_transition_materialization/local_repo_verifier_transition_review_rows.jsonl"
)
CURRENT_SPLITS = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"
SPLIT_FILES = [
    "agentkernel_lite_encdec_train.jsonl",
    "agentkernel_lite_encdec_validation.jsonl",
    "agentkernel_lite_encdec_strict_eval.jsonl",
    "agentkernel_lite_encdec_stress_eval.jsonl",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def current_ids() -> tuple[set[str], set[str]]:
    row_ids: set[str] = set()
    root_ids: set[str] = set()
    for name in SPLIT_FILES:
        for row in read_jsonl(CURRENT_SPLITS / name):
            if row.get("row_id"):
                row_ids.add(str(row["row_id"]))
            if row.get("source_root_id"):
                root_ids.add(str(row["source_root_id"]))
    return row_ids, root_ids


def audit_row(row: dict[str, Any], row_ids: set[str], root_ids: set[str]) -> dict[str, Any]:
    prompt = str(row.get("input_text") or "")
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    target = str(row.get("target_text") or "")
    target_opt = next((o for o in options if isinstance(o, dict) and str(o.get("label")) == target), None)
    blockers: list[str] = []
    warnings: list[str] = []
    if row.get("row_id") in row_ids:
        blockers.append("row_id_overlap_current_package")
    if row.get("source_root_id") in root_ids:
        blockers.append("source_root_overlap_current_package")
    if len(options) < 3:
        blockers.append("insufficient_options")
    if "Verifier target ledger:" not in prompt:
        blockers.append("missing_verifier_target_ledger")
    if "PASS_TO_PASS" not in prompt:
        blockers.append("missing_pass_to_pass_transition")
    if "pytest verifier result" not in prompt:
        blockers.append("missing_pytest_result")
    if not row.get("selected_test_anchor") or not row.get("verifier_anchor"):
        blockers.append("missing_anchor_flags")
    if "TODO_" in prompt or "PLACEHOLDER" in prompt:
        blockers.append("placeholder_text")
    if target_opt is None:
        blockers.append("target_label_missing_from_options")
    elif "PASS_TO_PASS" not in str(target_opt.get("value")):
        blockers.append("target_option_not_pass_to_pass")
    # These are support rows, so the direct test name is visible by design. Warn
    # if the source/test basename alone appears to be the only useful signal.
    if "source snippet" not in prompt or "direct test snippet" not in prompt:
        warnings.append("weak_snippet_context")
    return {
        "row_id": row.get("row_id"),
        "source_root_id": row.get("source_root_id"),
        "target_text": target,
        "option_count": len(options),
        "blockers": blockers,
        "warnings": warnings,
        "admitted": not blockers,
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS)
    row_ids, root_ids = current_ids()
    cards = [audit_row(row, row_ids, root_ids) for row in rows]
    admitted_ids = {card["row_id"] for card in cards if card["admitted"]}
    admitted_rows = [row for row in rows if row.get("row_id") in admitted_ids]
    blocker_counts = Counter(b for card in cards for b in card["blockers"])
    warning_counts = Counter(w for card in cards for w in card["warnings"])
    label_counts = Counter(str(row.get("target_text")) for row in admitted_rows)
    summary = {
        "stage": 11155,
        "stage_name": "local_verifier_transition_admission_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "review_rows": str(ROWS.relative_to(ROOT)),
            "current_split_dir": str(CURRENT_SPLITS.relative_to(ROOT)),
        },
        "metrics": {
            "rows_audited": len(rows),
            "admitted_rows": len(admitted_rows),
            "blocked_rows": len(rows) - len(admitted_rows),
            "admitted_unique_roots": len({r.get("source_root_id") for r in admitted_rows}),
            "admitted_target_label_counts": dict(sorted(label_counts.items())),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "warning_counts": dict(sorted(warning_counts.items())),
        },
        "decision": "admit_review_rows_for_support_package" if admitted_rows else "no_rows_admitted",
        "claim_scope": (
            "Admitted rows are local-repo PASS_TO_PASS verifier guardrail support. "
            "They are not strict heldout and not a broad capability claim."
        ),
        "next_best_step": (
            "If admitted_rows > 0, build a support package that appends these rows "
            "to the cleaned stage11146 train split and run one diagnostic probe only."
        ),
        "outputs": {
            "audit_cards_jsonl": str((OUT_DIR / "local_verifier_transition_admission_cards.jsonl").relative_to(ROOT)),
            "admitted_rows_jsonl": str((OUT_DIR / "admitted_local_verifier_transition_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "local_verifier_transition_admission_audit.json").relative_to(ROOT)),
        },
    }
    with (OUT_DIR / "local_verifier_transition_admission_cards.jsonl").open("w") as f:
        for card in cards:
            f.write(json.dumps(card, sort_keys=True) + "\n")
    with (OUT_DIR / "admitted_local_verifier_transition_rows.jsonl").open("w") as f:
        for row in admitted_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    (OUT_DIR / "local_verifier_transition_admission_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
