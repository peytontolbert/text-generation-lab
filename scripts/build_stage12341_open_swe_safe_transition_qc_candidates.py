#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12341_open_swe_safe_transition_qc_candidates"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE = ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_priority_capped_trace_support_candidates.jsonl"
MAX_CANDIDATES = 25
MAX_PER_REPO = 3


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(payload: Any, n: int = 16) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def score(row: dict[str, Any]) -> tuple[int, int, int]:
    meta = row.get("trace_metadata") or {}
    verification_turns = int(meta.get("verification_turn_count") or 0)
    modified_files = int(meta.get("metadata_num_modified_files") or 0)
    modified_lines = int(meta.get("metadata_num_modified_lines") or 0)
    return (verification_turns, -abs(modified_files - 1), -abs(modified_lines - 8))


def transition_family(row: dict[str, Any]) -> str:
    markers = set((row.get("trace_metadata") or {}).get("failure_markers") or [])
    if {"PASSED", "FAILED"} & markers and "pytest" in markers:
        return "python_pytest_patch_verify_trace_candidate"
    if "Traceback" in markers:
        return "python_traceback_recovery_trace_candidate"
    return "python_generic_verify_trace_candidate"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(SOURCE)
    ranked = sorted(rows, key=score, reverse=True)
    selected = []
    per_repo = defaultdict(int)
    blocked_by_cap = []
    for row in ranked:
        repo = row.get("repo_family") or "unknown"
        if per_repo[repo] >= MAX_PER_REPO:
            blocked_by_cap.append(row.get("candidate_id"))
            continue
        selected.append(row)
        per_repo[repo] += 1
        if len(selected) >= MAX_CANDIDATES:
            break
    qc_rows = []
    for index, row in enumerate(selected, 1):
        source_ref = row.get("source_record_ref") or {}
        meta = row.get("trace_metadata") or {}
        lineage_payload = {
            "source_adapter": row.get("source_adapter"),
            "dataset_file": source_ref.get("dataset_file"),
            "trajectory_family": source_ref.get("trajectory_family"),
            "trajectory_id": source_ref.get("trajectory_id"),
            "instance_id": source_ref.get("instance_id"),
        }
        qc_rows.append({
            "stage": STAGE,
            "record_type": "open_swe_safe_transition_qc_candidate",
            "qc_candidate_id": f"{STAGE}::{stable_hash(lineage_payload)}",
            "source_candidate_id": row.get("candidate_id"),
            "source_adapter": "Open-SWE-Traces",
            "rank": index,
            "language_family": row.get("language_family"),
            "repo_family": row.get("repo_family"),
            "lineage_key_hash": stable_hash(lineage_payload, 24),
            "source_record_ref_hash": stable_hash(source_ref, 24),
            "seed_path_count": row.get("seed_path_count"),
            "seed_path_hashes": (row.get("seed_path_hashes") or [])[:8],
            "selected_test_count": row.get("selected_test_count"),
            "selected_test_hashes": (row.get("selected_test_hashes") or [])[:12],
            "trace_counts": {
                "turn_count": meta.get("turn_count"),
                "tool_turn_count": meta.get("tool_turn_count"),
                "verification_turn_count": meta.get("verification_turn_count"),
                "metadata_num_modified_files": meta.get("metadata_num_modified_files"),
                "metadata_num_modified_lines": meta.get("metadata_num_modified_lines"),
            },
            "trace_marker_classes": sorted(set(meta.get("failure_markers") or [])),
            "tool_name_hashes": (meta.get("tool_name_hashes") or [])[:12],
            "transition_function_candidate_key": transition_family(row),
            "safe_derived_state": {
                "has_patch_signal": bool(meta.get("metadata_num_modified_files") or meta.get("metadata_num_modified_lines")),
                "has_verifier_signal": bool(meta.get("verification_turn_count")),
                "has_failure_marker_signal": bool(meta.get("failure_markers")),
                "same_source_order_proven": False,
                "verifier_causality_proven": False,
                "state_before_hydrated": False,
                "state_after_hydrated": False,
            },
            "raw_content_policy": {
                "raw_issue_text_emitted": False,
                "raw_patch_emitted": False,
                "raw_trajectory_emitted": False,
                "raw_verifier_output_emitted": False,
            },
            "admission": {
                "training_allowed": False,
                "train_support_allowed": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "admission_status": "qc_candidate_only",
            },
            "blocked_reasons": [
                "raw_trace_not_semantically_extracted",
                "same_source_order_not_proven",
                "verifier_causality_not_proven",
                "state_before_after_not_hydrated",
                "anti_leak_renderer_missing",
                "candidate_only_not_train_support",
            ],
            "hard_rejects": [
                "treat Open-SWE resolved metadata as repair proof",
                "treat patch and verifier co-presence as causality",
                "emit raw trajectory/diff/verifier output into model-facing rows",
                "count qc_candidate as train-support or Level-3",
            ],
        })
    write_jsonl(OUT / "open_swe_safe_transition_qc_candidates.jsonl", qc_rows)
    summary = {
        "stage": STAGE,
        "decision": "open_swe_safe_transition_qc_candidates_ready_no_admission",
        "training_allowed": False,
        "claim_boundary": "QC candidate records only. No train-support, strict eval, Level-3, patch-trace, or repair rows admitted.",
        "source_priority_candidates": len(rows),
        "qc_candidate_count": len(qc_rows),
        "max_candidates": MAX_CANDIDATES,
        "max_per_repo": MAX_PER_REPO,
        "repo_counts": dict(Counter(row.get("repo_family") for row in qc_rows)),
        "transition_function_candidate_counts": dict(Counter(row.get("transition_function_candidate_key") for row in qc_rows)),
        "blocked_by_repo_cap_count": len(blocked_by_cap),
        "next_stage": "stage123xx_open_swe_raw_trace_internal_semantic_extractor_with_no_raw_model_output",
    }
    (OUT / "open_swe_safe_transition_qc_candidates_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "OPEN_SWE_SAFE_TRANSITION_QC_CANDIDATES_STAGE12341.md").write_text(
        "# Stage12341 Open-SWE Safe Transition QC Candidates\n\n"
        "Produces capped, source-diverse Open-SWE QC candidates with hashes/enums only. This stage admits zero rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
