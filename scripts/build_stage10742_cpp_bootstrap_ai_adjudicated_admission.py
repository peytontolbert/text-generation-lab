#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10742
NAME = "stage10742_cpp_bootstrap_ai_adjudicated_admission"
OUT_DIR = ARTIFACTS / NAME
PACKETS_DIR = OUT_DIR / "review_packets"
SUMMARY_JSON = OUT_DIR / "cpp_bootstrap_ai_adjudicated_admission.json"
ADMITTED_JSON = OUT_DIR / "cpp_bootstrap_ai_adjudicated_admitted_manifest.json"
BLOCKED_JSON = OUT_DIR / "cpp_bootstrap_ai_adjudicated_blocked_manifest.json"
ROOT_MANIFEST_JSONL = OUT_DIR / "cpp_bootstrap_ai_adjudicated_root_manifest.jsonl"

SOURCE_SUMMARY = ARTIFACTS / "stage10741_cpp_bootstrap_review_packet_scaffolds" / "cpp_bootstrap_review_packet_scaffolds.json"
SOURCE_MANIFEST = ARTIFACTS / "stage10741_cpp_bootstrap_review_packet_scaffolds" / "cpp_bootstrap_review_packet_scaffold_manifest.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def source_packet_dir(packet_row: dict[str, Any]) -> Path:
    return ROOT / packet_row["packet_dir"]


def require_packet(packet_row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    preview = load_json(ROOT / packet_row["preview_bundle"])
    rubric = load_json(ROOT / packet_row["rubric_review"])
    anti = load_json(ROOT / packet_row["anti_cheat_review"])
    gold = load_json(ROOT / packet_row["perspective_gold_adjudication"])
    return preview, rubric, anti, gold


def admitted_preview(bundle: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(bundle))
    out["claim_boundary"]["preview_only"] = False
    out["claim_boundary"]["gold_answers_fully_adjudicated"] = True
    out["claim_boundary"]["supports_training_or_scoring_now"] = True
    out["claim_boundary"]["requires_bundle_admission_before_scoring"] = False
    out["claim_boundary"]["train_support_only_admitted"] = True
    out.setdefault("discovery_metadata", {})
    out["discovery_metadata"]["train_support_only_admitted"] = True
    out["discovery_metadata"]["admitted_by_stage"] = STAGE
    out["discovery_metadata"]["supports_promotable_packet"] = False
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
    out["decision_rationale"] = (
        "Admit this bootstrap execution-backed C/C++ bundle for reviewed train-support use. "
        "The packet has AI-completed rubric, anti-cheat, and gold adjudication, but it is not yet "
        "authorized as headline same-surface strict eval."
    )
    notes = list(out.get("reviewer_notes") or [])
    notes.append("Train-support admission only. Do not treat this packet as strict heldout frontier evidence yet.")
    out["reviewer_notes"] = notes
    return out


def admitted_anti(anti: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(anti))
    out["status"] = "completed"
    out["passed"] = True
    out["admissible_for_same_surface_comparison"] = False
    out["train_support_only"] = True
    out["ready_for_bundle_admission_review"] = False
    out["decision_rationale"] = (
        "Admit for reviewed train-support use. Bootstrap execution-backed evidence and AI adjudication are sufficient for support and training, "
        "but the packet still requires a later fairness gate before any same-surface Gemma headline claim."
    )
    notes = list(out.get("reviewer_notes") or [])
    notes.append("Not same-surface admissible. Candidate-order and fairness checks remain a later promotion gate.")
    out["reviewer_notes"] = notes
    return out


def admitted_gold(gold: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(gold))
    out["status"] = "completed"
    out["bundle_gold_ready_for_eval"] = True
    out["train_support_only"] = True
    out["decision_rationale"] = (
        "AI maintainer gold answers admitted for train-support use on a bootstrap execution-backed C/C++ root. "
        "The packet is scoreable for internal support and training workflows but not a promoted same-surface frontier row."
    )
    guidance = list(out.get("reviewer_guidance") or [])
    guidance.extend(
        [
            "This packet is admitted for reviewed train-support use only.",
            "Keep it out of strict headline same-surface comparison until a later bundle-fairness gate admits it explicitly.",
        ]
    )
    out["reviewer_guidance"] = guidance
    return out


def build_root_record(
    *,
    preview: dict[str, Any],
    rubric_path: Path,
    anti_path: Path,
    gold_path: Path,
    abstain_count: int,
    non_abstain_count: int,
) -> dict[str, Any]:
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
        "language_family": "c_cpp",
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
        "claim_notes": [
            "bootstrap_execution_backed_cpp_bundle",
            "ai_adjudicated",
            "train_support_only_admitted",
            "not_admissible_for_same_surface_comparison",
        ],
        "packet_dir": rel(rubric_path.parent),
        "perspective_gold_adjudication": rel(gold_path),
        "rubric_review": rel(rubric_path),
        "anti_cheat_review": rel(anti_path),
        "reviewer_id": "codex-gpt5-ai-review",
    }


def main() -> None:
    source_summary = load_json(SOURCE_SUMMARY)
    if source_summary.get("passed") is not True:
        raise SystemExit("stage10741_not_passed")

    source_manifest = load_json(SOURCE_MANIFEST)
    source_rows = list(source_manifest.get("packets") or [])

    admitted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for packet_row in source_rows:
        bundle_id = str(packet_row.get("bundle_id") or "")
        try:
            preview, rubric, anti, gold = require_packet(packet_row)
        except Exception:
            reason_counts["packet_read_failure"] += 1
            blocked_rows.append({"bundle_id": bundle_id, "blocked_reasons": ["packet_read_failure"]})
            continue

        blocked_reasons: list[str] = []
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
                    "bundle_id": bundle_id,
                    "repo_id": packet_row.get("repo_id"),
                    "repo_family": packet_row.get("repo_family"),
                    "blocked_reasons": blocked_reasons,
                }
            )
            continue

        preview_out = admitted_preview(preview)
        rubric_out = admitted_rubric(rubric)
        anti_out = admitted_anti(anti)
        gold_out = admitted_gold(gold)

        src_packet_dir = source_packet_dir(packet_row)
        packet_dir = PACKETS_DIR / slugify(bundle_id)
        preview_path = packet_dir / "fresh_cpp_bundle_preview.json"
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
        anti_path = packet_dir / "anti_cheat_review_card.json"
        gold_path = packet_dir / "perspective_gold_adjudication.json"

        write_json(preview_path, preview_out)
        write_json(rubric_path, rubric_out)
        write_json(packet_dir / "expert_maintainer_recommendation_draft.json", load_json(src_packet_dir / "expert_maintainer_recommendation_draft.json"))
        write_json(anti_path, anti_out)
        write_json(packet_dir / "anti_cheat_recommendation_draft.json", load_json(src_packet_dir / "anti_cheat_recommendation_draft.json"))
        write_json(gold_path, gold_out)
        write_json(packet_dir / "perspective_gold_recommendation_draft.json", load_json(src_packet_dir / "perspective_gold_recommendation_draft.json"))

        abstain_count, non_abstain_count = count_gold_kinds(gold_out)
        root_record = build_root_record(
            preview=preview_out,
            rubric_path=rubric_path,
            anti_path=anti_path,
            gold_path=gold_path,
            abstain_count=abstain_count,
            non_abstain_count=non_abstain_count,
        )
        root_rows.append(root_record)
        admitted_rows.append(
            {
                "bundle_id": bundle_id,
                "repo_id": root_record["repo_id"],
                "repo_family": root_record["repo_family"],
                "language_family": "c_cpp",
                "train_support_only": True,
                "same_surface_eval_admissible": False,
                "strict_eval_eligible": False,
                "paths": {
                    "packet_dir": rel(packet_dir),
                    "preview_bundle": rel(preview_path),
                    "rubric_review": rel(rubric_path),
                    "anti_cheat_review": rel(anti_path),
                    "perspective_gold_adjudication": rel(gold_path),
                },
                "claim_boundary": [
                    "Admitted for reviewed train-support use only.",
                    "Not admitted for same-surface comparison or strict heldout headline claims.",
                    "Bootstrap execution-backed C/C++ materialization lane is now reusable in the next v2.7 support package.",
                ],
            }
        )

    write_jsonl(ROOT_MANIFEST_JSONL, root_rows)

    admitted_manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision_boundary": "Admit only AI-completed bootstrap execution-backed C/C++ reviewed bundles, and admit them for train-support use only.",
        "metrics": {
            "admitted_bundles": len(admitted_rows),
            "blocked_bundles": len(blocked_rows),
            "admitted_language_counts": {"c_cpp": len(admitted_rows)} if admitted_rows else {},
            "blocked_reason_counts": dict(sorted(reason_counts.items())),
        },
        "row_count": len(admitted_rows),
        "rows": admitted_rows,
    }
    blocked_manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "row_count": len(blocked_rows),
        "rows": blocked_rows,
    }
    write_json(ADMITTED_JSON, admitted_manifest)
    write_json(BLOCKED_JSON, blocked_manifest)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "decision": "cpp_bootstrap_execution_backed_packets_admitted_for_train_support_only",
        "claim_scope": [
            "Promote the 5 stage10741 bootstrap C/C++ review packet scaffolds into admitted reviewed bundles for train-support use.",
            "Keep same-surface and strict-heldout promotion boundaries explicit so these roots improve v2.7 support supply without creating an overclaim.",
            "Produce a root manifest that the next multilingual reviewed support package can ingest directly.",
        ],
        "headline_findings": [
            f"Admitted {len(admitted_rows)} bootstrap execution-backed C/C++ bundles for reviewed train-support use.",
            "All admitted bundles remain non-promotable for same-surface comparison until a later fairness and split gate upgrades them.",
            "The clean bootstrap C/C++ root-materialization lane now produces reusable reviewed-root inventory instead of isolated scaffold packets.",
        ],
        "output_files": {
            "summary_json": rel(SUMMARY_JSON),
            "admitted_manifest_json": rel(ADMITTED_JSON),
            "blocked_manifest_json": rel(BLOCKED_JSON),
            "root_manifest_jsonl": rel(ROOT_MANIFEST_JSONL),
            "review_packets_dir": rel(PACKETS_DIR),
        },
        "metrics": {
            "admitted_bundle_count": len(admitted_rows),
            "blocked_bundle_count": len(blocked_rows),
            "repo_family_counts": dict(sorted(Counter(row["repo_family"] for row in root_rows).items())),
            "selected_test_anchor_count": sum(1 for row in root_rows if row["selected_test_anchor"]),
        },
        "next_best_steps": [
            "Merge these 5 admitted C/C++ bundles into the reviewed multilingual v2.7 support inventory.",
            "Use the same admission pattern on bootstrap execution-backed Python and Rust lanes as fresh materialized roots arrive.",
            "Keep same-surface promotion separate: these bundles should strengthen training and support supply before any new headline 100M-vs-Gemma claim.",
        ],
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
