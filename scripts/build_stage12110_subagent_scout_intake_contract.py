#!/usr/bin/env python3
"""Define deterministic intake gates for subagent-scouted sealed roots."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12110
NAME = "stage12110_subagent_scout_intake_contract"
OUT = ROOT / "runs/local/artifacts" / NAME
SUMMARY = OUT / "subagent_scout_intake_contract.json"
MIRROR = ROOT / "runs/summaries" / f"{NAME}.json"
TEMPLATE = OUT / "subagent_scout_candidate_template.json"

STAGE12109 = ROOT / "runs/summaries/stage12109_build_verifier_gap_fill_queue.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prior = read_json(STAGE12109)
    template = {
        "repo_family": "example_repo_family",
        "source_path": "/absolute/local/source/path",
        "language": "rust|c_cpp|web_js_ts_html|mixed_build_config_dependency",
        "verifier_type": "selected_test_anchor|build_config_anchor|static_compile_anchor|dependency_resolution_anchor",
        "available_evidence": ["manifest path", "source path", "test/build marker", "command/log availability"],
        "missing_evidence": ["selected test if absent", "runtime log if not executed yet"],
        "candidate_task_family": "transition_next_action|transition_candidate_selection|transition_verifier_transition|transition_continue_or_stop",
        "why_valid": "One sentence explaining the verifier-grounded decision boundary.",
        "reserved_family_conflict": False,
        "conflict_reason": "",
        "suggested_commands": [["command", "arg"]],
        "anti_cheat_notes": {
            "must_use_opaque_shuffled_options": True,
            "no_singleton_options": True,
            "target_not_visible_before_options": True,
            "build_only_not_selected_test": True,
        },
        "split_status": "sealed_candidate|dev_only",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "subagent_scout_intake_contract_ready",
        "do_not_train": True,
        "why": "Subagents may propose roots and draft row materialization metadata, but deterministic lineage, evidence, and anti-cheat gates decide admission.",
        "current_remaining_gap": prior["remaining_after_build_verifier_gap_fill"],
        "accepted_input_schema": template,
        "deterministic_promotion_gates": [
            "source_path exists locally",
            "language is one of rust/c_cpp/web_js_ts_html/mixed_build_config_dependency",
            "repo_family and canonical lineage are disjoint from Stage11897, Stage11943, Stage120xx, Stage12105, Stage12107, Stage12109",
            "reserved_family_conflict is false for sealed eligibility",
            "verifier_type is correctly scoped: build_config_anchor cannot be counted as selected_test_anchor",
            "available_evidence includes manifest plus source/build/test marker appropriate to verifier_type",
            "suggested_commands are non-destructive and local",
            "candidate_task_family targets a remaining gap lane or transition family",
            "anti_cheat notes require opaque shuffled non-singleton candidates",
            "target semantic value must not appear before options in any emitted row",
        ],
        "scout_roles": {
            "rust": {
                "target_roots": prior["remaining_after_build_verifier_gap_fill"].get("rust", 0),
                "claim_boundary": "Fresh Rust roots only; consumed candle/tokenizers/git/perftree-like families are dev_only unless lineage audit proves otherwise.",
            },
            "web_js_ts_html": {
                "target_roots": prior["remaining_after_build_verifier_gap_fill"].get("web_js_ts_html", 0),
                "claim_boundary": "Build/dependency roots allowed, but no selected-test claim without real tests.",
            },
            "c_cpp": {
                "target_roots": prior["remaining_after_build_verifier_gap_fill"].get("c_cpp", 0),
                "claim_boundary": "Build/config/static compile roots allowed when labeled honestly.",
            },
        },
        "next_stage_recommendation": {
            "stage": "stage12111_subagent_scout_intake_audit",
            "action": "Paste or materialize scout outputs into a JSONL intake file, then run deterministic lineage/evidence gates before row building.",
        },
        "source_artifacts": {
            "stage12109_gap_fill_queue": rel(STAGE12109),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "candidate_template": rel(TEMPLATE),
        },
    }
    write_json(TEMPLATE, template)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "current_remaining_gap": summary["current_remaining_gap"],
        "next_stage": summary["next_stage_recommendation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
