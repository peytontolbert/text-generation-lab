#!/usr/bin/env python3
"""Gate Stage11972/11975 transition-root review rows before any train package."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11976
NAME = "stage11976_transition_root_250_review_package_gate"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_review_package_gate.json"
ADMITTED = OUT / "transition_root_250_admitted_review_package.jsonl"
REJECTED = OUT / "transition_root_250_rejected_review_rows.jsonl"
STAGE11972_ROWS = ART / "stage11972_transition_root_250_probe_admission_audit/transition_root_250_admitted_review_rows.jsonl"
STAGE11975_ROWS = ART / "stage11975_transition_root_250_probe_expansion/transition_root_250_probe_expansion_review_rows.jsonl"
STAGE11967 = ART / "stage11967_transition_root_250_supply_contract/transition_root_250_supply_contract.json"

STATUS_FLOORS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}
LANG_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def status(row: dict[str, Any]) -> str:
    return str(row.get("observed_verifier_transition") or (row.get("standalone_projection_source") or {}).get("observed_verifier_transition") or "UNKNOWN")


def root_key(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return "::".join([str(row.get("repo_family") or row.get("repo_id") or "unknown"), str(source.get("selected_verifier_path") or row.get("source_root_id") or row.get("row_id"))])


def valid_row(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    ac = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    opts = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    if len(opts) < 2:
        reasons.append("missing_competing_options")
    if ac.get("deterministic_option_shuffle") is not True:
        reasons.append("deterministic_option_shuffle_missing")
    if ac.get("target_label_not_visible_before_options") is not True:
        reasons.append("target_label_leak_guard_missing")
    if ac.get("singleton_options") is not False:
        reasons.append("singleton_option_guard_missing")
    if status(row) not in {"PASS_TO_PASS", "PASS_CURRENT_BUILD"}:
        reasons.append("unsupported_transition_for_review_package")
    if row.get("strict_eval_eligible") is True:
        reasons.append("strict_eval_eligible_should_be_false")
    return reasons


def main() -> None:
    source_rows = [("stage11972", row) for row in read_jsonl(STAGE11972_ROWS)] + [("stage11975", row) for row in read_jsonl(STAGE11975_ROWS)]
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Prefer executed PASS_TO_PASS over collect/build rows for the same repo/test.
    source_rows.sort(key=lambda item: (0 if status(item[1]) == "PASS_TO_PASS" else 1, item[0], item[1].get("row_id", "")))
    for source_stage, row in source_rows:
        reasons = valid_row(row)
        key = root_key(row)
        if key in seen:
            reasons.append("duplicate_repo_verifier_key")
        if reasons:
            rejected.append({"row_id": row.get("row_id"), "source_stage": source_stage, "repo_family": row.get("repo_family"), "status": status(row), "reasons": reasons})
            continue
        copy = dict(row)
        copy["review_package_source_stage"] = source_stage
        copy["split_role"] = "review_package_only"
        copy["train_support_only"] = True
        copy["strict_eval_eligible"] = False
        admitted.append(copy)
        seen.add(key)
    write_jsonl(ADMITTED, admitted)
    write_jsonl(REJECTED, rejected)
    status_counts = Counter(status(row) for row in admitted)
    lang_roots: dict[str, set[str]] = {}
    for row in admitted:
        lang_roots.setdefault(str(row.get("language_family") or "unknown"), set()).add(root_key(row))
    lang_counts = {lang: len(roots) for lang, roots in sorted(lang_roots.items())}
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "review_package_gate_complete_not_trainable",
        "source_artifacts": {
            "stage11967_contract": rel(STAGE11967),
            "stage11972_rows": rel(STAGE11972_ROWS),
            "stage11975_rows": rel(STAGE11975_ROWS),
        },
        "gate_summary": {
            "input_rows": len(source_rows),
            "admitted_review_rows": len(admitted),
            "rejected_rows": len(rejected),
            "status_counts": dict(status_counts),
            "language_root_counts": lang_counts,
        },
        "remaining_to_stage11967_floor_from_review_package_only": {
            "status_remaining": {k: max(0, v - status_counts.get(k, 0)) for k, v in STATUS_FLOORS.items()},
            "language_root_remaining": {k: max(0, v - lang_counts.get(k, 0)) for k, v in LANG_FLOORS.items()},
        },
        "quality_decision": {
            "train_package_ready": False,
            "reason": [
                "Review package has useful source-backed PASS_TO_PASS/PASS_CURRENT_BUILD rows but is far below Transition-Root-250 scale.",
                "No FAIL_TO_PASS rows are admitted yet.",
                "No fresh Rust rows are admitted yet.",
                "Rows remain train_support_only until a larger package passes lineage and anti-cheat review.",
            ],
        },
        "outputs": {"summary": rel(SUMMARY), "admitted_rows": rel(ADMITTED), "rejected_rows": rel(REJECTED)},
        "next_stage_recommendation": {
            "stage": "stage11977_fail_to_pass_mutation_from_pass_roots",
            "action": "Use Stage11976 PASS_TO_PASS rows as the only eligible source for controlled mutation; generate fail-to-pass records from temp copies and keep review-only until verified.",
        },
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "gate_summary": artifact["gate_summary"], "quality_decision": artifact["quality_decision"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
