#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10756
NAME = "stage10756_python_verifier_geometry_upgrade_scaffolds"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "python_verifier_geometry_upgrade_scaffolds.json"
PACKETS_DIR = OUT_DIR / "review_packets"

QUEUE_JSON = ARTIFACTS / "stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_queue.json"
QUEUE_TARGETS_JSONL = ARTIFACTS / "stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_targets.jsonl"
TARGET_STATUS_JSONL = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder/python_verifier_review_target_status.jsonl"

HF_LOCAL_GOLD = ARTIFACTS / "stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/perspective_gold_adjudication.json"
HF_LOCAL_RUBRIC = ARTIFACTS / "stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/expert_maintainer_rubric_review.json"
HF_LOCAL_ANTI = ARTIFACTS / "stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/anti_cheat_review_card.json"

AGENTKERNEL_RUBRIC = ARTIFACTS / "stage10111_real_session_successor_review_packets/review_packets/stage10110__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14___a8d45d33b1e54081/expert_maintainer_rubric_review.json"
AGENTKERNEL_ANTI = ARTIFACTS / "stage10111_real_session_successor_review_packets/review_packets/stage10110__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14___a8d45d33b1e54081/anti_cheat_review_card.json"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]

VISIBLE_EVIDENCE_KEYS = [
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def bundle_slug(bundle_id: str) -> str:
    return bundle_id.replace("::", "__")


def existing_gold_by_perspective(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in payload.get("perspective_gold_answers") or []:
        if isinstance(row, dict) and row.get("perspective"):
            out[str(row["perspective"])] = row
    return out


def make_preview(target: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    selected_tests = list(target.get("selected_tests") or [])
    candidate_paths = list(target.get("change_paths_for_language") or [])
    episode_id = str(target["episode_id"])
    repo_id = str(target.get("repo_id") or "unknown")
    return {
        "bundle_id": f"stage10756::{repo_id}::{episode_id}",
        "root_example_id": episode_id,
        "repo_id": repo_id,
        "language_family": "python",
        "source_route": "reviewed_python_verifier_geometry_upgrade_scaffold",
        "seed_paths": candidate_paths,
        "selected_tests": selected_tests,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": False,
            "supports_training_or_scoring_now": False,
            "preview_only": True,
            "geometry_upgrade_required": True,
        },
        "maintainer_visible_evidence": {
            "candidate_change_surface": [
                {
                    "path": path,
                    "source_type": "existing_review_packet_surface",
                    "retrieval_reason": "python_verifier_geometry_upgrade",
                    "distance_from_seed": 0,
                    "text": "TODO_ATTACH_REAL_SURFACE_SNIPPET_OR_PROMPT_VISIBLE_CHANGE_CONTEXT",
                }
                for path in candidate_paths[:8]
            ],
            "verifier_and_test_constraint": [
                {
                    "path": test_path,
                    "source_type": "queued_selected_test_anchor",
                    "retrieval_reason": "python_verifier_geometry_upgrade_target",
                    "distance_from_seed": 0,
                    "text": "TODO_ATTACH_REAL_TEST_OR_VERIFIER_EVIDENCE_WITHOUT_LEAKING_GOLD_ORDER",
                }
                for test_path in selected_tests
            ],
            "symptom_or_call_path_analogue": [
                {
                    "path": candidate_paths[0] if candidate_paths else "TODO_PRIMARY_SIGNAL_PATH",
                    "source_type": "call_path_or_behavior_signal_placeholder",
                    "retrieval_reason": "must_support_b_vs_c_or_multi_test_disambiguation",
                    "distance_from_seed": 0,
                    "text": "TODO_ATTACH_REAL_VISIBLE_BEHAVIOR_SIGNAL_THAT_COMPETES_WITH_NEARBY_TEST_CHOICES",
                }
            ],
            "nearby_definition_or_usage_context": [
                {
                    "path": candidate_paths[1] if len(candidate_paths) > 1 else (candidate_paths[0] if candidate_paths else "TODO_CONTEXT_PATH"),
                    "source_type": "definition_context_placeholder",
                    "retrieval_reason": "candidate_path_and_verifier_target_competition",
                    "distance_from_seed": 0,
                    "text": "TODO_ATTACH_REAL_NEARBY_DEFINITION_OR_USAGE_CONTEXT",
                }
            ],
        },
        "discovery_metadata": {
            "priority_order": target.get("priority_order"),
            "candidate_geometry_tags": target.get("candidate_geometry_tags") or [],
            "required_bundle_shape": target.get("required_bundle_shape") or [],
            "existing_review_status": list(status.get("gaps") or []),
            "supports_promotable_packet": False,
        },
        "perspective_rows": [
            {
                "bundle_id": f"stage10756::{repo_id}::{episode_id}",
                "language_family": "python",
                "perspective": perspective,
                "prompt_contract": {
                    "task": "TODO_ATTACH_REAL_REVIEWED_PYTHON_VERIFIER_TASK_TEXT",
                    "candidate_paths": candidate_paths[:8],
                    "selected_tests": selected_tests,
                    "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "geometry_upgrade_review_required",
                "eligible_for_training_or_scoring_now": False,
            }
            for perspective in PERSPECTIVES
        ],
    }


def make_anti_cheat(target: dict[str, Any], source_payload: dict[str, Any] | None) -> dict[str, Any]:
    episode_id = str(target["episode_id"])
    repo_id = str(target.get("repo_id") or "unknown")
    inherited_notes = []
    if isinstance(source_payload, dict):
        inherited_notes = list(source_payload.get("reviewer_notes") or [])
    return {
        "bundle_id": f"stage10756::{repo_id}::{episode_id}",
        "repo_id": repo_id,
        "language_family": "python",
        "status": "pending_geometry_upgrade_review",
        "reviewer_id": "codex-gpt5-ai-review-scaffold",
        "decision_rationale": "Scaffold only. The packet is not yet admissible because it still needs richer verifier geometry with multiple plausible selected tests and real visible evidence.",
        "challenge_families": {
            "candidate_path_or_order_bias": True,
            "selected_test_label_leakage": True,
            "same_repo_family_saturation_bias": True,
            "geometry_collapse_to_singleton_test": True,
            "prompt_target_leakage": True,
        },
        "required_human_action": "Attach real verifier/test evidence with 3+ plausible selected tests, then audit whether the gold is still identifiable without exposing the answer string before options.",
        "required_gates_before_admission": [
            "3 or more plausible selected tests remain visible",
            "gold test path not exposed verbatim before options in future bounded projection",
            "prompt-visible evidence justifies one selected test over the others or abstention",
            "same root remains disjoint from current strict family",
        ],
        "template_inheritance_notes": inherited_notes,
        "passed": False,
        "admissible_for_same_surface_comparison": False,
    }


def make_gold(target: dict[str, Any], existing_gold: dict[str, Any] | None) -> dict[str, Any]:
    episode_id = str(target["episode_id"])
    repo_id = str(target.get("repo_id") or "unknown")
    existing = existing_gold_by_perspective(existing_gold or {})
    selected_tests = list(target.get("selected_tests") or [])
    candidate_paths = list(target.get("change_paths_for_language") or [])
    answers = []
    for perspective in PERSPECTIVES:
        prior = existing.get(perspective, {})
        answers.append(
            {
                "perspective": perspective,
                "candidate_paths": candidate_paths[:8],
                "selected_tests": selected_tests,
                "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                "abstention_option_required": perspective == "abstention_insufficient_evidence",
                "gold_answer_kind": prior.get("gold_answer_kind", "TODO_AFTER_GEOMETRY_UPGRADE"),
                "gold_answer_value": prior.get("gold_answer_value", "TODO_AFTER_GEOMETRY_UPGRADE"),
                "reviewer_rationale": prior.get(
                    "reviewer_rationale",
                    "TODO_AFTER_GEOMETRY_UPGRADE_WITH_MULTIPLE_PLAUSIBLE_SELECTED_TESTS",
                ),
            }
        )
    return {
        "bundle_id": f"stage10756::{repo_id}::{episode_id}",
        "repo_id": repo_id,
        "language_family": "python",
        "reviewer_id": "codex-gpt5-ai-review-scaffold",
        "status": "pending_geometry_upgrade",
        "decision_rationale": "Gold adjudication must be refreshed after richer verifier geometry is materialized. Existing singleton answers are not sufficient for the intended multi-test contrast packet.",
        "required_human_action": "After geometry upgrade, record one gold answer per perspective using the expanded selected-test set and abstain whenever the visible evidence is still insufficient.",
        "perspective_gold_answers": answers,
    }


def main() -> None:
    queue = load_json(QUEUE_JSON)
    queue_targets = {str(row["episode_id"]): row for row in load_jsonl(QUEUE_TARGETS_JSONL)}
    target_status = {str(row["episode_id"]): row for row in load_jsonl(TARGET_STATUS_JSONL)}
    hf_local_gold = load_json(HF_LOCAL_GOLD)
    hf_local_rubric = load_json(HF_LOCAL_RUBRIC)
    hf_local_anti = load_json(HF_LOCAL_ANTI)
    agentkernel_rubric = load_json(AGENTKERNEL_RUBRIC)
    agentkernel_anti = load_json(AGENTKERNEL_ANTI)

    deferred_targets = [
        row for row in queue.get("queue_targets") or []
        if not bool((target_status.get(str(row["episode_id"])) or {}).get("immediately_qualified_for_reviewed_verifier_packet"))
    ]

    written_packets = []
    for target in deferred_targets:
        episode_id = str(target["episode_id"])
        repo_id = str(target.get("repo_id") or "unknown")
        slug = bundle_slug(f"{repo_id}::{episode_id}")
        packet_dir = PACKETS_DIR / slug
        status = target_status[episode_id]

        if "hf_local" in episode_id:
            preview = make_preview(target, status)
            anti = make_anti_cheat(target, hf_local_anti)
            gold = make_gold(target, hf_local_gold)
            rubric = dict(hf_local_rubric)
            rubric["decision_rationale"] = "Existing reviewed rubric is insufficient for richer verifier geometry; refresh after multi-test packet materialization."
            rubric["bundle_valid_for_eval"] = False
            rubric["train_support_only"] = True
        else:
            preview = make_preview(target, status)
            anti = make_anti_cheat(target, agentkernel_anti)
            gold = make_gold(target, None)
            rubric = dict(agentkernel_rubric)
            rubric["decision_rationale"] = "Current row-level honesty review is insufficient for richer verifier geometry; refresh after multi-test packet materialization."
            rubric["bundle_valid_for_eval"] = False
            rubric["train_support_only"] = True

        preview_path = packet_dir / "fresh_python_bundle_preview.json"
        anti_path = packet_dir / "anti_cheat_review_card.json"
        gold_path = packet_dir / "perspective_gold_adjudication.json"
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"

        write_json(preview_path, preview)
        write_json(anti_path, anti)
        write_json(gold_path, gold)
        write_json(rubric_path, rubric)

        written_packets.append(
            {
                "episode_id": episode_id,
                "repo_id": repo_id,
                "packet_dir": rel(packet_dir),
                "preview_bundle": rel(preview_path),
                "anti_cheat_review_card": rel(anti_path),
                "perspective_gold_adjudication": rel(gold_path),
                "rubric_review": rel(rubric_path),
                "selected_tests_count": len(target.get("selected_tests") or []),
                "supports_shortcut_safe_successor": bool(target.get("supports_shortcut_safe_successor")),
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "python_verifier_geometry_upgrade_scaffolds_ready",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claim_scope": [
            "Create concrete review-packet scaffolds for the deferred richer-geometry Python verifier roots.",
            "Carry forward existing reviewed assets where possible, but make the missing multi-test verifier geometry explicit instead of pretending the old singleton packets are already enough.",
            "These scaffolds are not scoreable yet; they exist to focus the next materialization/adjudication work on the two deferred Python lanes.",
        ],
        "source_artifacts": {
            "queue": rel(QUEUE_JSON),
            "queue_targets": rel(QUEUE_TARGETS_JSONL),
            "target_status": rel(TARGET_STATUS_JSONL),
            "hf_local_gold": rel(HF_LOCAL_GOLD),
            "agentkernel_rubric": rel(AGENTKERNEL_RUBRIC),
        },
        "headline_findings": [
            "hf_local now has a concrete richer-geometry scaffold packet instead of only the old singleton-test reviewed packet.",
            "agentkernel now has a concrete richer-geometry scaffold packet instead of only the honesty-only row review.",
            "Both deferred Python lanes are now packetized for future real evidence materialization and re-adjudication.",
        ],
        "scaffold_targets": [str(row["episode_id"]) for row in deferred_targets],
        "required_materialization_fields": [
            "real prompt-visible verifier/test evidence for 3+ plausible selected tests",
            "no gold test path leakage before options",
            "candidate path and verifier target competition preserved under anti-cheat review",
            "refreshed perspective gold adjudication after geometry upgrade",
        ],
        "outputs": {
            "summary": rel(SUMMARY_JSON),
            "review_packets_dir": rel(PACKETS_DIR),
        },
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
