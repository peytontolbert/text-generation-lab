#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11530
NAME = "stage11530_web_new_family_materialization_packets"
OUT = ART / NAME
SUMMARY = OUT / "web_new_family_materialization_packets.json"
PACKETS = OUT / "web_new_family_root_packets.jsonl"
ROW_SHELLS = OUT / "web_new_family_perspective_row_shells.jsonl"

QUEUE = ART / "stage11529_web_materialization_queue/web_materialization_work_items.jsonl"

PRIORITY_FAMILIES = {"openclaw_clawhub", "dspy", "ai_town"}
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "patch_impact",
    "minimal_fix_selection",
    "abstention_insufficient_evidence",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_snippet(path: Path, max_lines: int = 80) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"path": str(path), "exists": False, "sha256": None, "line_start": None, "line_end": None, "text": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    preview = "\n".join(lines[:max_lines])
    return {
        "path": str(path),
        "exists": True,
        "sha256": sha_text(text),
        "line_start": 1 if lines else 0,
        "line_end": min(max_lines, len(lines)),
        "total_lines": len(lines),
        "text": preview,
    }


def choose_source(paths: list[str]) -> str | None:
    preferred_fragments = (
        "skills",
        "tokens",
        "app",
        "agent",
        "http",
        "schema",
    )
    for fragment in preferred_fragments:
        for path in paths:
            if fragment.lower() in path.lower() and not path.lower().endswith((".css", ".html")):
                return path
    return paths[0] if paths else None


def choose_verifier(paths: list[str]) -> str | None:
    for path in paths:
        lower = path.lower()
        if ".test." in lower or ".spec." in lower or lower.endswith(".test.ts") or lower.endswith(".test.js"):
            return path
    return paths[0] if paths else None


def option_set(item: dict[str, Any], selected_source: str | None, selected_verifier: str | None) -> list[dict[str, Any]]:
    source_paths = list(item.get("candidate_change_surface_paths") or [])
    verifier_paths = list(item.get("verifier_and_test_constraint_paths") or [])
    wrong_source = next((path for path in source_paths if path != selected_source), None)
    wrong_verifier = next((path for path in verifier_paths if path != selected_verifier), None)
    options = [
        {
            "label": "A",
            "semantic_role": "candidate_change_surface",
            "path": selected_source,
            "description": "Implementation or configuration surface most likely to be edited.",
        },
        {
            "label": "B",
            "semantic_role": "verifier_and_test_constraint",
            "path": selected_verifier,
            "description": "Test or verifier surface that constrains the expected behavior.",
        },
        {
            "label": "C",
            "semantic_role": "symptom_or_call_path_analogue",
            "path": wrong_source or selected_source,
            "description": "Nearby source/call-path evidence that may explain the symptom but is not automatically the edit target.",
        },
        {
            "label": "D",
            "semantic_role": "distractor_verifier_or_neighbor",
            "path": wrong_verifier or wrong_source or selected_verifier,
            "description": "Plausible neighboring test or source surface used as a hard negative.",
        },
        {
            "label": "E",
            "semantic_role": "abstain_insufficient_evidence",
            "path": None,
            "description": "Visible evidence is insufficient for a forced singleton decision.",
        },
    ]
    return [opt for opt in options if opt.get("path") or opt["semantic_role"] == "abstain_insufficient_evidence"]


def make_packet(item: dict[str, Any]) -> dict[str, Any]:
    repo = Path(str(item["repo_path"]))
    selected_source = choose_source(item.get("candidate_change_surface_paths") or [])
    selected_verifier = choose_verifier(item.get("verifier_and_test_constraint_paths") or [])
    source_snippets = {
        path: read_snippet(repo / path)
        for path in item.get("candidate_change_surface_paths") or []
    }
    verifier_snippets = {
        path: read_snippet(repo / path)
        for path in item.get("verifier_and_test_constraint_paths") or []
    }
    family = str(item.get("git_repo_family") or item.get("repo_family"))
    root_id = f"stage11530::{family}::{item.get('repo_family')}::root_candidate_v1"
    missing = []
    if not selected_source:
        missing.append("selected_changed_path")
    if not selected_verifier:
        missing.append("selected_verifier_path")
    if selected_source and not source_snippets[selected_source]["exists"]:
        missing.append("selected_changed_path_exists")
    if selected_verifier and not verifier_snippets[selected_verifier]["exists"]:
        missing.append("selected_verifier_path_exists")
    missing.extend(
        [
            "observed_verifier_transition",
            "gold_perspective_answers",
            "anti_cheat_decision",
            "root_split_assignment",
        ]
    )
    packet = {
        "root_id": root_id,
        "source_candidate_id": item.get("source_candidate_id"),
        "review_item_id": item.get("review_item_id"),
        "language_family": "web_js_ts_html",
        "repo_family": item.get("repo_family"),
        "git_repo_family": family,
        "repo_path": str(repo),
        "git_head": item.get("git_head"),
        "selected_changed_path_proposal": selected_source,
        "selected_verifier_path_proposal": selected_verifier,
        "candidate_options": option_set(item, selected_source, selected_verifier),
        "source_snippets": source_snippets,
        "verifier_snippets": verifier_snippets,
        "admission_status": "materialized_pending_verifier_gold_and_anti_cheat",
        "trainable_now": False,
        "strict_eval_eligible_now": False,
        "missing_for_train_admission": sorted(set(missing)),
        "review_questions": [
            "Can a maintainer derive a unique answer from these visible snippets and verifier evidence?",
            "Which candidate path is the minimal edit surface, if any?",
            "Which verifier/test actually constrains the behavior?",
            "Which visible fact distinguishes the edit surface from the verifier surface?",
            "Is abstention more appropriate than a forced singleton answer?",
        ],
        "anti_cheat_precheck": {
            "opaque_option_labels_prepared": True,
            "target_label_not_assigned_yet": True,
            "source_and_verifier_snippets_materialized": bool(source_snippets and verifier_snippets),
            "no_training_until_gold_and_verifier": True,
            "existing_openhands_llama_heldout_family": family in {"openhands_openhands", "llama_stack"},
        },
    }
    return packet


def make_row_shells(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    options_text = "\n".join(
        f"option {opt['label']}: {opt['semantic_role']} :: {opt.get('path') or 'ABSTAIN'}"
        for opt in packet["candidate_options"]
    )
    source_path = packet.get("selected_changed_path_proposal")
    verifier_path = packet.get("selected_verifier_path_proposal")
    source_snip = (packet.get("source_snippets") or {}).get(source_path or "", {})
    verifier_snip = (packet.get("verifier_snippets") or {}).get(verifier_path or "", {})
    visible = (
        f"Repository family: {packet['git_repo_family']}\n"
        f"Selected source candidate preview ({source_path}):\n{source_snip.get('text', '')}\n\n"
        f"Selected verifier candidate preview ({verifier_path}):\n{verifier_snip.get('text', '')}\n\n"
        f"Options:\n{options_text}\n"
    )
    for perspective in PERSPECTIVES:
        rows.append(
            {
                "row_id": f"{packet['root_id']}::{perspective}",
                "root_id": packet["root_id"],
                "language_family": packet["language_family"],
                "task_type": perspective,
                "input_text": (
                    f"Task: {perspective}. Use only the visible source/test evidence. "
                    "If the evidence does not justify a unique maintainer decision, choose abstention.\n\n"
                    + visible
                ),
                "opaque_options": packet["candidate_options"],
                "bounded_choice_target_label": None,
                "semantic_target_value": None,
                "target_status": "pending_gold_adjudication",
                "train_support_only": False,
                "strict_eval_eligible": False,
                "admission_status": "row_shell_pending_gold_and_verifier",
                "anti_cheat": {
                    "target_label_not_visible_before_options": True,
                    "target_not_assigned": True,
                    "deterministic_option_shuffle": False,
                    "do_not_score_or_train": True,
                },
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue = load_jsonl(QUEUE)
    selected = [
        item
        for item in queue
        if item.get("priority") == 1 and item.get("git_repo_family") in PRIORITY_FAMILIES
    ]
    packets = [make_packet(item) for item in selected]
    rows = [row for packet in packets for row in make_row_shells(packet)]
    admitted = [
        packet
        for packet in packets
        if not any(key.endswith("_exists") for key in packet["missing_for_train_admission"])
    ]
    train_ready = [
        packet
        for packet in packets
        if packet["trainable_now"] is True and not packet["missing_for_train_admission"]
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(packets),
        "decision": "new_web_family_packets_materialized_but_not_trainable",
        "counts": {
            "priority_queue_items_selected": len(selected),
            "root_packets": len(packets),
            "row_shells": len(rows),
            "file_materialized_packets": len(admitted),
            "train_ready_packets": len(train_ready),
            "strict_eval_ready_packets": 0,
        },
        "families": sorted(packet["git_repo_family"] for packet in packets),
        "admission": {
            "trainable_now": False,
            "strict_eval_eligible_now": False,
            "why": "Real source/test snippets and opaque options are materialized, but focused verifier outputs, gold perspective answers, anti-cheat signoff, and split assignment are still missing.",
            "do_not_train": True,
        },
        "next_actions": [
            "Run or recover focused verifier output for one selected test per packet.",
            "Fill gold answers for the six perspective row shells.",
            "Assign at least some new-family roots to sealed heldout, not only train.",
            "Run prompt-target leak and root-overlap audits before adding any row to train/eval.",
        ],
        "source_artifacts": {"stage11529_queue": rel(QUEUE)},
        "outputs": {"summary": rel(SUMMARY), "packets": rel(PACKETS), "row_shells": rel(ROW_SHELLS)},
    }
    write_jsonl(PACKETS, packets)
    write_jsonl(ROW_SHELLS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
