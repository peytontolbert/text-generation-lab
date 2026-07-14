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
    / "runs/local/artifacts/stage11160_explicit_verifier_transition_competition_materialization/explicit_verifier_transition_review_rows.jsonl"
)
MATERIALIZATION_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage11160_explicit_verifier_transition_competition_materialization/explicit_verifier_transition_competition_materialization.json"
)
CURRENT_PACKAGE_DIR = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"
OUT_DIR = ROOT / "runs/local/artifacts/stage11161_explicit_verifier_transition_admission_audit"

SPLIT_FILES = [
    "agentkernel_lite_encdec_train.jsonl",
    "agentkernel_lite_encdec_validation.jsonl",
    "agentkernel_lite_encdec_strict_eval.jsonl",
    "agentkernel_lite_encdec_stress_eval.jsonl",
]
REQUIRED_TRANSITIONS = {
    "PASS_TO_PASS",
    "NOT_EXERCISED",
    "FAIL_TO_PASS",
    "INSUFFICIENT_EVIDENCE",
}


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


def package_ids_and_roots() -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    roots: set[str] = set()
    for name in SPLIT_FILES:
        for row in read_jsonl(CURRENT_PACKAGE_DIR / name):
            if row.get("row_id"):
                ids.add(str(row["row_id"]))
            if row.get("source_root_id"):
                roots.add(str(row["source_root_id"]))
    return ids, roots


def before_options_text(prompt: str) -> str:
    return prompt.split("Options:", 1)[0] if "Options:" in prompt else prompt


def option_transition_prefixes(row: dict[str, Any]) -> set[str]:
    prefixes = set()
    for opt in row.get("opaque_options") or []:
        value = str(opt.get("value") or "")
        prefixes.add(value.split("|", 1)[0].strip())
    return prefixes


def target_value_from_row(row: dict[str, Any]) -> str:
    target_label = str(row.get("target_text") or "")
    for opt in row.get("opaque_options") or []:
        if str(opt.get("label") or "") == target_label:
            return str(opt.get("value") or "")
    return ""


def audit_row(row: dict[str, Any], existing_ids: set[str], existing_roots: set[str]) -> list[str]:
    blockers: list[str] = []
    row_id = str(row.get("row_id") or "")
    root_id = str(row.get("source_root_id") or "")
    prompt = str(row.get("input_text") or row.get("prompt_text") or "")
    options = row.get("opaque_options") or []
    anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    target = str(row.get("target_text") or "")
    target_value = target_value_from_row(row)

    if not row_id:
        blockers.append("missing_row_id")
    if not root_id:
        blockers.append("missing_source_root_id")
    if row_id in existing_ids:
        blockers.append("row_id_overlap_existing_package")
    if root_id in existing_roots:
        blockers.append("source_root_overlap_existing_package")
    if row.get("task_type") != "verifier_outcome_semantic_transition":
        blockers.append("wrong_task_type")
    if len(options) != 4:
        blockers.append("expected_four_transition_options")
    if option_transition_prefixes(row) != REQUIRED_TRANSITIONS:
        blockers.append("missing_required_transition_option")
    if not target or target not in {str(opt.get("label") or "") for opt in options}:
        blockers.append("target_label_not_in_options")
    if not target_value.startswith(str(row.get("semantic_target_value") or "")):
        blockers.append("semantic_target_value_mismatch")
    if not anti_cheat.get("deterministic_option_shuffle"):
        blockers.append("missing_deterministic_option_shuffle")
    if not anti_cheat.get("explicit_transition_options"):
        blockers.append("missing_explicit_transition_options")
    if not anti_cheat.get("focused_verifier_target"):
        blockers.append("missing_focused_verifier_target")
    if not anti_cheat.get("pytest_results_visible"):
        blockers.append("missing_pytest_results_visible_flag")
    if "Focused verifier target:" not in prompt:
        blockers.append("missing_focused_verifier_target_text")
    if "E4 direct verifier result:" not in prompt or "E5 neighboring verifier result:" not in prompt:
        blockers.append("missing_verifier_command_results")
    if "Options:" not in prompt:
        blockers.append("missing_options_section")
    if re.search(rf"Answer:\s*{re.escape(target)}\b", before_options_text(prompt)):
        blockers.append("target_label_leaks_before_options")
    if not projection.get("direct_result", {}).get("passed"):
        blockers.append("direct_pytest_not_passing")
    if not projection.get("distractor_result", {}).get("passed"):
        blockers.append("distractor_pytest_not_passing")
    return blockers


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(IN_ROWS)
    materialization = read_json(MATERIALIZATION_SUMMARY)
    existing_ids, existing_roots = package_ids_and_roots()
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for row in rows:
        blockers = audit_row(row, existing_ids, existing_roots)
        if blockers:
            rejected.append({"row_id": row.get("row_id"), "source_root_id": row.get("source_root_id"), "blockers": blockers})
        else:
            admitted_row = dict(row)
            admitted_row["split_role"] = "train_support"
            admitted_row["review_status"] = "admitted_by_stage11161_ai_audit"
            admitted_row["admission_stage"] = 11161
            admitted.append(admitted_row)

    summary = {
        "stage": 11161,
        "stage_name": "explicit_verifier_transition_admission_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "review_rows": str(IN_ROWS.relative_to(ROOT)),
            "materialization_summary": str(MATERIALIZATION_SUMMARY.relative_to(ROOT)),
            "current_package_dir": str(CURRENT_PACKAGE_DIR.relative_to(ROOT)),
        },
        "metrics": {
            "input_rows": len(rows),
            "admitted_rows": len(admitted),
            "rejected_rows": len(rejected),
            "admitted_unique_roots": len({row.get("source_root_id") for row in admitted}),
            "admitted_semantic_targets": dict(sorted(Counter(str(row.get("semantic_target_value")) for row in admitted).items())),
            "admitted_target_labels": dict(sorted(Counter(str(row.get("target_text")) for row in admitted).items())),
        },
        "blockers": rejected,
        "decision": "admit_explicit_transition_rows_for_train_support" if admitted and not rejected else "partial_or_blocked_admission",
        "claim_scope": (
            "Admits local source-backed explicit verifier-transition rows for train support only. "
            "These rows are not strict heldout and do not prove frontier improvement by themselves."
        ),
        "materialization_metrics": materialization.get("metrics"),
        "outputs": {
            "admitted_rows_jsonl": str((OUT_DIR / "admitted_explicit_verifier_transition_rows.jsonl").relative_to(ROOT)),
            "rejected_rows_jsonl": str((OUT_DIR / "rejected_explicit_verifier_transition_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "explicit_verifier_transition_admission_audit.json").relative_to(ROOT)),
        },
    }
    write_jsonl(OUT_DIR / "admitted_explicit_verifier_transition_rows.jsonl", admitted)
    write_jsonl(OUT_DIR / "rejected_explicit_verifier_transition_rows.jsonl", rejected)
    (OUT_DIR / "explicit_verifier_transition_admission_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
