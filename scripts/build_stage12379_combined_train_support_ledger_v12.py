#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12379_combined_train_support_ledger_v12"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
BASE_SCRIPT = ROOT / "scripts/build_stage12376_combined_train_support_ledger_v11.py"
BASE_SUMMARY = ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json"
BASE_ROWS = ROOT / "runs/local/artifacts/stage12376_combined_train_support_ledger_v11/combined_selected_test_rows_v11.jsonl"
WEB_RERENDER = ROOT / "runs/local/artifacts/stage12378_web_fallback_task_specific_selected_test_rerender/web_fallback_task_specific_selected_test_rows.jsonl"
SUPERSEDED_ROOTS = {
    "stage12351::web_js_ts_html::llama_stack_ui_format_message",
    "stage12351::web_js_ts_html::mcp_sep_automation_transition",
    "stage12351::web_js_ts_html::mcp_typescript_sdk_server",
}
NON_SELECTED_BASE_ROWS = 91
RISKY_FIELDS = ["strict_eval_eligible", "source_heldout_admissible", "level3_admitted", "patch_trace_admitted", "repair_claim_admitted"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_counts(rows: list[dict]) -> dict:
    counts: Counter[str] = Counter()
    for row in rows:
        admission = row.get("admission") or {}
        for field in RISKY_FIELDS:
            if admission.get(field) or row.get(field):
                counts[field] += 1
    return dict(counts)


def target_semantic(row: dict) -> str:
    if row.get("target_semantic_id"):
        return str(row["target_semantic_id"])
    target = row.get("bounded_choice_target_label")
    for option in row.get("opaque_options") or []:
        if option.get("label") == target:
            return str(option.get("semantic_id") or option.get("canonical_value") or option.get("value") or "")
    return ""


def main() -> None:
    subprocess.run(["python", str(BASE_SCRIPT)], cwd=str(ROOT), check=True)
    base = json.loads(BASE_SUMMARY.read_text(encoding="utf-8"))
    base_rows = read_jsonl(BASE_ROWS)
    web_rows = read_jsonl(WEB_RERENDER)
    superseded_rows = [row for row in base_rows if row.get("root_id") in SUPERSEDED_ROOTS]
    kept_base_rows = [row for row in base_rows if row.get("root_id") not in SUPERSEDED_ROOTS]
    selected_rows = kept_base_rows + web_rows

    language_counts: Counter[str] = Counter({"session_unknown_language": NON_SELECTED_BASE_ROWS})
    task_counts: Counter[str] = Counter({"event_local_transition_observation": NON_SELECTED_BASE_ROWS})
    semantic_by_root: dict[str, set[str]] = {}
    raw_command_rows = 0
    for row in selected_rows:
        language_counts[row.get("language_family") or "session_unknown_language"] += 1
        task_counts[row.get("task_family") or row.get("record_type") or "unknown"] += 1
        if row.get("stage") == "stage12378_web_fallback_task_specific_selected_test_rerender":
            semantic_by_root.setdefault(row.get("root_id") or row.get("row_id"), set()).add(target_semantic(row))
            text = row.get("input_text") or ""
            if "command=" in text or "Observed command" in text or "node_modules/.bin" in text or "vitest run" in text:
                raw_command_rows += 1

    anti_collapse_failures = {root: sorted(values) for root, values in semantic_by_root.items() if len(values) < 5}
    source_counts = dict(base.get("source_counts") or {})
    source_counts["stage12351_web_fallback_selected_test_superseded"] = 0
    source_counts["stage12378_web_fallback_task_specific_rerender"] = len(web_rows)
    total = NON_SELECTED_BASE_ROWS + len(selected_rows)
    ledger = dict(base)
    ledger.update({
        "stage": STAGE,
        "decision": "combined_train_support_ledger_v12_ready_500_not_reached" if not anti_collapse_failures and not risky_counts(selected_rows) and raw_command_rows == 0 else "combined_train_support_ledger_v12_needs_review",
        "training_allowed": False,
        "claim_boundary": "Authoritative current ledger. Training remains blocked until 500-row target and QC gates are met; row-local admission is not global training clearance.",
        "supersedes": [
            str(BASE_SUMMARY),
            str(ROOT / "runs/summaries/stage12378_web_fallback_task_specific_selected_test_rerender.json"),
        ],
        "current_admitted_train_support_tasks": total,
        "remaining_gap_to_500": max(0, 500 - total),
        "non_selected_base_rows": NON_SELECTED_BASE_ROWS,
        "selected_test_rows_admitted_after_audit": len(selected_rows),
        "selected_test_rows_superseded_from_v11": len(superseded_rows),
        "superseded_roots": sorted(SUPERSEDED_ROOTS),
        "source_counts": source_counts,
        "language_counts": dict(language_counts),
        "task_family_or_record_type_counts": dict(task_counts),
        "risky_claim_counts_should_be_zero": risky_counts(selected_rows),
        "stage12378_target_semantic_values_by_root": {root: sorted(values) for root, values in semantic_by_root.items()},
        "stage12378_raw_command_rows_should_be_zero": raw_command_rows,
        "anti_collapse_failures_should_be_empty": anti_collapse_failures,
        "training_blockers": [
            "500_train_support_target_not_reached",
            "einops/web_higher_risk_re_render_pending",
            "Open-SWE/MCP transformation rows not yet admitted under Stage12364 policy beyond transformed train-support",
        ],
    })
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "combined_selected_test_rows_v12.jsonl", selected_rows)
    write_jsonl(OUT / "superseded_selected_test_rows_v12.jsonl", superseded_rows)
    (OUT / "combined_train_support_ledger_v12.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
