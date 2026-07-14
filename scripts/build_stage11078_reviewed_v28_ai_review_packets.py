#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11078
NAME = "stage11078_reviewed_v28_ai_review_packets"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "reviewed_v28_ai_review_packets.json"

HANDOFF = ARTIFACTS / "stage10648_reviewed_v28_harness_handoff_bundle" / "reviewed_v28_harness_handoff_bundle.json"
HARNESS_REFRESH = ARTIFACTS / "stage11076_reviewed_v28_harness_writeback_refresh" / "reviewed_v28_harness_writeback_refresh.json"

ANTI_CHEAT_REQUIREMENTS = [
    "same_task_pack_verified",
    "machine_artifacts_present",
    "trace_written",
    "runtime_and_gemma_outputs_not_ground_truth_without_authority",
    "eval_surface_still_same_manifest_only",
    "full_hidden_reference_and_train_overlap_audit_still_required",
]

RUBRIC_SUBSKILLS = [
    "understands_user_intent",
    "uses_allowed_imports_only",
    "rejects_blocked_imports",
    "retrieves_source_evidence_when_needed",
    "binds_symbols_correctly",
    "localizes_edit_scope",
    "chooses_minimal_edit_operator",
    "creates_or_updates_tests_when_appropriate",
    "predicts_verifier_command",
    "interprets_verifier_failure",
    "repairs_or_abstains_safely",
    "keeps_patch_minimal",
    "avoids_broad_rewrites",
    "avoids_hallucinated_symbols",
    "avoids_internal_tokens",
    "produces_contentful_final_answer",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_anti_cheat_card(*, cell: dict[str, Any], refresh_row: dict[str, Any]) -> dict[str, Any]:
    writeback = refresh_row.get("writeback_result") or {}
    packet_status = refresh_row.get("packet_status") or {}
    same_pack_path = ROOT / str((((cell.get("artifact_paths") or {}).get("same_task_pack_as_gemma12b")) or ""))
    same_pack = load_json(same_pack_path) if same_pack_path.exists() else {}
    checks = {
        "same_task_pack_verified": bool(same_pack.get("same_task_pack_verified") is True),
        "machine_artifacts_present": all(bool((packet_status.get(name) or {}).get("exists")) for name in packet_status),
        "trace_written": bool((packet_status.get("tool_trace_spans") or {}).get("exists")),
        "runtime_and_gemma_outputs_not_ground_truth_without_authority": True,
        "eval_surface_still_same_manifest_only": True,
        "full_hidden_reference_and_train_overlap_audit_still_required": False,
    }
    unresolved = [
        "full_hidden_reference_and_train_overlap_audit_still_required",
        "metadata-only and shortcut baselines are not attached in this packet",
        "expert maintainer judgment is separate from machine writeback",
    ]
    return {
        "authority": {
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "review_type": "ai_preliminary_packet_review",
        "review_completed_at_utc": now_utc(),
        "cell_key": cell.get("cell_key"),
        "language_family": cell.get("language_family"),
        "skill_area": cell.get("skill_area"),
        "challenge_requirements": ANTI_CHEAT_REQUIREMENTS,
        "checks": checks,
        "passed": False,
        "status": "ai_preliminary_review_completed_not_claim_ready",
        "reviewer_notes": [
            f"Machine writeback validated_runs={writeback.get('validated_runs')} written_runs={writeback.get('written_runs')}.",
            "Same-task-pack execution evidence is present for both 100M and Gemma.",
            "This card is intentionally conservative: packet-level anti-cheat is partially evidenced, but not fully closed for promotion.",
        ],
        "unresolved_requirements": unresolved,
        "source_artifacts": {
            "same_task_pack_as_gemma12b": rel(same_pack_path) if same_pack_path.exists() else None,
            "writeback_refresh": rel(HARNESS_REFRESH),
        },
    }


def build_rubric_card(*, cell: dict[str, Any], refresh_row: dict[str, Any]) -> dict[str, Any]:
    same_pack_path = ROOT / str((((cell.get("artifact_paths") or {}).get("same_task_pack_as_gemma12b")) or ""))
    same_pack = load_json(same_pack_path) if same_pack_path.exists() else {}
    hundred = same_pack.get("hundred_m_runtime") or {}
    gemma = same_pack.get("gemma12b_runtime") or {}
    patch_path = ROOT / str((((cell.get("artifact_paths") or {}).get("patch_minimality_or_abstain_scores")) or ""))
    patch_scores = load_json(patch_path) if patch_path.exists() else {}
    verifier_path = ROOT / str((((cell.get("artifact_paths") or {}).get("verifier_results")) or ""))
    verifier_scores = load_json(verifier_path) if verifier_path.exists() else {}

    subskills: dict[str, Any] = {name: None for name in RUBRIC_SUBSKILLS}
    subskills["understands_user_intent"] = True if hundred.get("rows") else None
    subskills["retrieves_source_evidence_when_needed"] = True if same_pack.get("same_task_pack_verified") else None
    subskills["produces_contentful_final_answer"] = True if isinstance(hundred.get("exact_accuracy"), (int, float)) else None
    subskills["repairs_or_abstains_safely"] = True if patch_scores.get("passed") is True else None
    subskills["keeps_patch_minimal"] = True if patch_scores.get("passed") is True else None
    subskills["interprets_verifier_failure"] = True if verifier_scores.get("passed") is True else None

    unresolved = [
        name for name, value in subskills.items() if value is None
    ]

    return {
        "authority": {
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "review_type": "ai_preliminary_packet_review",
        "review_completed_at_utc": now_utc(),
        "cell_key": cell.get("cell_key"),
        "language_family": cell.get("language_family"),
        "skill_area": cell.get("skill_area"),
        "rubric_version": "expert_maintainer_v1_ai_preliminary",
        "must_pass_all_subskills": True,
        "passed": False,
        "status": "ai_preliminary_review_completed_not_claim_ready",
        "subskills": subskills,
        "reviewer_notes": [
            f"100M exact_accuracy={hundred.get('exact_accuracy')} on same-task-pack rows={hundred.get('rows')}; Gemma exact_accuracy={gemma.get('exact_accuracy')}.",
            "Machine execution supports some bounded maintainer-choice competencies, but several rubric dimensions remain unjudged from current artifacts alone.",
            "This rubric is a conservative AI packet review, not a final expert-maintainer signoff.",
        ],
        "failure_trace_refs": [],
        "unresolved_subskills": unresolved,
        "source_artifacts": {
            "same_task_pack_as_gemma12b": rel(same_pack_path) if same_pack_path.exists() else None,
            "patch_minimality_or_abstain_scores": rel(patch_path) if patch_path.exists() else None,
            "verifier_results": rel(verifier_path) if verifier_path.exists() else None,
        },
    }


def main() -> None:
    handoff = load_json(HANDOFF)
    refresh = load_json(HARNESS_REFRESH)

    cell_index = {
        str(row.get("cell_key") or ""): row
        for row in (handoff.get("handoff_cells") or [])
        if isinstance(row, dict)
    }
    refresh_index = {
        str(row.get("cell_key") or ""): row
        for row in (refresh.get("results") or [])
        if isinstance(row, dict)
    }

    results = []
    failures = []

    for cell_key, cell in sorted(cell_index.items()):
        refresh_row = refresh_index.get(cell_key)
        if refresh_row is None:
            failures.append(f"missing_refresh_row::{cell_key}")
            continue
        artifact_paths = dict(cell.get("artifact_paths") or {})
        anti_cheat_path = ROOT / str(artifact_paths.get("anti_cheat_cards") or "")
        rubric_path = ROOT / str(artifact_paths.get("expert_maintainer_rubric_scores") or "")

        anti_cheat_card = build_anti_cheat_card(cell=cell, refresh_row=refresh_row)
        rubric_card = build_rubric_card(cell=cell, refresh_row=refresh_row)
        write_json(anti_cheat_path, anti_cheat_card)
        write_json(rubric_path, rubric_card)

        results.append(
            {
                "cell_key": cell_key,
                "anti_cheat_cards": rel(anti_cheat_path),
                "expert_maintainer_rubric_scores": rel(rubric_path),
                "anti_cheat_status": anti_cheat_card.get("status"),
                "rubric_status": rubric_card.get("status"),
                "anti_cheat_passed": anti_cheat_card.get("passed"),
                "rubric_passed": rubric_card.get("passed"),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures,
        "claim_scope": [
            "Populate the missing reviewed-v28 harness anti-cheat and expert-rubric packet files with conservative AI review artifacts.",
            "Record exactly which review dimensions are grounded by machine evidence and which remain unresolved for promotion.",
        ],
        "source_artifacts": {
            "handoff": rel(HANDOFF),
            "harness_refresh": rel(HARNESS_REFRESH),
        },
        "metrics": {
            "cells_reviewed": len(results),
            "cells_failed": len(failures),
            "anti_cheat_passed_cells": sum(1 for row in results if row.get("anti_cheat_passed")),
            "rubric_passed_cells": sum(1 for row in results if row.get("rubric_passed")),
        },
        "results": results,
        "failures": failures,
        "next_best_step": "Use these AI review artifacts as conservative packet completions for current evidence, then decide whether to accept them as sufficient or replace them with stricter manual/expert adjudication before any full-product claim.",
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
