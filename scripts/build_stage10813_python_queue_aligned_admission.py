#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10813
NAME = "stage10813_python_queue_aligned_admission"
OUT_DIR = ARTIFACTS / NAME
PACKETS_DIR = OUT_DIR / "review_packets"
SUMMARY_JSON = OUT_DIR / "python_queue_aligned_admission.json"
ADMITTED_JSON = OUT_DIR / "python_queue_aligned_admitted_manifest.json"
BLOCKED_JSON = OUT_DIR / "python_queue_aligned_blocked_manifest.json"
ROOT_MANIFEST_JSONL = OUT_DIR / "python_queue_aligned_root_manifest.jsonl"

QUEUE_JSONL = ARTIFACTS / "stage10810_multilingual_root_materialization_queue_v2" / "materialization_queue.jsonl"
SOURCE_TARGETS = ARTIFACTS / "stage10492_python_verifier_reviewed_root_expansion_queue" / "python_verifier_reviewed_root_expansion_targets.jsonl"
STAGE10236_PACKET = ARTIFACTS / "stage10236_context_pack_python_replenishment_bundle" / "review_packets" / "stage10236__code_assist__python"
STAGE10300_PACKET = ARTIFACTS / "stage10300_hf_local_python_replenishment_bundle" / "review_packets" / "stage10300__code_assist__python"
STAGE10756_PACKET = ARTIFACTS / "stage10756_python_verifier_geometry_upgrade_scaffolds" / "review_packets" / "agentkernel__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662"


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def slugify(value: str) -> str:
    return value.replace("::", "__").replace("/", "_")


def packet_mapping() -> dict[str, dict[str, Path]]:
    return {
        "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662": {
            "packet_dir": STAGE10236_PACKET,
            "preview_path": ARTIFACTS / "stage10236_context_pack_python_replenishment_bundle" / "context_pack_python_replenishment_bundle.json",
        },
        "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662": {
            "packet_dir": STAGE10300_PACKET,
            "preview_path": ARTIFACTS / "stage10300_hf_local_python_replenishment_bundle" / "hf_local_python_replenishment_bundle.json",
        },
        "localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662": {
            "packet_dir": STAGE10756_PACKET,
            "preview_path": STAGE10756_PACKET / "fresh_python_bundle_preview.json",
        },
    }


def count_gold_kinds(payload: dict[str, Any]) -> tuple[int, int]:
    abstain = 0
    non_abstain = 0
    for answer in payload.get("perspective_gold_answers") or []:
        if str(answer.get("gold_answer_kind") or "") == "abstain":
            abstain += 1
        else:
            non_abstain += 1
    return abstain, non_abstain


def visible_keys(bundle: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    evidence = bundle.get("maintainer_visible_evidence")
    if not isinstance(evidence, dict):
        return keys
    for key, values in evidence.items():
        if isinstance(values, list) and values:
            keys.append(str(key))
    return sorted(keys)


def require_packet(packet_dir: Path, preview_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    preview = load_json(preview_path)
    rubric = load_json(packet_dir / "expert_maintainer_rubric_review.json")
    anti = load_json(packet_dir / "anti_cheat_review_card.json")
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    return preview, rubric, anti, gold


def admitted_preview(bundle: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(bundle))
    out.setdefault("claim_boundary", {})
    out["claim_boundary"]["preview_only"] = False
    out["claim_boundary"]["gold_answers_fully_adjudicated"] = True
    out["claim_boundary"]["supports_training_or_scoring_now"] = True
    out["claim_boundary"]["requires_bundle_admission_before_scoring"] = False
    out["claim_boundary"]["train_support_only_admitted"] = True
    out.setdefault("discovery_metadata", {})
    out["discovery_metadata"]["train_support_only_admitted"] = True
    out["discovery_metadata"]["admitted_by_stage"] = STAGE
    for row in out.get("perspective_rows") or []:
        row["eligible_for_training_or_scoring_now"] = True
        row["gold_answer_status"] = "completed_ai_maintainer_adjudication"
    return out


def admitted_rubric(rubric: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(rubric))
    out["status"] = "completed"
    out["passed"] = True
    out["bundle_valid_for_eval"] = False
    out["train_support_only"] = True
    notes = list(out.get("reviewer_notes") or [])
    notes.append("Queue-aligned train-support admission only. Keep out of headline strict eval claims.")
    out["reviewer_notes"] = notes
    return out


def admitted_anti(anti: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(anti))
    out["status"] = "completed"
    out["passed"] = True
    out["admissible_for_same_surface_comparison"] = False
    out["train_support_only"] = True
    notes = list(out.get("reviewer_notes") or [])
    notes.append("Selected-test anchor preserved, but same-surface fairness and heldout gates still block headline use.")
    out["reviewer_notes"] = notes
    return out


def admitted_gold(gold: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(gold))
    out["status"] = "completed"
    out["bundle_gold_ready_for_eval"] = True
    out["train_support_only"] = True
    guidance = list(out.get("reviewer_guidance") or [])
    guidance.extend([
        "This queue-selected packet is admitted for reviewed train-support use only.",
        "Keep it out of strict headline same-surface comparison until a later fairness gate admits it explicitly.",
    ])
    out["reviewer_guidance"] = guidance
    return out


def build_root_record(*, preview: dict[str, Any], rubric_path: Path, anti_path: Path, gold_path: Path, abstain_count: int, non_abstain_count: int, queue_row: dict[str, Any]) -> dict[str, Any]:
    selected_tests = [str(v) for v in (preview.get("selected_tests") or []) if v]
    bundle_id = str(preview["bundle_id"])
    candidate_paths = [str(v) for v in (preview.get("candidate_paths") or []) if v]
    keys = visible_keys(preview)
    return {
        "record_type": "reviewed_bundle_root",
        "bundle_id": bundle_id,
        "root_id": bundle_id,
        "repo_id": str(preview.get("repo_id") or ""),
        "repo_family": str(preview.get("repo_family") or preview.get("repo_id") or ""),
        "language_family": "python",
        "task_types": [str(row.get("perspective") or "") for row in (preview.get("perspective_rows") or []) if isinstance(row, dict)],
        "task_type_count": len(preview.get("perspective_rows") or []),
        "candidate_paths_count": len(candidate_paths),
        "selected_tests_count": len(selected_tests),
        "selected_test_anchor": bool(selected_tests),
        "verifier_anchor": bool(selected_tests) and ("verifier_and_test_constraint" in keys),
        "visible_evidence_keys": keys,
        "visible_evidence_key_count": len(keys),
        "abstention_count": abstain_count,
        "non_abstention_count": non_abstain_count,
        "abstention_heavy": abstain_count >= 4,
        "source_heldout_admissible": False,
        "train_support_only": True,
        "strict_eval_eligible": False,
        "stress_overlap_only": False,
        "split_role": "train_support",
        "split": "train",
        "same_surface_eval_admissible": False,
        "reviewed_bundle_source": True,
        "successor_row_source": False,
        "queue_aligned_admission": True,
        "claim_notes": [
            "python_verifier_reviewed_bundle",
            "ai_adjudicated",
            "queue_aligned_train_support_admission",
            "not_admissible_for_same_surface_comparison",
        ],
        "queue_candidate_id": queue_row["candidate_id"],
        "queue_global_order": queue_row["global_queue_order"],
        "packet_dir": rel(rubric_path.parent),
        "perspective_gold_adjudication": rel(gold_path),
        "rubric_review": rel(rubric_path),
        "anti_cheat_review": rel(anti_path),
        "reviewer_id": "codex-gpt5-ai-review",
    }


def main() -> None:
    queue_rows = [row for row in load_jsonl(QUEUE_JSONL) if str(row.get("language_family") or "") == "python"]
    queue_ids = {str(row.get("candidate_id") or ""): row for row in queue_rows}
    target_rows = {str(row.get("episode_id") or ""): row for row in load_jsonl(SOURCE_TARGETS)}
    packet_dirs = packet_mapping()

    admitted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for candidate_id, queue_row in sorted(queue_ids.items(), key=lambda item: int(item[1]["global_queue_order"])):
        packet_meta = packet_dirs[candidate_id]
        packet_dir = packet_meta["packet_dir"]
        preview_path = packet_meta["preview_path"]
        preview, rubric, anti, gold = require_packet(packet_dir, preview_path)

        blocked_reasons: list[str] = []
        claim_boundary = preview.get("claim_boundary") if isinstance(preview.get("claim_boundary"), dict) else {}
        if claim_boundary.get("supports_training_or_scoring_now") is not True:
            blocked_reasons.append("supports_training_or_scoring_now_false")
        if claim_boundary.get("gold_answers_fully_adjudicated") is not True:
            blocked_reasons.append("gold_answers_not_fully_adjudicated")
        if rubric.get("passed") is not True:
            blocked_reasons.append("rubric_not_passed")
        if anti.get("passed") is not True:
            blocked_reasons.append("anti_cheat_not_passed")
        if gold.get("bundle_gold_ready_for_eval") is not True:
            blocked_reasons.append("gold_not_ready")
        if len(preview.get("perspective_rows") or []) != 8:
            blocked_reasons.append("perspective_row_count_mismatch")
        if len(gold.get("perspective_gold_answers") or []) != 8:
            blocked_reasons.append("gold_answer_count_mismatch")

        if blocked_reasons:
            for reason in blocked_reasons:
                reason_counts[reason] += 1
            blocked_rows.append(
                {
                    "candidate_id": candidate_id,
                    "queue_global_order": queue_row["global_queue_order"],
                    "repo_id": queue_row.get("repo_id"),
                    "repo_family": queue_row.get("repo_family"),
                    "blocked_reasons": blocked_reasons,
                    "promotability": queue_row.get("promotability"),
                }
            )
            continue

        preview_out = admitted_preview(preview)
        rubric_out = admitted_rubric(rubric)
        anti_out = admitted_anti(anti)
        gold_out = admitted_gold(gold)

        target_row = target_rows[candidate_id]
        out_packet_dir = PACKETS_DIR / slugify(preview_out["bundle_id"])
        preview_out_path = out_packet_dir / "fresh_python_bundle_preview.json"
        rubric_path = out_packet_dir / "expert_maintainer_rubric_review.json"
        anti_path = out_packet_dir / "anti_cheat_review_card.json"
        gold_path = out_packet_dir / "perspective_gold_adjudication.json"

        write_json(preview_out_path, preview_out)
        write_json(rubric_path, rubric_out)
        write_json(anti_path, anti_out)
        write_json(gold_path, gold_out)
        for optional_name in [
            "expert_maintainer_recommendation_draft.json",
            "anti_cheat_recommendation_draft.json",
            "perspective_gold_recommendation_draft.json",
        ]:
            src = packet_dir / optional_name
            if src.exists():
                write_json(out_packet_dir / optional_name, load_json(src))

        abstain_count, non_abstain_count = count_gold_kinds(gold_out)
        root_record = build_root_record(
            preview=preview_out,
            rubric_path=rubric_path,
            anti_path=anti_path,
            gold_path=gold_path,
            abstain_count=abstain_count,
            non_abstain_count=non_abstain_count,
            queue_row=queue_row,
        )
        root_rows.append(root_record)
        admitted_rows.append(
            {
                "bundle_id": preview_out["bundle_id"],
                "queue_candidate_id": candidate_id,
                "queue_global_order": queue_row["global_queue_order"],
                "repo_id": root_record["repo_id"],
                "repo_family": root_record["repo_family"],
                "language_family": "python",
                "selected_tests_count": int(target_row.get("selected_tests_count") or 0),
                "train_support_only": True,
                "same_surface_eval_admissible": False,
                "strict_eval_eligible": False,
                "paths": {
                    "packet_dir": rel(out_packet_dir),
                    "preview_bundle": rel(preview_out_path),
                    "rubric_review": rel(rubric_path),
                    "anti_cheat_review": rel(anti_path),
                    "perspective_gold_adjudication": rel(gold_path),
                },
                "claim_boundary": [
                    "Admitted for queue-aligned reviewed train-support use only.",
                    "Not admitted for same-surface comparison or strict heldout headline claims.",
                    "Selected directly from the stage10810 multilingual queue.",
                ],
            }
        )

    write_jsonl(ROOT_MANIFEST_JSONL, root_rows)
    write_json(
        ADMITTED_JSON,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "decision_boundary": "Admit only queue-selected Python verifier reviewed bundles that are already fully adjudicated and support training now.",
            "metrics": {
                "admitted_bundles": len(admitted_rows),
                "blocked_bundles": len(blocked_rows),
                "admitted_language_counts": {"python": len(admitted_rows)} if admitted_rows else {},
                "blocked_reason_counts": dict(sorted(reason_counts.items())),
            },
            "row_count": len(admitted_rows),
            "rows": admitted_rows,
        },
    )
    write_json(
        BLOCKED_JSON,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "row_count": len(blocked_rows),
            "rows": blocked_rows,
        },
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "decision": "python_queue_selected_packets_admitted_when_geometry_complete",
        "claim_scope": [
            "Admit the queue-selected Python verifier packets that are already fully adjudicated and scoreable.",
            "Keep scaffold-only geometry-upgrade packets blocked until real verifier geometry and gold adjudication exist.",
            "Produce a queue-aligned Python reviewed-root manifest for the next multilingual support refresh.",
        ],
        "headline_findings": [
            f"Admitted {len(admitted_rows)} queue-selected Python bundles for reviewed train-support use.",
            f"Blocked {len(blocked_rows)} queue-selected Python bundles that are still scaffold-only or missing refreshed gold geometry.",
            "The Python lane now distinguishes honest reviewed support from unfinished verifier-geometry scaffolds instead of mixing them together.",
        ],
        "source_artifacts": {
            "queue": rel(QUEUE_JSONL),
            "source_targets": rel(SOURCE_TARGETS),
        },
        "output_files": {
            "summary_json": rel(SUMMARY_JSON),
            "admitted_manifest_json": rel(ADMITTED_JSON),
            "blocked_manifest_json": rel(BLOCKED_JSON),
            "root_manifest_jsonl": rel(ROOT_MANIFEST_JSONL),
            "review_packets_dir": rel(PACKETS_DIR),
        },
        "metrics": {
            "selected_queue_bundles": len(queue_rows),
            "admitted_bundle_count": len(admitted_rows),
            "blocked_bundle_count": len(blocked_rows),
            "repo_family_counts": dict(sorted(Counter(row["repo_family"] for row in root_rows).items())),
            "selected_test_anchor_count": sum(1 for row in root_rows if row["selected_test_anchor"]),
        },
        "next_best_steps": [
            "Refresh the reviewed multilingual support package from this queue-aligned Python admitted inventory.",
            "Keep the blocked agentkernel geometry-upgrade packet out of train-support until real multi-test verifier evidence is attached.",
            "Continue with the Rust citation lane after the Python support refresh is generated.",
        ],
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
