#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10862
NAME = "stage10862_python_successor_visible_evidence_shortcut_gate"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "python_successor_visible_evidence_shortcut_gate.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

SOURCE_PACKET = (
    ARTIFACTS
    / "stage10110_real_session_shortcut_safe_successor_packet"
    / "real_session_shortcut_safe_successor_packet.jsonl"
)
QUEUE_TARGETS = (
    ARTIFACTS
    / "stage10492_python_verifier_reviewed_root_expansion_queue"
    / "python_verifier_reviewed_root_expansion_targets.jsonl"
)
QUEUE_STATUS = (
    ARTIFACTS
    / "stage10493_python_verifier_fresh_review_packet_builder"
    / "python_verifier_review_target_status.jsonl"
)
RECENT_BLOCK_AUDIT = (
    ARTIFACTS
    / "stage10861_code_assist_cognitive_perfection_python_recoverability_audit"
    / "code_assist_cognitive_perfection_python_recoverability_audit.json"
)

COMMON_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "true",
    "false",
    "none",
    "null",
    "json",
    "path",
    "paths",
    "data",
    "value",
    "values",
    "field",
    "fields",
    "import",
    "return",
    "class",
    "def",
    "self",
    "tests",
    "test",
    "repo",
    "code",
    "agent",
    "kernel",
    "code_assist",
}


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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def short(text: str, limit: int = 180) -> str:
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3] + "..."


def tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text or ""))
    return {tok.lower() for tok in tokens if tok.lower() not in COMMON_STOPWORDS}


def overlap_ratio(a: set[str], b: set[str]) -> float:
    if not a:
        return 0.0
    return len(a & b) / max(1, len(a))


def test_stems(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        base = Path(path).stem.lower()
        out.add(base)
        parts = [part.lower() for part in re.split(r"[_/.-]+", path) if len(part) >= 4]
        out.update(parts)
    return {item for item in out if item not in COMMON_STOPWORDS}


def queue_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    target_map = {row["episode_id"]: row for row in load_jsonl(QUEUE_TARGETS)}
    status_map = {row["episode_id"]: row for row in load_jsonl(QUEUE_STATUS)}
    return target_map, status_map


def classify_row(row: dict[str, Any], target_map: dict[str, dict[str, Any]], status_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hidden = row.get("hidden_metadata") or {}
    prompt = row.get("prompt_surface") or {}
    episode_id = row["episode_id"]
    selected_tests = list(hidden.get("selected_tests") or [])
    visible_evidence = list(prompt.get("visible_evidence") or [])
    candidate_choices = list(prompt.get("candidate_choices") or [])

    candidate_tokens = [tokenize(choice.get("snippet_preview") or "") for choice in candidate_choices]
    candidate_union = set().union(*candidate_tokens) if candidate_tokens else set()
    selected_test_terms = test_stems(selected_tests)

    visible_records: list[dict[str, Any]] = []
    low_overlap_noise_count = 0
    candidate_self_overlap_count = 0
    selected_test_anchor_hits = 0
    repo_local_hits = 0

    for idx, snippet in enumerate(visible_evidence):
        vtok = tokenize(snippet)
        candidate_overlap = overlap_ratio(vtok, candidate_union)
        best_choice_overlap = max((overlap_ratio(vtok, ctok) for ctok in candidate_tokens), default=0.0)
        has_selected_test_anchor = any(term in snippet.lower() for term in selected_test_terms)
        if has_selected_test_anchor:
            selected_test_anchor_hits += 1
        if any(term in snippet.lower() for term in ("orchestrator", "context_pack", "improvement", "cycle_runner", "liftoff", "memory", "config", "policy", "loop")):
            repo_local_hits += 1
        if candidate_overlap < 0.08 and not has_selected_test_anchor:
            low_overlap_noise_count += 1
        if best_choice_overlap >= 0.30:
            candidate_self_overlap_count += 1
        visible_records.append(
            {
                "index": idx,
                "preview": short(snippet),
                "candidate_overlap": round(candidate_overlap, 4),
                "best_choice_overlap": round(best_choice_overlap, 4),
                "has_selected_test_anchor": has_selected_test_anchor,
            }
        )

    selected_tests_hidden_metadata_only = selected_test_anchor_hits == 0 and len(selected_tests) > 0

    queue_target = target_map.get(episode_id)
    queue_status = status_map.get(episode_id)
    queue_priority = queue_target.get("priority_order") if queue_target else None
    queue_immediate = bool(queue_status and queue_status.get("immediately_qualified_for_reviewed_verifier_packet"))
    queue_executable_verifier_rows = int(queue_status.get("executable_verifier_row_count") or 0) if queue_status else 0

    hidden_test_risk = selected_tests_hidden_metadata_only and candidate_self_overlap_count >= 2
    analogue_noise_risk = low_overlap_noise_count >= 2
    blocked_for_verifier = hidden_test_risk and analogue_noise_risk

    recoverability_score = 0.0
    recoverability_score += min(len(selected_tests), 8) * 0.8
    recoverability_score += repo_local_hits * 0.7
    recoverability_score += queue_executable_verifier_rows * 2.5
    recoverability_score += 4.0 if queue_immediate else 0.0
    recoverability_score -= low_overlap_noise_count * 1.8
    recoverability_score -= 3.5 if selected_tests_hidden_metadata_only else 0.0
    recoverability_score -= 2.0 if blocked_for_verifier else 0.0

    recommendation = "review_candidate"
    if blocked_for_verifier:
        recommendation = "block_or_quarantine"
    elif queue_immediate:
        recommendation = "prefer_for_next_recovery"
    elif queue_executable_verifier_rows > 0:
        recommendation = "recover_with_materialization"

    return {
        "row_id": row["row_id"],
        "episode_id": episode_id,
        "repo_id": row.get("repo_id"),
        "language_family": row.get("language_family"),
        "successor_template": row.get("successor_template"),
        "selected_tests_count": len(selected_tests),
        "selected_tests_hidden_metadata_only": selected_tests_hidden_metadata_only,
        "selected_tests_preview": selected_tests[:6],
        "candidate_count": len(candidate_choices),
        "candidate_self_overlap_count": candidate_self_overlap_count,
        "low_overlap_noise_count": low_overlap_noise_count,
        "repo_local_hits": repo_local_hits,
        "queue_priority_order": queue_priority,
        "queue_immediately_qualified_for_reviewed_verifier_packet": queue_immediate,
        "queue_executable_verifier_row_count": queue_executable_verifier_rows,
        "blocked_for_current_verifier_goal": blocked_for_verifier,
        "recommended_action": recommendation,
        "recoverability_score": round(recoverability_score, 3),
        "visible_evidence_diagnostics": visible_records,
    }


def main() -> None:
    target_map, status_map = queue_maps()
    rows = [
        row
        for row in load_jsonl(SOURCE_PACKET)
        if row.get("language_family") == "python"
        and row.get("successor_template") == "python_implementation_vs_config"
    ]
    classified = [classify_row(row, target_map, status_map) for row in rows]
    ranked = sorted(
        classified,
        key=lambda row: (
            row["recommended_action"] != "prefer_for_next_recovery",
            row["recommended_action"] == "block_or_quarantine",
            -(row["recoverability_score"]),
            row["queue_priority_order"] if row["queue_priority_order"] is not None else math.inf,
        ),
    )

    blocked_rows = [row for row in ranked if row["blocked_for_current_verifier_goal"]]
    preferred_rows = [row for row in ranked if row["recommended_action"] == "prefer_for_next_recovery"]
    recoverable_rows = [row for row in ranked if row["recommended_action"] in {"prefer_for_next_recovery", "recover_with_materialization", "review_candidate"}]

    recent_block = json.loads(RECENT_BLOCK_AUDIT.read_text(encoding="utf-8")) if RECENT_BLOCK_AUDIT.exists() else None

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "scanned_row_count": len(rows),
        "repo_distribution": Counter(row["repo_id"] for row in ranked),
        "blocked_row_count": len(blocked_rows),
        "preferred_next_rows": preferred_rows[:5],
        "recoverable_candidate_rows": recoverable_rows[:10],
        "blocked_examples": blocked_rows[:5],
        "gate_definition": {
            "selected_tests_hidden_metadata_only": "No selected-test stem appears in prompt-visible evidence despite selected tests existing in hidden metadata.",
            "candidate_self_overlap_count": "Count of visible evidence snippets that mostly restate one of the candidate previews.",
            "low_overlap_noise_count": "Count of visible evidence snippets with weak lexical overlap to local candidate code and no selected-test anchor.",
            "blocked_for_current_verifier_goal": "True when hidden selected tests and analogue-noise geometry make the row unfit for verifier-oriented recovery.",
        },
        "headline_findings": [
            "The blocked cognitive_perfection Python row is not an isolated review gap; it matches a broader hidden-selected-test geometry that can be auto-flagged.",
            "stage10236 context_pack remains the only queue-reviewed Python root that is immediately qualified for a richer verifier packet under the current inventory.",
            "Most remaining python_implementation_vs_config successor rows are agentkernel-heavy and still need real verifier materialization rather than direct admission.",
        ],
        "recent_block_reference": recent_block,
        "recommended_next_actions": [
            "Treat stage10236 context_pack as the best current non-MirrorMind Python verifier-support root, but keep it train-support only unless a fresh strict-heldout family is built.",
            "Prioritize agentkernel verifier materialization only on rows where prompt-visible evidence can expose selected-test or verifier-transition anchors, not just implementation-vs-config previews.",
            "Apply this gate before future AI adjudication so rows with hidden selected tests and analogue-noise evidence are blocked automatically.",
        ],
    }

    write_json(OUT_JSON, summary)
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
