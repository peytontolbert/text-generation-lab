#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12330_selected_test_language_balance_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
ROLLUP = ROOT / "runs/local/artifacts/stage12146_selected_test_supply_rollup/selected_test_supply_rollup.jsonl"
LEDGER = ROOT / "runs/summaries/stage12324_combined_train_support_ledger.json"
ATLAS = ROOT / "runs/summaries/stage12329_stratified_source_adapter_atlas.json"
WEB_QUEUE = ROOT / "runs/summaries/stage11529_web_materialization_queue.json"
WEB_RUNTIME = ROOT / "runs/summaries/stage11399_disjoint_web_runtime_feasibility_and_queue.json"

ALREADY_ADMITTED_ROOTS = {
    "stage12118::c_cpp::002::Neargye_magic_enum",
    "stage12118::c_cpp::019::fastfloat_fast_float",
    "stage12118::python::016::pallets_click",
    "stage12118::python::018::pallets_jinja",
    "stage12118::python::034::pytest_dev_pluggy",
    "stage12143__python__PyCQA_flake8",
    "stage12118::rust::010::assert_rs_predicates_rs",
    "stage12118::rust::017::dtolnay_anyhow",
    "stage12118::rust::044::toml_rs_toml",
}

TASK_FAMILIES = [
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def blockers(record: dict[str, Any]) -> list[str]:
    out = []
    if record.get("root_id") in ALREADY_ADMITTED_ROOTS:
        out.append("already_admitted_in_stage12322_or_stage12326")
    if record.get("status") != "ready_for_row_materialization":
        out.append("not_ready_for_row_materialization")
    if record.get("strict_eval_eligible") is True:
        out.append("unexpected_strict_eval_claim")
    if record.get("train_support_only") is not True:
        out.append("not_train_support_only")
    if not record.get("selected_tests"):
        out.append("selected_tests_missing")
    if record.get("language_family") == "web_js_ts_html":
        # Stage12145 noted dependency material in visible_source_files; require a cleanup pass before row admission.
        if record.get("repo_family") == "moment/luxon":
            out.append("requires_visible_source_cleanup_remove_dependency_paths")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = load(LEDGER)
    atlas = load(ATLAS)
    web_queue = load(WEB_QUEUE)
    web_runtime = load(WEB_RUNTIME)
    records = read_jsonl(ROLLUP)
    queued = []
    blocked = []
    for record in records:
        block = blockers(record)
        item = {
            "stage": STAGE,
            "record_type": "selected_test_language_balance_queue_item",
            "root_id": record.get("root_id"),
            "repo_family": record.get("repo_family"),
            "language_family": record.get("language_family"),
            "source_stage": record.get("source_stage"),
            "selected_test_count": record.get("selected_test_count") or len(record.get("selected_tests") or []),
            "selected_test_hash_count": len(record.get("selected_tests") or []),
            "proposed_row_count": len(TASK_FAMILIES),
            "proposed_task_families": TASK_FAMILIES,
            "admission_boundary": {
                "candidate_only": True,
                "training_allowed": False,
                "train_support_admitted": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "repair_claim_admitted": False,
            },
            "blocked_reasons": block,
            "next_required_action": "materialize with source/test hash capture, dependency-source cleanup, anti-cheat rendering, and lineage audit" if not block or block == ["requires_visible_source_cleanup_remove_dependency_paths"] else "do_not_materialize_until_blockers_cleared",
        }
        if not block or block == ["requires_visible_source_cleanup_remove_dependency_paths"]:
            queued.append(item)
        else:
            blocked.append(item)


    web_hydration_queue = []
    for item in web_queue.get("work_items") or []:
        priority = int(item.get("priority") or 99)
        if priority > 2:
            continue
        materialization_blockers = list(item.get("materialization_blockers") or [])
        runtime_blockers = []
        for runtime_item in web_runtime.get("runtime_blockers") or []:
            if runtime_item.get("repo_family") == item.get("git_repo_family"):
                runtime_blockers.append(runtime_item.get("blocker") or runtime_item.get("status"))
        web_hydration_queue.append({
            "stage": STAGE,
            "record_type": "web_selected_test_hydration_candidate",
            "review_item_id": item.get("review_item_id"),
            "repo_family": item.get("git_repo_family"),
            "subrepo_family": item.get("repo_family"),
            "repo_path": item.get("repo_path"),
            "language_family": "web_js_ts_html",
            "priority": priority,
            "recommended_split": item.get("recommended_split"),
            "candidate_change_surface_count": len(item.get("candidate_change_surface_paths") or []),
            "verifier_path_count": len(item.get("verifier_and_test_constraint_paths") or []),
            "expected_rows_if_hydrated": len(TASK_FAMILIES),
            "training_allowed": False,
            "train_support_admitted": False,
            "blocked_reasons": sorted(set(materialization_blockers + runtime_blockers)),
            "next_required_action": "execute_or_recover_focused_verifier_output_then_fill_stage12322_style_anti_cheat_contract",
        })
    write_jsonl(OUT / "web_selected_test_hydration_queue.jsonl", web_hydration_queue)

    write_jsonl(OUT / "selected_test_language_balance_queue.jsonl", queued)
    write_jsonl(OUT / "selected_test_language_balance_blocked.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "selected_test_language_balance_queue_ready_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Queue/control artifact only. No rows admitted. Web Luxon requires visible-source cleanup before row materialization.",
        "current_train_support_ledger": {
            "admitted_train_support": (atlas.get("current_ledger") or {}).get("admitted_train_support") or 136,
            "language_counts": ledger.get("language_counts", {}),
            "source_counts": ledger.get("source_counts", {}),
        },
        "queued_candidates": len(queued),
        "queued_proposed_rows": sum(int(row.get("proposed_row_count") or 0) for row in queued),
        "web_hydration_candidates": len(web_hydration_queue),
        "web_hydration_expected_rows_if_all_pass": sum(int(row.get("expected_rows_if_hydrated") or 0) for row in web_hydration_queue),
        "blocked_records": len(blocked),
        "queued_language_counts": dict(Counter(row.get("language_family") or "unknown" for row in queued)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
        "language_balance_gap": {
            "web_js_ts_html": "critical: only one queued web selected-test root and zero admitted web rows in Stage12324 ledger",
            "c_cpp": "thin but current selected-test roots already admitted; need new hydration roots",
            "rust": "thin but current ready selected-test roots already admitted; need stage12315 hydration worklist follow-through",
            "session_unknown_language": "must not grow; needs attribution or cap enforcement",
        },
        "next_recommended_stage": "stage12331_web_selected_test_materialization_or_stage12332_repair_hydration_probe",
    }
    (OUT / "selected_test_language_balance_queue_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "SELECTED_TEST_LANGUAGE_BALANCE_QUEUE_STAGE12330.md").write_text(
        "# Stage12330 Selected-Test Language Balance Queue\n\n"
        "This queue identifies remaining selected-test materialization candidates after Stage12322/12326. It admits zero rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
