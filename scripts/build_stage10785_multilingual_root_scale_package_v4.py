#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10785
NAME = "stage10785_multilingual_root_scale_package_v4"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_root_scale_package_v4.json"
SCALE_READY_JSONL = OUT_DIR / "scale_ready_root_inventory.jsonl"
QUARANTINE_BACKLOG_JSONL = OUT_DIR / "quarantine_rewrite_backlog.jsonl"
LANGUAGE_CARDS_JSONL = OUT_DIR / "language_scale_cards.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10784_root_admission_manifest_v5/root_admission_manifest_v5.jsonl"
ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10784_root_admission_manifest_v5/root_admission_manifest_v5.json"

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
    materialization_status = str(row.get("materialization_status") or "")
    if leak_rows > 0:
        return "quarantine"
    if quality >= 0.75 and verifier and selected:
        return "gold"
    if quality >= 0.60 and verifier and materialization_status == "bulk_support_materialized":
        return "silver"
    if quality >= 0.50 and verifier:
        return "silver"
    return "bronze"


def phase_eligibility(tier: str, admit_role: str, materialization_status: str) -> dict[str, bool]:
    promotable_role = admit_role in {"train", "validation", "strict_eval"}
    strict_ready = tier in {"gold", "silver"} and promotable_role
    return {
        "phase_1": strict_ready,
        "phase_2": tier in {"gold", "silver", "bronze"} and promotable_role,
        "long_term": tier in {"gold", "silver", "bronze"} and admit_role != "quarantine",
        "needs_materialization": materialization_status in {"support_ready_not_materialized", "needs_richer_competition"},
    }


def summarize_counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    admission_summary = load_json(ADMISSION_SUMMARY)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scale_ready_rows: list[dict[str, Any]] = []
    quarantine_backlog: list[dict[str, Any]] = []

    for row in admission_rows:
        admit_role = str(row.get("admit_role") or "")
        materialization_status = str(row.get("materialization_status") or "unknown")
        quality_tier = tier_for_root(row)
        phase_flags = phase_eligibility(quality_tier, admit_role, materialization_status)
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

    language_cards: list[dict[str, Any]] = []
    for language in LANGUAGES:
        rows = by_language.get(language, [])
        promotable_rows = [row for row in rows if str(row.get("admit_role") or "") in {"train", "validation", "strict_eval"}]
        phase_1_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_1"])
        phase_2_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_2"])
        long_term_ready = sum(1 for row in rows if row["phase_eligibility"]["long_term"])
        language_cards.append(
            {
                "language_family": language,
                "total_roots": len(rows),
                "promotable_roots": len(promotable_rows),
                "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "") for row in rows).items())),
                "admit_role_counts": summarize_counter(rows, "admit_role"),
                "source_kind_counts": summarize_counter(rows, "source_kind"),
                "materialization_status_counts": summarize_counter(rows, "materialization_status"),
                "repo_family_counts_top10": [
                    {"repo_family": repo_family, "roots": count}
                    for repo_family, count in Counter(str(row.get("repo_family") or "") for row in rows).most_common(10)
                ],
                "phase_ready_counts": {
                    "phase_1": phase_1_ready,
                    "phase_2": phase_2_ready,
                    "long_term": long_term_ready,
                },
                "trainable_now_by_materialization": {
                    "reviewed_bundle_or_existing_train": sum(
                        1
                        for row in promotable_rows
                        if str(row.get("materialization_status") or "") in {"reviewed_bundle", "bootstrap_only"}
                    ),
                    "bulk_support_materialized": sum(
                        1 for row in promotable_rows if str(row.get("materialization_status") or "") == "bulk_support_materialized"
                    ),
                    "support_ready_not_materialized": sum(
                        1 for row in rows if str(row.get("materialization_status") or "") == "support_ready_not_materialized"
                    ),
                    "needs_richer_competition": sum(
                        1 for row in rows if str(row.get("materialization_status") or "") == "needs_richer_competition"
                    ),
                },
            }
        )

    write_jsonl(SCALE_READY_JSONL, scale_ready_rows)
    write_jsonl(QUARANTINE_BACKLOG_JSONL, quarantine_backlog)
    write_jsonl(LANGUAGE_CARDS_JSONL, language_cards)

    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_package_v4_ready",
        "claim_scope": [
            "Refresh the scale-ready root package against admission manifest v5, which folds in the newer bulk reviewed support lane from stages10775-10778.",
            "Separate materialized bulk support from merely support-ready candidate roots so scale planning stays honest.",
            "This remains a scaling-control artifact, not a new 100M-vs-Gemma result.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v5": display(ADMISSION_ROWS),
            "root_admission_summary_v5": display(ADMISSION_SUMMARY),
        },
        "headline_findings": [
            "The scale package now distinguishes roots that truly gained materialized bulk support rows from roots that are only queued or still need richer competition.",
            "C/C++ and Python now show a materially larger trainable support lane than the older v3 package captured.",
            "Rust and web remain the limiting languages for broader scale, but the inventory now states that directly instead of hiding them behind the older reviewed-root slice.",
        ],
        "global_counts": {
            "roots_total": len(scale_ready_rows),
            "quarantine_backlog_roots": len(quarantine_backlog),
            "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "") for row in scale_ready_rows).items())),
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "") for row in scale_ready_rows).items())),
            "materialization_status_counts": dict(sorted(Counter(str(row.get("materialization_status") or "") for row in scale_ready_rows).items())),
            "ready_for_large_scale_train_by_language": {
                language: sum(1 for row in by_language.get(language, []) if row["ready_for_large_scale_train"])
                for language in LANGUAGES
            },
            "support_ready_not_materialized_by_language": {
                language: sum(
                    1
                    for row in by_language.get(language, [])
                    if str(row.get("materialization_status") or "") == "support_ready_not_materialized"
                )
                for language in LANGUAGES
            },
            "needs_richer_competition_by_language": {
                language: sum(
                    1
                    for row in by_language.get(language, [])
                    if str(row.get("materialization_status") or "") == "needs_richer_competition"
                )
                for language in LANGUAGES
            },
        },
        "language_cards": language_cards,
        "admission_metrics_snapshot": admission_summary.get("metrics") or {},
        "next_best_step": "Use this v4 scale package as the control plane for the next larger root-split multilingual manifest, prioritizing languages that still have low materialized support and high competition-gap counts.",
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
            "package": display(PACKAGE_JSON),
        },
    )
    print(json.dumps(package, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
