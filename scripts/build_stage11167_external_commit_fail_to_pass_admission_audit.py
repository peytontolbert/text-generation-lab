#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IN_ROWS = (
    ROOT
    / "runs/local/artifacts/stage11166_external_commit_fail_to_pass_verifier_target_materialization/external_commit_fail_to_pass_verifier_target_review_rows.jsonl"
)
MATERIALIZATION_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage11166_external_commit_fail_to_pass_verifier_target_materialization/external_commit_fail_to_pass_verifier_target_materialization.json"
)
CURRENT_PACKAGE_DIR = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"
OUT_DIR = ROOT / "runs/local/artifacts/stage11167_external_commit_fail_to_pass_admission_audit"
SPLITS = [
    "agentkernel_lite_encdec_train.jsonl",
    "agentkernel_lite_encdec_validation.jsonl",
    "agentkernel_lite_encdec_strict_eval.jsonl",
    "agentkernel_lite_encdec_stress_eval.jsonl",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def package_ids_roots() -> tuple[set[str], set[str]]:
    ids, roots = set(), set()
    for split in SPLITS:
        for row in read_jsonl(CURRENT_PACKAGE_DIR / split):
            if row.get("row_id"):
                ids.add(str(row["row_id"]))
            if row.get("source_root_id"):
                roots.add(str(row["source_root_id"]))
    return ids, roots


def before_options(prompt: str) -> str:
    return prompt.split("Options:", 1)[0] if "Options:" in prompt else prompt


def target_value(row: dict[str, Any]) -> str:
    label = str(row.get("target_text") or "")
    for opt in row.get("opaque_options") or []:
        if str(opt.get("label") or "") == label:
            return str(opt.get("value") or "")
    return ""


def audit_row(row: dict[str, Any], existing_ids: set[str], existing_roots: set[str]) -> list[str]:
    blockers: list[str] = []
    row_id = str(row.get("row_id") or "")
    root_id = str(row.get("source_root_id") or "")
    prompt = str(row.get("input_text") or row.get("prompt_text") or "")
    options = list(row.get("opaque_options") or [])
    option_values = [str(opt.get("value") or "") for opt in options]
    labels = {str(opt.get("label") or "") for opt in options}
    anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    target = str(row.get("target_text") or "")
    tv = target_value(row)

    if not row_id:
        blockers.append("missing_row_id")
    if not root_id:
        blockers.append("missing_source_root_id")
    if row_id in existing_ids:
        blockers.append("row_id_overlap_existing_package")
    if root_id in existing_roots:
        blockers.append("source_root_overlap_existing_package")
    if row.get("task_type") != "verifier_outcome":
        blockers.append("wrong_task_type")
    if len(options) != 4:
        blockers.append("expected_four_options")
    if target not in labels:
        blockers.append("target_label_not_in_options")
    if not tv.startswith("T1 | FAIL_TO_PASS | selected verifier target"):
        blockers.append("target_value_not_selected_verifier_fail_to_pass")
    if not all(value.startswith("T") and "FAIL_TO_PASS" in value for value in option_values):
        blockers.append("not_all_options_fail_to_pass")
    if not anti_cheat.get("deterministic_option_shuffle"):
        blockers.append("missing_deterministic_option_shuffle")
    if not anti_cheat.get("all_options_same_transition"):
        blockers.append("missing_all_options_same_transition_flag")
    if not anti_cheat.get("historical_commit_plus_verify_not_runtime_execution"):
        blockers.append("missing_historical_not_runtime_caveat")
    if projection.get("git_show_stat_returncode") != 0:
        blockers.append("git_show_stat_not_successful")
    if "Verification targets from commit-plus-verify metadata:" not in prompt:
        blockers.append("missing_verification_targets_prompt")
    if "E1 commit stat:" not in prompt or "E2 selected verifier snippet" not in prompt:
        blockers.append("missing_commit_or_verifier_evidence")
    if re.search(rf"Answer:\s*{re.escape(target)}\b", before_options(prompt)):
        blockers.append("target_label_leak_before_options")
    return blockers


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(IN_ROWS)
    materialization = read_json(MATERIALIZATION_SUMMARY)
    existing_ids, existing_roots = package_ids_roots()
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        blockers = audit_row(row, existing_ids, existing_roots)
        if blockers:
            rejected.append({"row_id": row.get("row_id"), "source_root_id": row.get("source_root_id"), "blockers": blockers})
        else:
            admitted_row = dict(row)
            admitted_row["split_role"] = "train_support"
            admitted_row["review_status"] = "admitted_by_stage11167_ai_audit"
            admitted_row["admission_stage"] = 11167
            admitted.append(admitted_row)

    summary = {
        "stage": 11167,
        "stage_name": "external_commit_fail_to_pass_admission_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "review_rows": rel(IN_ROWS),
            "materialization_summary": rel(MATERIALIZATION_SUMMARY),
            "current_package_dir": rel(CURRENT_PACKAGE_DIR),
        },
        "metrics": {
            "input_rows": len(rows),
            "admitted_rows": len(admitted),
            "rejected_rows": len(rejected),
            "admitted_unique_roots": len({row.get("source_root_id") for row in admitted}),
            "admitted_repo_counts": dict(sorted(Counter(str(row.get("repo_id")) for row in admitted).items())),
            "admitted_target_labels": dict(sorted(Counter(str(row.get("target_text")) for row in admitted).items())),
        },
        "blockers": rejected,
        "decision": "admit_external_commit_rows_for_train_support" if admitted and not rejected else "partial_or_blocked_admission",
        "claim_scope": (
            "Admits external commit-backed FAIL_TO_PASS verifier-target rows for train support only. "
            "They use historical COMMIT_PLUS_VERIFY metadata, not fresh runtime execution."
        ),
        "materialization_metrics": materialization.get("metrics"),
        "outputs": {
            "admitted_rows_jsonl": rel(OUT_DIR / "admitted_external_commit_fail_to_pass_rows.jsonl"),
            "rejected_rows_jsonl": rel(OUT_DIR / "rejected_external_commit_fail_to_pass_rows.jsonl"),
            "summary_json": rel(OUT_DIR / "external_commit_fail_to_pass_admission_audit.json"),
        },
    }
    write_jsonl(OUT_DIR / "admitted_external_commit_fail_to_pass_rows.jsonl", admitted)
    write_jsonl(OUT_DIR / "rejected_external_commit_fail_to_pass_rows.jsonl", rejected)
    (OUT_DIR / "external_commit_fail_to_pass_admission_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
