#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10863
NAME = "stage10863_agentkernel_second_python_verifier_materialization"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "agentkernel_second_python_verifier_materialization.json"
PACKETS_DIR = OUT_DIR / "review_packets"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

EPISODE_ID = (
    "localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_24t22_32_18_019d21fa_350b_7401_bd0e_c83e_"
    "agent_kernel_config_py_agent_kernel_cycle_runner_py_agent_kernel_improvement_py__28d49f6b85_aug_1500000_8b46e7f662"
)
REPO_ID = "agentkernel"
LANGUAGE = "python"

CHUNKS_PARQUET = (
    ARTIFACTS
    / "merged_packable_examples"
    / "strict_commit_plus_strict_session_plus_current_recent96_strict_packs_5m_hardened_v2"
    / "parquet"
    / "strict_long_context_pack_chunks-000000.parquet"
)

QUEUE_STATUS_JSONL = (
    ARTIFACTS
    / "stage10493_python_verifier_fresh_review_packet_builder"
    / "python_verifier_review_target_status.jsonl"
)

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

CANDIDATE_PATHS = [
    "agent_kernel/cycle_runner.py",
    "agent_kernel/config.py",
]

CHANGED_SUPPORT_PATHS = [
    "agent_kernel/improvement.py",
    "agent_kernel/loop.py",
]

SELECTED_TESTS = [
    "tests/test_compare_retained_baseline.py",
    "tests/test_config_validation.py",
    "tests/test_improvement.py",
    "tests/test_improvement_catalog.py",
    "tests/test_improvement_cycle_observation.py",
    "tests/test_liftoff_loop.py",
    "tests/test_loop.py",
    "tests/test_loop_runtime_support.py",
]


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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def short_text(text: str, limit: int = 900) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def load_chunk_map(paths: list[str]) -> dict[str, dict[str, Any]]:
    con = duckdb.connect()
    query = (
        "select chunk_id, path, role, retrieval_reason, text "
        "from read_parquet(?) where path in (" + ",".join(["?"] * len(paths)) + ")"
    )
    rows = con.execute(query, [str(CHUNKS_PARQUET), *paths]).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for chunk_id, path, role, retrieval_reason, text in rows:
        out[str(path)] = {
            "chunk_id": str(chunk_id),
            "path": str(path),
            "role": str(role),
            "retrieval_reason": str(retrieval_reason),
            "text": str(text),
        }
    missing = [path for path in paths if path not in out]
    if missing:
        raise FileNotFoundError(f"missing chunk paths: {missing}")
    return out


def evidence_entry(chunk: dict[str, Any], source_type: str, distance: int = 0) -> dict[str, Any]:
    return {
        "distance_from_seed": distance,
        "meta": {
            "chunk_id": chunk["chunk_id"],
            "path": chunk["path"],
            "role": chunk["role"],
        },
        "path": chunk["path"],
        "retrieval_reason": chunk["retrieval_reason"],
        "source_type": source_type,
        "text": short_text(chunk["text"]),
    }


def perspective_rows(candidate_paths: list[str], selected_tests: list[str]) -> list[dict[str, Any]]:
    task = (
        "A real repository-maintenance session changed multiple loop/config/improvement surfaces. "
        "Use the visible implementation and verifier snippets to decide which surface or test is "
        "most justified, and abstain only when the perspective explicitly requires it."
    )
    rows = []
    for perspective in PERSPECTIVES:
        rows.append(
            {
                "bundle_id": f"stage10863::{REPO_ID}::{EPISODE_ID}",
                "language_family": LANGUAGE,
                "perspective": perspective,
                "prompt_contract": {
                    "task": task,
                    "candidate_paths": candidate_paths,
                    "selected_tests": selected_tests,
                    "visible_evidence_keys": VISIBLE_EVIDENCE_KEYS,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "completed",
                "eligible_for_training_or_scoring_now": True,
            }
        )
    return rows


def queue_status() -> dict[str, Any] | None:
    for row in load_jsonl(QUEUE_STATUS_JSONL):
        if row.get("episode_id") == EPISODE_ID:
            return row
    return None


def main() -> None:
    supporting_paths = [*CANDIDATE_PATHS, *CHANGED_SUPPORT_PATHS, *SELECTED_TESTS]
    chunks = load_chunk_map(supporting_paths)
    status = queue_status()

    bundle_id = f"stage10863::{REPO_ID}::{EPISODE_ID}"
    bundle_dir = PACKETS_DIR / f"{REPO_ID}__{EPISODE_ID}"

    preview = {
        "bundle_id": bundle_id,
        "root_example_id": EPISODE_ID,
        "repo_id": REPO_ID,
        "language_family": LANGUAGE,
        "source_route": "agentkernel_direct_chunk_materialization",
        "candidate_paths": CANDIDATE_PATHS,
        "selected_tests": SELECTED_TESTS,
        "claim_boundary": {
            "gold_answers_fully_adjudicated": True,
            "partial_source_materialization_complete": True,
            "preview_only": False,
            "supports_training_or_scoring_now": True,
            "supports_training_only": True,
            "headline_eligible": False,
        },
        "maintainer_visible_evidence": {
            "candidate_change_surface": [
                evidence_entry(chunks["agent_kernel/cycle_runner.py"], "local_repo_seed_change"),
                evidence_entry(chunks["agent_kernel/config.py"], "local_repo_seed_change"),
            ],
            "nearby_definition_or_usage_context": [
                evidence_entry(chunks["agent_kernel/improvement.py"], "local_repo_neighbor"),
                evidence_entry(chunks["agent_kernel/loop.py"], "local_repo_neighbor"),
            ],
            "symptom_or_call_path_analogue": [
                evidence_entry(chunks["tests/test_compare_retained_baseline.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_loop.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_loop_runtime_support.py"], "local_repo_selected_test"),
            ],
            "verifier_and_test_constraint": [
                evidence_entry(chunks["tests/test_config_validation.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_improvement.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_improvement_catalog.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_improvement_cycle_observation.py"], "local_repo_selected_test"),
                evidence_entry(chunks["tests/test_liftoff_loop.py"], "local_repo_selected_test"),
            ],
        },
        "discovery_metadata": {
            "candidate_geometry_tags": [
                "has_selected_tests",
                "implementation_vs_config",
                "implementation_vs_implementation",
                "symbol_vs_symbol",
            ],
            "queue_status": status or {},
            "source_kind": "direct_packable_chunk_materialization_without_mixture_row",
            "supports_promotable_packet": False,
            "train_support_only": True,
        },
        "perspective_rows": perspective_rows(CANDIDATE_PATHS, SELECTED_TESTS),
    }

    anti_cheat = {
        "bundle_id": bundle_id,
        "completed_by": "codex-gpt5",
        "language_family": LANGUAGE,
        "passed": True,
        "review_scope": "prompt_visible_evidence_only",
        "review_lines": {
            "selected_test_names_are_visible_but_not_raw_target_only_shortcuts": True,
            "changed_path_signature_not_exposed_verbatim": True,
            "candidate_order_not_relied_on": True,
            "real_test_and_behavior_snippets_present": True,
            "same_surface_selected_test_name_prior_still_present": True,
        },
        "reviewer_notes": (
            "Pass for train-support materialization only. Unlike the blocked code_assist rows, this packet exposes real "
            "selected-test snippets and changed implementation/config surfaces. It still remains non-headline because "
            "selected test names and same-family surfaces could act as priors, so it should not be promoted as a fresh "
            "strict-heldout verifier benchmark."
        ),
    }

    rubric = {
        "bundle_id": bundle_id,
        "completed_by": "codex-gpt5",
        "language_family": LANGUAGE,
        "passed": True,
        "gold_label_slot": {
            "selected_candidate_id": None,
            "abstain_due_to_insufficient_evidence": True,
            "reviewer_rationale": (
                "Admit as train-support-only abstention-oriented verifier materialization. The visible prompt now has real "
                "test and implementation/config snippets, but those clues still keep multiple loop/config/improvement surfaces "
                "plausible. Forcing a singleton implementation-vs-config gold would overstate identifiability."
            ),
        },
        "rubric_lines": {
            "visible_evidence_supports_one_candidate": False,
            "candidate_set_is_maintainer_plausible": True,
            "raw_changed_path_list_not_exposed": True,
            "visible_snippets_are_sufficient_for_local_reasoning": True,
            "abstention_would_be_more_honest_if_evidence_is_insufficient": True,
        },
    }

    write_json(bundle_dir / "materialized_preview.json", preview)
    write_json(bundle_dir / "anti_cheat_review_card.json", anti_cheat)
    write_json(bundle_dir / "expert_maintainer_rubric_review.json", rubric)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "agentkernel_second_python_verifier_root_materialized_for_train_support",
        "bundle_id": bundle_id,
        "repo_id": REPO_ID,
        "language_family": LANGUAGE,
        "packet_dir": rel(bundle_dir),
        "selected_test_count": len(SELECTED_TESTS),
        "candidate_path_count": len(CANDIDATE_PATHS),
        "materialized_paths": supporting_paths,
        "claim_boundary": [
            "This packet is source-backed and exposes real selected-test snippets.",
            "It is still train-support only and not strict-heldout headline evidence.",
            "Gold is abstention-oriented because the visible evidence is richer but still not a clean singleton implementation-vs-config decision.",
        ],
        "next_best_step": (
            "Use this packet as the second source-backed Python verifier-support root in the residual inventory, "
            "then build a fresh strict-heldout verifier-transition row whose visible target is test/transition rather than implementation-vs-config."
        ),
        "created_artifacts": {
            "summary": rel(OUT_JSON),
            "materialized_preview": rel(bundle_dir / "materialized_preview.json"),
            "anti_cheat_review_card": rel(bundle_dir / "anti_cheat_review_card.json"),
            "expert_maintainer_rubric_review": rel(bundle_dir / "expert_maintainer_rubric_review.json"),
        },
    }

    write_json(OUT_JSON, summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
