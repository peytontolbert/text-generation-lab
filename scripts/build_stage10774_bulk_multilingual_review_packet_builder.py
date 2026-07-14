#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10774
NAME = "stage10774_bulk_multilingual_review_packet_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "bulk_multilingual_review_packet_builder.json"
PACKET_INDEX_JSONL = OUT_DIR / "packet_index.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

BRIEFS_JSONL = ROOT / "runs/local/artifacts/stage10773_bulk_multilingual_root_materialization_briefs/root_materialization_briefs.jsonl"
SUPPLY_SUMMARY = ROOT / "runs/local/artifacts/stage10772_bulk_multilingual_root_supply_census/bulk_multilingual_root_supply_census.json"

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


def perspective_task(language_family: str, perspective: str) -> str:
    lang = {"python": "python", "rust": "rust", "c_cpp": "C/C++", "web_js_ts_html": "web"}[language_family]
    tasks = {
        "symptom_localization": f"Choose the most likely {lang} edit target from the visible maintainer evidence.",
        "evidence_citation": f"Identify the visible {lang} fact that most strongly supports the chosen target.",
        "alternative_hypothesis_elimination": f"Explain why a plausible alternative {lang} target is less justified.",
        "patch_impact": f"Compare candidate {lang} interventions by expected behavior change and risk.",
        "verifier_outcome": f"Choose the test or verifier consequence that best matches the visible {lang} evidence.",
        "minimal_fix_selection": f"Choose the smallest maintainable {lang} intervention supported by the evidence.",
        "regression_risk": f"Name what the likely {lang} fix could break or destabilize.",
        "abstention_insufficient_evidence": f"Decide whether the visible {lang} evidence supports a singleton answer or whether abstention is more honest.",
    }
    return tasks[perspective]


def evidence_from_brief(brief: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    changed_files = [str(item) for item in brief.get("changed_files_sample") or []]
    tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    symbols = [str(item) for item in brief.get("key_symbols_sample") or []]
    query_preview = str(brief.get("query_preview") or "")
    duplicate_sources = [str(item) for item in brief.get("duplicate_source_families") or []]
    return {
        "candidate_change_surface": [
            {
                "path": item,
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_changed_file_preview",
                "text": f"Changed file candidate: {item}",
            }
            for item in changed_files[:6]
        ],
        "verifier_and_test_constraint": [
            {
                "path": item,
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_verification_target_preview",
                "text": f"Verification target preview: {item}",
            }
            for item in tests[:6]
        ],
        "nearby_definition_or_usage_context": (
            [
                {
                    "path": "",
                    "source_type": "compiled_root_brief",
                    "retrieval_reason": "brief_key_symbol_preview",
                    "text": "Key symbols: " + ", ".join(symbols[:14]),
                }
            ]
            if symbols
            else []
        ),
        "symptom_or_call_path_analogue": (
            [
                {
                    "path": "",
                    "source_type": "compiled_root_brief",
                    "retrieval_reason": "brief_query_preview",
                    "text": query_preview,
                }
            ]
            if query_preview
            else []
        ),
        "external_analogue_reference": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_execution_route_summary",
                "text": (
                    f"Execution route: {brief['execution_route']}\n"
                    f"Verifier route: {brief['verifier_id']}\n"
                    f"Source family: {brief['source_family_id']}"
                ),
            }
        ],
        "algorithmic_background_reference": [
            {
                "path": "",
                "source_type": "compiled_root_brief",
                "retrieval_reason": "brief_duplicate_source_summary",
                "text": (
                    f"Duplicate source count: {brief['duplicate_source_count']}\n"
                    f"Duplicate source families: {', '.join(duplicate_sources[:6]) or 'none'}"
                ),
            }
        ],
    }


def anti_cheat_status(brief: dict[str, Any]) -> str:
    if brief["language_family"] == "web_js_ts_html":
        return "high_shortcut_risk_review_required"
    if brief["verifier_id"] == "PASS_TRACE_VERIFICATION_TARGETS":
        return "trace_anchor_review_required"
    return "review_required"


def anti_cheat_review_card(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    changed_files = [str(item) for item in brief.get("changed_files_sample") or []]
    tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    return {
        "stage": STAGE,
        "root_id": brief["root_id"],
        "root_lineage_key": brief["root_lineage_key"],
        "language_family": brief["language_family"],
        "repo_family": brief["repo_family"],
        "status": anti_cheat_status(brief),
        "checks_required": [
            "gold path or gold test must not appear verbatim before the option set",
            "changed-path-only solving risk must be tested explicitly",
            "visible evidence must support the adjudicated gold answer",
            "same root and root_lineage_key must remain isolated from promotable eval until signoff",
            "candidate competition must include plausible non-gold files/tests/symbols from the same repo family",
        ],
        "current_preview_risks": [
            "evidence is still summarized from brief-level changed files and verification targets",
            "candidate pool is not yet expanded into a fully adjudicated maintainer bundle",
            "no final human/AI gold answer has been attached yet",
        ],
        "suggested_candidate_pool_seed": {
            "changed_files_sample": changed_files,
            "verification_targets_sample": tests,
            "key_symbols_sample": list(brief.get("key_symbols_sample") or []),
        },
        "packet_dir": display(packet_dir),
    }


def gold_stub(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    entries = []
    for perspective in PERSPECTIVES:
        answer_kind = "abstain_or_set_valued_review" if perspective == "abstention_insufficient_evidence" else "singleton_or_abstain_review"
        entries.append(
            {
                "perspective": perspective,
                "task": perspective_task(str(brief["language_family"]), perspective),
                "answer_kind": answer_kind,
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


def snippet_plan(brief: dict[str, Any], packet_dir: Path) -> dict[str, Any]:
    changed_files = [str(item) for item in brief.get("changed_files_sample") or []]
    tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    return {
        "stage": STAGE,
        "root_id": brief["root_id"],
        "language_family": brief["language_family"],
        "status": "snippet_materialization_required",
        "primary_snippet_targets": changed_files[:6],
        "verifier_targets": tests[:6],
        "notes": [
            "Recover concrete code snippets and test/assertion fragments for all promoted bundles.",
            "Prefer snippets that differentiate neighboring candidates rather than only restating the changed path.",
        ],
        "packet_dir": display(packet_dir),
    }


def perspective_rows(brief: dict[str, Any], evidence: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    candidate_paths = [str(item) for item in brief.get("changed_files_sample") or []]
    selected_tests = [str(item) for item in brief.get("verification_targets_sample") or []]
    return [
        {
            "bundle_id": f"stage10774::{brief['root_id']}",
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
        for perspective in PERSPECTIVES
    ]


def main() -> None:
    briefs = load_jsonl(BRIEFS_JSONL)
    supply_summary = load_json(SUPPLY_SUMMARY)

    packet_index: list[dict[str, Any]] = []
    for brief in briefs:
        packet_dir = OUT_DIR / "review_packets" / slug(str(brief["root_id"]))
        packet_dir.mkdir(parents=True, exist_ok=True)
        evidence = evidence_from_brief(brief)
        bundle = {
            "bundle_id": f"stage10774::{brief['root_id']}",
            "root_id": brief["root_id"],
            "root_lineage_key": brief["root_lineage_key"],
            "repo_family": brief["repo_family"],
            "language_family": brief["language_family"],
            "source_route": "bulk_compiled_root_brief_preview",
            "claim_boundary": {
                "gold_answers_fully_adjudicated": False,
                "supports_training_or_scoring_now": False,
                "preview_only": True,
            },
            "queue_metadata": {
                "queue_rank": brief["queue_rank"],
                "priority_score": brief["priority_score"],
                "semantic_lane": brief["semantic_lane"],
                "quality_tier": brief["quality_tier"],
            },
            "compiled_brief_summary": {
                "execution_route": brief["execution_route"],
                "verifier_id": brief["verifier_id"],
                "selected_test_anchor_present": brief["selected_test_anchor_present"],
                "verifier_anchor_present": brief["verifier_anchor_present"],
                "duplicate_source_count": brief["duplicate_source_count"],
                "changed_file_count": brief["changed_file_count"],
                "verification_target_count": brief["verification_target_count"],
                "key_symbol_count": brief["key_symbol_count"],
                "changed_files_sample": brief.get("changed_files_sample") or [],
                "verification_targets_sample": brief.get("verification_targets_sample") or [],
                "key_symbols_sample": brief.get("key_symbols_sample") or [],
                "query_preview": brief.get("query_preview") or "",
            },
            "maintainer_visible_evidence": evidence,
            "perspective_rows": perspective_rows(brief, evidence),
        }

        bundle_path = packet_dir / "fresh_root_bundle_preview.json"
        anti_cheat_path = packet_dir / "anti_cheat_review_card.json"
        gold_path = packet_dir / "perspective_gold_adjudication.json"
        rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
        snippet_plan_path = packet_dir / "snippet_materialization_plan.json"

        write_json(bundle_path, bundle)
        write_json(anti_cheat_path, anti_cheat_review_card(brief, packet_dir))
        write_json(gold_path, gold_stub(brief, packet_dir))
        write_json(rubric_path, rubric_stub(brief, packet_dir))
        write_json(snippet_plan_path, snippet_plan(brief, packet_dir))

        packet_index.append(
            {
                "root_id": brief["root_id"],
                "root_lineage_key": brief["root_lineage_key"],
                "repo_family": brief["repo_family"],
                "language_family": brief["language_family"],
                "queue_rank": brief["queue_rank"],
                "priority_score": brief["priority_score"],
                "semantic_lane": brief["semantic_lane"],
                "packet_dir": display(packet_dir),
                "bundle_preview": display(bundle_path),
                "anti_cheat_review": display(anti_cheat_path),
                "perspective_gold_adjudication": display(gold_path),
                "rubric_review": display(rubric_path),
                "snippet_materialization_plan": display(snippet_plan_path),
                "selected_test_anchor_preview": bool(brief.get("selected_test_anchor_present")),
                "verifier_anchor_preview": bool(brief.get("verifier_anchor_present")),
            }
        )

    packet_index.sort(key=lambda row: (row["language_family"], int(row["queue_rank"]), -int(row["priority_score"]), row["root_id"]))
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bulk_multilingual_review_packet_builder_ready",
        "claim_scope": [
            "Turn the stage10773 bulk materialization briefs into concrete multilingual review-packet directories.",
            "Keep every packet preview-only until anti-cheat and gold adjudication are completed.",
            "Provide the next reviewed-bundle build step with real packet files instead of another queue or census.",
        ],
        "metrics": {
            "preview_packet_count": len(packet_index),
            "preview_packets_by_language": dict(sorted(Counter(row["language_family"] for row in packet_index).items())),
            "selected_test_anchor_packets": sum(1 for row in packet_index if row["selected_test_anchor_preview"]),
            "verifier_anchor_packets": sum(1 for row in packet_index if row["verifier_anchor_preview"]),
        },
        "headline_findings": [
            "The bulk brief queue now has concrete review packet directories for every currently queued multilingual root.",
            "C/C++ packets are the cleanest immediate reviewed-bundle candidates because they are all selected-test anchored and spread across real repo families.",
            "Python packets now provide broader reviewed-growth potential beyond the old narrow frontier, but repo-family caps still matter at promotion time.",
            "Rust and Web remain low-count lanes, so each packet should be treated as high-value source acquisition and adjudication work.",
        ],
        "anti_cheat_contract": [
            "These packets are scaffolds only and must not be treated as scored or train-ready data.",
            "Any promoted bundle must replace preview path summaries with real competing candidate surfaces and adjudicated gold answers.",
            "The anti-cheat review card must explicitly test changed-path shortcut risk before admission.",
            "Root-level split isolation remains mandatory for all follow-on materialization.",
        ],
        "next_best_step": "Adjudicate and enrich the highest-ranked C/C++ and Python packets first, then complete all Rust and Web packets so the next reviewed multilingual package grows breadth instead of replaying the old 24-row canary.",
        "source_artifacts": {
            "briefs": display(BRIEFS_JSONL),
            "supply_summary": display(SUPPLY_SUMMARY),
            "supply_language_rollup": supply_summary.get("language_rollup") or {},
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
