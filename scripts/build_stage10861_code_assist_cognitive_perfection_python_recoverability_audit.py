#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10861
NAME = "stage10861_code_assist_cognitive_perfection_python_recoverability_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "code_assist_cognitive_perfection_python_recoverability_audit.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

ROW_ID = (
    "stage10110::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_"
    "src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::"
    "python_implementation_vs_config"
)
SOURCE_PACKET = (
    ARTIFACTS
    / "stage10110_real_session_shortcut_safe_successor_packet"
    / "real_session_shortcut_safe_successor_packet.jsonl"
)
REVIEW_PACKET_DIR = (
    ARTIFACTS
    / "stage10111_real_session_successor_review_packets"
    / "review_packets"
    / "stage10110__localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13___c1bb544ab8bd6da7"
)
RUBRIC_PATH = REVIEW_PACKET_DIR / "expert_maintainer_rubric_review.json"
ANTI_CHEAT_PATH = REVIEW_PACKET_DIR / "anti_cheat_review_card.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_source_row() -> dict[str, Any]:
    with SOURCE_PACKET.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("row_id") == ROW_ID:
                return row
    raise FileNotFoundError(f"row_id not found in source packet: {ROW_ID}")


def short_text(text: str, limit: int = 220) -> str:
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3] + "..."


def main() -> None:
    source_row = load_source_row()
    prompt_surface = source_row["prompt_surface"]
    hidden_metadata = source_row["hidden_metadata"]

    rubric = load_json(RUBRIC_PATH)
    anti_cheat = load_json(ANTI_CHEAT_PATH)

    expert_rationale = (
        "Do not admit this row for singleton scoring or Python verifier-support training. "
        "The prompt-visible evidence does not expose the selected tests or verifier transition that would justify "
        "implementation over config. Three visible evidence snippets are unrelated analogue noise, and the remaining "
        "two snippets are effectively the candidate previews themselves. That makes the row vulnerable to surface-prior "
        "or self-matching shortcuts rather than maintainer reasoning."
    )
    anti_cheat_notes = (
        "Fail for shortcut risk and missing maintainer-grade evidence. Raw changed paths are hidden, but the prompt still "
        "collapses to a weak template: unrelated analogue snippets plus direct candidate previews. The selected test set "
        "exists only in hidden metadata, so the visible prompt cannot support a clean implementation-vs-config decision "
        "from maintainer-visible evidence alone."
    )

    rubric["status"] = "completed"
    rubric["passed"] = False
    rubric["reviewer_id"] = "codex-gpt5-ai-review"
    rubric["reviewer_notes"] = "AI adjudication on prompt-visible evidence only."
    rubric["gold_label_slot"] = {
        "selected_candidate_id": None,
        "abstain_due_to_insufficient_evidence": True,
        "reviewer_rationale": expert_rationale,
    }
    rubric["rubric_lines"] = {
        "visible_evidence_supports_one_candidate": False,
        "candidate_set_is_maintainer_plausible": True,
        "raw_changed_path_list_not_exposed": True,
        "visible_snippets_are_sufficient_for_local_reasoning": False,
        "abstention_would_be_more_honest_if_evidence_is_insufficient": True,
    }

    anti_cheat["status"] = "completed"
    anti_cheat["passed"] = False
    anti_cheat["reviewer_id"] = "codex-gpt5-ai-review"
    anti_cheat["reviewer_notes"] = anti_cheat_notes
    anti_cheat["challenge_lines"] = {
        "changed_path_signature_leakage": True,
        "candidate_position_or_id_bias": True,
        "cross_repo_analogue_surface_leakage": False,
        "review_scope_matches_prompt_visible_evidence_only": True,
        "template_specific_surface_prior": False,
    }

    write_json(RUBRIC_PATH, rubric)
    write_json(ANTI_CHEAT_PATH, anti_cheat)

    visible_evidence = [short_text(item) for item in prompt_surface.get("visible_evidence") or []]
    candidate_choices = [
        {
            "candidate_id": item.get("candidate_id"),
            "snippet_preview": short_text(item.get("snippet_preview") or "", limit=180),
        }
        for item in prompt_surface.get("candidate_choices") or []
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "row_id": ROW_ID,
        "passed": False,
        "repo_id": source_row.get("repo_id"),
        "language_family": source_row.get("language_family"),
        "successor_template": source_row.get("successor_template"),
        "review_packet_dir": str(REVIEW_PACKET_DIR.relative_to(ROOT)),
        "updated_reviews": {
            "expert_maintainer_rubric_review": str(RUBRIC_PATH.relative_to(ROOT)),
            "anti_cheat_review_card": str(ANTI_CHEAT_PATH.relative_to(ROOT)),
        },
        "prompt_visible_geometry": {
            "candidate_count": len(candidate_choices),
            "candidate_choices": candidate_choices,
            "visible_evidence_count": len(visible_evidence),
            "visible_evidence_preview": visible_evidence,
            "task_observation": prompt_surface.get("task_observation"),
            "selected_tests_hidden_metadata_only": True,
            "selected_tests": hidden_metadata.get("selected_tests") or [],
        },
        "blocking_findings": [
            "Prompt-visible evidence does not include selected tests or verifier transition evidence.",
            "Three visible evidence snippets are unrelated analogue text rather than local maintainer evidence.",
            "The two locally relevant visible snippets mostly restate the candidate surfaces themselves.",
            "This geometry supports template-prior or candidate self-matching shortcuts, not clean implementation-vs-config reasoning.",
            "Even abstention-labeled admission would not help the active Python verifier residual, which needs visible verifier/test contrast.",
        ],
        "claim_status": "blocked_not_admissible_for_current_python_verifier_recovery_goal",
        "recommended_next_actions": [
            "Recover real prompt-visible test or verifier snippets for the selected tests and rebuild the row as a maintainer-grade verifier packet.",
            "If source-backed materialization cannot expose those verifier anchors, quarantine this row and mine a different disjoint Python root.",
            "Prefer a fresh Python root whose visible prompt directly contrasts plausible tests and transitions rather than implementation-vs-config template priors.",
        ],
        "review_completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    write_json(OUT_JSON, summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
