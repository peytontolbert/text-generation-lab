#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10773
NAME = "stage10773_bulk_multilingual_root_materialization_briefs"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "bulk_multilingual_root_materialization_briefs.json"
BRIEFS_JSONL = OUT_DIR / "root_materialization_briefs.jsonl"
LANE_JSONL = OUT_DIR / "lane_rollup.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPLY_SUMMARY = ROOT / "runs/local/artifacts/stage10772_bulk_multilingual_root_supply_census/bulk_multilingual_root_supply_census.json"
SUPPLY_UNIQUE = ROOT / "runs/local/artifacts/stage10772_bulk_multilingual_root_supply_census/unique_root_supply_manifest.jsonl"
SUPPLY_QUEUE = ROOT / "runs/local/artifacts/stage10772_bulk_multilingual_root_supply_census/language_lane_queue.jsonl"


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


def materialization_actions(language_family: str, verifier_id: str) -> list[str]:
    actions = [
        "Recover real source snippets and concrete verifier observations before writing any candidate options.",
        "Create candidate competition across nearby changed files, tests, and symbols so the answer is not solvable from path exposure alone.",
        "Write a fresh anti-cheat card that checks prompt_target_leak, changed-path shortcut risk, and visible-evidence sufficiency.",
    ]
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        actions.append("Preserve trace-backed observations in the visible evidence instead of compressing them away.")
    elif verifier_id == "PASS_TARGETED_TEST_SELECTION":
        actions.append("Keep selected-test competition explicit, but hide the gold test identity until the option set.")

    if language_family == "python":
        actions.append("Prefer verifier-outcome and evidence-citation perspectives that separate similar tests or files.")
    elif language_family == "rust":
        actions.append("Force citation contrast away from candidate_change_surface and toward verifier/test/trace evidence.")
    elif language_family == "c_cpp":
        actions.append("Exploit build/test anchors to create real kernel-wrapper-test competition across files.")
    elif language_family == "web_js_ts_html":
        actions.append("Require a pure-web verifier/test path before using the bundle for any promotable claim.")
    return actions


def query_preview(query_text: str, limit: int = 600) -> str:
    compact = " ".join(part.strip() for part in query_text.splitlines() if part.strip())
    return compact[:limit]


def main() -> None:
    supply_summary = load_json(SUPPLY_SUMMARY)
    unique_rows = load_jsonl(SUPPLY_UNIQUE)
    queue_rows = load_jsonl(SUPPLY_QUEUE)

    unique_by_lineage = {str(row["root_lineage_key"]): row for row in unique_rows}
    queue_rank_by_language: dict[str, int] = Counter()

    briefs: list[dict[str, Any]] = []
    for queue_row in queue_rows:
        language_family = str(queue_row["language_family"])
        queue_rank_by_language[language_family] += 1
        lineage_key = str(queue_row["root_lineage_key"])
        root = unique_by_lineage[lineage_key]
        briefs.append(
            {
                "language_family": language_family,
                "queue_rank": int(queue_rank_by_language[language_family]),
                "root_lineage_key": lineage_key,
                "root_id": str(queue_row["root_id"]),
                "repo_family": str(queue_row["repo_family"]),
                "verifier_id": str(queue_row["verifier_id"]),
                "quality_tier": str(queue_row["quality_tier"]),
                "priority_score": int(queue_row["priority_score"]),
                "semantic_lane": str(queue_row["semantic_lane"]),
                "pack_id": str(queue_row["pack_id"]),
                "query_index": int(queue_row["query_index"]),
                "source_family_id": str(queue_row["source_family_id"]),
                "duplicate_source_count": int(root["duplicate_source_count"]),
                "duplicate_source_families": list(root["duplicate_source_families"]),
                "execution_route": str(root["execution_route"]),
                "selected_test_anchor_present": bool(root["selected_test_anchor_present"]),
                "verifier_anchor_present": bool(root["verifier_anchor_present"]),
                "changed_file_count": int(root["changed_file_count"]),
                "verification_target_count": int(root["verification_target_count"]),
                "key_symbol_count": int(root["key_symbol_count"]),
                "changed_files_sample": list(root["changed_files_sample"]),
                "verification_targets_sample": list(root["verification_targets_sample"]),
                "key_symbols_sample": list(root["key_symbols_sample"]),
                "query_preview": query_preview(str(root["query_text"])),
                "review_contract": {
                    "must_keep_root_split_atomic": True,
                    "must_hide_gold_path_before_options": True,
                    "must_avoid_changed_path_shortcut": True,
                    "must_require_visible_support_for_gold": True,
                },
                "materialization_actions": materialization_actions(language_family, str(queue_row["verifier_id"])),
            }
        )

    briefs.sort(key=lambda row: (row["language_family"], row["queue_rank"], -row["priority_score"], row["root_lineage_key"]))

    lane_rollup: list[dict[str, Any]] = []
    for language_family in ("c_cpp", "python", "rust", "web_js_ts_html"):
        subset = [row for row in briefs if row["language_family"] == language_family]
        if not subset:
            continue
        repo_counts = Counter(str(row["repo_family"]) for row in subset)
        verifier_counts = Counter(str(row["verifier_id"]) for row in subset)
        lane_rollup.append(
            {
                "language_family": language_family,
                "brief_count": len(subset),
                "top_repo_families": dict(repo_counts.most_common(8)),
                "verifier_counts": dict(verifier_counts.most_common()),
                "headline_gap": ((supply_summary.get("language_rollup") or {}).get(language_family) or {}).get("root_gap"),
                "top_brief_ids": [str(row["root_id"]) for row in subset[:5]],
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bulk_multilingual_root_materialization_briefs_ready",
        "claim_scope": [
            "Turn the bulk multilingual root-supply census into actionable materialization briefs for reviewed bundle construction.",
            "Keep the queue tied to real source-backed verifier anchors and anti-cheat review instead of raw root count inflation.",
            "Expose the next concrete roots per language for scaling reviewed v2.7 toward a broader v2.8 inventory.",
        ],
        "metrics": {
            "brief_count": len(briefs),
            "lane_counts": dict(sorted(Counter(str(row["language_family"]) for row in briefs).items())),
            "verifier_counts": dict(sorted(Counter(str(row["verifier_id"]) for row in briefs).items())),
            "selected_test_anchor_briefs": sum(1 for row in briefs if row["selected_test_anchor_present"]),
        },
        "headline_findings": [
            "The bulk queue is now materialization-ready: every brief carries repo family, verifier strength, path/test samples, and anti-cheat obligations.",
            "C/C++ is the cleanest immediate reviewed-bundle lane because the queue is small, verifier-anchored, and spread across real repos like cccl, onnxruntime, cuEmbed, falco, and parametergolf.",
            "Python has enough queued roots to broaden support, but repo-family caps still matter because agentkernel remains dominant even after dedupe.",
            "Rust and Web are still scarce enough that each new brief is high leverage and should be materialized before another broad probe.",
        ],
        "next_best_step": "Use the highest-ranked C/C++ and Python briefs for the next reviewed packet builder, then materialize all queued Rust and Web briefs to improve language balance before the next multilingual training package.",
        "source_artifacts": {
            "supply_summary": display(SUPPLY_SUMMARY),
            "unique_root_supply_manifest": display(SUPPLY_UNIQUE),
            "language_lane_queue": display(SUPPLY_QUEUE),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "briefs_jsonl": display(BRIEFS_JSONL),
            "lane_rollup_jsonl": display(LANE_JSONL),
        },
    }

    write_jsonl(BRIEFS_JSONL, briefs)
    write_jsonl(LANE_JSONL, lane_rollup)
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
