#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10673
NAME = "stage10673_multilingual_residual_builder_packet"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "multilingual_residual_builder_packet.json"
OUT_TARGETS = OUT_DIR / "multilingual_residual_builder_targets.jsonl"

AUDIT_10672 = ARTIFACTS / "stage10672_dual_residual_targeted_probe_audit/dual_residual_targeted_probe_audit.json"
PYTHON_10493 = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder/python_verifier_fresh_review_packet_builder.json"
PYTHON_10493_STATUS = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder/python_verifier_review_target_status.jsonl"
PYTHON_10475 = ARTIFACTS / "stage10475_python_verifier_materialized_root_bundle_builder/python_verifier_materialized_root_bundle_builder.json"
RUST_10441 = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"
RUST_10505 = ARTIFACTS / "stage10505_multilingual_residual_root_scaling_queue/multilingual_residual_root_scaling_targets.jsonl"
RUST_10663 = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit/rust_flash_attn_executable_support_audit.json"
RUST_10664 = ARTIFACTS / "stage10664_rust_materialization_inventory_refresh/rust_materialization_inventory_refresh.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    audit = load_json(AUDIT_10672)
    python_packet = load_json(PYTHON_10493)
    python_status_rows = load_jsonl(PYTHON_10493_STATUS)
    python_inventory = load_json(PYTHON_10475)
    rust_builder = load_json(RUST_10441)
    rust_scaling_rows = load_jsonl(RUST_10505)
    rust_flash = load_json(RUST_10663)
    rust_inventory = load_json(RUST_10664)

    strict_lang = (audit.get("strict_eval_result") or {}).get("language_breakdown") or {}
    strict_miss_ids = ((audit.get("strict_eval_result") or {}).get("miss_summary") or {}).get("miss_row_ids") or []

    python_ready = [row for row in python_status_rows if row.get("immediately_qualified_for_reviewed_verifier_packet")]
    python_blocked = [row for row in python_status_rows if not row.get("immediately_qualified_for_reviewed_verifier_packet")]

    rust_primary_ids = {
        "linux::rust",
        "candle::candle-datasets",
        "candle::candle-transformers",
    }
    rust_scaling_by_id = {row["bundle_id"]: row for row in rust_scaling_rows if row.get("language_family") == "rust"}
    rust_builder_candidates = []
    for candidate in rust_builder.get("recommended_candidates") or []:
        root_id = candidate.get("candidate_root_id")
        if root_id in rust_primary_ids:
            merged = {
                "bundle_id": root_id,
                "language_family": "rust",
                "repo_id": candidate.get("repo_id"),
                "priority_order": rust_scaling_by_id.get(root_id, {}).get("priority_order"),
                "status": rust_scaling_by_id.get(root_id, {}).get("status", "builder_target_not_yet_materialized"),
                "blockers": rust_scaling_by_id.get(root_id, {}).get("blockers", []),
                "competition_geometries": candidate.get("competition_geometries"),
                "candidate_paths_preview": candidate.get("candidate_paths_preview"),
                "required_builder_delta": candidate.get("required_builder_delta"),
                "review_ready_for_bundle_construction": candidate.get("review_ready_for_bundle_construction"),
                "test_file_count": candidate.get("test_file_count"),
                "priority_score": candidate.get("priority_score"),
            }
            rust_builder_candidates.append(merged)
    rust_builder_candidates.sort(key=lambda row: (row.get("priority_order") or 999, -(row.get("priority_score") or 0)))

    preserve_only = []
    for language in ("c_cpp", "web_js_ts_html"):
        metrics = strict_lang.get(language)
        if metrics:
            preserve_only.append(
                {
                    "language_family": language,
                    "current_strict_accuracy": metrics.get("accuracy"),
                    "rows": metrics.get("rows"),
                    "role": "preserve_only_canary_lane",
                    "next_action": "keep canary stable while expanding fresh disjoint roots elsewhere",
                }
            )

    targets: list[dict[str, Any]] = []
    for row in python_ready:
        targets.append(
            {
                "lane": "python_verifier",
                "bundle_id": row["bundle_id"],
                "language_family": "python",
                "priority_order": row.get("priority_order", 1),
                "status": "ready_now_promotable_support",
                "supports_promotable_packet": True,
                "selected_tests_count": row.get("reviewed_selected_tests_count"),
                "gold_target": row.get("reviewed_verifier_gold_value"),
                "required_next_action": "use as fresh disjoint executable verifier support without replaying the MirrorMind strict root",
                "honesty_gates": [
                    "do not copy the current strict MirrorMind root into train",
                    "preserve selected-test competition without exposing the gold path before options",
                    "treat this as support only until fresh strict roots exist",
                ],
            }
        )
    for row in python_blocked:
        targets.append(
            {
                "lane": "python_verifier",
                "bundle_id": row["bundle_id"],
                "language_family": "python",
                "priority_order": row.get("priority_order", 99),
                "status": "needs_packet_rebuild_or_gold",
                "supports_promotable_packet": False,
                "selected_tests_count": row.get("reviewed_selected_tests_count"),
                "blockers": row.get("gaps"),
                "required_next_action": "rebuild verifier competition or complete gold materialization before using for promotable support",
            }
        )
    for row in rust_builder_candidates:
        targets.append(
            {
                "lane": "rust_evidence_citation",
                "bundle_id": row["bundle_id"],
                "language_family": "rust",
                "priority_order": row.get("priority_order", 99),
                "status": row.get("status"),
                "supports_promotable_packet": False,
                "blockers": row.get("blockers"),
                "competition_geometries": row.get("competition_geometries"),
                "candidate_paths_preview": row.get("candidate_paths_preview"),
                "required_builder_delta": row.get("required_builder_delta"),
                "required_next_action": "build reviewed maintainer packet with explicit E-vs-F evidence contrast and selected-test or verifier anchor",
            }
        )
    targets.append(
        {
            "lane": "rust_evidence_citation",
            "bundle_id": "stage10413::candle::candle-flash-attn::rust",
            "language_family": "rust",
            "priority_order": 0,
            "status": "ready_now_train_support_only",
            "supports_promotable_packet": False,
            "blockers": ["abstention_heavy", "not_same_surface_promotable"],
            "selected_tests_count": len((rust_flash.get("bundle_identity") or {}).get("selected_tests") or []),
            "required_next_action": "keep as reviewed Rust support while primary non-tokenizers builder targets are materialized",
        }
    )
    for row in preserve_only:
        targets.append(row)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "decision": "multilingual_residual_builder_packet_ready",
        "claim_scope": [
            "Collapse the current multilingual residual state into one executable builder packet for the next honest v2.7-to-v2.8 expansion step.",
            "Separate ready-now support roots from blocked builder targets and preserve-only canary lanes.",
            "Keep anti-cheat and promotion boundaries explicit so fresh-root work does not drift back into same-surface replay.",
        ],
        "current_frontier_state": {
            "strict_constrained_accuracy": (audit.get("headline") or {}).get("current_hundred_m_strict_accuracy"),
            "baseline_gemma_strict_accuracy": (audit.get("headline") or {}).get("baseline_gemma_strict_accuracy"),
            "strict_miss_row_ids": strict_miss_ids,
            "strict_language_breakdown": strict_lang,
        },
        "language_lane_status": {
            "python": {
                "current_strict_accuracy": strict_lang.get("python", {}).get("accuracy"),
                "immediately_qualified_support_roots": len(python_ready),
                "blocked_or_incomplete_roots": len(python_blocked),
                "promotable_root_shortfall_vs_requested_six": (python_inventory.get("metrics") or {}).get("promotable_root_shortfall"),
                "required_shape": [
                    "multiple plausible test-file candidates",
                    "selected-test anchor present but not answer-revealing",
                    "fresh disjoint roots, not MirrorMind replay",
                ],
            },
            "rust": {
                "current_strict_accuracy": strict_lang.get("rust", {}).get("accuracy"),
                "ready_now_train_support_roots": (rust_inventory.get("metrics") or {}).get("refreshed_executable_support_root_count"),
                "primary_builder_targets": [row["bundle_id"] for row in rust_builder_candidates],
                "required_shape": [
                    "evidence citation rows where candidate_change_surface is a tempting negative",
                    "gold support fact distinct from verifier/test constraint",
                    "selected-test or trace anchor retained without exposing the answer token verbatim",
                ],
            },
            "c_cpp": {
                "current_strict_accuracy": strict_lang.get("c_cpp", {}).get("accuracy"),
                "status": "preserve_only_canary_lane",
            },
            "web_js_ts_html": {
                "current_strict_accuracy": strict_lang.get("web_js_ts_html", {}).get("accuracy"),
                "status": "preserve_only_canary_lane",
            },
        },
        "ready_now_support": {
            "python_promotable_support_roots": [row["bundle_id"] for row in python_ready],
            "rust_train_support_only_roots": ["stage10413::candle::candle-flash-attn::rust"],
        },
        "primary_builder_targets": [row["bundle_id"] for row in rust_builder_candidates],
        "promotion_and_anti_cheat_gates": [
            "No same-root replay from the current strict overlay into train.",
            "Target path or support fact must not appear verbatim before options.",
            "Fresh roots must remain disjoint from the current strict Python MirrorMind and Rust tokenizers rows.",
            "Every new root needs review packet quality: rubric, anti-cheat, and gold perspective answers before scoring.",
            "Any future promotion run must beat 22/24 with zero regressions on the repaired reviewed-v2.7 strict canary.",
        ],
        "next_best_steps": [
            "Use the single ready-now Python verifier root plus flash-attn support in the next broader training package only as support, not as headline evidence.",
            "Build reviewed maintainer packets for linux::rust, candle::candle-datasets, and candle::candle-transformers with explicit evidence-citation E-vs-F geometry.",
            "Replenish at least four more disjoint Python verifier roots before treating Python as adequately scaled.",
            "Keep c_cpp and web stable as canary lanes while fresh-root expansion is focused on Python verifier and Rust evidence citation.",
        ],
        "sources": {
            "stage10672_targeted_probe_audit": rel(AUDIT_10672),
            "stage10493_python_verifier_packet": rel(PYTHON_10493),
            "stage10475_python_materialized_inventory": rel(PYTHON_10475),
            "stage10441_rust_builder_request": rel(RUST_10441),
            "stage10505_multilingual_residual_scaling_queue": rel(RUST_10505),
            "stage10663_rust_flash_attn_support_audit": rel(RUST_10663),
            "stage10664_rust_materialization_inventory_refresh": rel(RUST_10664),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_TARGETS, targets)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
