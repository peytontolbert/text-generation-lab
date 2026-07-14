#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10752
NAME = "stage10752_multilingual_bulk_root_materialization_queue"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_bulk_root_materialization_queue.json"
QUEUE_JSONL = OUT_DIR / "materialization_queue.jsonl"
RUNBOOK_JSONL = OUT_DIR / "materialization_runbook.jsonl"
RUN_SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RATCHET_JSON = ROOT / "runs/local/artifacts/stage10751_multilingual_root_scale_quality_ratchet/multilingual_root_scale_quality_ratchet.json"
LANGUAGE_BATCH_PLANS = ROOT / "runs/local/artifacts/stage10751_multilingual_root_scale_quality_ratchet/language_batch_plans.jsonl"
CPP_SCAFFOLD_SUMMARY = ROOT / "runs/local/artifacts/stage10741_cpp_bootstrap_review_packet_scaffolds/cpp_bootstrap_review_packet_scaffolds.json"
CPP_SCAFFOLD_MANIFEST = ROOT / "runs/local/artifacts/stage10741_cpp_bootstrap_review_packet_scaffolds/cpp_bootstrap_review_packet_scaffold_manifest.json"
PYTHON_TARGETS = ROOT / "runs/local/artifacts/stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_targets.jsonl"
RUST_TARGETS = ROOT / "runs/local/artifacts/stage10467_rust_citation_fresh_root_builder/rust_citation_fresh_root_targets.jsonl"
WEB_AUDIT = ROOT / "runs/local/artifacts/stage10175_web_root_supply_and_bundle_gap_audit/web_root_supply_and_bundle_gap_audit.json"


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


def plan_by_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["language_family"]): row for row in rows}


def build_cpp_entries(plan: dict[str, Any], scaffold_summary: dict[str, Any], scaffold_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    packets = list(scaffold_manifest.get("packets") or [])
    max_items = min(len(packets), int(plan["recommended_next_batch"]["target_roots"]))
    entries: list[dict[str, Any]] = []
    for idx, packet in enumerate(packets[:max_items], start=1):
        entries.append(
            {
                "queue_order": idx,
                "language_family": "c_cpp",
                "lane_priority": 1,
                "work_type": "bundle_admission_and_train_support_materialization",
                "source_artifact": display(CPP_SCAFFOLD_MANIFEST),
                "candidate_id": str(packet.get("bundle_id") or ""),
                "repo_id": str(packet.get("repo_id") or ""),
                "repo_family": str(packet.get("repo_family") or packet.get("repo_id") or ""),
                "target_stage": "stage10742_cpp_bootstrap_ai_adjudicated_admission",
                "batch_constraints": {
                    "max_roots_per_repo_family": plan["recommended_next_batch"]["max_roots_per_repo_family"],
                    "fresh_heldout_required_before_training": True,
                    "same_surface_headline_forbidden": True,
                },
                "must_hold": [
                    "keep packet train-support only after admission",
                    "do not promote as strict eval without a later fairness gate",
                    "preserve 8-perspective bundle structure and AI adjudication artifacts",
                ],
                "why_now": "C/C++ is the cleanest near-term scale lane and already has bootstrap packets ready for admission.",
            }
        )
    entries.append(
        {
            "queue_order": len(entries) + 1,
            "language_family": "c_cpp",
            "lane_priority": 1,
            "work_type": "reviewed_package_rebuild_after_admission",
            "source_artifact": display(CPP_SCAFFOLD_SUMMARY),
            "candidate_id": "cpp_admitted_bundle_merge",
            "repo_id": "multi",
            "repo_family": "multi",
            "target_stage": "reviewed_v27_cpp_support_refresh",
            "batch_constraints": {
                "merge_only_after_bundle_admission": True,
                "strict_eval_rows_unchanged": True,
            },
            "must_hold": [
                "rebuild train-support only",
                "keep current strict frontier rows out of support merge",
            ],
            "why_now": f'{scaffold_summary.get("packet_count", 0)} clean C/C++ packets are already scaffolded and should be merged before opening new C/C++ mining lanes.',
        }
    )
    return entries


def build_python_entries(plan: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, target in enumerate(targets, start=1):
        entries.append(
            {
                "queue_order": idx,
                "language_family": "python",
                "lane_priority": 2,
                "work_type": "fresh_verifier_bundle_review",
                "source_artifact": display(PYTHON_TARGETS),
                "candidate_id": str(target.get("episode_id") or ""),
                "repo_id": str(target.get("repo_id") or ""),
                "repo_family": str(target.get("repo_id") or ""),
                "target_stage": "fresh_python_verifier_bundle_review",
                "batch_constraints": {
                    "max_roots_per_repo_family": plan["recommended_next_batch"]["max_roots_per_repo_family"],
                    "selected_test_anchor_required": True,
                    "minimum_plausible_test_targets": 3,
                },
                "must_hold": list(target.get("required_bundle_shape") or []),
                "why_now": str(target.get("motivation") or ""),
            }
        )
    return entries


def build_rust_entries(plan: dict[str, Any], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    fresh_targets = [row for row in targets if str(row.get("support_role") or "") == "fresh_root_builder_target"]
    for idx, target in enumerate(fresh_targets, start=1):
        entries.append(
            {
                "queue_order": idx,
                "language_family": "rust",
                "lane_priority": 3,
                "work_type": "fresh_citation_bundle_construction",
                "source_artifact": display(RUST_TARGETS),
                "candidate_id": str(target.get("candidate_root_id") or ""),
                "repo_id": str(target.get("repo_id") or ""),
                "repo_family": str(target.get("repo_id") or ""),
                "target_stage": "fresh_rust_citation_bundle_review",
                "batch_constraints": {
                    "max_roots_per_repo_family": plan["recommended_next_batch"]["max_roots_per_repo_family"],
                    "non_tokenizers_required_for_promotable_use": True,
                    "candidate_change_surface_negative_required": True,
                },
                "must_hold": list(target.get("required_builder_delta") or []),
                "why_now": "Rust still lacks promotable fresh E-vs-F citation roots; these are the current non-tokenizers builder targets.",
            }
        )
    return entries


def build_web_entries(plan: dict[str, Any], web_audit: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, target in enumerate(web_audit.get("replenishment_web_candidates") or [], start=1):
        repo_id = str(target.get("repo_id") or "")
        candidate_id = str(target.get("episode_id") or "")
        needs_filter = repo_id == "code_assist"
        entries.append(
            {
                "queue_order": idx,
                "language_family": "web_js_ts_html",
                "lane_priority": 4,
                "work_type": "web_replenishment_bundle_compiler",
                "source_artifact": display(WEB_AUDIT),
                "candidate_id": candidate_id,
                "repo_id": repo_id,
                "repo_family": repo_id,
                "target_stage": "mixed_language_web_bundle_filter_and_review" if needs_filter else "pure_web_bundle_review",
                "batch_constraints": {
                    "max_roots_per_repo_family": plan["recommended_next_batch"]["max_roots_per_repo_family"],
                    "selected_test_anchor_required_for_promotable_use": True,
                    "venv_neighbor_filter_required": needs_filter,
                },
                "must_hold": [
                    "filter non-maintainer venv and site-packages neighbors before bundle review" if needs_filter else "deduplicate identical bundle digests before promotion",
                    "do not promote broad web claim without pure-web verifier anchors",
                    "route bundle through rubric, anti-cheat, and gold adjudication before any standalone package merge",
                ],
                "why_now": "Web remains source-acquisition-limited; these are the only current replenishment candidates worth materializing.",
            }
        )
    return entries


def main() -> None:
    ratchet = load_json(RATCHET_JSON)
    batch_plans = plan_by_language(load_jsonl(LANGUAGE_BATCH_PLANS))
    cpp_scaffold_summary = load_json(CPP_SCAFFOLD_SUMMARY)
    cpp_scaffold_manifest = load_json(CPP_SCAFFOLD_MANIFEST)
    python_targets = load_jsonl(PYTHON_TARGETS)
    rust_targets = load_jsonl(RUST_TARGETS)
    web_audit = load_json(WEB_AUDIT)

    queue_rows: list[dict[str, Any]] = []
    runbook_rows: list[dict[str, Any]] = []

    lane_builders = [
        ("c_cpp", build_cpp_entries(batch_plans["c_cpp"], cpp_scaffold_summary, cpp_scaffold_manifest)),
        ("python", build_python_entries(batch_plans["python"], python_targets)),
        ("rust", build_rust_entries(batch_plans["rust"], rust_targets)),
        ("web_js_ts_html", build_web_entries(batch_plans["web_js_ts_html"], web_audit)),
    ]

    for language, entries in lane_builders:
        queue_rows.extend(entries)
        runbook_rows.append(
            {
                "language_family": language,
                "lane_priority": entries[0]["lane_priority"] if entries else None,
                "planned_work_items": len(entries),
                "lane_blocker": batch_plans[language]["lane_blocker"],
                "recommended_next_batch": batch_plans[language]["recommended_next_batch"],
                "must_hold": list(batch_plans[language]["recommended_next_batch"]["must_hold"]),
                "headline_constraint": "No headline score upgrade from this lane until fresh heldout is reserved and the canary remains preserved.",
            }
        )

    queue_rows.sort(key=lambda row: (row["lane_priority"], row["queue_order"], row["candidate_id"]))
    for index, row in enumerate(queue_rows, start=1):
        row["global_queue_order"] = index

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_bulk_root_materialization_queue_ready",
        "claim_scope": [
            "Turn the quality-ratchet and current lane inventories into the next multilingual root materialization queue.",
            "Prioritize honest C/C++ reviewed-bundle expansion first, then Python verifier fresh roots, then Rust citation fresh roots, while keeping web on filtered replenishment.",
            "This queue is for root materialization and anti-cheat-safe scaling control, not a new model-comparison claim.",
        ],
        "source_artifacts": {
            "quality_ratchet": display(RATCHET_JSON),
            "language_batch_plans": display(LANGUAGE_BATCH_PLANS),
            "cpp_scaffold_summary": display(CPP_SCAFFOLD_SUMMARY),
            "python_verifier_targets": display(PYTHON_TARGETS),
            "rust_citation_targets": display(RUST_TARGETS),
            "web_gap_audit": display(WEB_AUDIT),
        },
        "headline_findings": [
            "C/C++ should be the first bulk materialization lane because five bootstrap packets are already review-complete and only need admission plus train-support merge.",
            "Python has the largest raw scale potential, but the immediate safe queue is still a small verifier-root lane with explicit selected-test competition and anti-cheat constraints.",
            "Rust remains a fresh-root construction lane rather than a merge lane; web remains a filtered-source lane rather than a broad promotion lane.",
        ],
        "queue_counts_by_language": {
            language: sum(1 for row in queue_rows if row["language_family"] == language)
            for language in ("c_cpp", "python", "rust", "web_js_ts_html")
        },
        "global_constraints": ratchet["global_contract"]["batch_acceptance_gates"],
        "next_best_step": "Execute the queue in priority order: admit and merge the C/C++ packets first, then build reviewed Python verifier and Rust citation bundles, and keep web on filtered replenishment until a pure-web verifier-anchored family exists.",
        "outputs": {
            "summary": display(SUMMARY_JSON),
            "materialization_queue": display(QUEUE_JSONL),
            "materialization_runbook": display(RUNBOOK_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(RUNBOOK_JSONL, runbook_rows)
    write_json(
        RUN_SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary": display(SUMMARY_JSON),
            "queue": display(QUEUE_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
