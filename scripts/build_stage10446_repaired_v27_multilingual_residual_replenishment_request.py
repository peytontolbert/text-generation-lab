#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10446
NAME = "stage10446_repaired_v27_multilingual_residual_replenishment_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "repaired_v27_multilingual_residual_replenishment_request.json"
TARGETS_JSONL = OUT_DIR / "repaired_v27_multilingual_residual_replenishment_targets.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

FRONTIER_AUDIT_JSON = ROOT / "runs/local/artifacts/stage10443_repaired_v27_frontier_status_audit/repaired_v27_frontier_status_audit.json"
RESIDUAL_QUEUE_JSON = ROOT / "runs/local/artifacts/stage10444_repaired_v27_disjoint_residual_queue/repaired_v27_disjoint_residual_queue.json"
PYTHON_ATLAS_JSON = ROOT / "runs/local/artifacts/stage10445_python_disjoint_root_candidate_atlas/python_disjoint_root_candidate_atlas.json"
RUST_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    frontier = load_json(FRONTIER_AUDIT_JSON)
    residual_queue = load_json(RESIDUAL_QUEUE_JSON)
    python_atlas = load_json(PYTHON_ATLAS_JSON)
    rust_request = load_json(RUST_REQUEST_JSON)

    python_candidates = python_atlas.get("top_candidates") or []
    rust_candidates = rust_request.get("recommended_candidates") or []

    targets = []
    for row in residual_queue.get("targets") or []:
        if row["language_family"] == "python":
            targets.append(
                {
                    "language_family": "python",
                    "row_id": row["row_id"],
                    "task_type": row["task_type"],
                    "priority": 1,
                    "residual_family": row["residual_family"],
                    "required_support_shape": row["required_support_shape"],
                    "recommended_candidate_roots": [candidate["candidate_root_id"] for candidate in python_candidates[:3]],
                    "recommended_candidate_bundle_ids": [candidate["bundle_id"] for candidate in python_candidates[:3]],
                    "next_stage_name": "stage10447_python_disjoint_residual_support_package",
                    "builder_goal": "materialize disjoint Python verifier/evidence support from code_assist-rooted candidates before any further replay-style training",
                }
            )
        elif row["language_family"] == "rust":
            targets.append(
                {
                    "language_family": "rust",
                    "row_id": row["row_id"],
                    "task_type": row["task_type"],
                    "priority": 2,
                    "residual_family": row["residual_family"],
                    "required_support_shape": row["required_support_shape"],
                    "recommended_candidate_roots": [candidate["candidate_root_id"] for candidate in rust_candidates[:3]],
                    "next_stage_name": "stage10448_rust_disjoint_residual_builder_packet",
                    "builder_goal": "materialize at least one reviewed Rust evidence-citation root with a real candidate-surface-vs-support contrast",
                }
            )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Multilingual replenishment request for the remaining repaired-v2.7 residuals.",
            "This request turns the current honest frontier status into concrete disjoint root intake work for Python and Rust.",
        ],
        "source_artifacts": {
            "frontier_status_audit": display(FRONTIER_AUDIT_JSON),
            "residual_queue": display(RESIDUAL_QUEUE_JSON),
            "python_atlas": display(PYTHON_ATLAS_JSON),
            "rust_builder_request": display(RUST_REQUEST_JSON),
        },
        "frontier_context": {
            "same_manifest_100m_strict_accuracy": frontier["frontier_summary"]["live_same_manifest_100m_strict_accuracy"],
            "same_manifest_gemma12b_strict_accuracy": frontier["frontier_summary"]["live_same_manifest_gemma12b_strict_accuracy"],
            "same_manifest_delta": frontier["frontier_summary"]["live_same_manifest_delta"],
            "repaired_overlay_prompt_target_leak_rows": frontier["anti_cheat_status"]["repaired_overlay_prompt_target_leak_rows"],
        },
        "targets": targets,
        "request_policy": {
            "do_not_replay_current_strict_rows_into_train": True,
            "prefer_disjoint_code_assist_python_supply_over_same_family_mirrormind_support": True,
            "require_rust_builder_review_before_training_use": True,
            "keep_stage10424_as_live_headline_until_disjoint_roots_land": True,
        },
        "recommended_stage_sequence": [
            "stage10447_python_disjoint_residual_support_package",
            "stage10448_rust_disjoint_residual_builder_packet",
            "stage10449_reviewed_v27_disjoint_residual_support_probe",
            "stage10450_reviewed_v27_disjoint_residual_probe_audit",
        ],
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "targets_jsonl": display(TARGETS_JSONL),
        },
    }

    write_json(REQUEST_JSON, payload)
    write_jsonl(TARGETS_JSONL, targets)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
