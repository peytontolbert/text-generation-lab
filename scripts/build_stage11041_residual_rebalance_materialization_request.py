#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11041
NAME = "stage11041_residual_rebalance_materialization_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "residual_rebalance_materialization_request.json"
REQUEST_ROWS_JSONL = OUT_DIR / "request_rows.jsonl"

QUEUE_JSON = ARTIFACTS / "stage11040_residual_rebalance_root_expansion_queue" / "residual_rebalance_root_expansion_queue.json"
QUEUE_ROWS = ARTIFACTS / "stage11040_residual_rebalance_root_expansion_queue" / "residual_rebalance_targets.jsonl"
SEED_QUEUE_ROWS = ARTIFACTS / "stage10763_multilingual_root_admission_seed_manifest" / "first_wave_materialization_queue.jsonl"
POSTRUN_AUDIT = ARTIFACTS / "stage11038_successor_residual_postrun_audit" / "successor_residual_postrun_audit.json"
GEOMETRY_AUDIT = ARTIFACTS / "stage11039_successor_residual_geometry_audit" / "successor_residual_geometry_audit.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def request_kind_for(target: dict[str, Any]) -> str:
    lane = str(target.get("queue_lane") or "")
    if lane == "python_verifier_transition_expansion":
        return "python_verifier_transition_seed_materialization"
    if lane == "web_verifier_anchor_acquisition":
        return "pure_web_verifier_anchor_seed_materialization"
    if lane == "rust_non_aliased_evidence_replenishment":
        return "rust_non_aliased_evidence_seed_materialization"
    return "evidence_and_verifier_seed_materialization"


def claim_role_for(target: dict[str, Any]) -> str:
    lane = str(target.get("queue_lane") or "")
    if lane == "web_verifier_anchor_acquisition":
        return "future_promotable_only_after_anchor_review"
    if lane == "python_verifier_transition_expansion":
        return "strict_successor_replacement_candidate"
    if lane == "rust_non_aliased_evidence_replenishment":
        return "rust_replenishment_candidate"
    return "train_support_plus_reserved_candidate"


def promotion_lane_for(target: dict[str, Any]) -> str:
    lane = str(target.get("queue_lane") or "")
    if lane == "python_verifier_transition_expansion":
        return "python_verifier_transition"
    if lane == "rust_non_aliased_evidence_replenishment":
        return "rust_evidence_citation"
    if lane == "web_verifier_anchor_acquisition":
        return "pure_web_anchor"
    return "c_cpp_evidence_and_verifier"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    queue = read_json(QUEUE_JSON)
    queue_rows = read_jsonl(QUEUE_ROWS)
    seed_rows = read_jsonl(SEED_QUEUE_ROWS)
    postrun = read_json(POSTRUN_AUDIT)
    geometry = read_json(GEOMETRY_AUDIT)

    seed_by_root = {str(row.get("root_id") or ""): row for row in seed_rows}
    request_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for target in queue_rows:
        root_id = str(target.get("root_id") or "")
        seed = seed_by_root.get(root_id)
        if seed is None:
            unresolved.append(
                {
                    "queue_rank": target.get("queue_rank"),
                    "root_id": root_id,
                    "repo_id": target.get("repo_id"),
                    "language_family": target.get("language_family"),
                    "reason": "missing_in_stage10763_seed_queue",
                }
            )
            continue

        request_rows.append(
            {
                "priority": int(target.get("queue_rank") or 999),
                "request_kind": request_kind_for(target),
                "claim_role": claim_role_for(target),
                "promotion_lane": promotion_lane_for(target),
                "language_family": target.get("language_family"),
                "repo_id": target.get("repo_id"),
                "repo_family": target.get("repo_family"),
                "root_id": root_id,
                "snapshot_id": target.get("snapshot_id"),
                "source_family_id": target.get("source_family_id"),
                "verifier_id": target.get("verifier_id"),
                "queue_lane": target.get("queue_lane"),
                "queue_rank": target.get("queue_rank"),
                "priority_score": target.get("priority_score"),
                "quality_tier": target.get("quality_tier"),
                "semantic_lane": seed.get("semantic_lane"),
                "seed_queue_lane": seed.get("queue_lane"),
                "seed_queue_rank": seed.get("queue_rank"),
                "seed_reason_codes": list(seed.get("reason_codes") or []),
                "seed_compiled_repo_family_root_count": seed.get("compiled_repo_family_root_count"),
                "objective": " / ".join(str(item) for item in (target.get("required_shape") or [])),
                "why_now": target.get("rationale"),
                "anti_cheat_requirements": list(target.get("anti_cheat_requirements") or []),
                "materialization_requirements": list(target.get("required_shape") or []),
                "global_constraints": list(queue.get("global_constraints") or []),
                "must_hold": [
                    "reserve fresh heldout rows before any training",
                    "keep root-level split isolation",
                    "do not promote same-surface headline gains from these roots without anti-cheat review",
                ],
            }
        )

    request_rows.sort(key=lambda row: (row["priority"], row["language_family"], row["repo_id"], row["root_id"]))

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(request_rows),
        "decision": "residual_rebalance_materialization_request_ready",
        "claim_scope": [
            "Convert the stage11040 residual rebalance queue into executable materialization requests with exact root IDs and lane-specific objectives.",
            "Prioritize real root growth for the remaining Python verifier-transition, C/C++ parametergolf, Rust evidence, and pure-web anchor gaps before any further narrow support probe.",
            "Keep the request honest about promotability: web remains future-promotable-only-after-anchor-review, and all new roots must stay heldout-reserved before training.",
        ],
        "source_artifacts": {
            "residual_rebalance_queue": rel(QUEUE_JSON),
            "residual_rebalance_targets": rel(QUEUE_ROWS),
            "seed_materialization_queue": rel(SEED_QUEUE_ROWS),
            "successor_postrun_audit": rel(POSTRUN_AUDIT),
            "successor_geometry_audit": rel(GEOMETRY_AUDIT),
        },
        "metrics": {
            "request_count": len(request_rows),
            "unresolved_targets": len(unresolved),
            "current_successor_strict_accuracy": ((postrun.get("successor_surface_result") or {}).get("strict_accuracy")),
            "current_reserved_candidate_accuracy": (((postrun.get("reserved_candidate_result") or {}).get("overall") or {}).get("exact_accuracy")),
            "current_train_unique_roots": ((geometry.get("geometry") or {}).get("train_unique_roots")),
            "by_language": {
                language: sum(1 for row in request_rows if str(row.get("language_family") or "") == language)
                for language in sorted({str(row.get("language_family") or "") for row in request_rows})
            },
            "by_request_kind": {
                kind: sum(1 for row in request_rows if str(row.get("request_kind") or "") == kind)
                for kind in sorted({str(row.get("request_kind") or "") for row in request_rows})
            },
        },
        "headline_findings": [
            "The executed successor branch stayed flat and only reached 5/10 on the reserved residual bank, so the next honest move is new root materialization rather than more scorer tuning.",
            "The queue now concretely prioritizes three parametergolf C/C++ roots, two repository_library Python verifier-transition roots, three fresh Rust evidence roots, and two pure-web mem0 anchor candidates.",
            "All selected targets map back to the stage10763 seed queue, so the next stage can proceed as real materialization work instead of another abstract queue reshuffle.",
        ],
        "next_best_step": "Materialize the priority 1-5 C/C++ and Python requests first, then the Rust replenishment roots, and keep web separate until pure-web anchor review passes.",
        "unresolved_targets": unresolved,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "request_rows_jsonl": rel(REQUEST_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(REQUEST_ROWS_JSONL, request_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
