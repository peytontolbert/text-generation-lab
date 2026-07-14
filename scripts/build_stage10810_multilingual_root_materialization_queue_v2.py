#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10810
NAME = "stage10810_multilingual_root_materialization_queue_v2"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_root_materialization_queue_v2.json"
QUEUE_JSONL = OUT_DIR / "materialization_queue.jsonl"
RUNBOOK_JSONL = OUT_DIR / "materialization_runbook.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SCALE_PACKAGE = ROOT / "runs/local/artifacts/stage10809_multilingual_root_scale_package_v3/multilingual_root_scale_package_v3.json"
LANGUAGE_CARDS = ROOT / "runs/local/artifacts/stage10809_multilingual_root_scale_package_v3/language_scale_cards.jsonl"
CPP_SCAFFOLD_MANIFEST = ROOT / "runs/local/artifacts/stage10741_cpp_bootstrap_review_packet_scaffolds/cpp_bootstrap_review_packet_scaffold_manifest.json"
PYTHON_TARGETS = ROOT / "runs/local/artifacts/stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_targets.jsonl"
RUST_TARGETS = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_targets.jsonl"
WEB_AUDIT = ROOT / "runs/local/artifacts/stage10175_web_root_supply_and_bundle_gap_audit/web_root_supply_and_bundle_gap_audit.json"

LANGUAGE_ORDER = ["c_cpp", "python", "rust", "web_js_ts_html"]


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


def cards_by_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["language_family"]): row for row in rows}


def lane_constraints(card: dict[str, Any]) -> dict[str, Any]:
    batch = card["recommended_next_batch"]
    return {
        "max_roots_per_repo_family": batch["max_roots_per_repo_family"],
        "target_roots": batch["target_roots"],
        "must_hold": list(batch["must_hold"]),
        "lane_blocker": card["lane_blocker"],
    }


def build_cpp_entries(card: dict[str, Any], cpp_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = lane_constraints(card)
    entries: list[dict[str, Any]] = []
    for idx, packet in enumerate(cpp_manifest.get("packets") or [], start=1):
        entries.append(
            {
                "queue_order": idx,
                "language_family": "c_cpp",
                "lane_priority": 1,
                "promotability": "train_support_promotable_after_admission",
                "work_type": "bundle_admission_and_support_materialization",
                "candidate_id": str(packet.get("bundle_id") or ""),
                "root_id": str(packet.get("root_id") or ""),
                "repo_id": str(packet.get("repo_id") or ""),
                "repo_family": str(packet.get("repo_family") or packet.get("repo_id") or ""),
                "target_stage": "fresh_cpp_bundle_admission_refresh",
                "source_artifact": display(CPP_SCAFFOLD_MANIFEST),
                "anti_cheat_status": "review_packet_present",
                "lane_constraints": constraints,
                "must_hold": [
                    "preserve rubric, anti-cheat, and gold adjudication packet links",
                    "keep admitted rows out of strict eval until a later heldout reservation pass",
                    "dilute parametergolf with cccl and onnxruntime before further parametergolf expansion",
                ],
                "why_now": "C/C++ is the strongest immediate scale lane: reviewed packets already exist and the current strict slice is 6/6.",
            }
        )
    return entries


def build_python_entries(card: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constraints = lane_constraints(card)
    entries: list[dict[str, Any]] = []
    for idx, target in enumerate(sorted(targets, key=lambda row: int(row.get("priority_order") or 9999)), start=1):
        repo_id = str(target.get("repo_id") or "")
        promotability = "train_support_promotable_after_review" if repo_id != "agentkernel" else "train_support_promotable_with_repo_cap_check"
        entries.append(
            {
                "queue_order": idx,
                "language_family": "python",
                "lane_priority": 2,
                "promotability": promotability,
                "work_type": "fresh_verifier_bundle_review",
                "candidate_id": str(target.get("episode_id") or ""),
                "root_id": str(target.get("episode_id") or ""),
                "repo_id": repo_id,
                "repo_family": repo_id,
                "target_stage": "fresh_python_verifier_bundle_review",
                "source_artifact": display(PYTHON_TARGETS),
                "anti_cheat_status": "selected_test_anchor_required",
                "lane_constraints": constraints,
                "must_hold": list(target.get("required_bundle_shape") or []) + [
                    "preserve root disjointness from the MirrorMind strict family",
                    "do not expose gold test path before options",
                    "keep repo-family dilution visible because agentkernel already dominates raw Python supply",
                ],
                "why_now": str(target.get("motivation") or ""),
            }
        )
    return entries


def build_rust_entries(card: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constraints = lane_constraints(card)
    entries: list[dict[str, Any]] = []
    fresh_targets = [
        row for row in sorted(targets, key=lambda row: int(row.get("priority_order") or 9999))
        if str(row.get("support_role") or "") == "fresh_root_builder_target"
    ]
    for idx, target in enumerate(fresh_targets, start=1):
        entries.append(
            {
                "queue_order": idx,
                "language_family": "rust",
                "lane_priority": 3,
                "promotability": "diagnostic_until_review_and_verifier_anchor",
                "work_type": "fresh_citation_bundle_construction",
                "candidate_id": str(target.get("candidate_root_id") or ""),
                "root_id": str(target.get("candidate_root_id") or ""),
                "repo_id": str(target.get("repo_id") or ""),
                "repo_family": str(target.get("package_root") or target.get("repo_id") or ""),
                "target_stage": "fresh_rust_citation_bundle_review",
                "source_artifact": display(RUST_TARGETS),
                "anti_cheat_status": "requires_E_vs_F_contrast_review",
                "lane_constraints": constraints,
                "must_hold": list(target.get("required_builder_delta") or []) + [
                    "do not count tokenizers same-surface rows toward fresh-root success",
                    "retain candidate_change_surface as a tempting negative only",
                    "upgrade to promotable only after selected-test or verifier anchors are recovered",
                ],
                "why_now": "Rust is still blocked on fresh non-tokenizers evidence-citation roots with honest E-vs-F geometry.",
            }
        )
    return entries


def build_web_entries(card: dict[str, Any], web_audit: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = lane_constraints(card)
    entries: list[dict[str, Any]] = []
    for idx, target in enumerate(web_audit.get("replenishment_web_candidates") or [], start=1):
        repo_id = str(target.get("repo_id") or "")
        selected_tests = list(target.get("selected_tests") or [])
        pure_web = repo_id == "bddy_website"
        entries.append(
            {
                "queue_order": idx,
                "language_family": "web_js_ts_html",
                "lane_priority": 4,
                "promotability": "stress_or_support_only" if not pure_web else "diagnostic_until_verifier_anchor",
                "work_type": "web_bundle_filter_and_review",
                "candidate_id": str(target.get("episode_id") or ""),
                "root_id": str(target.get("episode_id") or ""),
                "repo_id": repo_id,
                "repo_family": repo_id,
                "target_stage": "pure_web_bundle_review" if pure_web else "mixed_language_web_bundle_filter_and_review",
                "source_artifact": display(WEB_AUDIT),
                "anti_cheat_status": "requires_changed_path_shortcut_filter",
                "lane_constraints": constraints,
                "must_hold": [
                    "filter venv and site-packages neighbors before adjudication" if repo_id == "code_assist" else "deduplicate repeated bundle digests before promotion",
                    "do not make a broad web claim without selected-test or verifier anchors",
                    "route bundle through rubric, anti-cheat, and gold adjudication before any standalone package merge",
                    f"selected_tests_present={bool(selected_tests)}",
                ],
                "why_now": "Web remains supply-limited; these are the only current replenishment candidates with any realistic path to maintainer-grade review.",
            }
        )
    return entries


def main() -> None:
    scale_package = load_json(SCALE_PACKAGE)
    cards = cards_by_language(load_jsonl(LANGUAGE_CARDS))
    cpp_manifest = load_json(CPP_SCAFFOLD_MANIFEST)
    python_targets = load_jsonl(PYTHON_TARGETS)
    rust_targets = load_jsonl(RUST_TARGETS)
    web_audit = load_json(WEB_AUDIT)

    lane_entries = {
        "c_cpp": build_cpp_entries(cards["c_cpp"], cpp_manifest),
        "python": build_python_entries(cards["python"], python_targets),
        "rust": build_rust_entries(cards["rust"], rust_targets),
        "web_js_ts_html": build_web_entries(cards["web_js_ts_html"], web_audit),
    }

    queue_rows: list[dict[str, Any]] = []
    runbook_rows: list[dict[str, Any]] = []
    for language in LANGUAGE_ORDER:
        entries = lane_entries[language]
        queue_rows.extend(entries)
        card = cards[language]
        runbook_rows.append(
            {
                "language_family": language,
                "lane_priority": entries[0]["lane_priority"] if entries else None,
                "planned_work_items": len(entries),
                "promotable_items_now": sum(1 for row in entries if "promotable" in str(row["promotability"])),
                "lane_blocker": card["lane_blocker"],
                "strict_accuracy": card["strict_accuracy"],
                "recommended_next_batch": card["recommended_next_batch"],
                "phase_1_gaps": card["phase_cards"]["phase_1"]["current_gaps"],
                "must_hold": list(card["recommended_next_batch"]["must_hold"]),
                "headline_constraint": "No headline upgrade from this lane until fresh heldout is reserved and the repaired v2.7 canary remains preserved.",
            }
        )

    queue_rows.sort(key=lambda row: (row["lane_priority"], row["queue_order"], row["candidate_id"]))
    for idx, row in enumerate(queue_rows, start=1):
        row["global_queue_order"] = idx

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_materialization_queue_v2_ready",
        "claim_scope": [
            "Turn the refreshed 10809 scale package into the next actionable multilingual root materialization queue.",
            "Prioritize reviewed C/C++ bundle admission first, then Python verifier fresh roots, then Rust citation fresh roots, while keeping web explicitly quality-constrained.",
            "This queue is for root materialization, anti-cheat-safe scaling, and future heldout growth, not a new model-comparison claim.",
        ],
        "source_artifacts": {
            "scale_package_v3": display(SCALE_PACKAGE),
            "language_cards_v3": display(LANGUAGE_CARDS),
            "cpp_packet_scaffolds": display(CPP_SCAFFOLD_MANIFEST),
            "python_verifier_targets": display(PYTHON_TARGETS),
            "rust_fresh_root_targets": display(RUST_TARGETS),
            "web_supply_audit": display(WEB_AUDIT),
        },
        "headline_findings": [
            "C/C++ should still go first: five reviewed packet scaffolds already exist and can become support-ready admitted bundles without inventing new roots.",
            "Python has the broadest immediate fresh-root queue, but repo-family dilution still matters because agentkernel remains overrepresented in raw supply.",
            "Rust and web are not training bottlenecks in the narrow sense; they are honest-source and anti-cheat bottlenecks, so their queue items stay review-heavy until anchors are recovered.",
        ],
        "frontier_status": scale_package["frontier_status"],
        "metrics": {
            "queue_items": len(queue_rows),
            "lane_counts": {language: len(lane_entries[language]) for language in LANGUAGE_ORDER},
            "promotability_counts": {
                "train_support_promotable_after_admission": sum(1 for row in queue_rows if row["promotability"] == "train_support_promotable_after_admission"),
                "train_support_promotable_after_review": sum(1 for row in queue_rows if row["promotability"] == "train_support_promotable_after_review"),
                "train_support_promotable_with_repo_cap_check": sum(1 for row in queue_rows if row["promotability"] == "train_support_promotable_with_repo_cap_check"),
                "diagnostic_until_review_and_verifier_anchor": sum(1 for row in queue_rows if row["promotability"] == "diagnostic_until_review_and_verifier_anchor"),
                "diagnostic_until_verifier_anchor": sum(1 for row in queue_rows if row["promotability"] == "diagnostic_until_verifier_anchor"),
                "stress_or_support_only": sum(1 for row in queue_rows if row["promotability"] == "stress_or_support_only"),
            },
        },
        "next_best_step": "Execute the queue in order: admit the five C/C++ reviewed packets, review the three Python verifier roots, build the four Rust citation bundles, and only then decide which items are promotable enough to merge into the next larger multilingual package.",
        "outputs": {
            "summary": display(SUMMARY_JSON),
            "queue": display(QUEUE_JSONL),
            "runbook": display(RUNBOOK_JSONL),
        },
    }

    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(RUNBOOK_JSONL, runbook_rows)
    write_json(SUMMARY_JSON, summary)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "queue": display(QUEUE_JSONL),
            "summary": display(SUMMARY_JSON),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
