#!/usr/bin/env python3
"""Audit residual review packets for repairable maintainer rows.

This stage is intentionally non-training.  It records which blocked residual
packets have enough adjudicated geometry to become new support rows, and which
ones still need source/test materialization before they can be trusted.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11143_residual_packet_repair_audit"

PY_PACKET_DIR = (
    ROOT
    / "runs/local/artifacts/stage10756_python_verifier_geometry_upgrade_scaffolds/review_packets"
)
RUST_PACKET_DIR = (
    ROOT / "runs/local/artifacts/stage10674_rust_fresh_review_packet_scaffolds/review_packets"
)
BASE_PACKAGE = (
    ROOT
    / "runs/local/artifacts/stage11131_evidence_item_support_package/evidence_item_support_package.json"
)

PERSPECTIVES_REQUIRED_FOR_VERIFIER_REPAIR = {
    "evidence_citation",
    "verifier_outcome",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def compact(value: Any, limit: int = 240) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[: limit - 3] + "..."
    if isinstance(value, list):
        return [compact(v, limit) for v in value[:8]]
    if isinstance(value, dict):
        return {k: compact(v, limit) for k, v in list(value.items())[:12]}
    return value


def packet_files(packet: Path, language: str) -> dict[str, Path]:
    preview_name = "fresh_python_bundle_preview.json" if language == "python" else "fresh_rust_bundle_preview.json"
    return {
        "preview": packet / preview_name,
        "gold": packet / "perspective_gold_adjudication.json",
        "anti_cheat": packet / "anti_cheat_review_card.json",
        "rubric": packet / "expert_maintainer_rubric_review.json",
    }


def analyze_packet(packet: Path, language: str) -> dict[str, Any]:
    files = packet_files(packet, language)
    missing = [name for name, path in files.items() if not path.exists()]
    preview = load_json(files["preview"]) if files["preview"].exists() else {}
    gold = load_json(files["gold"]) if files["gold"].exists() else {}
    anti = load_json(files["anti_cheat"]) if files["anti_cheat"].exists() else {}
    rubric = load_json(files["rubric"]) if files["rubric"].exists() else {}

    answers = gold.get("perspective_gold_answers") or []
    completed_answers = [
        a
        for a in answers
        if a.get("gold_answer_kind")
        and not str(a.get("gold_answer_kind")).startswith("TODO")
        and a.get("gold_answer_value")
        and not str(a.get("gold_answer_value")).startswith("TODO")
    ]
    completed_by_perspective = {a.get("perspective"): a for a in completed_answers}
    missing_required = sorted(
        PERSPECTIVES_REQUIRED_FOR_VERIFIER_REPAIR - set(completed_by_perspective)
    )
    selected_tests = preview.get("selected_tests") or []
    candidate_paths = preview.get("candidate_paths") or []
    for answer in answers:
        if not selected_tests and answer.get("selected_tests"):
            selected_tests = answer.get("selected_tests") or []
        if not candidate_paths and answer.get("candidate_paths"):
            candidate_paths = answer.get("candidate_paths") or []
    evidence_blob = json.dumps(preview.get("maintainer_visible_evidence", {}), sort_keys=True)
    placeholder_evidence_count = evidence_blob.count("TODO_")
    anti_passed = bool(anti.get("passed"))
    rubric_passed = bool(rubric.get("passed")) if rubric else False

    blockers: list[str] = []
    if missing:
        blockers.append("missing_review_files:" + ",".join(missing))
    if not selected_tests:
        blockers.append("missing_selected_tests")
    if len(candidate_paths) < 2:
        blockers.append("insufficient_candidate_paths")
    if missing_required:
        blockers.append("missing_required_gold:" + ",".join(missing_required))
    if placeholder_evidence_count:
        blockers.append(f"placeholder_visible_evidence:{placeholder_evidence_count}")
    if not anti_passed:
        blockers.append("anti_cheat_not_passed")
    if not rubric_passed:
        blockers.append("rubric_not_passed")
    if str(gold.get("status", "")).startswith("pending"):
        blockers.append("gold_status_pending")

    repairable_after_review = (
        not missing
        and bool(selected_tests)
        and len(candidate_paths) >= 2
        and not missing_required
        and placeholder_evidence_count == 0
        and rubric_passed
    )
    admitted_now = repairable_after_review and anti_passed and not str(gold.get("status", "")).startswith("pending")

    return {
        "packet_name": packet.name,
        "language_family": language,
        "bundle_id": preview.get("bundle_id") or gold.get("bundle_id"),
        "repo_id": preview.get("repo_id") or gold.get("repo_id"),
        "selected_tests_count": len(selected_tests),
        "candidate_paths_count": len(candidate_paths),
        "gold_status": gold.get("status"),
        "anti_cheat_status": anti.get("status"),
        "anti_cheat_passed": anti_passed,
        "rubric_status": rubric.get("status") if rubric else "missing",
        "rubric_passed": rubric_passed,
        "placeholder_visible_evidence_count": placeholder_evidence_count,
        "completed_gold_perspectives": sorted(k for k in completed_by_perspective if k),
        "missing_required_gold_perspectives": missing_required,
        "repairable_after_review": repairable_after_review,
        "admitted_now": admitted_now,
        "blockers": blockers,
        "recommended_next_action": recommend_action(
            language=language,
            selected_tests=selected_tests,
            candidate_paths=candidate_paths,
            missing_required=missing_required,
            placeholder_evidence_count=placeholder_evidence_count,
            anti_passed=anti_passed,
            rubric_passed=rubric_passed,
            gold_status=gold.get("status"),
        ),
        "gold_answer_summaries": [
            {
                "perspective": a.get("perspective"),
                "gold_answer_kind": a.get("gold_answer_kind"),
                "gold_answer_value": compact(a.get("gold_answer_value")),
                "reviewer_rationale": compact(a.get("reviewer_rationale")),
            }
            for a in completed_answers
        ],
    }


def recommend_action(
    *,
    language: str,
    selected_tests: list[Any],
    candidate_paths: list[Any],
    missing_required: list[str],
    placeholder_evidence_count: int,
    anti_passed: bool,
    rubric_passed: bool,
    gold_status: Any,
) -> str:
    if not selected_tests:
        return "materialize_selected_test_or_verifier_anchor"
    if len(candidate_paths) < 2:
        return "materialize_competing_candidate_paths"
    if missing_required:
        return "complete_gold_for_" + "_and_".join(missing_required)
    if placeholder_evidence_count:
        return "materialize_real_visible_snippets_before_signoff"
    if not rubric_passed:
        return "complete_expert_rubric_review"
    if not anti_passed or str(gold_status or "").startswith("pending"):
        if language == "python":
            return "complete_geometry_anti_cheat_signoff_then_emit_train_support_rows"
        return "complete_materialization_anti_cheat_signoff"
    return "admit_for_row_materialization"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    packets: list[dict[str, Any]] = []
    for language, base in [("python", PY_PACKET_DIR), ("rust", RUST_PACKET_DIR)]:
        if not base.exists():
            continue
        for packet in sorted(p for p in base.iterdir() if p.is_dir()):
            packets.append(analyze_packet(packet, language))

    blocker_counts = Counter()
    action_counts = Counter()
    for packet in packets:
        blocker_counts.update(packet["blockers"])
        action_counts[packet["recommended_next_action"]] += 1

    summary = {
        "stage": 11143,
        "stage_name": "residual_packet_repair_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "python_packets": str(PY_PACKET_DIR.relative_to(ROOT)),
            "rust_packets": str(RUST_PACKET_DIR.relative_to(ROOT)),
            "base_package": str(BASE_PACKAGE.relative_to(ROOT)),
        },
        "metrics": {
            "packets_total": len(packets),
            "admitted_now": sum(1 for p in packets if p["admitted_now"]),
            "repairable_after_review": sum(1 for p in packets if p["repairable_after_review"]),
            "by_language": dict(Counter(p["language_family"] for p in packets)),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "recommended_action_counts": dict(sorted(action_counts.items())),
        },
        "decision": "no_training_run_requested",
        "next_best_step": (
            "Materialize real prompt-visible snippets for the code_assist Python "
            "geometry packet before anti-cheat signoff; Rust packets require "
            "selected-test or verifier-anchor materialization before row generation."
        ),
        "outputs": {
            "packet_audit_jsonl": str((OUT_DIR / "packet_repair_audit.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "residual_packet_repair_audit.json").relative_to(ROOT)),
        },
    }

    with (OUT_DIR / "packet_repair_audit.jsonl").open("w") as f:
        for packet in packets:
            f.write(json.dumps(packet, sort_keys=True) + "\n")
    (OUT_DIR / "residual_packet_repair_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
