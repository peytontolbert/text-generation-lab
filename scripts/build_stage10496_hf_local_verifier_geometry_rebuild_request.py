#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10496
NAME = "stage10496_hf_local_verifier_geometry_rebuild_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "hf_local_verifier_geometry_rebuild_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE10493 = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"
STAGE10495 = ROOT / "runs/local/artifacts/stage10495_context_pack_only_promotable_python_probe_audit/context_pack_only_promotable_python_probe_audit.json"
HF_LOCAL_GOLD = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/perspective_gold_adjudication.json"
HF_LOCAL_ANTICHEAT = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/anti_cheat_review_card.json"
HF_LOCAL_ROWS = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"

HF_LOCAL_BUNDLE_ID = (
    "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    stage10493 = load_json(STAGE10493)
    stage10495 = load_json(STAGE10495)
    gold = load_json(HF_LOCAL_GOLD)
    anti_cheat = load_json(HF_LOCAL_ANTICHEAT)
    support_rows = [
        row
        for row in load_jsonl(HF_LOCAL_ROWS)
        if str(row.get("source_bundle_id")) == HF_LOCAL_BUNDLE_ID
    ]

    verifier_entry = next(
        entry for entry in gold["perspective_gold_answers"]
        if entry["perspective"] == "verifier_outcome"
    )
    support_task_counts: dict[str, int] = {}
    for row in support_rows:
        task = str(row.get("task_type") or "unknown")
        support_task_counts[task] = support_task_counts.get(task, 0) + 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "hf_local_verifier_geometry_rebuild_required",
        "claim_scope": [
            "Define the next Python reviewed-root rebuild needed after stage10495 preserved the 22/24 frontier without moving the verifier residual.",
            "Upgrade hf_local from a singleton verifier packet into a true verifier-target disambiguation packet that can legitimately test the missing Python skill.",
        ],
        "plateau_evidence": {
            "stage10495_accuracy": stage10495["accuracy"]["probe"],
            "stage10495_delta": stage10495["accuracy"]["delta"],
            "python_residual_fixed": stage10495["python_residual"]["fixed"],
            "python_residual_probe_label": stage10495["python_residual"]["probe_label"],
            "python_residual_target": stage10495["python_residual"]["probe_target"],
            "python_residual_target_rank_full_vocab": stage10495["python_residual"]["probe_target_rank_full_vocab"],
        },
        "current_hf_local_status": {
            "bundle_id": HF_LOCAL_BUNDLE_ID,
            "reviewed_selected_tests_count": len(verifier_entry["selected_tests"]),
            "reviewed_selected_tests": verifier_entry["selected_tests"],
            "support_row_count": len(support_rows),
            "support_task_counts": dict(sorted(support_task_counts.items())),
            "current_verifier_options_are_singleton": len(verifier_entry["selected_tests"]) == 1,
            "anti_cheat_caution": anti_cheat["decision_rationale"],
        },
        "why_rebuild_is_required": [
            "The current reviewed verifier row has only one selected test, so it cannot teach or evaluate verifier-target disambiguation among close sibling tests.",
            "The anti-cheat review still notes lexical shortcut risk because the verifier imports HFLocalAgent by name.",
            "Stage10493 showed hf_local does not satisfy the stage10492 queue contract of three or more plausible verifier targets.",
            "Stage10495 showed that cleaner reuse of context_pack alone is insufficient to move the Python verifier residual.",
        ],
        "rebuild_requirements": {
            "minimum_visible_verifier_targets": 3,
            "must_include": [
                "at least one wrong but plausible sibling test target",
                "a selected-test anchor that does not reveal the answer by name alone",
                "visible evidence that distinguishes the gold verifier target from the tempting sibling targets",
                "candidate options with deterministic permutation balancing",
                "prompt-target leak audit before any train or strict execution use",
            ],
            "must_reduce_shortcuts": [
                "remove or weaken direct HFLocalAgent-name leakage in the verifier evidence where possible",
                "avoid singleton verifier options",
                "ensure candidate order is non-semantic",
                "require the verifier choice to depend on evidence, not only on the imported symbol name",
            ],
            "acceptable_evidence_sources": [
                "multiple selected unit or integration tests around hf_local parameter handling",
                "neighboring config and orchestrator tests that stay plausible but wrong",
                "wiring snippets that preserve competition between hf_local.py and nearby config/orchestrator surfaces",
            ],
            "promotion_boundary": [
                "The rebuilt hf_local packet may become promotable Python support only after full review, anti-cheat pass, and bounded executable row materialization.",
                "Do not use the current singleton hf_local verifier row as evidence that the Python verifier residual has been adequately trained.",
            ],
        },
        "anti_cheat_gates": {
            "existing_review_flags": anti_cheat["challenge_families"],
            "new_required_checks": [
                "verifier_target_count_gte_3",
                "no_singleton_selected_test_packet",
                "prompt_target_leak_false",
                "candidate_order_balance_verified",
                "symbol_name_only_baseline_does_not_solve",
            ],
        },
        "source_artifacts": {
            "stage10493_packet_audit": display(STAGE10493),
            "stage10495_probe_audit": display(STAGE10495),
            "hf_local_gold": display(HF_LOCAL_GOLD),
            "hf_local_anti_cheat": display(HF_LOCAL_ANTICHEAT),
            "hf_local_support_rows": display(HF_LOCAL_ROWS),
        },
        "recommended_next_stage": "stage10497_hf_local_multitest_verifier_packet_builder",
        "follow_on_after_hf_local": [
            "materialize and adjudicate the queued agentkernel Python root so the Python lane is not dependent on one code_assist family only",
            "keep Rust on its separate fresh non-tokenizers citation rebuild path rather than mixing it into Python support claims",
            "rerun the multilingual repaired v2.7 strict overlay only after the rebuilt hf_local packet passes anti-cheat and bounded-row execution gates",
        ],
    }

    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
