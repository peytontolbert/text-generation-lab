#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12417_combined_train_support_ledger_v16"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12385_LEDGER = ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_train_support_ledger_v15_dedup.json"
STAGE12385_ROWS = ROOT / "runs/local/artifacts/stage12385_combined_train_support_ledger_v15_dedup/combined_selected_test_rows_v15_dedup.jsonl"
STAGE12416_MANIFEST = ROOT / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/direct_verifier_log_train_support_manifest.json"
STAGE12416_ROWS = ROOT / "runs/local/artifacts/stage12416_direct_verifier_log_train_support_canonicalizer/direct_verifier_log_train_support_rows.jsonl"

NON_SELECTED_BASE_ROWS = 91
TARGET_TRAIN_SUPPORT_TASKS = 500

RISKY_FIELDS = [
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "fail_to_pass_claim_admitted",
    "level4_admitted",
]

RAW_COMMAND_PATTERNS = [
    "command=",
    "Observed command",
    "node_modules/.bin",
    "vitest run",
    "pytest ",
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
COMMANDISH_RE = re.compile(r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git)\b.+\s(-m|-q|test|run|checkout|diff)\b", re.I)
DIFF_RE = re.compile(r"(^|\n)(diff --git|@@ |\+{3} |--- )")
RAW_KEY_RE = re.compile(r"^(command|cmd|argv|cwd|stdout|stderr|stdout_tail|stderr_tail|output|path|url|diff|source_text|content)$", re.I)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} did not contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_no} did not contain a JSON object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def target_semantic_value(row: dict[str, Any]) -> str:
    if row.get("target_semantic_value"):
        return str(row["target_semantic_value"])
    for option in row.get("opaque_options") or []:
        if not isinstance(option, dict):
            continue
        if option.get("label") == row.get("bounded_choice_target_label"):
            return str(option.get("semantic_id") or option.get("value") or "")
    return str(row.get("target_semantic_id") or "")


def task_projection(row: dict[str, Any]) -> str:
    return str(row.get("task_projection") or row.get("task_family") or row.get("record_type") or "")


def dedupe_keys(row: dict[str, Any]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    if row.get("row_id"):
        keys.append(("row_id", str(row["row_id"])))
    if row.get("source_key_audit_hash"):
        keys.append(("source_key_audit_hash", str(row["source_key_audit_hash"])))
    root_hash = row.get("root_lineage_key_hash")
    projection = task_projection(row)
    target = target_semantic_value(row)
    if root_hash and projection and target:
        keys.append(("root_projection_target", f"{root_hash}::{projection}::{target}"))
    return keys


def dedupe(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: dict[tuple[str, str], str] = {}
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        matches = [key for key in dedupe_keys(row) if key in seen]
        if matches:
            dup = dict(row)
            dup["duplicate_reasons"] = [
                {"dedupe_key_type": key_type, "dedupe_key": key_value, "first_row_id": seen[(key_type, key_value)]}
                for key_type, key_value in matches
            ]
            duplicates.append(dup)
            continue
        kept.append(row)
        row_id = str(row.get("row_id") or f"row_index_{len(kept) - 1}")
        for key in dedupe_keys(row):
            seen[key] = row_id
    return kept, duplicates


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    return False


def risky_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
        for field in RISKY_FIELDS:
            if truthy(row.get(field)) or truthy(admission.get(field)):
                counts[field] += 1
    return dict(sorted(counts.items()))


def raw_command_rows(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if any(pattern in (row.get("input_text") or "") for pattern in RAW_COMMAND_PATTERNS))


def generic_non_candidate_targets(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        target = str(row.get("target_semantic_id") or target_semantic_value(row))
        if task_projection(row) != "transition_candidate_selection" and (
            "candidate_0" in target or "candidate_selected_test_backed" in target
        ):
            count += 1
    return count


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from iter_strings(child_value, str(child_key))
    elif isinstance(value, list):
        for child_value in value:
            yield from iter_strings(child_value, key)
    elif isinstance(value, str):
        yield key, value


def raw_leak_overclaim_guardrail(rows: list[dict[str, Any]], ledger: dict[str, Any]) -> dict[str, Any]:
    raw_findings = []
    overclaim_findings = []
    # Stage12385 rows are already authoritative; the new guardrail is for v16
    # metadata plus newly admitted Stage12416 rows, while overclaim checks stay
    # global across the full combined ledger.
    new_rows = [row for row in rows if row.get("stage") == "stage12416_direct_verifier_log_train_support_canonicalizer"]
    for obj in [ledger, new_rows]:
        for key, text in iter_strings(obj):
            if RAW_KEY_RE.search(key):
                raw_findings.append({"kind": "raw_key", "key": key})
            elif ABS_PATH_RE.search(text) or URL_RE.search(text) or COMMANDISH_RE.search(text) or DIFF_RE.search(text):
                raw_findings.append({"kind": "raw_value", "key": key})
    for row in rows:
        admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
        if truthy(row.get("strict_eval_eligible")) or truthy(admission.get("strict_eval_eligible")):
            overclaim_findings.append({"kind": "strict_eval_eligible_true", "row_id": row.get("row_id")})
        if truthy(row.get("source_heldout_admissible")) or truthy(admission.get("source_heldout_admissible")):
            overclaim_findings.append({"kind": "source_heldout_admissible_true", "row_id": row.get("row_id")})
        for field in ("patch_trace_admitted", "repair_claim_admitted", "fail_to_pass_claim_admitted", "level3_admitted", "level4_admitted"):
            if truthy(row.get(field)) or truthy(admission.get(field)):
                overclaim_findings.append({"kind": f"{field}_positive", "row_id": row.get("row_id")})
    return {
        "scan_passed": not raw_findings and not overclaim_findings,
        "raw_leak_count": len(raw_findings),
        "overclaim_count": len(overclaim_findings),
        "raw_findings": raw_findings[:20],
        "overclaim_findings": overclaim_findings[:20],
    }


def count_by(rows: list[dict[str, Any]], field: str, fallback: str = "unknown") -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or fallback) for row in rows).items()))


def main() -> None:
    stage12385_ledger = read_json(STAGE12385_LEDGER)
    stage12416_manifest = read_json(STAGE12416_MANIFEST)
    source_rows = read_jsonl(STAGE12385_ROWS)
    delta_rows = read_jsonl(STAGE12416_ROWS)
    input_rows = source_rows + delta_rows
    combined_rows, duplicates = dedupe(input_rows)

    selected_test_rows = len(combined_rows)
    total = NON_SELECTED_BASE_ROWS + selected_test_rows
    risky = risky_counts(combined_rows)
    raw_command_count = raw_command_rows(combined_rows)
    generic_count = generic_non_candidate_targets(combined_rows)

    duplicate_reason_counts: Counter[str] = Counter()
    duplicate_key_type_counts: Counter[str] = Counter()
    for row in duplicates:
        for reason in row.get("duplicate_reasons") or []:
            if isinstance(reason, dict):
                duplicate_key_type_counts[str(reason.get("dedupe_key_type") or "unknown")] += 1
                duplicate_reason_counts[str(reason.get("dedupe_key") or "unknown")] += 1

    language_counts = Counter({"session_unknown_language": NON_SELECTED_BASE_ROWS})
    language_counts.update(str(row.get("language_family") or "unknown") for row in combined_rows)
    projection_counts = Counter(task_projection(row) for row in combined_rows)
    task_family_counts = Counter({"event_local_transition_observation": NON_SELECTED_BASE_ROWS})
    task_family_counts.update(task_projection(row) for row in combined_rows)
    source_counts = Counter(str(row.get("stage") or row.get("source_stage") or "unknown") for row in combined_rows)
    target_counts = Counter(target_semantic_value(row) or "unknown" for row in combined_rows)

    ledger = dict(stage12385_ledger)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v16_ready_500_not_reached",
        "claim_boundary": (
            "Authoritative v16 ledger merging Stage12385 and Stage12416 train-support rows. "
            "Training remains blocked until the 500-row target is met; no strict eval, source-heldout, "
            "repair, patch-trace, level3, or fail-to-pass claims are newly admitted."
        ),
        "supersedes": [
            str(STAGE12385_LEDGER.relative_to(ROOT)),
            str(STAGE12416_MANIFEST.relative_to(ROOT)),
        ],
        "training_allowed": False,
        "training_blockers": [
            "500_train_support_target_not_reached",
            "Open-SWE transformation rows not yet admitted under Stage12364 policy",
        ],
        "non_selected_base_rows": NON_SELECTED_BASE_ROWS,
        "stage12385_selected_test_rows_input": len(source_rows),
        "stage12416_direct_verifier_log_rows_input": len(delta_rows),
        "combined_rows_input": len(input_rows),
        "combined_selected_test_rows_admitted_after_audit": selected_test_rows,
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, TARGET_TRAIN_SUPPORT_TASKS - total),
        "target_train_support_tasks": TARGET_TRAIN_SUPPORT_TASKS,
        "duplicate_rows_removed_v16": len(duplicates),
        "duplicate_row_ids_should_be_zero": sum(1 for row in duplicates for reason in row.get("duplicate_reasons", []) if reason.get("dedupe_key_type") == "row_id"),
        "duplicate_row_id_counts": {},
        "stage12385_prior_duplicate_row_id_counts": dict(stage12385_ledger.get("duplicate_row_id_counts") or {}),
        "stage12385_prior_duplicate_rows_removed": int(stage12385_ledger.get("selected_test_duplicate_rows_removed") or 0),
        "duplicate_key_type_counts": dict(sorted(duplicate_key_type_counts.items())),
        "duplicate_key_counts": dict(sorted(duplicate_reason_counts.items())),
        "risky_claim_counts_should_be_zero": risky,
        "selected_test_raw_command_rows_should_be_zero": raw_command_count,
        "selected_test_generic_non_candidate_targets_should_be_zero": generic_count,
        "source_counts": dict(sorted(source_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "task_projection_counts": dict(sorted(projection_counts.items())),
        "task_family_or_record_type_counts": dict(sorted(task_family_counts.items())),
        "target_semantic_counts": dict(sorted(target_counts.items())),
        "stage12416_guardrail_scan_passed": bool(stage12416_manifest.get("guardrail_scan_passed")),
        "stage12416_raw_leak_count": int(stage12416_manifest.get("raw_leak_count") or 0),
        "stage12416_overclaim_count": int(stage12416_manifest.get("overclaim_count") or 0),
        "level3_admitted": risky.get("level3_admitted", 0),
        "patch_trace_admitted": risky.get("patch_trace_admitted", 0),
        "repair_claim_admitted": risky.get("repair_claim_admitted", 0),
        "fail_to_pass_claim_admitted": risky.get("fail_to_pass_claim_admitted", 0),
        "strict_eval_eligible": risky.get("strict_eval_eligible", 0),
        "source_heldout_admissible": risky.get("source_heldout_admissible", 0),
    })
    guardrail = raw_leak_overclaim_guardrail(combined_rows, ledger)
    ledger.update({
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "overclaim_count": guardrail["overclaim_count"],
        "artifact_names": {
            "combined_rows": "combined_train_support_rows_v16.jsonl",
            "duplicates": "duplicate_train_support_rows_v16.jsonl",
            "ledger": "combined_train_support_ledger_v16.json",
            "guardrail": "guardrail_scan.json",
        },
    })

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "combined_train_support_rows_v16.jsonl", combined_rows)
    write_jsonl(OUT / "duplicate_train_support_rows_v16.jsonl", duplicates)
    write_json(OUT / "combined_train_support_ledger_v16.json", ledger)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(SUMMARY, ledger)
    print(json.dumps(ledger, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
