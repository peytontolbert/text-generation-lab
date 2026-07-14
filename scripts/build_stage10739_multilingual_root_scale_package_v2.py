#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10739
NAME = "stage10739_multilingual_root_scale_package_v2"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_root_scale_package_v2.json"
SCALE_READY_JSONL = OUT_DIR / "scale_ready_root_inventory.jsonl"
QUARANTINE_BACKLOG_JSONL = OUT_DIR / "quarantine_rewrite_backlog.jsonl"
LANGUAGE_CARDS_JSONL = OUT_DIR / "language_scale_cards.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10738_root_admission_manifest_v3/root_admission_manifest_v3.jsonl"
ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10738_root_admission_manifest_v3/root_admission_manifest_v3.json"
ROOT_SCALE_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"
SCALE_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"

LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def tier_for_root(row: dict[str, Any]) -> str:
    if str(row.get("admit_role") or "") == "quarantine":
        return "quarantine"
    quality = float(row.get("quality_score") or 0.0)
    selected = bool(row.get("selected_test_anchor"))
    verifier = bool(row.get("verifier_anchor"))
    leak_rows = int(row.get("prompt_target_leak_rows") or 0)
    if leak_rows > 0:
        return "quarantine"
    if quality >= 0.75 and verifier and selected:
        return "gold"
    if quality >= 0.5 and verifier:
        return "silver"
    return "bronze"


def phase_eligibility(tier: str, admit_role: str) -> dict[str, bool]:
    promotable_role = admit_role in {"train", "validation", "strict_eval"}
    return {
        "phase_1": tier in {"gold", "silver"} and promotable_role,
        "phase_2": tier in {"gold", "silver", "bronze"} and promotable_role,
        "long_term": tier in {"gold", "silver", "bronze"} and admit_role != "quarantine",
    }


def summarize_counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    admission_summary = load_json(ADMISSION_SUMMARY)
    scale_queue = load_json(ROOT_SCALE_QUEUE)
    scale_contract = load_json(SCALE_CONTRACT)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scale_ready_rows: list[dict[str, Any]] = []
    quarantine_backlog: list[dict[str, Any]] = []

    for row in admission_rows:
        admit_role = str(row.get("admit_role") or "")
        quality_tier = tier_for_root(row)
        phase_flags = phase_eligibility(quality_tier, admit_role)
        enriched = {
            **row,
            "quality_tier": quality_tier,
            "phase_eligibility": phase_flags,
            "ready_for_large_scale_train": quality_tier in {"gold", "silver"} and admit_role == "train",
            "needs_interface_rewrite": admit_role == "quarantine" or int(row.get("prompt_target_leak_rows") or 0) > 0,
        }
        scale_ready_rows.append(enriched)
        by_language[str(row.get("language_family") or "unknown")].append(enriched)
        if enriched["needs_interface_rewrite"]:
            quarantine_backlog.append(
                {
                    "root_id": enriched["root_id"],
                    "language_family": enriched["language_family"],
                    "repo_family": enriched["repo_family"],
                    "source_kind": enriched["source_kind"],
                    "quality_score": enriched["quality_score"],
                    "admit_role": enriched["admit_role"],
                    "prompt_target_leak_rows": enriched["prompt_target_leak_rows"],
                    "notes": enriched.get("notes") or [],
                    "rewrite_priority": "high" if enriched["language_family"] in {"rust", "web_js_ts_html"} else "medium",
                }
            )

    scale_ready_rows.sort(
        key=lambda row: (
            str(row.get("language_family") or ""),
            str(row.get("quality_tier") or ""),
            -float(row.get("quality_score") or 0.0),
            str(row.get("root_id") or ""),
        )
    )
    quarantine_backlog.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("rewrite_priority") or "low"), 3),
            str(row.get("language_family") or ""),
            -float(row.get("quality_score") or 0.0),
            str(row.get("root_id") or ""),
        )
    )

    language_cards: list[dict[str, Any]] = []
    queue_lanes = scale_queue.get("language_lanes") or {}
    for language in LANGUAGES:
        rows = by_language.get(language, [])
        lane = queue_lanes.get(language) or {}
        phase_targets = lane.get("phase_targets") or {}
        phase_1_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_1"])
        phase_2_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_2"])
        long_term_ready = sum(1 for row in rows if row["phase_eligibility"]["long_term"])
        language_cards.append(
            {
                "language_family": language,
                "total_roots": len(rows),
                "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "unknown") for row in rows).items())),
                "admit_role_counts": summarize_counter(rows, "admit_role"),
                "source_kind_counts": summarize_counter(rows, "source_kind"),
                "repo_family_counts_top10": [
                    {"repo_family": repo_family, "roots": count}
                    for repo_family, count in Counter(str(row.get("repo_family") or "unknown") for row in rows).most_common(10)
                ],
                "phase_ready_counts": {
                    "phase_1": phase_1_ready,
                    "phase_2": phase_2_ready,
                    "long_term": long_term_ready,
                },
                "targets": phase_targets,
                "gaps": {
                    "phase_1": max(int(phase_targets.get("phase_1") or 0) - phase_1_ready, 0),
                    "phase_2": max(int(phase_targets.get("phase_2") or 0) - phase_2_ready, 0),
                    "phase_3": max(int(phase_targets.get("phase_3") or 0) - long_term_ready, 0),
                    "phase_4": max(int(phase_targets.get("phase_4") or 0) - long_term_ready, 0),
                },
                "lane_blocker": lane.get("lane_blocker"),
                "strict_accuracy": lane.get("strict_accuracy"),
                "next_actions": lane.get("next_actions") or [],
                "notes": lane.get("notes") or [],
            }
        )

    write_jsonl(SCALE_READY_JSONL, scale_ready_rows)
    write_jsonl(QUARANTINE_BACKLOG_JSONL, quarantine_backlog)
    write_jsonl(LANGUAGE_CARDS_JSONL, language_cards)

    ready_train_counts = {
        language: sum(1 for row in by_language.get(language, []) if row["ready_for_large_scale_train"])
        for language in LANGUAGES
    }
    current_frontier = scale_queue.get("current_frontier") or {}
    reviewed_bundle_roots_by_language_current = dict(
        sorted(
            Counter(
                str(row.get("language_family") or "")
                for row in admission_rows
                if str(row.get("source_kind") or "") == "reviewed_bundle_root"
            ).items()
        )
    )
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_package_v2_ready",
        "claim_scope": [
            "Refresh the root-scale control package against the latest admission manifest that includes the new reviewed C/C++ train-support roots.",
            "Expose scale-ready roots, quarantine rewrite backlog, and per-language blockers under the current post-10729 plateau.",
            "This is a scaling-control artifact, not a new standalone frontier claim.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v3": display(ADMISSION_ROWS),
            "root_admission_summary_v3": display(ADMISSION_SUMMARY),
            "multilingual_root_scale_frontier_queue": display(ROOT_SCALE_QUEUE),
            "multilingual_root_scale_quality_contract": display(SCALE_CONTRACT),
        },
        "headline_findings": [
            "The standalone strict frontier is still 22/24, so the next honest gain has to come from root-scale growth and interface cleanup rather than another same-surface probe.",
            "C/C++ now has a materially larger reviewed train-support lane than the old v1 scale package showed; the stale v1 counts understated C/C++ readiness.",
            "Python and Rust remain the two headline residual blockers, but their next move is fresh reviewed root supply, not more replay on the current strict rows.",
        ],
        "frontier_status": {
            "strict_accuracy": current_frontier.get("strict_accuracy"),
            "strict_rows": 24,
            "miss_row_ids": current_frontier.get("strict_miss_rows") or [],
        },
        "global_counts": {
            "roots_total": len(scale_ready_rows),
            "quarantine_backlog_roots": len(quarantine_backlog),
            "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "unknown") for row in scale_ready_rows).items())),
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "unknown") for row in scale_ready_rows).items())),
            "ready_for_large_scale_train_by_language": ready_train_counts,
            "phase_1_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_1"]),
            "phase_2_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_2"]),
            "reviewed_bundle_roots_by_language_current": reviewed_bundle_roots_by_language_current,
        },
        "language_cards": language_cards,
        "anti_cheat_contract": scale_queue.get("anti_cheat_contract") or [],
        "next_best_step": "Use this v2 package to drive the next bulk materialization sprint: C/C++ reviewed bundle expansion first, then Python verifier and Rust citation fresh-root acquisition under the queue's lane-specific blockers.",
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "scale_ready_inventory": display(SCALE_READY_JSONL),
            "quarantine_backlog": display(QUARANTINE_BACKLOG_JSONL),
            "language_cards": display(LANGUAGE_CARDS_JSONL),
        },
    }

    write_json(PACKAGE_JSON, package)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": package["decision"],
            "package_json": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
