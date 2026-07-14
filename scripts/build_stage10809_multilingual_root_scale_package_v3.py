#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10809
NAME = "stage10809_multilingual_root_scale_package_v3"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_root_scale_package_v3.json"
SCALE_READY_JSONL = OUT_DIR / "scale_ready_root_inventory.jsonl"
QUARANTINE_BACKLOG_JSONL = OUT_DIR / "quarantine_rewrite_backlog.jsonl"
LANGUAGE_CARDS_JSONL = OUT_DIR / "language_scale_cards.jsonl"
REPO_PRESSURE_JSONL = OUT_DIR / "repo_family_pressure_cards.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10784_root_admission_manifest_v5/root_admission_manifest_v5.jsonl"
ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10784_root_admission_manifest_v5/root_admission_manifest_v5.json"
ROOT_SCALE_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"
SCALE_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
STRICT_AUDIT = ROOT / "runs/local/artifacts/stage10808_raw_role_option_value_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"

LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]

PHASE_CAP_FRACTIONS = {
    "python": {"phase_1": 0.12, "phase_2": 0.08, "phase_3": 0.05, "phase_4": 0.04},
    "rust": {"phase_1": 0.18, "phase_2": 0.12, "phase_3": 0.08, "phase_4": 0.06},
    "c_cpp": {"phase_1": 0.15, "phase_2": 0.10, "phase_3": 0.07, "phase_4": 0.05},
    "web_js_ts_html": {"phase_1": 0.18, "phase_2": 0.12, "phase_3": 0.08, "phase_4": 0.06},
}

MIN_GOLD_SHARE = {"phase_1": 0.55, "phase_2": 0.45, "phase_3": 0.35, "phase_4": 0.30}
MIN_VERIFIER_SHARE = {"phase_1": 0.70, "phase_2": 0.60, "phase_3": 0.50, "phase_4": 0.45}
MIN_SELECTED_TEST_SHARE = {"phase_1": 0.55, "phase_2": 0.45, "phase_3": 0.40, "phase_4": 0.35}
MIN_DISTINCT_REPOS = {
    "python": {"phase_1": 25, "phase_2": 80, "phase_3": 250, "phase_4": 600},
    "rust": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
    "c_cpp": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
    "web_js_ts_html": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
}
MIN_BATCH_SIZE = {"python": 250, "rust": 150, "c_cpp": 150, "web_js_ts_html": 150}


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


def build_frontier_status(strict_audit: dict[str, Any]) -> dict[str, Any]:
    miss_rows = [
        row["row_id"]
        for row in strict_audit.get("row_cards") or []
        if not bool(row.get("constrained_choice_match"))
    ]
    return {
        "strict_accuracy": strict_audit.get("constrained_choice_top1_accuracy"),
        "strict_rows": strict_audit.get("constrained_choice_rows"),
        "full_vocab_top1_accuracy": strict_audit.get("full_vocab_top1_accuracy"),
        "miss_row_ids": miss_rows,
    }


def phase_target(scale_targets: dict[str, Any], lane_phase_targets: dict[str, Any], language: str, phase_name: str) -> int:
    lane_value = (lane_phase_targets.get(phase_name) if lane_phase_targets else None) or 0
    contract_value = ((scale_targets.get(phase_name) or {}).get(language)) or 0
    if lane_value:
        return int(lane_value)
    return int(contract_value)


def pressure_label(current_count: int, repo_cap: int) -> str:
    if current_count > repo_cap:
        return "over_cap"
    if current_count > max(repo_cap // 2, 1):
        return "high"
    if current_count > max(repo_cap // 4, 1):
        return "medium"
    return "low"


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    admission_summary = load_json(ADMISSION_SUMMARY)
    scale_queue = load_json(ROOT_SCALE_QUEUE)
    scale_contract = load_json(SCALE_CONTRACT)
    strict_audit = load_json(STRICT_AUDIT)

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
                    "materialization_status": enriched.get("materialization_status"),
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

    queue_lanes = scale_queue.get("language_lanes") or {}
    scale_targets = scale_contract.get("scale_targets") or {}
    language_cards: list[dict[str, Any]] = []
    repo_pressure_cards: list[dict[str, Any]] = []

    for language in LANGUAGES:
        rows = by_language.get(language, [])
        lane = queue_lanes.get(language) or {}
        lane_phase_targets = lane.get("phase_targets") or {}
        promotable_rows = [row for row in rows if str(row.get("admit_role") or "") in {"train", "validation", "strict_eval"}]
        repo_counts = Counter(str(row.get("repo_family") or "unknown") for row in promotable_rows)
        tier_counts = Counter(str(row.get("quality_tier") or "unknown") for row in promotable_rows)
        source_kind_counts = Counter(str(row.get("source_kind") or "unknown") for row in rows)
        phase_ready_counts = {
            "phase_1": sum(1 for row in rows if row["phase_eligibility"]["phase_1"]),
            "phase_2": sum(1 for row in rows if row["phase_eligibility"]["phase_2"]),
            "long_term": sum(1 for row in rows if row["phase_eligibility"]["long_term"]),
        }
        verifier_count = sum(1 for row in promotable_rows if bool(row.get("verifier_anchor")))
        selected_count = sum(1 for row in promotable_rows if bool(row.get("selected_test_anchor")))
        gold_count = tier_counts.get("gold", 0)
        total_promotable = len(promotable_rows)

        phase_cards: dict[str, Any] = {}
        for phase_name in ("phase_1", "phase_2", "phase_3", "phase_4"):
            target = phase_target(scale_targets, lane_phase_targets, language, phase_name)
            repo_cap = max(1, math.ceil(target * PHASE_CAP_FRACTIONS[language][phase_name]))
            min_distinct = MIN_DISTINCT_REPOS[language][phase_name]
            min_gold = math.ceil(target * MIN_GOLD_SHARE[phase_name])
            min_verifier = math.ceil(target * MIN_VERIFIER_SHARE[phase_name])
            min_selected = math.ceil(target * MIN_SELECTED_TEST_SHARE[phase_name])
            phase_cards[phase_name] = {
                "target_roots": target,
                "max_repo_family_roots": repo_cap,
                "min_distinct_repo_families": min_distinct,
                "min_gold_roots": min_gold,
                "min_verifier_anchor_roots": min_verifier,
                "min_selected_test_anchor_roots": min_selected,
                "current_gaps": {
                    "roots": max(target - total_promotable, 0),
                    "gold": max(min_gold - gold_count, 0),
                    "verifier": max(min_verifier - verifier_count, 0),
                    "selected_test": max(min_selected - selected_count, 0),
                    "distinct_repo_families": max(min_distinct - len(repo_counts), 0),
                },
            }
            for repo_family, count in repo_counts.items():
                repo_pressure_cards.append(
                    {
                        "language_family": language,
                        "phase": phase_name,
                        "repo_family": repo_family,
                        "current_promotable_roots": count,
                        "max_allowed_roots": repo_cap,
                        "pressure": pressure_label(count, repo_cap),
                    }
                )

        phase1 = phase_cards["phase_1"]
        next_batch_roots = max(
            MIN_BATCH_SIZE[language],
            min(max(phase1["current_gaps"]["roots"], 0), phase1["target_roots"]),
        )
        next_batch_roots = min(next_batch_roots, max(phase1["target_roots"], MIN_BATCH_SIZE[language]))
        recommended_mix = {
            "gold_min": min(next_batch_roots, math.ceil(next_batch_roots * MIN_GOLD_SHARE["phase_1"])),
            "silver_max": max(0, math.floor(next_batch_roots * 0.40)),
            "bronze_max": max(0, math.floor(next_batch_roots * 0.10)),
        }

        language_cards.append(
            {
                "language_family": language,
                "total_roots": len(rows),
                "promotable_roots": total_promotable,
                "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "unknown") for row in rows).items())),
                "admit_role_counts": summarize_counter(rows, "admit_role"),
                "source_kind_counts": dict(sorted(source_kind_counts.items())),
                "materialization_status_counts": dict(sorted(Counter(str(row.get("materialization_status") or "unknown") for row in rows).items())),
                "repo_family_counts_top10": [
                    {"repo_family": repo_family, "roots": count}
                    for repo_family, count in Counter(str(row.get("repo_family") or "unknown") for row in rows).most_common(10)
                ],
                "phase_ready_counts": phase_ready_counts,
                "phase_cards": phase_cards,
                "lane_blocker": lane.get("lane_blocker"),
                "strict_accuracy": lane.get("strict_accuracy"),
                "next_actions": lane.get("next_actions") or [],
                "notes": lane.get("notes") or [],
                "recommended_next_batch": {
                    "target_roots": next_batch_roots,
                    "min_distinct_repo_families": max(8, math.ceil(next_batch_roots / max(phase1["max_repo_family_roots"], 1))),
                    "max_roots_per_repo_family": phase1["max_repo_family_roots"],
                    "mix": recommended_mix,
                    "must_hold": [
                        "prompt_target_leak_rows == 0 for every promoted root",
                        "same root_id and root_lineage_key isolated to one split component",
                        "fresh heldout reserved before training",
                        "repo family cap respected at admission time",
                        "new batch preserves the repaired v2.7 canary and leak-clean status",
                    ],
                },
            }
        )

    language_cards.sort(key=lambda row: LANGUAGES.index(row["language_family"]))
    repo_pressure_cards.sort(
        key=lambda row: (
            row["language_family"],
            row["phase"],
            {"over_cap": 0, "high": 1, "medium": 2, "low": 3}.get(str(row["pressure"]), 4),
            -int(row["current_promotable_roots"]),
            row["repo_family"],
        )
    )

    write_jsonl(SCALE_READY_JSONL, scale_ready_rows)
    write_jsonl(QUARANTINE_BACKLOG_JSONL, quarantine_backlog)
    write_jsonl(LANGUAGE_CARDS_JSONL, language_cards)
    write_jsonl(REPO_PRESSURE_JSONL, repo_pressure_cards)

    ready_train_counts = {
        language: sum(1 for row in by_language.get(language, []) if row["ready_for_large_scale_train"])
        for language in LANGUAGES
    }
    frontier_status = build_frontier_status(strict_audit)
    reviewed_bundle_roots_by_language_current = dict(
        sorted(
            Counter(
                str(row.get("language_family") or "")
                for row in admission_rows
                if str(row.get("source_kind") or "") == "reviewed_bundle_root"
            ).items()
        )
    )
    current_promotable_by_language = {
        language: sum(1 for row in by_language.get(language, []) if str(row.get("admit_role") or "") in {"train", "validation", "strict_eval"})
        for language in LANGUAGES
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_package_v3_ready",
        "claim_scope": [
            "Refresh the multilingual root-scale control package against the latest v5 admission manifest and current strict frontier artifact.",
            "Expose current promotable root supply, quarantine backlog, repo-family pressure, and per-language phase gaps under the 20k+/language scale target.",
            "This is a scale-control and anti-eval-hacking artifact, not a new 100M-vs-Gemma score claim.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v5": display(ADMISSION_ROWS),
            "root_admission_summary_v5": display(ADMISSION_SUMMARY),
            "multilingual_root_scale_frontier_queue": display(ROOT_SCALE_QUEUE),
            "multilingual_root_scale_quality_contract": display(SCALE_CONTRACT),
            "current_strict_frontier_audit": display(STRICT_AUDIT),
        },
        "headline_findings": [
            "The long-term 40k Python / 20k Rust / 20k C/C++ / 20k Web target is compatible with the current contracts, but current promotable supply is still tiny and badly imbalanced.",
            "Python remains the dominant raw supply lane and therefore the highest concentration risk; Rust and Web remain the highest acquisition-risk lanes for honest promotion.",
            "The next scaling gain has to come from root admission, repo dilution, verifier-backed replenishment, and heldout reservation, not more same-surface strict-row repair.",
        ],
        "frontier_status": frontier_status,
        "global_counts": {
            "roots_total": len(scale_ready_rows),
            "quarantine_backlog_roots": len(quarantine_backlog),
            "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "unknown") for row in scale_ready_rows).items())),
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "unknown") for row in scale_ready_rows).items())),
            "ready_for_large_scale_train_by_language": ready_train_counts,
            "promotable_roots_by_language": current_promotable_by_language,
            "phase_1_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_1"]),
            "phase_2_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_2"]),
            "reviewed_bundle_roots_by_language_current": reviewed_bundle_roots_by_language_current,
            "manifest_rows": len(admission_rows),
            "compiled_root_rows": admission_summary.get("metrics", {}).get("compiled_root_rows"),
        },
        "anti_cheat_contract": scale_queue.get("anti_cheat_contract") or [],
        "scale_targets": scale_targets,
        "language_cards": language_cards,
        "next_best_step": "Use this v3 package to admit the next multilingual root batches under repo-family caps and heldout reservation, then materialize fresh Rust/Web and verifier-backed Python/C++ roots instead of chasing the current two strict residual rows.",
        "outputs": {
            "package_json": display(PACKAGE_JSON),
            "scale_ready_inventory": display(SCALE_READY_JSONL),
            "quarantine_backlog": display(QUARANTINE_BACKLOG_JSONL),
            "language_cards": display(LANGUAGE_CARDS_JSONL),
            "repo_family_pressure": display(REPO_PRESSURE_JSONL),
        },
    }

    write_json(PACKAGE_JSON, package)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": package["decision"],
            "summary": display(PACKAGE_JSON),
            "scale_ready_inventory": display(SCALE_READY_JSONL),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
