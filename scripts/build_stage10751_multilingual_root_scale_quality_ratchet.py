#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10751
NAME = "stage10751_multilingual_root_scale_quality_ratchet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_root_scale_quality_ratchet.json"
LANGUAGE_PLANS_JSONL = OUT_DIR / "language_batch_plans.jsonl"
REPO_CAPS_JSONL = OUT_DIR / "repo_family_caps.jsonl"
SOURCE_EXPANSION_JSONL = OUT_DIR / "source_family_expansion_manifest.jsonl"
THRESHOLDS_JSONL = OUT_DIR / "root_quality_thresholds.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10738_root_admission_manifest_v3/root_admission_manifest_v3.jsonl"
ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10738_root_admission_manifest_v3/root_admission_manifest_v3.json"
SCALE_PACKAGE = ROOT / "runs/local/artifacts/stage10739_multilingual_root_scale_package_v2/multilingual_root_scale_package_v2.json"
SCALE_READY = ROOT / "runs/local/artifacts/stage10739_multilingual_root_scale_package_v2/scale_ready_root_inventory.jsonl"
FRONTIER_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"
QUALITY_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"

LANGUAGES = ["python", "rust", "c_cpp", "web_js_ts_html"]

PHASE_CAP_FRACTIONS = {
    "python": {"phase_1": 0.12, "phase_2": 0.08, "phase_3": 0.05, "phase_4": 0.04},
    "rust": {"phase_1": 0.18, "phase_2": 0.12, "phase_3": 0.08, "phase_4": 0.06},
    "c_cpp": {"phase_1": 0.15, "phase_2": 0.10, "phase_3": 0.07, "phase_4": 0.05},
    "web_js_ts_html": {"phase_1": 0.18, "phase_2": 0.12, "phase_3": 0.08, "phase_4": 0.06},
}

MIN_GOLD_SHARE = {
    "phase_1": 0.55,
    "phase_2": 0.45,
    "phase_3": 0.35,
    "phase_4": 0.30,
}

MIN_VERIFIER_SHARE = {
    "phase_1": 0.70,
    "phase_2": 0.60,
    "phase_3": 0.50,
    "phase_4": 0.45,
}

MIN_SELECTED_TEST_SHARE = {
    "phase_1": 0.55,
    "phase_2": 0.45,
    "phase_3": 0.40,
    "phase_4": 0.35,
}

MIN_DISTINCT_REPOS = {
    "python": {"phase_1": 25, "phase_2": 80, "phase_3": 250, "phase_4": 600},
    "rust": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
    "c_cpp": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
    "web_js_ts_html": {"phase_1": 20, "phase_2": 60, "phase_3": 180, "phase_4": 400},
}

MIN_BATCH_SIZE = {
    "python": 250,
    "rust": 150,
    "c_cpp": 150,
    "web_js_ts_html": 150,
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def phase_target(lane: dict[str, Any], phase_name: str) -> int:
    return int(((lane.get("phase_targets") or {}).get(phase_name)) or 0)


def threshold_rows() -> list[dict[str, Any]]:
    return [
        {
            "quality_tier": "gold",
            "min_quality_score": 0.75,
            "required_properties": [
                "prompt_target_leak_rows == 0",
                "verifier_anchor == true",
                "selected_test_anchor == true",
                "admit_role in {train, validation, strict_eval}",
            ],
            "preferred_properties": [
                "reviewed maintainer bundle or equivalent adjudicated root",
                "non-abstention-heavy unless the task is genuinely underdetermined",
                "repo family not already near cap for the target language",
            ],
        },
        {
            "quality_tier": "silver",
            "min_quality_score": 0.50,
            "required_properties": [
                "prompt_target_leak_rows == 0",
                "verifier_anchor == true",
                "admit_role in {train, validation, strict_eval}",
            ],
            "preferred_properties": [
                "selected_test_anchor == true",
                "candidate competition present",
                "source-heldout admissible when available",
            ],
        },
        {
            "quality_tier": "bronze",
            "min_quality_score": 0.00,
            "required_properties": [
                "prompt_target_leak_rows == 0",
                "admit_role != quarantine",
            ],
            "preferred_properties": [
                "used for retrieval/pretraining support rather than headline promotion",
                "must not dominate a language batch",
            ],
        },
        {
            "quality_tier": "quarantine",
            "min_quality_score": 0.00,
            "required_properties": [
                "prompt_target_leak_rows > 0 or admit_role == quarantine",
            ],
            "preferred_properties": [
                "rewrite interface or re-materialize root before any promotable use",
            ],
        },
    ]


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    load_json(ADMISSION_SUMMARY)
    scale_package = load_json(SCALE_PACKAGE)
    scale_ready_rows = load_jsonl(SCALE_READY)
    frontier_queue = load_json(FRONTIER_QUEUE)
    quality_contract = load_json(QUALITY_CONTRACT)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scale_ready_rows:
        by_language[str(row.get("language_family") or "unknown")].append(row)

    language_batch_plans: list[dict[str, Any]] = []
    repo_caps: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []

    for language in LANGUAGES:
        lane = (frontier_queue.get("language_lanes") or {}).get(language) or {}
        rows = by_language.get(language, [])
        promotable_rows = [row for row in rows if str(row.get("admit_role") or "") in {"train", "validation", "strict_eval"}]
        repo_counts = Counter(str(row.get("repo_family") or "unknown") for row in promotable_rows)
        source_counts = Counter(str(row.get("source_kind") or "unknown") for row in promotable_rows)
        tier_counts = Counter(str(row.get("quality_tier") or "unknown") for row in promotable_rows)
        verifier_count = sum(1 for row in promotable_rows if bool(row.get("verifier_anchor")))
        selected_count = sum(1 for row in promotable_rows if bool(row.get("selected_test_anchor")))
        abstention_heavy_count = sum(1 for row in promotable_rows if bool(row.get("abstention_heavy")))
        total_promotable = len(promotable_rows)

        phase_cards: dict[str, Any] = {}
        for phase_name in ("phase_1", "phase_2", "phase_3", "phase_4"):
            target = phase_target(lane, phase_name)
            cap_fraction = PHASE_CAP_FRACTIONS[language][phase_name]
            repo_cap = max(1, math.ceil(target * cap_fraction))
            distinct_repo_min = MIN_DISTINCT_REPOS[language][phase_name]
            gold_needed = math.ceil(target * MIN_GOLD_SHARE[phase_name])
            verifier_needed = math.ceil(target * MIN_VERIFIER_SHARE[phase_name])
            selected_needed = math.ceil(target * MIN_SELECTED_TEST_SHARE[phase_name])
            current_gold = tier_counts.get("gold", 0)
            current_distinct_repos = len(repo_counts)
            phase_cards[phase_name] = {
                "target_roots": target,
                "max_repo_family_roots": repo_cap,
                "min_distinct_repo_families": distinct_repo_min,
                "min_gold_roots": gold_needed,
                "min_verifier_anchor_roots": verifier_needed,
                "min_selected_test_anchor_roots": selected_needed,
                "current_gaps": {
                    "roots": max(target - total_promotable, 0),
                    "gold": max(gold_needed - current_gold, 0),
                    "verifier": max(verifier_needed - verifier_count, 0),
                    "selected_test": max(selected_needed - selected_count, 0),
                    "distinct_repo_families": max(distinct_repo_min - current_distinct_repos, 0),
                },
            }
            for repo_family, current_count in repo_counts.items():
                repo_caps.append(
                    {
                        "language_family": language,
                        "phase": phase_name,
                        "repo_family": repo_family,
                        "current_promotable_roots": current_count,
                        "max_allowed_roots": repo_cap,
                        "over_cap_now": current_count > repo_cap,
                        "needs_dilution": current_count > max(repo_cap // 2, 1),
                    }
                )

        top_repo_families = [
            {
                "repo_family": repo_family,
                "promotable_roots": count,
                "share": round(count / max(total_promotable, 1), 4),
            }
            for repo_family, count in repo_counts.most_common(10)
        ]

        phase1 = phase_cards["phase_1"]
        next_batch_size = max(
            MIN_BATCH_SIZE[language],
            min(
                max(phase1["current_gaps"]["roots"], 0),
                phase1["target_roots"],
            ),
        )
        next_batch_size = min(next_batch_size, max(phase1["target_roots"], MIN_BATCH_SIZE[language]))

        next_batch_mix = {
            "gold_min": min(next_batch_size, math.ceil(next_batch_size * MIN_GOLD_SHARE["phase_1"])),
            "silver_max": max(0, math.floor(next_batch_size * 0.40)),
            "bronze_max": max(0, math.floor(next_batch_size * 0.10)),
        }

        plan = {
            "language_family": language,
            "current_frontier_strict_accuracy": lane.get("strict_accuracy"),
            "lane_blocker": lane.get("lane_blocker"),
            "total_promotable_roots": total_promotable,
            "quality_tier_counts": dict(sorted(tier_counts.items())),
            "source_kind_counts": dict(sorted(source_counts.items())),
            "verifier_anchor_roots": verifier_count,
            "selected_test_anchor_roots": selected_count,
            "abstention_heavy_roots": abstention_heavy_count,
            "distinct_repo_families": len(repo_counts),
            "top_repo_families": top_repo_families,
            "phase_cards": phase_cards,
            "recommended_next_batch": {
                "target_roots": next_batch_size,
                "min_distinct_repo_families": max(8, math.ceil(next_batch_size / max(phase1["max_repo_family_roots"], 1))),
                "max_roots_per_repo_family": phase1["max_repo_family_roots"],
                "mix": next_batch_mix,
                "must_hold": [
                    "prompt_target_leak_rows == 0 for every promoted root",
                    "same root_id and root_lineage_key isolated to one split component",
                    "fresh heldout reserved before training",
                    "repo family cap respected at admission time",
                    "new batch preserves the repaired v2.7 canary and leak-clean status",
                ],
            },
            "priority_notes": list(lane.get("notes") or []),
            "next_actions": list(lane.get("next_actions") or []),
        }
        language_batch_plans.append(plan)

        for repo_family, count in repo_counts.most_common(12):
            source_manifest.append(
                {
                    "language_family": language,
                    "repo_family": repo_family,
                    "current_promotable_roots": count,
                    "phase_1_repo_cap": phase_cards["phase_1"]["max_repo_family_roots"],
                    "saturation_risk": "high"
                    if count > phase_cards["phase_1"]["max_repo_family_roots"]
                    else "medium"
                    if count > max(phase_cards["phase_1"]["max_repo_family_roots"] // 2, 1)
                    else "low",
                    "action": "dilute_with_new_repo_families" if count > max(phase_cards["phase_1"]["max_repo_family_roots"] // 2, 1) else "can_expand_carefully",
                }
            )

    repo_caps.sort(
        key=lambda row: (
            row["language_family"],
            row["phase"],
            not row["over_cap_now"],
            -int(row["current_promotable_roots"]),
            row["repo_family"],
        )
    )
    language_batch_plans.sort(key=lambda row: LANGUAGES.index(row["language_family"]))
    source_manifest.sort(
        key=lambda row: (
            row["language_family"],
            {"high": 0, "medium": 1, "low": 2}.get(str(row["saturation_risk"]), 3),
            -int(row["current_promotable_roots"]),
            row["repo_family"],
        )
    )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_quality_ratchet_ready",
        "claim_scope": [
            "Translate the current root-admission inventory into a concrete quality-ratchet for scaling toward 20k+ roots per language without degrading eval integrity.",
            "Set explicit per-language batch targets, repo-family caps, verifier/share minima, and gold/silver/bronze requirements before counting new roots toward scale.",
            "This is a scaling-control and anti-eval-hacking artifact, not a new 100M-vs-Gemma score claim.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v3": display(ADMISSION_ROWS),
            "multilingual_root_scale_package_v2": display(SCALE_PACKAGE),
            "scale_ready_inventory": display(SCALE_READY),
            "multilingual_root_scale_frontier_queue": display(FRONTIER_QUEUE),
            "multilingual_root_scale_quality_contract": display(QUALITY_CONTRACT),
        },
        "headline_findings": [
            "The repo already has the right root/state compiler and admission scaffold, but scale is still unconstrained enough that Python and a few repo families could dominate future batches.",
            "A 20k-per-language target is viable only if new roots are counted under per-language repo caps, verifier-anchor minima, selected-test minima, and fresh-heldout reservation rules.",
            "C/C++ is closest to honest near-term scale materialization, Python has the largest raw supply but the highest concentration risk, Rust is still supply-limited for promotable citation roots, and Web is still acquisition-limited for pure-web verifier-anchored roots.",
        ],
        "global_contract": {
            "quality_thresholds": threshold_rows(),
            "batch_acceptance_gates": [
                "No batch counts toward scale unless it is leak-clean, root-split clean, and heldout-reserved before training.",
                "No language batch may exceed its per-phase repo-family cap.",
                "No batch may reduce verifier-anchor share, selected-test share, or gold-root share below the phase minima.",
                "No batch may be promoted unless it preserves or improves the repaired v2.7 canary and fresh heldout score.",
            ],
            "long_term_targets": quality_contract.get("scale_targets") or {},
        },
        "language_batch_plans": language_batch_plans,
        "next_best_step": "Use this ratchet to build the next bulk root materialization queue. Admit roots against the per-language caps and minima instead of adding raw supply indiscriminately.",
        "outputs": {
            "summary": display(SUMMARY_JSON),
            "language_batch_plans": display(LANGUAGE_PLANS_JSONL),
            "repo_family_caps": display(REPO_CAPS_JSONL),
            "source_family_expansion_manifest": display(SOURCE_EXPANSION_JSONL),
            "quality_thresholds": display(THRESHOLDS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(LANGUAGE_PLANS_JSONL, language_batch_plans)
    write_jsonl(REPO_CAPS_JSONL, repo_caps)
    write_jsonl(SOURCE_EXPANSION_JSONL, source_manifest)
    write_jsonl(THRESHOLDS_JSONL, threshold_rows())
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary": display(SUMMARY_JSON),
            "language_batch_plans": display(LANGUAGE_PLANS_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
