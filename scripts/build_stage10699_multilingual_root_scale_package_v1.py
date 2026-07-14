#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10699
NAME = "stage10699_multilingual_root_scale_package_v1"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKAGE_JSON = OUT_DIR / "multilingual_root_scale_package_v1.json"
SCALE_READY_JSONL = OUT_DIR / "scale_ready_root_inventory.jsonl"
QUARANTINE_BACKLOG_JSONL = OUT_DIR / "quarantine_rewrite_backlog.jsonl"
LANGUAGE_CARDS_JSONL = OUT_DIR / "language_scale_cards.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

ADMISSION_ROWS = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.jsonl"
ADMISSION_SUMMARY = ROOT / "runs/local/artifacts/stage10691_root_admission_manifest_v2/root_admission_manifest_v2.json"
SUPPLY_AUDIT = ROOT / "runs/local/artifacts/stage10692_multilingual_root_supply_balance_audit_refreshed/multilingual_root_supply_balance_audit_refreshed.json"
SCALE_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
LATEST_MULTILINGUAL_AUDIT = ROOT / "runs/local/artifacts/stage10698_reviewed_plus_bootstrap_multilingual_probe_balanced_deduped_audit/reviewed_plus_bootstrap_multilingual_probe_balanced_deduped_audit.json"

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


def language_scale_card(
    language: str,
    rows: list[dict[str, Any]],
    supply_row: dict[str, Any] | None,
    targets: dict[str, dict[str, int]],
) -> dict[str, Any]:
    by_tier = Counter(str(row.get("quality_tier") or "unknown") for row in rows)
    phase_1_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_1"])
    phase_2_ready = sum(1 for row in rows if row["phase_eligibility"]["phase_2"])
    long_term_ready = sum(1 for row in rows if row["phase_eligibility"]["long_term"])
    strict_eval_roots = sum(1 for row in rows if str(row.get("admit_role") or "") == "strict_eval")
    validation_roots = sum(1 for row in rows if str(row.get("admit_role") or "") == "validation")
    quarantine_roots = sum(1 for row in rows if str(row.get("admit_role") or "") == "quarantine")

    phase_1_target = int(targets["phase_1"][language])
    phase_2_target = int(targets["phase_2"][language])
    long_term_target = int(targets["long_term"][language])
    return {
        "language_family": language,
        "total_roots": len(rows),
        "quality_tier_counts": dict(sorted(by_tier.items())),
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
        "targets": {
            "phase_1": phase_1_target,
            "phase_2": phase_2_target,
            "long_term": long_term_target,
        },
        "gaps": {
            "phase_1": max(phase_1_target - phase_1_ready, 0),
            "phase_2": max(phase_2_target - phase_2_ready, 0),
            "long_term": max(long_term_target - long_term_ready, 0),
        },
        "eval_support": {
            "strict_eval_roots": strict_eval_roots,
            "validation_roots": validation_roots,
            "quarantine_roots": quarantine_roots,
        },
        "supply_audit": supply_row or {},
    }


def main() -> None:
    admission_rows = load_jsonl(ADMISSION_ROWS)
    admission_summary = load_json(ADMISSION_SUMMARY)
    supply_audit = load_json(SUPPLY_AUDIT)
    scale_contract = load_json(SCALE_CONTRACT)
    latest_multilingual_audit = load_json(LATEST_MULTILINGUAL_AUDIT)

    targets = scale_contract.get("scale_targets") or {}
    supply_rows_by_language = {
        str(row.get("language_family") or ""): row for row in (supply_audit.get("language_supply") or [])
    }

    scale_ready_rows: list[dict[str, Any]] = []
    quarantine_backlog: list[dict[str, Any]] = []
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)

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

    language_cards = [
        language_scale_card(language, by_language.get(language, []), supply_rows_by_language.get(language), targets)
        for language in LANGUAGES
    ]
    write_jsonl(SCALE_READY_JSONL, scale_ready_rows)
    write_jsonl(QUARANTINE_BACKLOG_JSONL, quarantine_backlog)
    write_jsonl(LANGUAGE_CARDS_JSONL, language_cards)

    ready_train_counts = {
        language: sum(
            1
            for row in by_language.get(language, [])
            if row["ready_for_large_scale_train"]
        )
        for language in LANGUAGES
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_scale_package_v1_ready",
        "claim_scope": [
            "Package the current admitted multilingual roots into scale-ready tiers so growth can proceed under explicit quality gates.",
            "Keep quarantined or prompt-target-leaking roots visible as a rewrite backlog rather than silently counting them toward language-scale claims.",
            "This is a scaling-control artifact, not a new standalone frontier claim.",
        ],
        "source_artifacts": {
            "root_admission_manifest_v2": display(ADMISSION_ROWS),
            "root_admission_summary_v2": display(ADMISSION_SUMMARY),
            "multilingual_root_scale_quality_contract": display(SCALE_CONTRACT),
            "multilingual_root_supply_balance_audit_refreshed": display(SUPPLY_AUDIT),
            "latest_multilingual_frontier_audit": display(LATEST_MULTILINGUAL_AUDIT),
        },
        "headline_findings": [
            "The current multilingual standalone frontier remains 22/24, so the next honest gain has to come from root-scale growth and interface cleanup rather than another same-surface preservation probe.",
            "This package separates roots that are immediately scale-ready from those that still need interface rewrites, especially the large prompt-target-leak quarantine backlog.",
            "Python has the largest raw ready pool but still needs repo-family caps; Rust and web remain supply-constrained and should be mined or rewritten first for honest multilingual growth.",
        ],
        "frontier_status": {
            "strict_accuracy": ((latest_multilingual_audit.get("headline") or {}).get("hundred_m_strict_accuracy")),
            "strict_rows": ((latest_multilingual_audit.get("headline") or {}).get("strict_rows_honest")),
            "miss_row_ids": ((latest_multilingual_audit.get("strict_eval_result") or {}).get("miss_row_ids")) or [],
        },
        "global_counts": {
            "roots_total": len(scale_ready_rows),
            "quarantine_backlog_roots": len(quarantine_backlog),
            "quality_tier_counts": dict(sorted(Counter(str(row.get("quality_tier") or "unknown") for row in scale_ready_rows).items())),
            "admit_role_counts": dict(sorted(Counter(str(row.get("admit_role") or "unknown") for row in scale_ready_rows).items())),
            "ready_for_large_scale_train_by_language": ready_train_counts,
            "phase_1_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_1"]),
            "phase_2_ready_total": sum(1 for row in scale_ready_rows if row["phase_eligibility"]["phase_2"]),
        },
        "language_cards": language_cards,
        "next_scale_priorities": [
            "Rewrite quarantined prompt-target-leak roots into visible-candidate contracts before counting them toward scale.",
            "Cap dominant Python repo families while mining fresh Rust and pure-web verifier-backed roots.",
            "Reserve fresh heldout roots before training any expanded v2.8 or long-context package.",
            "Keep the 24-row cleaned compact multilingual slice as a regression suite while scale growth happens elsewhere.",
        ],
        "recommended_next_stage": "stage10700_root_scale_rewrite_priority_manifest",
        "outputs": {
            "scale_ready_root_inventory": display(SCALE_READY_JSONL),
            "quarantine_rewrite_backlog": display(QUARANTINE_BACKLOG_JSONL),
            "language_scale_cards": display(LANGUAGE_CARDS_JSONL),
            "package_json": display(PACKAGE_JSON),
        },
        "upstream_context": {
            "current_scale_contract_targets": targets,
            "admission_global_counts": admission_summary.get("global_counts") or {},
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
