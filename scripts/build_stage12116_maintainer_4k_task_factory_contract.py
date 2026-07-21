#!/usr/bin/env python3
"""Define the Maintainer-4K task factory contract for subagent production."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12116
NAME = "stage12116_maintainer_4k_task_factory_contract"
OUT = ART / NAME
SUMMARY = OUT / "maintainer_4k_task_factory_contract.json"
MIRROR = SUM / f"{NAME}.json"
ROOT_TEMPLATE = OUT / "root_task_candidate_template.json"
TRANSITION_TEMPLATE = OUT / "verified_transition_record_template.json"
WORK_PACKETS = OUT / "subagent_work_packets.jsonl"
AUDIT_CONTRACT = OUT / "deterministic_admission_audit_contract.json"


LANGUAGES = {
    "python": {
        "target_tasks": 1000,
        "minimum_distinct_roots": 250,
        "repo_family_cap": 50,
        "packet_count": 10,
        "preferred_verifiers": ["pytest", "tox", "nox", "ruff/mypy as static-only anchors"],
        "avoid_overfit_families": ["MirrorMind", "code_assist", "repository_library"],
        "compatibility_note": "Stage12114 does not admit language=python; Python needs a successor audit with the same gates plus python in VALID_LANGS.",
    },
    "rust": {
        "target_tasks": 1000,
        "minimum_distinct_roots": 250,
        "repo_family_cap": 50,
        "packet_count": 10,
        "preferred_verifiers": ["cargo test", "cargo test --workspace", "cargo check as static-only anchor"],
        "avoid_overfit_families": ["tokenizers", "candle", "perftree", "git/libgit-rs unless lineage-clean"],
        "compatibility_note": "Stage12114/12115 are directly compatible after checkout/probe evidence exists.",
    },
    "c_cpp": {
        "target_tasks": 1000,
        "minimum_distinct_roots": 250,
        "repo_family_cap": 50,
        "packet_count": 10,
        "preferred_verifiers": ["ctest", "cmake --build", "make test", "ninja test"],
        "avoid_overfit_families": ["parametergolf", "agentkernel", "cccl", "onnxruntime"],
        "compatibility_note": "Stage12114/12115 are directly compatible; selected-test claims require concrete ctest/unit-test evidence.",
    },
    "web_js_ts_html": {
        "target_tasks": 1000,
        "minimum_distinct_roots": 250,
        "repo_family_cap": 50,
        "packet_count": 10,
        "preferred_verifiers": ["npm test", "pnpm test", "yarn test", "vitest", "playwright test", "build/typecheck as scoped anchors"],
        "avoid_overfit_families": ["OpenHands", "LlamaStack", "code_assist", "OpenClaw unless heldout-clean"],
        "compatibility_note": "Stage12114/12115 are directly compatible; avoid OpenHands/Llama schema overfit and preserve renderer parity.",
    },
}

TASK_FAMILY_QUOTAS = {
    "transition_next_action": 0.25,
    "transition_candidate_selection": 0.20,
    "transition_verifier_transition": 0.20,
    "transition_continue_or_stop": 0.15,
    "evidence_role_boundary": 0.10,
    "repair_intent_or_patch_sketch": 0.05,
    "abstraction_boundary_or_dependency_contract": 0.05,
}

VERIFIER_STATUS_FLOORS_PER_LANGUAGE = {
    "FAIL_TO_PASS": 120,
    "PASS_TO_PASS": 180,
    "PASS_CURRENT_BUILD": 100,
    "PASS_CURRENT_BUILD_AND_RUN": 100,
    "PASS_CURRENT_STATE": 100,
    "NOT_EXERCISED": 120,
    "INSUFFICIENT_EVIDENCE": 120,
    "VERIFIER_REMOVED": 60,
    "FAIL_TO_FAIL_OR_STILL_BROKEN": 100,
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def build_root_template() -> dict[str, Any]:
    return {
        "root_id": "stable unique root id",
        "repo_id": "owner/repo or local canonical repo",
        "repo_family": "canonical family after remote/local lineage normalization",
        "root_lineage_key": "repo_family + snapshot + task seed; never split across train/eval",
        "language_family": "python|rust|c_cpp|web_js_ts_html",
        "snapshot": {
            "source_kind": "git_checkout|local_repo|generated_mutation",
            "commit_sha": "required when git-backed",
            "source_path": "absolute local path after acquisition",
            "dependency_lock_digest": "hash if lockfile exists",
        },
        "task_contract": {
            "task_family": "transition_next_action|transition_candidate_selection|transition_verifier_transition|transition_continue_or_stop|...",
            "user_task": "brief realistic maintainer task",
            "constraints": ["no production effects", "no public API change unless task says so"],
            "acceptance_criteria": ["focused verifier result", "regression or build preservation condition"],
        },
        "evidence_ledger": [
            {"evidence_id": "S01", "kind": "source", "path": "file", "excerpt": "short visible excerpt"},
            {"evidence_id": "V01", "kind": "verifier_log", "command": "command", "summary": "observed result"},
        ],
        "candidate_set": [
            {
                "candidate_id": "opaque shuffled label at render time",
                "semantic_role": "SELECT_TEST|PLAN_PATCH|VERIFY_RESULT|ABSTAIN|candidate_change_surface|verifier_and_test_constraint",
                "artifact_type": "file|symbol|test|command|action|evidence|patch_sketch",
                "value": "semantic target value hidden before options",
                "evidence_ids": ["S01", "V01"],
            }
        ],
        "gold": {
            "semantic_candidate_id": "candidate object identity, not display letter",
            "verifier_transition": "FAIL_TO_PASS|PASS_TO_PASS|PASS_CURRENT_BUILD|NOT_EXERCISED|INSUFFICIENT_EVIDENCE|...",
            "why_positive_is_correct": "evidence-backed explanation",
            "why_negatives_are_wrong": {"candidate_id": "specific reason"},
        },
        "split": {
            "component": "train|validation|strict_eval|sealed_eval|diagnostic|quarantine",
            "source_heldout_admissible": True,
            "train_support_only": False,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "post_fix_source_absent_from_pre_action_state": True,
            "root_lineage_disjoint_across_splits": True,
        },
        "quality_tier": "gold|silver|bronze|quarantine",
        "review_status": "draft|machine_audited|human_or_senior_reviewed|admitted|rejected",
    }


def build_transition_template() -> dict[str, Any]:
    return {
        "transition_record_schema": "verified_transition_record_v1",
        "root_id": "same as root task",
        "episode_id": "rollout or oracle/repaired episode id",
        "state_id": "causal state before decision",
        "state_before": {
            "visible_evidence_ids": ["S01", "V01"],
            "known_facts": [],
            "open_questions": [],
            "last_verifier_result": "none|pass|fail|not_exercised|insufficient",
            "milestone_status": "ready|blocked|verified|invalidated",
        },
        "candidate_actions": [
            {"action_id": "A1", "action_type": "INSPECT|RUN_TEST|PATCH|VERIFY|ABSTAIN|FINISH", "target": "file/test/symbol/command"}
        ],
        "chosen_or_gold_action": "A1",
        "tool_observation": {
            "command": "optional executed command",
            "exit_code": 0,
            "summary": "bounded observation, not raw terminal spam",
        },
        "verifier_result": {
            "status": "FAIL_TO_PASS|PASS_TO_PASS|PASS_CURRENT_BUILD|PASS_CURRENT_BUILD_AND_RUN|NOT_EXERCISED|INSUFFICIENT_EVIDENCE",
            "selected_verifier_path": "test path or build/config command",
            "claim_scope": "selected_test_anchor|build_config_anchor|static_compile_anchor|dependency_resolution_anchor",
        },
        "state_after": {
            "new_facts": [],
            "invalidated_claims": [],
            "continue_or_stop": "CONTINUE|STOP|ABSTAIN",
        },
        "projected_targets": [
            "transition_next_action",
            "transition_candidate_selection",
            "transition_verifier_transition",
            "transition_continue_or_stop",
            "evidence_role_boundary",
        ],
    }


def build_work_packets() -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for language, spec in LANGUAGES.items():
        for batch in range(1, spec["packet_count"] + 1):
            packets.append({
                "work_packet_id": f"stage12116::{language}::packet_{batch:02d}",
                "language_family": language,
                "target_tasks": 100,
                "minimum_distinct_roots": 25,
                "preferred_distinct_roots": 35,
                "max_tasks_per_root": 4,
                "target_projected_rows_minimum": 600,
                "target_projected_rows_preferred": 1200,
                "repo_family_cap_within_packet": 10,
                "global_repo_family_cap": spec["repo_family_cap"],
                "required_root_mix": {
                    "new_external_repo_roots": 70,
                    "local_lineage_clean_roots": 10,
                    "semantic_mutation_roots": 10,
                    "oracle_or_repaired_rollout_roots": 10,
                },
                "task_family_quota": TASK_FAMILY_QUOTAS,
                "verifier_status_floor_hint": {
                    key: max(5, value // spec["packet_count"]) for key, value in VERIFIER_STATUS_FLOORS_PER_LANGUAGE.items()
                },
                "preferred_verifiers": spec["preferred_verifiers"],
                "avoid_overfit_families": spec["avoid_overfit_families"],
                "compatibility_note": spec["compatibility_note"],
                "subagent_allowed_actions": [
                    "propose acquisition candidates",
                    "inspect local repo metadata",
                    "draft root/task records",
                    "draft verifier command plans",
                    "draft candidate hard negatives",
                ],
                "subagent_forbidden_actions": [
                    "mark a row admitted",
                    "claim selected-test evidence without an executed verifier log",
                    "train or evaluate model checkpoints",
                    "use protected heldout roots as train support",
                    "emit singleton-option rows",
                ],
                "promotion_requires": [
                    "deterministic intake audit pass",
                    "lineage dedup pass",
                    "verifier log or correctly scoped insufficient-evidence proof",
                    "candidate-object anti-cheat pass",
                    "quality tier gold or silver",
                ],
            })
    return packets


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    root_template = build_root_template()
    transition_template = build_transition_template()
    work_packets = build_work_packets()
    audit_contract = {
        "stage": STAGE,
        "audit_name": "maintainer_4k_deterministic_admission_audit",
        "hard_reject_reasons": [
            "root_lineage_crosses_split",
            "repo_family_cap_exceeded",
            "prompt_target_leak",
            "post_fix_source_in_pre_action_state",
            "singleton_options",
            "missing_verifier_or_scope_label",
            "selected_test_claim_without_executed_test",
            "duplicate_or_near_duplicate_root",
            "gold_not_supported_by_visible_evidence",
            "hard_negatives_not_plausible",
            "subagent_assertion_without_deterministic_evidence",
        ],
        "quality_scores": {
            "verifier_anchor_score": "0-4",
            "source_grounding_score": "0-4",
            "hard_negative_quality": "0-4",
            "novelty_score": "0-4",
            "transition_semantic_depth": "0-4",
            "leakage_risk": "0-4 inverted",
            "duplicate_risk": "0-4 inverted",
        },
        "minimum_admission": {
            "gold": "score >= 18 and verifier-backed",
            "silver": "score >= 14 and source-grounded with scoped verifier/build/insufficient evidence",
            "bronze": "pretraining/diagnostic only, never strict eval",
            "quarantine": "any hard reject",
        },
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "maintainer_4k_task_factory_contract_ready",
        "do_not_train": True,
        "objective": "Create 1000 high-quality verifier-grounded maintainer transition tasks per primary language before broad model-claim training.",
        "target_scale": {
            "total_tasks": 4000,
            "tasks_by_language": {language: spec["target_tasks"] for language, spec in LANGUAGES.items()},
            "minimum_distinct_roots": sum(spec["minimum_distinct_roots"] for spec in LANGUAGES.values()),
            "minimum_distinct_roots_by_language": {language: spec["minimum_distinct_roots"] for language, spec in LANGUAGES.items()},
            "max_tasks_per_root": 4,
            "minimum_projected_rows": 24000,
            "preferred_projected_rows": 48000,
            "long_horizon_upgrade_path": "After the 4K root factory is clean, expand selected roots into 50-200-step rollout episodes.",
        },
        "language_contracts": LANGUAGES,
        "task_family_quotas": TASK_FAMILY_QUOTAS,
        "verifier_status_floors_per_language": VERIFIER_STATUS_FLOORS_PER_LANGUAGE,
        "subagent_control_model": {
            "scout": "find candidate roots only",
            "builder": "draft schema-complete root/task/transition records",
            "auditor": "red-team the draft, but deterministic scripts decide admission",
            "main_agent": "owns schema, deterministic audits, integration, and promotion decisions",
        },
        "scale_guardrails": [
            "Scale by independent roots, not permutations.",
            "Every root stays in exactly one split.",
            "Every candidate has semantic object identity; answer letters are display only.",
            "Every selected-test claim requires an executed selected verifier log.",
            "Build/config/static anchors are useful but must be labeled as such.",
            "Every packet is useful only if it improves root breadth, verifier-status balance, or named failure-family coverage.",
            "No package proceeds to training if quality or leak gates fail.",
        ],
        "first_milestone": {
            "name": "Maintainer-400 pilot",
            "tasks": 400,
            "tasks_by_language": {language: 100 for language in LANGUAGES},
            "minimum_distinct_roots_by_language": {language: 25 for language in LANGUAGES},
            "purpose": "prove subagent factory, deterministic audits, row quality, and training response before generating all 4K tasks",
        },
        "second_milestone": {
            "name": "Maintainer-4K",
            "tasks": 4000,
            "tasks_by_language": {language: 1000 for language in LANGUAGES},
            "minimum_distinct_roots_by_language": {language: spec["minimum_distinct_roots"] for language, spec in LANGUAGES.items()},
            "promotion_use": "source-heldout training/eval substrate, not a same-surface residual patch packet",
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "root_task_candidate_template": rel(ROOT_TEMPLATE),
            "verified_transition_record_template": rel(TRANSITION_TEMPLATE),
            "subagent_work_packets": rel(WORK_PACKETS),
            "deterministic_admission_audit_contract": rel(AUDIT_CONTRACT),
        },
    }
    write_json(ROOT_TEMPLATE, root_template)
    write_json(TRANSITION_TEMPLATE, transition_template)
    write_jsonl(WORK_PACKETS, work_packets)
    write_json(AUDIT_CONTRACT, audit_contract)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "target_scale": summary["target_scale"],
        "work_packets": len(work_packets),
        "first_milestone": summary["first_milestone"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
