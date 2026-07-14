#!/usr/bin/env python3
"""Materialize fresh-root successor/reviewed rows into a joinable package.

This stage converts the stage11013 build-set inventory into prompt-visible,
quality-labeled records that downstream dataset builders can consume directly.
It does not pretend every row is scoreable now: Python/C++ successor lanes
carry review status and promotability flags, while Rust reviewed packets expose
their adjudicated perspective answers.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage11014_fresh_root_materialized_package"
BUILD_ROWS_PATH = ROOT / "runs/local/artifacts/stage11013_fresh_root_build_set/fresh_root_build_rows.jsonl"
SUCCESSOR_PACKET_PATH = ROOT / "runs/local/artifacts/stage10110_real_session_shortcut_safe_successor_packet/real_session_shortcut_safe_successor_packet.jsonl"
SUCCESSOR_REVIEW_INDEX_PATH = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/real_session_successor_review_packets.jsonl"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def slugify_row_id(row_id: str) -> str:
    parts = row_id.split("::")
    if len(parts) < 2:
        return row_id.replace(":", "_")
    episode = parts[1]
    prefix = episode[:48]
    digest = abs(hash(row_id)) & 0xFFFFFFFFFFFFFFFF
    return f"stage10110__{prefix}___{digest:016x}"


def derive_view(record: dict[str, Any]) -> dict[str, Any]:
    hidden = record.get("hidden_metadata") or {}
    prompt = record.get("prompt_surface") or {}
    candidates = prompt.get("candidate_choices") or []
    return {
        "task_observation": prompt.get("task_observation"),
        "return_protocol": prompt.get("return_protocol"),
        "visible_evidence_count": len(prompt.get("visible_evidence") or []),
        "visible_evidence": prompt.get("visible_evidence") or [],
        "candidate_count": len(candidates),
        "candidate_choices": [
            {
                "candidate_id": c.get("candidate_id"),
                "snippet_preview": c.get("snippet_preview"),
            }
            for c in candidates
        ],
        "selected_tests": hidden.get("selected_tests") or [],
        "candidate_geometry_tags": hidden.get("candidate_geometry_tags") or [],
        "raw_change_paths_withheld_from_prompt": hidden.get("raw_change_paths_withheld_from_prompt"),
        "redacted_candidates": hidden.get("redacted_candidates") or [],
    }


def classify_successor_usage(
    build_row: dict[str, Any],
    anti_cheat: dict[str, Any] | None,
    rubric: dict[str, Any] | None,
) -> tuple[str, bool, list[str]]:
    issues: list[str] = []
    lane = build_row.get("build_lane")
    selected_tests = build_row.get("selected_tests_count") or 0
    if anti_cheat is None:
        issues.append("missing_anti_cheat_card")
    elif anti_cheat.get("status") != "completed":
        issues.append(f"anti_cheat_status={anti_cheat.get('status')}")
    elif anti_cheat.get("passed") is not True:
        issues.append("anti_cheat_not_passed")

    if rubric is None:
        issues.append("missing_expert_rubric")
    elif rubric.get("status") != "completed":
        issues.append(f"rubric_status={rubric.get('status')}")
    elif rubric.get("passed") is not True:
        issues.append("rubric_not_passed")

    if lane == "python_fresh_successor_salvage":
        if selected_tests <= 0:
            issues.append("missing_selected_tests")
        usage = "fresh_candidate_needs_adjudication" if issues else "strict_candidate"
        promotable = not issues
        return usage, promotable, issues

    if lane == "cpp_successor_salvage":
        if selected_tests == 0:
            issues.append("no_selected_tests_abstention_only")
        usage = "abstention_or_support_only"
        promotable = False
        return usage, promotable, issues

    if lane == "web_support_only_successor":
        issues.append("web_overlap_support_only")
        return "support_only_overlap", False, issues

    issues.append("unknown_successor_lane")
    return "quarantine", False, issues


def rust_perspective_records(build_row: dict[str, Any]) -> list[dict[str, Any]]:
    packet_dir = ROOT / build_row["packet_dir"]
    gold = read_json(packet_dir / "perspective_gold_adjudication.json")
    answers = gold.get("perspective_gold_answers") or []
    bundle_id = gold.get("bundle_id")
    rows: list[dict[str, Any]] = []
    for answer in answers:
        perspective = answer.get("perspective")
        usage = "fresh_rust_scoreable"
        promotable = perspective in {"evidence_citation", "symptom_localization", "verifier_outcome"}
        if answer.get("abstention_option_required"):
            usage = "fresh_rust_abstention_capable"
        rows.append(
            {
                "materialized_id": f"{bundle_id}::{perspective}",
                "source_kind": "reviewed_rust_perspective",
                "language_family": build_row.get("language_family"),
                "repo_id": build_row.get("repo_id"),
                "build_lane": build_row.get("build_lane"),
                "bundle_id": bundle_id,
                "packet_dir": build_row.get("packet_dir"),
                "perspective": perspective,
                "gold_answer_kind": answer.get("gold_answer_kind"),
                "gold_answer_value": answer.get("gold_answer_value"),
                "candidate_paths": answer.get("candidate_paths") or [],
                "selected_tests": answer.get("selected_tests") or [],
                "visible_evidence_keys": answer.get("visible_evidence_keys") or [],
                "reviewer_rationale": answer.get("reviewer_rationale"),
                "abstention_option_required": bool(answer.get("abstention_option_required")),
                "usage_class": usage,
                "promotable_now": promotable,
                "quality_issues": [],
                "target_contract": build_row.get("target_contract"),
                "required_gates": build_row.get("required_gates") or [],
            }
        )
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    build_rows = read_jsonl(BUILD_ROWS_PATH)
    successor_packets = {
        row["row_id"]: row
        for row in read_jsonl(SUCCESSOR_PACKET_PATH)
        if "row_id" in row
    }
    review_index = {
        row["row_id"]: row
        for row in read_jsonl(SUCCESSOR_REVIEW_INDEX_PATH)
        if "row_id" in row
    }

    materialized_rows: list[dict[str, Any]] = []
    source_kind_counts = Counter()
    usage_counts = Counter()
    promotable_counts = Counter()
    language_counts = Counter()

    for build_row in build_rows:
        lane = build_row.get("build_lane")
        if lane == "rust_fresh_review_packet_materialization":
            rust_rows = rust_perspective_records(build_row)
            for row in rust_rows:
                materialized_rows.append(row)
                source_kind_counts[row["source_kind"]] += 1
                usage_counts[row["usage_class"]] += 1
                promotable_counts["promotable" if row["promotable_now"] else "not_promotable"] += 1
                language_counts[row["language_family"]] += 1
            continue

        row_id = build_row["row_id"]
        packet = successor_packets[row_id]
        review = review_index.get(row_id) or {}
        anti_cheat = read_json(ROOT / review["anti_cheat_review_card"]) if review.get("anti_cheat_review_card") else None
        rubric = read_json(ROOT / review["expert_maintainer_rubric_review"]) if review.get("expert_maintainer_rubric_review") else None
        usage_class, promotable, quality_issues = classify_successor_usage(build_row, anti_cheat, rubric)
        materialized = {
            "materialized_id": row_id,
            "source_kind": "successor_packet_row",
            "language_family": build_row.get("language_family"),
            "repo_id": build_row.get("repo_id"),
            "build_lane": lane,
            "row_id": row_id,
            "successor_template": packet.get("successor_template"),
            "packet_view": derive_view(packet),
            "review_packet_dir": review.get("packet_dir"),
            "anti_cheat_status": anti_cheat.get("status") if anti_cheat else None,
            "anti_cheat_passed": anti_cheat.get("passed") if anti_cheat else None,
            "anti_cheat_reviewer_notes": anti_cheat.get("reviewer_notes") if anti_cheat else None,
            "rubric_status": rubric.get("status") if rubric else None,
            "rubric_passed": rubric.get("passed") if rubric else None,
            "rubric_gold_label_slot": rubric.get("gold_label_slot") if rubric else None,
            "usage_class": usage_class,
            "promotable_now": promotable,
            "quality_issues": quality_issues,
            "target_contract": build_row.get("target_contract"),
            "required_gates": build_row.get("required_gates") or [],
            "selected_tests_count": build_row.get("selected_tests_count"),
            "shortcut_risk_score": build_row.get("shortcut_risk_score"),
        }
        materialized_rows.append(materialized)
        source_kind_counts[materialized["source_kind"]] += 1
        usage_counts[materialized["usage_class"]] += 1
        promotable_counts["promotable" if promotable else "not_promotable"] += 1
        language_counts[materialized["language_family"]] += 1

    summary = {
        "stage_id": "stage11014_fresh_root_materialized_package",
        "source_stage": "stage11013_fresh_root_build_set",
        "materialized_record_count": len(materialized_rows),
        "source_kind_counts": dict(source_kind_counts),
        "usage_class_counts": dict(usage_counts),
        "promotable_counts": dict(promotable_counts),
        "language_counts": dict(language_counts),
        "notes": [
            "Python successor rows are verifier-anchored fresh candidates but still carry pending expert rubric status in the successor review tree.",
            "C/C++ successor rows are abstention-capable support candidates because selected-test anchors are absent.",
            "Rust reviewed packets expose adjudicated perspective answers and can materialize into fresh evidence/localization rows immediately.",
            "Web remains support-only until a pure-web selected-test family exists.",
        ],
    }

    (ARTIFACT_DIR / "fresh_root_materialized_rows.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in materialized_rows) + "\n"
    )
    (ARTIFACT_DIR / "fresh_root_materialized_package.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n"
    )


if __name__ == "__main__":
    main()
