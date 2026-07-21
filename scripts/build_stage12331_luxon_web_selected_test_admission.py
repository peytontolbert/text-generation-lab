#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12331_luxon_web_selected_test_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE = ROOT / "runs/local/artifacts/stage12145_web_hydrated_selected_test_success_package/web_hydrated_selected_test_results.jsonl"
CHECKOUT = Path("/data/tmp/stage12128b_rust_web_smoke_repos/stage12118__web_js_ts_html__024__moment_luxon")
ROOT_ID = "stage12118::web_js_ts_html::024::moment_luxon"
REPO = "moment/luxon"
LANG = "web_js_ts_html"
TASK_FAMILIES = [
    "transition_candidate_selection",
    "transition_continue_or_stop",
    "transition_evidence_citation",
    "transition_next_action",
    "transition_verifier_transition",
]
LABELS_BY_TASK = {
    "transition_candidate_selection": ["T5", "X8", "Z4"],
    "transition_continue_or_stop": ["A7", "K3", "M9"],
    "transition_evidence_citation": ["B2", "F6", "H1"],
    "transition_next_action": ["C4", "N8", "R2"],
    "transition_verifier_transition": ["D3", "Q7", "S5"],
}
TARGET_INDEX_BY_TASK = {
    "transition_candidate_selection": 1,
    "transition_continue_or_stop": 2,
    "transition_evidence_citation": 1,
    "transition_next_action": 0,
    "transition_verifier_transition": 2,
}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(CHECKOUT)).replace("\\", "/")


def collect_hashes() -> tuple[list[str], list[str], list[str]]:
    source_candidates = [
        "src/datetime.js",
        "src/duration.js",
        "src/info.js",
        "src/settings.js",
        "src/impl/util.js",
        "src/impl/locale.js",
        "src/zones/IANAZone.js",
        "src/errors.js",
    ]
    config_candidates = ["package.json", "babel.config.js", "jest.config.js", "test/setupTests.js"]
    test_candidates = ["test/datetime/create.test.js", "test/helpers.js"]
    source_refs = []
    for item in source_candidates[:6]:
        path = CHECKOUT / item
        if path.exists() and "node_modules" not in item:
            source_refs.append(f"{item}@{sha_file(path)[:12]}")
    config_refs = []
    for item in config_candidates:
        path = CHECKOUT / item
        if path.exists() and "node_modules" not in item:
            config_refs.append(f"{item}@{sha_file(path)[:12]}")
    test_refs = []
    for item in test_candidates:
        path = CHECKOUT / item
        if path.exists() and "node_modules" not in item:
            test_refs.append(f"{item}@{sha_file(path)}")
    return source_refs, config_refs, test_refs


def load_luxon_record() -> dict[str, Any]:
    for row in read_jsonl(SOURCE):
        if row.get("queue_id") == ROOT_ID:
            return row
    return {}


def make_options(task: str) -> tuple[list[dict[str, Any]], str]:
    labels = LABELS_BY_TASK[task]
    target_index = TARGET_INDEX_BY_TASK[task]
    values = [
        "same_repo_unselected_web_surface_candidate [candidate_1; same_repo_decoy_requires_renderer_materialization]",
        "selected_test_backed_verifier_candidate [candidate_0; source_and_selected_test_evidence_only]",
        "abstain_or_insufficient_evidence_control [candidate_2; control_option_requires_renderer_materialization]",
    ]
    # Rotate values by task to avoid a single position prior while keeping deterministic opaque labels.
    rotation = list(range(3))
    if task == "transition_continue_or_stop":
        rotation = [1, 2, 0]
    elif task == "transition_evidence_citation":
        rotation = [2, 1, 0]
    elif task == "transition_next_action":
        rotation = [1, 0, 2]
    elif task == "transition_verifier_transition":
        rotation = [2, 0, 1]
    opts = []
    target_label = ""
    for pos, value_index in enumerate(rotation):
        label = labels[pos]
        semantic_id = ["candidate_1", "candidate_0", "candidate_2"][value_index]
        opts.append({
            "deterministic_position": pos,
            "label": label,
            "semantic_id": semantic_id,
            "value": values[value_index],
        })
        if semantic_id == "candidate_0":
            target_label = label
    return opts, target_label


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    record = load_luxon_record()
    blockers = []
    if not record:
        blockers.append("missing_stage12145_luxon_record")
    if not CHECKOUT.exists():
        blockers.append("missing_luxon_checkout")
    visible = record.get("visible_source_files") or []
    if any("node_modules" in path for path in visible):
        # This is allowed only if cleaned visible evidence excludes the dependency path.
        visible_cleanup_required = True
    else:
        visible_cleanup_required = False
    source_refs, config_refs, test_refs = collect_hashes()
    if not source_refs:
        blockers.append("source_hash_refs_missing")
    if not test_refs:
        blockers.append("test_hash_refs_missing")
    if not record.get("selected_test_command") or int(record.get("exit_code") if record.get("exit_code") is not None else -1) != 0:
        blockers.append("selected_test_command_or_success_missing")
    if visible_cleanup_required and any("node_modules" in ref for ref in source_refs + config_refs + test_refs):
        blockers.append("dependency_path_leaked_after_cleanup")
    commit = ""
    head_file = CHECKOUT / ".git" / "HEAD"
    if head_file.exists():
        import subprocess
        commit = subprocess.check_output(["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], text=True).strip()
    if not commit:
        blockers.append("commit_sha_missing")

    rows = []
    blocked = []
    evidence_refs = [
        "stage12145_web_hydrated_selected_test_success_package::moment_luxon::selected_test_success_record",
        "runs/local/artifacts/stage12145_web_hydrated_selected_test_success_package/web_hydrated_selected_test_results.jsonl",
    ] + [f"source_hash::{ref}" for ref in source_refs[:6]] + [f"test_hash::{ref}" for ref in test_refs[:2]]
    selected = record.get("selected_test_ids") or ["test/datetime/create.test.js"]
    selected_summary = f"{record.get('selected_test_count', 0)} selected tests in focused file; selected scope: {', '.join(selected[:2])}"
    source_summary = ", ".join(source_refs[:6])
    config_summary = ", ".join(config_refs[:4])
    for task in TASK_FAMILIES:
        options, target_label = make_options(task)
        row_blockers = list(blockers)
        input_text = (
            f"Task family: {task.replace('transition_', '')}\n"
            f"Repository: {REPO}\n"
            f"Language: {LANG}\n"
            f"Commit: {commit}\n"
            f"Selected-test evidence: {selected_summary}\n"
            f"Verifier command class: npm/jest focused file; exit_code=0; result summary: {record.get('result_summary')}\n"
            f"Source hash summary: {source_summary}\n"
            f"Config/test hash summary: {config_summary}\n"
            f"Evidence ledger refs: {json.dumps(evidence_refs[:10], sort_keys=True)}\n"
            "Choose the single option whose internally-audited evidence role is best supported by the compact verifier/source/test record. "
            "Use only the opaque labels below; do not infer from label names.\n"
            "Options:\n" + "\n".join(f"- {opt['label']}: Option {opt['label']}" for opt in options) + "\nAnswer:"
        )
        row = {
            "stage": STAGE,
            "record_type": "web_selected_test_train_support_row",
            "row_id": f"stage12331::{ROOT_ID}::{task}",
            "root_id": ROOT_ID,
            "repo_family": REPO,
            "language_family": LANG,
            "task_family": task,
            "input_text": input_text,
            "opaque_options": options,
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "loss_mask": {
                "decoder_ce": True,
                "bounded_choice_aux": True,
                "structured_aux": True,
                "transition_projection": True,
            },
            "source_refs": {
                "commit_sha": commit,
                "root_lineage_key": f"stage12331::{REPO.replace('/', '__')}::{ROOT_ID}",
                "source_root_id": ROOT_ID,
                "selected_test_command_ref": "stage12145_web_hydrated_selected_test_success_package::selected_test_command_hash_only",
                "raw_source_emitted": False,
                "raw_verifier_log_emitted": False,
                "dependency_paths_excluded": True,
            },
            "admission": {
                "training_allowed": not row_blockers,
                "train_support_allowed": not row_blockers,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "reason": "web selected-test train-support only; no strict/source-heldout/Level-3/patch/repair claim",
            },
            "blocked_reasons": row_blockers,
        }
        (rows if not row_blockers else blocked).append(row)
    write_jsonl(OUT / "luxon_web_selected_test_train_support_rows.jsonl", rows)
    write_jsonl(OUT / "luxon_web_selected_test_blocked_rows.jsonl", blocked)
    summary = {
        "stage": STAGE,
        "decision": "luxon_web_selected_test_admission_complete" if rows else "luxon_web_selected_test_admission_blocked",
        "training_allowed": bool(rows),
        "claim_boundary": "Train-support-only web selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked),
        "root_id": ROOT_ID,
        "repo_family": REPO,
        "language_family": LANG,
        "visible_dependency_path_in_source_record": visible_cleanup_required,
        "dependency_paths_excluded_from_materialized_rows": True,
        "source_hash_ref_count": len(source_refs),
        "test_hash_ref_count": len(test_refs),
        "task_family_counts": dict(Counter(row.get("task_family") for row in rows)),
        "blocked_reason_counts": dict(Counter(reason for row in blocked for reason in row.get("blocked_reasons", []))),
    }
    (OUT / "luxon_web_selected_test_admission_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "LUXON_WEB_SELECTED_TEST_ADMISSION_STAGE12331.md").write_text(
        "# Stage12331 Luxon Web Selected-Test Admission\n\n"
        "Materializes Luxon web selected-test train-support rows only after excluding dependency paths from visible evidence.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
