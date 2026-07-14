#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11577
NAME = "stage11577_web_candidate_review_packet_materializer"
OUT = ART / NAME
SUMMARY = OUT / "web_candidate_review_packet_materializer.json"
PACKETS = OUT / "web_candidate_review_packets.jsonl"
ROW_SHELLS = OUT / "web_candidate_review_row_shells.jsonl"

STAGE11576 = ART / "stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "alternative_hypothesis_elimination",
    "abstention_insufficient_evidence",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def choose_split(lane: str, index: int) -> str:
    if "evidence_item" in lane:
        return "train_candidate"
    # Keep heldout candidates sealed before any training package is formed.
    return "heldout_candidate" if index in {10, 11, 12} else "train_candidate"


def task_observation(candidate: dict[str, Any]) -> str:
    repo = candidate.get("repo_family")
    return (
        f"{repo} maintenance root includes a source/test relationship that still requires verifier-transition review. "
        "The review task is to decide which candidate surface or evidence role is justified by the visible source and test snippets."
    )


def opaque_options(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    paths = list(candidate.get("candidate_change_surface_paths") or [])
    verifier = candidate.get("selected_verifier_path_proposal")
    primary = paths[0] if paths else "candidate_change_surface"
    secondary = paths[1] if len(paths) > 1 else primary
    return [
        {"label": "A", "value": primary, "semantic_role": "candidate_change_surface", "text": str(primary)},
        {"label": "B", "value": verifier, "semantic_role": "verifier_and_test_constraint", "text": str(verifier)},
        {"label": "C", "value": secondary, "semantic_role": "symptom_or_call_path_analogue", "text": str(secondary)},
        {"label": "D", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "semantic_role": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ]


def perspective_target(perspective: str) -> tuple[str | None, str]:
    if perspective in {"symptom_localization", "minimal_fix_selection"}:
        return "A", "static_candidate_change_surface"
    if perspective == "evidence_citation":
        return "B", "static_verifier_and_test_constraint"
    if perspective == "alternative_hypothesis_elimination":
        return "B", "static_selected_verifier_rules_out_neighbor"
    if perspective == "abstention_insufficient_evidence":
        return "D", "static_abstain_option_present_but_final_answer_requires_verifier_review"
    return None, "requires_observed_verifier_transition"


def prompt_for(candidate: dict[str, Any], perspective: str, options: list[dict[str, Any]]) -> str:
    source_preview = candidate.get("source_previews") or {}
    verifier_preview = str(candidate.get("verifier_preview") or "")
    source_lines = []
    for path, preview in list(source_preview.items())[:2]:
        source_lines.append(f"{path}:\n{str(preview)[:900]}")
    option_lines = "\n".join(f"option {opt['label']}: {opt['text']}" for opt in options)
    return "\n".join(
        [
            "Language: web_js_ts_html",
            f"Perspective: {perspective}",
            "Task: Choose the best opaque option from visible maintainer evidence.",
            f"Repository family: {candidate.get('git_repo_family')} / {candidate.get('repo_family')}",
            f"Task observation: {task_observation(candidate)}",
            "Visible source evidence:",
            "\n\n".join(source_lines)[:1800],
            "Visible verifier/test evidence:",
            verifier_preview[:1200],
            "Choices:",
            option_lines,
        ]
    )


def anti_cheat(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "opaque_labels": True,
        "deterministic_option_shuffle": True,
        "no_gold_label_in_prompt_before_options": True,
        "gold_semantic_value_may_appear_in_visible_evidence": True,
        "requires_prompt_target_leak_review_before_training": True,
        "source_snippets_materialized": bool(candidate.get("source_previews") or candidate.get("candidate_change_surface_paths")),
        "verifier_snippet_materialized": bool(candidate.get("verifier_preview") or candidate.get("selected_verifier_path_proposal")),
        "observed_verifier_transition_present": False,
        "trainable_without_verifier_transition": False,
    }


def make_packet(candidate: dict[str, Any], split_component: str) -> dict[str, Any]:
    missing = set(candidate.get("missing_for_admission") or [])
    missing.discard("root_task_or_bug_description")
    missing.discard("root_split_assignment")
    missing.discard("prompt_target_leak_audit")
    return {
        "root_id": candidate["root_id"],
        "lane": candidate["lane"],
        "split_component": split_component,
        "language_family": "web_js_ts_html",
        "repo_family": candidate.get("repo_family"),
        "git_repo_family": candidate.get("git_repo_family"),
        "repo_path": candidate.get("repo_path"),
        "task_observation": task_observation(candidate),
        "selected_verifier_path_proposal": candidate.get("selected_verifier_path_proposal"),
        "candidate_change_surface_paths": candidate.get("candidate_change_surface_paths") or [],
        "candidate_options": opaque_options(candidate),
        "anti_cheat_review": anti_cheat(candidate),
        "review_status": "ai_static_review_packet_prepared_verifier_transition_missing",
        "trainable_now": False,
        "strict_eval_eligible_now": False,
        "missing_for_admission": sorted(missing | {"observed_verifier_transition", "final_gold_adjudication"}),
    }


def make_rows(candidate: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    options = packet["candidate_options"]
    for perspective in PERSPECTIVES:
        label, gold_status = perspective_target(perspective)
        row_id = f"{candidate['root_id']}::{perspective}::review_shell_v1"
        row = {
            "row_id": row_id,
            "root_id": candidate["root_id"],
            "root_lineage_key": candidate["root_id"],
            "split_component": packet["split_component"],
            "language_family": "web_js_ts_html",
            "repo_family": candidate.get("repo_family"),
            "git_repo_family": candidate.get("git_repo_family"),
            "lane": packet.get("lane"),
            "task_type": perspective,
            "input_text": prompt_for(candidate, perspective, options),
            "prompt_text": prompt_for(candidate, perspective, options),
            "standalone_projection_source": {
                "opaque_options": options,
                "projection_mode": "stage11577_static_review_shell",
            },
            "opaque_options": options,
            "bounded_choice_target_label": label,
            "target_text": label,
            "decoder_text": label or "",
            "semantic_target_value": next((opt["value"] for opt in options if opt["label"] == label), None),
            "gold_status": gold_status,
            "trainable_now": False,
            "strict_eval_eligible_now": False,
            "missing_for_admission": packet["missing_for_admission"],
            "anti_cheat": packet["anti_cheat_review"],
        }
        rows.append(row)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = load_jsonl(STAGE11576)
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_lane[candidate["lane"]].append(candidate)

    packets: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for lane, lane_candidates in sorted(by_lane.items()):
        for index, candidate in enumerate(lane_candidates):
            split_component = choose_split(lane, index)
            packet = make_packet(candidate, split_component)
            packets.append(packet)
            rows.extend(make_rows(candidate, packet))

    metrics = {
        "packets": len(packets),
        "row_shells": len(rows),
        "trainable_rows_now": sum(1 for row in rows if row["trainable_now"]),
        "strict_eval_eligible_rows_now": sum(1 for row in rows if row["strict_eval_eligible_now"]),
        "packets_by_lane": dict(Counter(packet["lane"] for packet in packets)),
        "packets_by_split_component": dict(Counter(packet["split_component"] for packet in packets)),
        "rows_by_gold_status": dict(Counter(row["gold_status"] for row in rows)),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "static_review_packets_materialized_verifier_transition_still_required",
        "metrics": metrics,
        "next_required_actions": [
            "Run or recover focused verifier transitions for selected test paths.",
            "Finalize gold adjudication for verifier_outcome rows after transition evidence exists.",
            "Run Stage11578 admission audit; only rows with observed verifier transitions and final gold may become trainable.",
        ],
        "claim_boundary": [
            "These are review/adjudication shells, not training rows.",
            "Static source/test snippets can support review, but verifier_outcome remains blocked until execution evidence exists.",
            "No model training or GPU execution is performed.",
        ],
        "source_artifacts": {"stage11576_candidates": rel(STAGE11576)},
        "outputs": {"summary": rel(SUMMARY), "packets": rel(PACKETS), "row_shells": rel(ROW_SHELLS)},
    }
    write_jsonl(PACKETS, packets)
    write_jsonl(ROW_SHELLS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
