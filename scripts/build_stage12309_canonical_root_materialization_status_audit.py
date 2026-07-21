#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12309_canonical_root_materialization_status_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12305 = ROOT / "runs/summaries/stage12305_canonical_root_candidate_materialization_queue.json"
S12306 = ROOT / "runs/summaries/stage12306_session_episode_graph_candidate_materializer.json"
S12307 = ROOT / "runs/summaries/stage12307_rust_cpp_selected_test_root_candidate_queue.json"
S12308 = ROOT / "runs/summaries/stage12308_h1_semantic_rule_feasibility_audit.json"
R12306 = ROOT / "runs/local/artifacts/stage12306_session_episode_graph_candidate_materializer/stage12306_session_episode_graph_candidate_materializer.jsonl"
R12307 = ROOT / "runs/local/artifacts/stage12307_rust_cpp_selected_test_root_candidate_queue/canonical_root_candidate_queue_records.jsonl"
R12308 = ROOT / "runs/local/artifacts/stage12308_h1_semantic_rule_feasibility_audit/h1_semantic_rule_feasibility_records.jsonl"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def candidate_action_shortcut_counts(rows: list[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for action in (row.get("candidate_action_set") or {}).get("actions", []):
            for field in ["position_role", "action_ref", "tool_pair_ref", "chosen", "gold", "correct", "target"]:
                if field in action:
                    counts[field] += 1
    return counts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s12305 = read_json(S12305)
    s12306 = read_json(S12306)
    s12307 = read_json(S12307)
    s12308 = read_json(S12308)
    r12306 = list(iter_jsonl(R12306) or [])
    r12307 = list(iter_jsonl(R12307) or [])
    r12308 = list(iter_jsonl(R12308) or [])

    shortcut_counts = candidate_action_shortcut_counts(r12306)
    stage12306_blockers = Counter()
    for row in r12306:
        stage12306_blockers.update(row.get("blocked_reasons") or [])
    stage12307_status = Counter(row.get("status_bucket") or row.get("readiness_status") or "unknown" for row in r12307)
    stage12307_languages = Counter(row.get("language_family") or "unknown" for row in r12307)
    stage12308_rejects = Counter()
    for row in r12308:
        stage12308_rejects.update(row.get("hard_reject_reasons") or [])

    summary = {
        "stage": STAGE,
        "decision": "canonical_root_materialization_candidates_ready_training_blocked",
        "claim_boundary": "Integration audit only. Candidate queues are useful but none are train/eval/claim admissible yet.",
        "training_allowed": False,
        "inputs": {
            "stage12305_decision": s12305.get("decision"),
            "stage12306_decision": s12306.get("decision"),
            "stage12307_decision": s12307.get("decision"),
            "stage12308_decision": s12308.get("decision"),
        },
        "candidate_counts": {
            "stage12306_episode_graph_candidates": len(r12306),
            "stage12307_rust_cpp_root_queue_records": len(r12307),
            "stage12308_h1_rule_feasibility_records": len(r12308),
            "total_candidate_records": len(r12306) + len(r12307) + len(r12308),
        },
        "admission_counts": {
            "training_rows_emitted": 0,
            "train_support_allowed": 0,
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "level_3_countable": 0,
            "external_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "stage12306_audit": {
            "candidate_action_shortcut_field_counts": dict(shortcut_counts),
            "blocked_reason_counts": dict(stage12306_blockers),
            "guardrail_decision": "pass_model_visible_action_ref_check" if not shortcut_counts else "blocked_shortcut_fields_present",
        },
        "stage12307_audit": {
            "status_counts": dict(stage12307_status),
            "language_counts": dict(stage12307_languages),
            "ready_for_training": 0,
        },
        "stage12308_audit": {
            "records_with_possible_rule": s12308.get("records_with_possible_rule", 0),
            "records_training_allowed": s12308.get("records_training_allowed", 0),
            "hard_reject_reason_counts": dict(stage12308_rejects),
        },
        "current_progress_counters_vs_stage12305": {
            "canonical_root_candidates": len(r12306) + len(r12307),
            "level_3_plus_candidates": 0,
            "patch_trace_candidates": 0,
            "languages_in_candidate_queue": sorted(set(stage12307_languages) | {row.get("language_family") for row in r12306 if row.get("language_family")}),
            "rust_external_candidates": stage12307_languages.get("rust", 0),
            "cpp_external_candidates": stage12307_languages.get("c_cpp", 0),
            "semantic_h1_rewrites": 0,
        },
        "next_blockers": [
            "Hydrate explicit pre-action state codes for Stage12306/12308 without raw text leakage.",
            "Materialize Rust/C++ commit/test/verifier hashes and selected logs from Stage12307 queue.",
            "Recover repo_family for Stage12306 session candidates from cwd/repo joins.",
            "Promote no row until semantic_rule_id and transition_function_key exist.",
            "Build Level-3 tuple proof; current candidates are still source/queue/review records.",
        ],
        "next_stage": "stage12310_state_code_hydration_design",
    }

    (OUT / "canonical_root_materialization_status_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
