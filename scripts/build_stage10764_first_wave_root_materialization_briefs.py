#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10764
NAME = "stage10764_first_wave_root_materialization_briefs"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "first_wave_root_materialization_briefs.json"
BRIEFS_JSONL = OUT_DIR / "root_materialization_briefs.jsonl"
LANE_JSONL = OUT_DIR / "lane_rollup.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

QUEUE_JSONL = ROOT / "runs/local/artifacts/stage10763_multilingual_root_admission_seed_manifest/first_wave_materialization_queue.jsonl"
ADMISSION_JSONL = ROOT / "runs/local/artifacts/stage10763_multilingual_root_admission_seed_manifest/root_admission_seed_manifest.jsonl"
COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
COMPILED_STATES = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_causal_states.jsonl"
COMPILED_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
FRONTIER_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"
CURRENT_RESIDUALS = ROOT / "runs/local/artifacts/stage10762_hf_local_repaired_support_probe_audit/strict_miss_rows.jsonl"


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


def summarized(values: list[str], limit: int = 12) -> list[str]:
    if len(values) <= limit:
        return values
    return values[:limit]


def root_brief_actions(language_family: str, repo_family: str, verifier_id: str) -> list[str]:
    actions: list[str] = [
        "Recover concrete source snippets, file paths, and verifier observations from the root-level state before writing candidate options.",
        "Build candidate competition around nearby changed files, tests, and symbols rather than letting changed-path signatures solve the row.",
        "Record explicit anti-cheat checks for prompt_target_leak, same-root split isolation, and target-supporting evidence visibility.",
    ]
    if language_family == "python":
        actions.append("Favor verifier_outcome and evidence-citation perspectives that separate nearby plausible tests without exposing the gold path.")
    elif language_family == "rust":
        actions.append("Force symptom-vs-verifier evidence contrast and keep candidate_change_surface from becoming the default shortcut.")
    elif language_family == "c_cpp":
        actions.append("Exploit the selected-test and build-verifier anchors to create multi-file maintainer bundles with real kernel/wrapper/test competition.")
    elif language_family == "web_js_ts_html":
        actions.append("Do not promote as pure-web unless selected tests or verifier anchors stay visible after materialization.")

    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        actions.append("Preserve trace-backed verifier evidence as a first-class visible field in the bundle.")
    elif verifier_id == "PASS_TARGETED_TEST_SELECTION":
        actions.append("Keep the selected-test set explicit, but hide the gold test identity behind candidate competition.")
    return actions


def lane_priority(language_family: str) -> int:
    order = {"c_cpp": 1, "python": 2, "rust": 3, "web_js_ts_html": 4}
    return order.get(language_family, 99)


def main() -> None:
    queue_rows = load_jsonl(QUEUE_JSONL)
    admission_rows = load_jsonl(ADMISSION_JSONL)
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    compiled_states = load_jsonl(COMPILED_STATES)
    compiled_rows = load_jsonl(COMPILED_ROWS)
    frontier_queue = load_json(FRONTIER_QUEUE)
    residual_rows = load_jsonl(CURRENT_RESIDUALS)

    admission_by_root = {str(row["root_id"]): row for row in admission_rows}
    compiled_by_root = {str(row["root_id"]): row for row in compiled_roots}
    states_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compiled_states:
        states_by_root[str(row["root_id"])].append(row)
    for row in compiled_rows:
        rows_by_root[str(row["root_id"])].append(row)

    residual_root_ids = {str(row.get("root_id") or "") for row in residual_rows}

    brief_rows: list[dict[str, Any]] = []
    for queue_row in queue_rows:
        root_id = str(queue_row["root_id"])
        compiled_root = compiled_by_root[root_id]
        state_rows = states_by_root.get(root_id, [])
        target_rows = rows_by_root.get(root_id, [])
        final_state = (state_rows[0].get("final_state") if state_rows else {}) or {}
        target_family_counts = Counter(str(row.get("target_family") or "unknown") for row in target_rows)
        target_subtype_counts = Counter(str(row.get("target_subtype") or "unknown") for row in target_rows)
        anti_cheat_flags = Counter()
        for row in target_rows:
            anti_cheat = row.get("anti_cheat") or {}
            for key, value in anti_cheat.items():
                if value:
                    anti_cheat_flags[key] += 1

        verifier_targets = [str(item) for item in final_state.get("verification_targets") or []]
        changed_files = [str(item) for item in final_state.get("expected_changed_files") or []]
        key_symbols = [str(item) for item in final_state.get("key_symbols") or []]

        brief_rows.append(
            {
                "root_id": root_id,
                "queue_rank": int(queue_row["queue_rank"]),
                "queue_lane": str(queue_row["queue_lane"]),
                "priority_score": int(queue_row["priority_score"]),
                "provisional_admit_role": str(queue_row["provisional_admit_role"]),
                "semantic_lane": str(queue_row["semantic_lane"]),
                "repo_id": str(queue_row["repo_id"]),
                "repo_family": str(queue_row["repo_family"]),
                "language_family": str(queue_row["language_family"]),
                "snapshot_id": str(queue_row["snapshot_id"]),
                "verifier_id": str(queue_row["verifier_id"]),
                "quality_tier": str(queue_row["quality_tier"]),
                "split_component": str(compiled_root.get("split_component") or "unknown"),
                "task_family": str(compiled_root.get("task_family") or "unknown"),
                "pack_id": str(queue_row.get("pack_id") or "unknown"),
                "query_index": int(queue_row.get("query_index") or -1),
                "event_state_count": len(state_rows),
                "multitarget_row_count": len(target_rows),
                "target_family_counts": dict(sorted(target_family_counts.items())),
                "target_subtype_counts": dict(sorted(target_subtype_counts.items())),
                "execution_route": str(final_state.get("execution_route") or "unknown"),
                "test_selection_route": str(final_state.get("test_selection_route") or queue_row["verifier_id"]),
                "changed_file_count": len(changed_files),
                "verification_target_count": len(verifier_targets),
                "key_symbol_count": len(key_symbols),
                "changed_files_sample": summarized(changed_files, limit=10),
                "verification_targets_sample": summarized(verifier_targets, limit=10),
                "key_symbols_sample": summarized(key_symbols, limit=14),
                "sample_query_text": str((state_rows[0].get("query_text") if state_rows else "") or ""),
                "sample_targets": {
                    str(row.get("target_subtype") or f"target_{idx}"): str(row.get("target_text") or "")
                    for idx, row in enumerate(target_rows[:6])
                },
                "anti_cheat_flags_observed": dict(sorted(anti_cheat_flags.items())),
                "review_ready_contract": {
                    "must_keep_root_split_atomic": True,
                    "must_build_candidate_competition": True,
                    "must_avoid_changed_path_shortcut": True,
                    "must_hide_gold_path_before_options": True,
                },
                "residual_overlap": root_id in residual_root_ids,
                "materialization_actions": root_brief_actions(
                    str(queue_row["language_family"]),
                    str(queue_row["repo_family"]),
                    str(queue_row["verifier_id"]),
                ),
            }
        )

    brief_rows.sort(key=lambda row: (lane_priority(str(row["language_family"])), int(row["queue_rank"]), row["root_id"]))

    lane_rows: list[dict[str, Any]] = []
    for language_family in ("c_cpp", "python", "rust", "web_js_ts_html"):
        subset = [row for row in brief_rows if row["language_family"] == language_family]
        if not subset:
            continue
        repo_counts = Counter(str(row["repo_family"]) for row in subset)
        verifier_counts = Counter(str(row["verifier_id"]) for row in subset)
        lane_rows.append(
            {
                "language_family": language_family,
                "queue_root_count": len(subset),
                "repo_family_counts": dict(sorted(repo_counts.items())),
                "verifier_id_counts": dict(sorted(verifier_counts.items())),
                "top_root_ids": [str(row["root_id"]) for row in subset[:5]],
                "headline": (
                    frontier_queue.get("language_summaries", {})
                    .get(language_family, {})
                    .get("lane_blocker")
                    or "no_summary"
                ),
                "immediate_builder_goal": {
                    "c_cpp": "materialize broad reviewed bundles from compiled roots with selected-test anchors",
                    "python": "materialize trace-backed verifier disambiguation roots outside dominant repo families",
                    "rust": "materialize fresh citation-contrast roots beyond tokenizers and abstention-heavy support",
                    "web_js_ts_html": "materialize pure-web verifier/test anchored roots and prove they are not changed-path shortcuts",
                }[language_family],
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "first_wave_root_materialization_briefs_ready",
        "claim_scope": [
            "Convert the stage10763 first-wave admission queue into concrete root materialization briefs with source/state evidence summaries.",
            "Make bundle construction actionable without reopening the old same-surface replay path.",
            "Prioritize multilingual reviewed-bundle scale according to the real supply bottlenecks and anti-cheat contract.",
        ],
        "metrics": {
            "brief_count": len(brief_rows),
            "lane_counts": dict(sorted(Counter(str(row["language_family"]) for row in brief_rows).items())),
            "execution_route_counts": dict(sorted(Counter(str(row["execution_route"]) for row in brief_rows).items())),
            "verifier_id_counts": dict(sorted(Counter(str(row["verifier_id"]) for row in brief_rows).items())),
        },
        "headline_findings": [
            "The queued compiled roots already contain enough state to drive bundle construction: changed files, verifier targets, key symbols, execution route, and multiple supervision projections.",
            "C/C++ is still the strongest first-wave materialization lane because it combines larger queue size with real selected-test anchors and broader repo diversity.",
            "Python first-wave roots now expose a trace-backed verifier subset that can grow beyond the single MirrorMind residual without replaying the strict root.",
            "Rust and Web remain supply-constrained, but the briefs now isolate which compiled roots are worth turning into real reviewed bundles next.",
        ],
        "anti_cheat_contract": [
            "Use these briefs only as source material for new reviewed bundles, not as direct promoted eval rows.",
            "Do not expose changed_files_sample or verification_targets_sample verbatim as the final candidate-answer surface without adding candidate competition.",
            "Keep root-level split isolation intact when any brief is promoted into train, validation, or strict reviewed bundles.",
            "If a brief is materialized into a bundle, require a new anti-cheat card that tests changed-path shortcut risk and visible-evidence sufficiency.",
        ],
        "next_best_step": "Use the highest-ranked C/C++ and Python briefs to build the next reviewed maintainer bundle packets, then add fresh Rust and pure-web reviewed bundles from their queued briefs before attempting another broader multilingual training package.",
        "source_artifacts": {
            "queue": display(QUEUE_JSONL),
            "admission_manifest": display(ADMISSION_JSONL),
            "compiled_roots": display(COMPILED_ROOTS),
            "compiled_states": display(COMPILED_STATES),
            "compiled_multitarget_rows": display(COMPILED_ROWS),
            "frontier_queue": display(FRONTIER_QUEUE),
            "current_residual_rows": display(CURRENT_RESIDUALS),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "briefs_jsonl": display(BRIEFS_JSONL),
            "lane_rollup_jsonl": display(LANE_JSONL),
        },
    }

    write_jsonl(BRIEFS_JSONL, brief_rows)
    write_jsonl(LANE_JSONL, lane_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "brief_count": payload["metrics"]["brief_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
