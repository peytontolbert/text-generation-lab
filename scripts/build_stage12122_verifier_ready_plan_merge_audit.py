#!/usr/bin/env python3
"""Merge and audit Stage12121 verifier-ready candidate plans.

This stage does not execute checkouts, admit rows, train, or evaluate. It turns
the four language-specific subagent plans into one normalized queue and records
which items are safe to try in the next bounded checkout/verifier smoke batch.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE = 12122
STAGE_NAME = "stage12122_verifier_ready_plan_merge_audit"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts" / STAGE_NAME
SUMMARY_PATH = ARTIFACT_DIR / "summary.json"
SUMMARY_MIRROR = ROOT / "runs/summaries" / f"{STAGE_NAME}.json"
NORMALIZED_JSONL = ARTIFACT_DIR / "normalized_verifier_ready_candidates.jsonl"
SHORTLIST_JSONL = ARTIFACT_DIR / "next_execution_shortlist.jsonl"

QUEUE_PATH = (
    ROOT
    / "runs/local/artifacts/stage12118_maintainer_400_pilot_checkout_probe_request/"
    "pilot_checkout_probe_targets.jsonl"
)
LESSONS_PATH = ROOT / "runs/summaries/stage12120_failed_stage_lessons_atlas.json"
STAGE12120_DISCOVERY_PATH = (
    ROOT
    / "runs/local/artifacts/stage12120_selected_test_discovery_smoke/"
    "selected_test_discovery_results.jsonl"
)

PLAN_INPUTS = {
    "c_cpp": ROOT
    / "runs/local/artifacts/stage12121_cpp_verifier_ready_candidate_plan/"
    "cpp_verifier_ready_candidate_plan.jsonl",
    "python": ROOT
    / "runs/local/artifacts/stage12121_python_verifier_ready_candidate_plan/"
    "python_verifier_ready_candidate_plan.jsonl",
    "rust": ROOT
    / "runs/local/artifacts/stage12121_rust_verifier_ready_candidate_plan/"
    "rust_verifier_ready_candidate_plan.jsonl",
    "web_js_ts_html": ROOT
    / "runs/local/artifacts/stage12121_web_verifier_ready_candidate_plan/"
    "web_verifier_ready_candidates.jsonl",
}

REQUIRED_FIELDS = {
    "queue_id",
    "repo_family",
    "canonical_remote",
    "reason_for_selection",
    "expected_verifier_scope",
    "proposed_no_install_commands",
    "selected_test_discovery_strategy",
    "dependency_risk",
    "anti_cheat_risks",
    "no_admission_statement",
}

HIGH_RISK_WORDS = ("high", "unknown", "heavy", "requires install")
LESSON_GATES = [
    "leakage_and_lineage",
    "evidence_verifier_mislabeled",
    "schema_renderer_option_geometry",
    "shared_training_interference",
    "web_transfer_gap",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def load_queue() -> dict[str, dict[str, Any]]:
    queue: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(QUEUE_PATH):
        queue[row["queue_id"]] = row
    return queue


def load_lessons() -> dict[str, Any]:
    if not LESSONS_PATH.exists():
        return {"available": False}
    data = json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
    return {
        "available": True,
        "scanned_summary_files": data.get("scanned_summary_files"),
        "failure_or_blocker_stage_records": data.get("failure_or_blocker_stage_records"),
        "lesson_category_counts": data.get("lesson_category_counts", {}),
        "active_gate_categories": {
            key: data.get("lesson_category_counts", {}).get(key, 0) for key in LESSON_GATES
        },
    }


def load_previous_discovery_blockers() -> dict[str, list[str]]:
    if not STAGE12120_DISCOVERY_PATH.exists():
        return {}
    blockers: dict[str, list[str]] = {}
    for row in read_jsonl(STAGE12120_DISCOVERY_PATH):
        queue_id = row.get("queue_id")
        if queue_id:
            blockers[queue_id] = list(row.get("blocker_reasons") or [])
    return blockers


def normalize_commands(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def has_no_admission_language(text: Any) -> bool:
    lowered = str(text).lower()
    return "no rows" in lowered or "no task rows" in lowered or "no training" in lowered


def risk_score(row: dict[str, Any], previous_blockers: list[str]) -> tuple[int, list[str]]:
    flags: list[str] = []
    score = 0
    risk = str(row.get("dependency_risk", "")).lower()
    if any(word in risk for word in HIGH_RISK_WORDS):
        score += 2
        flags.append("dependency_risk_not_low")
    if "selected_test" not in str(row.get("expected_verifier_scope", "")).lower():
        score += 1
        flags.append("not_selected_test_first")
    commands = normalize_commands(row.get("proposed_no_install_commands"))
    rendered = json.dumps(commands).lower()
    if "install" in rendered or "npm ci" in rendered or "pnpm install" in rendered or "cargo fetch" in rendered:
        score += 3
        flags.append("install_or_fetch_command_present")
    if not has_no_admission_language(row.get("no_admission_statement")):
        score += 3
        flags.append("missing_no_admission_language")
    if previous_blockers:
        score += 1
        flags.append("previous_smoke_blocker_present")
    if any(
        blocker
        in {
            "missing_cargo_cache_no_network_fetch",
            "missing_runtime_dependency_no_install",
            "node_modules_missing_no_install_no_test_execution",
            "prior_cmake_configure_failed_no_ctest_manifest",
        }
        for blocker in previous_blockers
    ):
        score += 3
        flags.append("previous_selected_test_execution_blocker_unresolved")
    return score, flags


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)

    queue = load_queue()
    lessons = load_lessons()
    previous_discovery_blockers = load_previous_discovery_blockers()
    normalized: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_queue_ids: set[str] = set()
    seen_repo_families: set[str] = set()
    missing_field_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()

    for language, path in PLAN_INPUTS.items():
        rows = read_jsonl(path)
        for rank, row in enumerate(rows, start=1):
            queue_id = row.get("queue_id")
            problems: list[str] = []
            missing = sorted(REQUIRED_FIELDS - set(row))
            for field in missing:
                missing_field_counts[field] += 1
            if missing:
                problems.append("missing_required_fields")
            if queue_id not in queue:
                problems.append("queue_id_not_in_stage12118")
            else:
                queued_language = queue[queue_id].get("language_family") or queue[queue_id].get("language")
                if queued_language != language:
                    problems.append("language_mismatch_with_stage12118")
            if queue_id in seen_queue_ids:
                problems.append("duplicate_queue_id")
            if row.get("repo_family") in seen_repo_families:
                problems.append("duplicate_repo_family")

            previous_blockers = previous_discovery_blockers.get(queue_id, [])
            score, flags = risk_score(row, previous_blockers)
            for flag in flags:
                risk_counts[flag] += 1

            record = {
                "stage": STAGE,
                "source_plan_language": language,
                "source_plan_rank": rank,
                "queue_id": queue_id,
                "repo_family": row.get("repo_family"),
                "canonical_remote": row.get("canonical_remote"),
                "reason_for_selection": row.get("reason_for_selection"),
                "expected_verifier_scope": row.get("expected_verifier_scope"),
                "proposed_no_install_commands": normalize_commands(row.get("proposed_no_install_commands")),
                "selected_test_discovery_strategy": row.get("selected_test_discovery_strategy"),
                "dependency_risk": row.get("dependency_risk"),
                "anti_cheat_risks": row.get("anti_cheat_risks"),
                "no_admission_statement": row.get("no_admission_statement"),
                "risk_score": score,
                "risk_flags": flags,
                "previous_discovery_blockers": previous_blockers,
                "audit_problems": problems,
                "admitted_for_training": False,
                "admitted_for_eval": False,
                "eligible_for_next_execution_smoke": not problems and score <= 2,
                "claim_boundary": "Verifier-ready plan only; next stage may execute smoke probes, but this stage admits no rows.",
            }
            if problems:
                rejected.append(record)
            else:
                normalized.append(record)
                seen_queue_ids.add(queue_id)
                seen_repo_families.add(row.get("repo_family"))
                language_counts[language] += 1

    shortlist: list[dict[str, Any]] = []
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        if row["eligible_for_next_execution_smoke"]:
            by_lang[row["source_plan_language"]].append(row)
    for language in PLAN_INPUTS:
        ranked = sorted(by_lang[language], key=lambda r: (r["risk_score"], r["source_plan_rank"]))
        shortlist.extend(ranked[:3])

    write_jsonl(NORMALIZED_JSONL, normalized)
    write_jsonl(SHORTLIST_JSONL, shortlist)

    summary = {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "created_at_utc": utc_now(),
        "input_plan_files": {lang: str(path.relative_to(ROOT)) for lang, path in PLAN_INPUTS.items()},
        "queue_input": str(QUEUE_PATH.relative_to(ROOT)),
        "previous_discovery_input": (
            str(STAGE12120_DISCOVERY_PATH.relative_to(ROOT))
            if STAGE12120_DISCOVERY_PATH.exists()
            else None
        ),
        "failed_stage_lessons": lessons,
        "counts": {
            "input_rows": sum(len(read_jsonl(path)) for path in PLAN_INPUTS.values()),
            "normalized_rows": len(normalized),
            "rejected_rows": len(rejected),
            "next_execution_shortlist_rows": len(shortlist),
            "admitted_for_training": 0,
            "admitted_for_eval": 0,
        },
        "counts_by_language": dict(language_counts),
        "missing_required_field_counts": dict(missing_field_counts),
        "risk_flag_counts": dict(risk_counts),
        "shortlist_by_language": dict(Counter(row["source_plan_language"] for row in shortlist)),
        "shortlist_repo_families": [
            {
                "language": row["source_plan_language"],
                "queue_id": row["queue_id"],
                "repo_family": row["repo_family"],
                "dependency_risk": row["dependency_risk"],
                "risk_score": row["risk_score"],
            }
            for row in shortlist
        ],
        "claim_boundary": [
            "Stage12122 merges/audits subagent plans only.",
            "No checkout, dependency install, verifier execution, training, or eval admission occurs here.",
            "Any next execution stage must still capture commit SHA, source/test evidence, command logs, anti-cheat metadata, and no train/eval lineage conflicts.",
        ],
        "promotion_decision": "not_promotable_support_planning_only",
        "next_recommended_stage": "stage12123_verifier_ready_checkout_execution_smoke",
        "outputs": {
            "artifact_dir": str(ARTIFACT_DIR.relative_to(ROOT)),
            "normalized_jsonl": str(NORMALIZED_JSONL.relative_to(ROOT)),
            "next_execution_shortlist": str(SHORTLIST_JSONL.relative_to(ROOT)),
            "summary": str(SUMMARY_PATH.relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_MIRROR.relative_to(ROOT)),
        },
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
