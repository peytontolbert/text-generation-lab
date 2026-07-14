#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10765
NAME = "stage10765_first_wave_bundle_preview_packets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "first_wave_bundle_preview_packets.json"
PACKET_INDEX_JSONL = OUT_DIR / "packet_index.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

BRIEFS_JSONL = ROOT / "runs/local/artifacts/stage10764_first_wave_root_materialization_briefs/root_materialization_briefs.jsonl"

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
LANGUAGE_QUOTA = {
    "python": 2,
    "rust": 2,
    "c_cpp": 2,
    "web_js_ts_html": 2,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{base[:96].rstrip('_')}_{digest}"


def first_lines(text: str, n: int = 8) -> str:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    return "\n".join(lines[:n])


def perspective_task(language_family: str, perspective: str) -> str:
    lang = {"python": "python", "rust": "rust", "c_cpp": "C/C++", "web_js_ts_html": "web"}[language_family]
    tasks = {
        "symptom_localization": f"Choose the most likely {lang} edit target from the visible evidence.",
        "evidence_citation": f"Name the visible {lang} fact that most strongly supports the chosen target.",
        "alternative_hypothesis_elimination": f"Explain why a plausible alternative {lang} target is less justified.",
        "patch_impact": f"Compare candidate {lang} edits by likely behavior change and risk.",
        "verifier_outcome": f"Choose the test or verifier consequence that best matches the visible {lang} evidence.",
        "minimal_fix_selection": f"Choose the smallest maintainable {lang} intervention supported by the evidence.",
        "regression_risk": f"Identify what the likely {lang} fix might break or destabilize.",
        "abstention_insufficient_evidence": f"Decide whether the visible {lang} evidence is enough for a singleton answer or whether abstention is more honest.",
    }
    return tasks[perspective]


def evidence_from_brief(brief: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    files = [str(item) for item in brief.get("changed_files_sample") or []]
    tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    symbols = [str(item) for item in brief.get("key_symbols_sample") or []]
    query = str(brief.get("sample_query_text") or "")
    execution_route = str(brief.get("execution_route") or "unknown")
    task_family = str(brief.get("task_family") or "unknown")

    return {
        "candidate_change_surface": [
            {
                "path": path_text,
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_changed_file_preview",
                "text": f"Changed file candidate: {path_text}",
            }
            for path_text in files[:4]
        ],
        "verifier_and_test_constraint": [
            {
                "path": path_text,
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_verification_target_preview",
                "text": f"Verification target preview: {path_text}",
            }
            for path_text in tests[:4]
        ],
        "nearby_definition_or_usage_context": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_key_symbol_preview",
                "text": "Key symbols: " + ", ".join(symbols[:12]),
            }
        ] if symbols else [],
        "symptom_or_call_path_analogue": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_query_projection",
                "text": first_lines(query, n=10),
            }
        ] if query else [],
        "external_analogue_reference": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_execution_route_summary",
                "text": f"Execution route: {execution_route}\nTask family: {task_family}",
            }
        ],
        "algorithmic_background_reference": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_repo_summary",
                "text": f"Repo family: {brief['repo_family']}\nSnapshot: {brief['snapshot_id']}\nPack: {brief['pack_id']}",
            }
        ],
    }


def anti_cheat_review_stub(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    sample_files = [str(item) for item in brief.get("changed_files_sample") or []]
    sample_tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    return {
        "stage": STAGE,
        "root_id": brief["root_id"],
        "language_family": brief["language_family"],
        "status": "review_required",
        "checks_required": [
            "candidate competition must include plausible non-gold paths, not only changed files",
            "gold path or gold test must not appear verbatim before options",
            "visible evidence must justify each promotable perspective row",
            "changed-path-only solving risk must be tested explicitly",
            "same root must remain outside promotable eval until bundle adjudication is complete",
        ],
        "current_preview_risks": [
            "preview evidence still derives from changed file and test summaries",
            "candidate set is not yet expanded beyond the brief path preview",
            "no human or AI gold adjudication has been attached yet",
        ],
        "suggested_candidate_pool_seed": {
            "changed_files_sample": sample_files,
            "verification_targets_sample": sample_tests,
        },
        "packet_dir": display(packet_dir),
    }


def gold_stub(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    entries = []
    for perspective in PERSPECTIVES:
        entries.append(
            {
                "perspective": perspective,
                "task": perspective_task(str(brief["language_family"]), perspective),
                "answer_kind": "pending_adjudication",
                "gold_value": None,
                "supporting_visible_evidence_keys": [],
                "adjudication_notes": "",
            }
        )
    return {
        "stage": STAGE,
        "root_id": brief["root_id"],
        "language_family": brief["language_family"],
        "status": "gold_required",
        "entries": entries,
        "packet_dir": display(packet_dir),
    }


def rubric_stub(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "root_id": brief["root_id"],
        "language_family": brief["language_family"],
        "status": "rubric_review_required",
        "questions": [
            "Is there enough visible maintainer evidence to justify a singleton answer for non-abstention rows?",
            "Do the selected tests and changed files create plausible competing hypotheses?",
            "Would a maintainer judge the candidate set as realistic rather than shortcut-prone?",
            "Should any perspectives be converted to abstain-first rather than forced singleton?",
        ],
        "packet_dir": display(packet_dir),
    }


def perspective_rows(brief: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    candidate_paths = [str(item) for item in brief.get("changed_files_sample") or []]
    selected_tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    for perspective in PERSPECTIVES:
        rows.append(
            {
                "bundle_id": f"stage10765::{brief['root_id']}",
                "root_id": brief["root_id"],
                "language_family": brief["language_family"],
                "perspective": perspective,
                "prompt_contract": {
                    "task": perspective_task(str(brief["language_family"]), perspective),
                    "candidate_paths_preview": candidate_paths,
                    "selected_tests_preview": selected_tests,
                    "visible_evidence_keys": sorted(key for key, value in evidence.items() if value),
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "human_or_ai_adjudication_required",
                "eligible_for_training_or_scoring_now": False,
            }
        )
    return rows


def main() -> None:
    briefs = load_jsonl(BRIEFS_JSONL)
    selected: list[dict[str, Any]] = []
    per_language: dict[str, int] = Counter()
    for brief in sorted(briefs, key=lambda row: (row["language_family"], int(row["queue_rank"]))):
        lang = str(brief["language_family"])
        if per_language[lang] >= LANGUAGE_QUOTA[lang]:
            continue
        per_language[lang] += 1
        selected.append(brief)

    packet_index: list[dict[str, Any]] = []
    for brief in selected:
        root_slug = slug(str(brief["root_id"]))
        packet_dir = OUT_DIR / "review_packets" / root_slug
        packet_dir.mkdir(parents=True, exist_ok=True)

        evidence = evidence_from_brief(brief)
        bundle = {
            "bundle_id": f"stage10765::{brief['root_id']}",
            "root_id": brief["root_id"],
            "repo_id": brief["repo_id"],
            "repo_family": brief["repo_family"],
            "language_family": brief["language_family"],
            "source_route": "compiled_root_brief_preview",
            "claim_boundary": {
                "gold_answers_fully_adjudicated": False,
                "supports_training_or_scoring_now": False,
                "preview_only": True,
            },
            "queue_metadata": {
                "queue_rank": brief["queue_rank"],
                "priority_score": brief["priority_score"],
                "semantic_lane": brief["semantic_lane"],
                "provisional_admit_role": brief["provisional_admit_role"],
                "quality_tier": brief["quality_tier"],
            },
            "compiled_brief_summary": {
                "execution_route": brief["execution_route"],
                "test_selection_route": brief["test_selection_route"],
                "changed_file_count": brief["changed_file_count"],
                "verification_target_count": brief["verification_target_count"],
                "key_symbol_count": brief["key_symbol_count"],
                "changed_files_sample": brief.get("changed_files_sample") or [],
                "verification_targets_sample": brief.get("verification_targets_sample") or [],
                "key_symbols_sample": brief.get("key_symbols_sample") or [],
            },
            "maintainer_visible_evidence": evidence,
            "perspective_rows": perspective_rows(brief, evidence),
        }

        bundle_path = packet_dir / "fresh_root_bundle_preview.json"
        anti_cheat_path = packet_dir / "anti_cheat_review_card.json"
        gold_path = packet_dir / "perspective_gold_adjudication.json"
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"

        write_json(bundle_path, bundle)
        write_json(anti_cheat_path, anti_cheat_review_stub(brief, packet_dir))
        write_json(gold_path, gold_stub(brief, packet_dir))
        write_json(rubric_path, rubric_stub(brief, packet_dir))

        packet_index.append(
            {
                "root_id": brief["root_id"],
                "repo_family": brief["repo_family"],
                "language_family": brief["language_family"],
                "queue_rank": brief["queue_rank"],
                "priority_score": brief["priority_score"],
                "packet_dir": display(packet_dir),
                "bundle_preview": display(bundle_path),
                "anti_cheat_review": display(anti_cheat_path),
                "perspective_gold_adjudication": display(gold_path),
                "rubric_review": display(rubric_path),
                "selected_test_anchor_preview": bool(brief.get("verification_target_count")),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "first_wave_bundle_preview_packets_ready",
        "claim_scope": [
            "Turn the highest-priority stage10764 briefs into concrete review-packet directories.",
            "Keep every packet preview-only until anti-cheat and gold adjudication are completed.",
            "Give the next reviewed-bundle build step concrete multilingual files instead of another ranked queue.",
        ],
        "metrics": {
            "preview_packet_count": len(packet_index),
            "preview_packets_by_language": dict(sorted(Counter(row["language_family"] for row in packet_index).items())),
        },
        "headline_findings": [
            "The next multilingual bundle-build step now has concrete packet directories for two roots per language.",
            "C/C++ and Python packets are the strongest immediate candidates because they already combine candidate file previews with verifier target previews.",
            "Rust packets now exist for fresh non-tokenizers roots instead of relying only on tokenizers/candle replay.",
            "Web remains preview-only and still needs explicit anti-cheat review to prove it is not just changed-path solvable.",
        ],
        "anti_cheat_contract": [
            "These packets are scaffolds only and must not be treated as scored or train-ready data.",
            "Any promoted bundle must replace preview path summaries with real competing candidate surfaces and adjudicated gold answers.",
            "The anti-cheat review card must explicitly test changed-path shortcut risk before admission.",
            "Root-level split isolation remains mandatory for all follow-on materialization.",
        ],
        "next_best_step": "Adjudicate and enrich the highest-value C/C++ and Python preview packets first, then do the same for the fresh Rust packets before building the next reviewed multilingual training package.",
        "source_artifacts": {
            "briefs": display(BRIEFS_JSONL),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "packet_index": display(PACKET_INDEX_JSONL),
            "review_packets_dir": display(OUT_DIR / "review_packets"),
        },
    }

    write_jsonl(PACKET_INDEX_JSONL, packet_index)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "preview_packet_count": payload["metrics"]["preview_packet_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
