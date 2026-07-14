#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10822
NAME = "stage10822_residual_lane_fresh_root_supply_manifest"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_lane_fresh_root_supply_manifest.json"
OUT_JSONL = OUT_DIR / "residual_lane_fresh_root_targets.jsonl"

PYTHON_PACKET = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder" / "python_verifier_fresh_review_packet_builder.json"
PYTHON_STATUS = ARTIFACTS / "stage10493_python_verifier_fresh_review_packet_builder" / "python_verifier_review_target_status.jsonl"
RUST_REQUEST = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request" / "rust_evidence_citation_fresh_builder_request.json"
RUST_TARGETS = ARTIFACTS / "stage10441_rust_evidence_citation_fresh_builder_request" / "rust_evidence_citation_fresh_builder_targets.jsonl"
RUST_INVENTORY = ARTIFACTS / "stage10664_rust_materialization_inventory_refresh" / "rust_materialization_inventory_refresh.json"
RUST_FLASH_AUDIT = ARTIFACTS / "stage10663_rust_flash_attn_executable_support_audit" / "rust_flash_attn_executable_support_audit.json"
DELTA_AUDIT = ARTIFACTS / "stage10821_queue_aligned_probe_delta_audit" / "queue_aligned_probe_delta_audit.json"


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    python_packet = load_json(PYTHON_PACKET)
    python_status_rows = load_jsonl(PYTHON_STATUS)
    rust_request = load_json(RUST_REQUEST)
    rust_targets = load_jsonl(RUST_TARGETS)
    rust_inventory = load_json(RUST_INVENTORY)
    rust_flash = load_json(RUST_FLASH_AUDIT)
    delta = load_json(DELTA_AUDIT)

    strict_misses = delta["strict_after"]["misses"]

    targets: list[dict[str, Any]] = []

    for row in python_status_rows:
        targets.append(
            {
                "language_family": "python",
                "lane": "python_verifier_outcome",
                "candidate_root_id": row["bundle_id"],
                "repo_id": row["repo_id"],
                "priority_order": row["priority_order"],
                "status": (
                    "immediately_qualified_reviewed_support"
                    if row["immediately_qualified_for_reviewed_verifier_packet"]
                    else "blocked_needs_more_materialization"
                ),
                "usable_now_for_promotable_support": bool(row["immediately_qualified_for_reviewed_verifier_packet"]),
                "selected_test_count": row["reviewed_selected_tests_count"],
                "executable_verifier_row_count": row["executable_verifier_row_count"],
                "gaps": row["gaps"],
                "motivation": row["motivation"],
                "gold_verifier_target": row["reviewed_verifier_gold_value"],
            }
        )

    for row in rust_targets:
        targets.append(
            {
                "language_family": "rust",
                "lane": "rust_evidence_citation",
                "candidate_root_id": row["candidate_root_id"],
                "repo_id": row["repo_id"],
                "priority_score": row["priority_score"],
                "status": (
                    "review_ready_but_needs_anchor"
                    if row["review_ready_for_bundle_construction"]
                    else "needs_bundle_and_anchor_materialization"
                ),
                "usable_now_for_promotable_support": False,
                "competition_geometries": row["competition_geometries"],
                "test_file_count": row["test_file_count"],
                "required_builder_delta": row["required_builder_delta"],
                "recommendation": row["recommendation"],
            }
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_lane_fresh_root_supply_manifest_ready",
        "claim_scope": [
            "Convert the current standalone plateau into a concrete fresh-root supply ledger for the two remaining strict misses.",
            "Separate immediately usable reviewed support from roots that still require verifier-anchor or review-packet construction.",
            "Keep anti-cheat and promotion boundaries explicit so new support does not get overstated as a fresh heldout win.",
        ],
        "current_plateau": {
            "strict_exact": delta["headline"]["strict_exact_after"],
            "strict_delta_last_probe": delta["headline"]["strict_delta"],
            "strict_miss_rows": strict_misses,
        },
        "python_lane": {
            "residual_family": "selected_test_verifier_disambiguation",
            "strict_miss_row_id": next((m["row_id"] for m in strict_misses if "::python::" in m["row_id"]), None),
            "immediately_qualified_reviewed_roots": [
                row["bundle_id"] for row in python_status_rows if row["immediately_qualified_for_reviewed_verifier_packet"]
            ],
            "blocked_roots": [
                {
                    "bundle_id": row["bundle_id"],
                    "gaps": row["gaps"],
                }
                for row in python_status_rows
                if not row["immediately_qualified_for_reviewed_verifier_packet"]
            ],
            "source_summary": python_packet["summary"],
            "required_next_step": "Build a promotable support package around the single immediately-qualified context_pack root, then source new disjoint Python verifier roots instead of replaying MirrorMind-style same-surface support.",
        },
        "rust_lane": {
            "residual_family": "evidence_support_disambiguation_e_vs_f",
            "strict_miss_row_id": next((m["row_id"] for m in strict_misses if "::rust::" in m["row_id"]), None),
            "support_only_reviewed_root": rust_flash["bundle_identity"]["expected_bundle_id"],
            "support_only_boundary": rust_flash["claim_boundary"],
            "remaining_builder_targets": rust_inventory["refreshed_state"]["remaining_builder_targets"],
            "fresh_builder_target_count_remaining": rust_inventory["metrics"]["fresh_builder_target_count_remaining"],
            "required_next_step": "Materialize at least one non-tokenizers reviewed Rust root with a real verifier or selected-test anchor and explicit candidate_change_surface versus symptom_or_call_path contrast.",
        },
        "anti_cheat_contract": [
            "No root in this manifest may be promoted if target path, gold test path, or gold evidence appears verbatim before the candidate set.",
            "Same-root and same-lineage support rows remain train-support only unless a distinct heldout root is reserved before training.",
            "Rust candidate_change_surface negatives must stay visible as tempting wrong options; the gold support fact must be distinct from verifier_and_test_constraint.",
            "Python verifier roots must contain multiple plausible selected tests; singleton or path-revealing packets are support-only, not promotion-ready.",
            "Support-only fresh roots such as flash-attn may improve training, but they do not count as source-heldout headline evidence.",
        ],
        "next_best_steps": [
            "Build the next promotable Python verifier support package from the single immediately-qualified reviewed context_pack root.",
            "Start Rust builder materialization with tokenizers::bindings/node and linux::rust, because they provide the best immediate non-tokenizers or geometry-rich candidate surfaces from the current inventories.",
            "Keep flash-attn in multilingual support for robustness, but do not use it as the proof artifact for the Rust headline.",
        ],
        "sources": {
            "python_review_packet_builder": rel(PYTHON_PACKET),
            "python_target_status": rel(PYTHON_STATUS),
            "rust_builder_request": rel(RUST_REQUEST),
            "rust_builder_targets": rel(RUST_TARGETS),
            "rust_inventory_refresh": rel(RUST_INVENTORY),
            "rust_flash_attn_support_audit": rel(RUST_FLASH_AUDIT),
            "latest_probe_delta_audit": rel(DELTA_AUDIT),
        },
    }

    write_json(OUT_JSON, summary)
    write_jsonl(OUT_JSONL, targets)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
