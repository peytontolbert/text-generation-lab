#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12315_rust_cpp_selected_test_hydration_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12307 = (
    ROOT
    / "runs/local/artifacts/stage12307_rust_cpp_selected_test_root_candidate_queue"
    / "canonical_root_candidate_queue_records.jsonl"
)

SUBAGENT_RANKING = {
    "Neargye/magic_enum": {
        "priority": 1,
        "route": "canonical_rewrite_from_stage12130",
        "reason": "Closest C/C++ root: existing selected-test support row contains commit/test/verifier/hash summaries but needs canonical root-candidate rewrite.",
    },
    "fastfloat/fast_float": {
        "priority": 1,
        "route": "canonical_rewrite_from_stage12130",
        "reason": "Closest C/C++ root: existing selected-test support row contains commit/test/verifier/hash summaries but needs canonical root-candidate rewrite.",
    },
    "dtolnay/anyhow": {
        "priority": 2,
        "route": "local_checkout_hash_capture",
        "reason": "Closest Rust root: recorded selected-test command/log evidence exists; source/test hash refs must be captured from recorded local checkout.",
    },
    "assert-rs/predicates-rs": {
        "priority": 2,
        "route": "local_checkout_hash_capture",
        "reason": "Closest Rust root: recorded selected-test command/log evidence exists; source/test hash refs must be captured from recorded local checkout.",
    },
    "toml-rs/toml": {
        "priority": 2,
        "route": "local_checkout_hash_capture",
        "reason": "Closest Rust root: recorded selected-test command/log evidence exists; source/test hash refs must be captured from recorded local checkout.",
    },
    "BurntSushi/byteorder": {
        "priority": 3,
        "route": "offline_selected_test_execution_required",
        "reason": "Likely local checkout, but selected executed test evidence and hashes are still missing.",
    },
    "uuid-rs/uuid": {
        "priority": 3,
        "route": "offline_selected_test_execution_required",
        "reason": "Likely local checkout, but selected executed test evidence and hashes are still missing.",
    },
    "jarro2783/cxxopts": {
        "priority": 4,
        "route": "full_hydration_required",
        "reason": "Planned C++ root; commit, selected tests, verifier log, source hashes, and test hashes are missing.",
    },
    "p-ranav/argparse": {
        "priority": 4,
        "route": "full_hydration_required",
        "reason": "Planned C++ root; commit, selected tests, verifier log, source hashes, and test hashes are missing.",
    },
}

NORMALIZE = {
    "aho-corasick": "BurntSushi/aho-corasick",
    "quote": "dtolnay/quote",
    "time": "time-rs/time",
    "uuid": "uuid-rs/uuid",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_id(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:18]


def derive_priority(record: dict[str, Any]) -> tuple[int, str, str, str]:
    repo = record.get("repo_family") or "unknown"
    canonical_repo = NORMALIZE.get(repo, repo)
    ranked = SUBAGENT_RANKING.get(canonical_repo)
    if ranked:
        return (
            int(ranked["priority"]),
            canonical_repo,
            str(ranked["route"]),
            str(ranked["reason"]),
        )
    status = record.get("status_bucket")
    if status == "ready_or_seed":
        return (5, canonical_repo, "review_ready_seed_but_not_ranked", "Ready/seed status requires manual deterministic review.")
    return (6, canonical_repo, "full_hydration_required", "Queue record lacks enough selected-test/root proof for admission.")


def hydration_steps(route: str) -> list[str]:
    common = [
        "verify_or_attach_commit_sha",
        "attach_selected_test_ids_or_selected_verifier_scope",
        "attach_executed_verifier_command_or_log_ref",
        "capture_source_hash_refs",
        "capture_test_hash_refs",
        "rewrite_non_singleton_semantic_candidate_set",
        "run anti_cheat/leak/lineage audit",
    ]
    if route == "canonical_rewrite_from_stage12130":
        return [
            "read Stage12130 embedded standalone_projection_source metadata",
            "rewrite support-row metadata into canonical root-candidate fields",
            "do not copy Stage12130 row as training/eval data",
            *common,
        ]
    if route == "local_checkout_hash_capture":
        return [
            "locate recorded local checkout from Stage12144/Stage12150 evidence",
            "verify checkout commit matches recorded commit_sha",
            "hash selected source/test files without emitting raw paths or contents",
            *common,
        ]
    if route == "offline_selected_test_execution_required":
        return [
            "locate local checkout and commit",
            "execute only offline no-network selected-test command",
            "store command/log ref with output hash, not raw output",
            *common,
        ]
    return [
        "materialize local/reproducible checkout or authoritative existing log",
        "avoid network/dependency fetch in this stage unless separately approved",
        *common,
    ]


def make_work_item(record: dict[str, Any]) -> dict[str, Any]:
    priority, canonical_repo, route, reason = derive_priority(record)
    missing = list(record.get("missing_fields") or [])
    required_hashes = record.get("required_hashes") or {}
    has_normalization_issue = canonical_repo != record.get("repo_family")
    blockers = list(missing)
    if has_normalization_issue:
        blockers.append("repo_family_normalization_required")
    if route != "canonical_rewrite_from_stage12130" and "selected_verifier_command_or_log_ref" in missing:
        blockers.append("executed_selected_test_log_missing")
    if route == "canonical_rewrite_from_stage12130":
        blockers.append("canonical_candidate_set_rewrite_required")

    return {
        "stage": STAGE,
        "record_type": "rust_cpp_selected_test_hydration_work_item",
        "work_item_id": "stage12315::" + stable_id(record.get("queue_record_id"), canonical_repo, route),
        "source_queue_record_id": record.get("queue_record_id"),
        "language_family": record.get("language_family"),
        "repo_family": record.get("repo_family"),
        "canonical_repo_family": canonical_repo,
        "priority_rank": priority,
        "hydration_route": route,
        "ranking_reason": reason,
        "current_status_bucket": record.get("status_bucket"),
        "current_readiness_status": record.get("readiness_status"),
        "missing_fields": missing,
        "required_hashes": required_hashes,
        "hydration_steps": hydration_steps(route),
        "blockers_before_admission": sorted(set(blockers)),
        "admission_after_this_stage": {
            "training_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "canonical_countable": False,
            "reason": "hydration worklist only; deterministic execution/hash capture/rewrite still required",
        },
        "fail_closed_rules": [
            "Do not admit without commit_sha, selected test IDs/scope, executed verifier log ref, source hashes, test hashes, and non-singleton semantic candidates.",
            "Do not count build-only evidence as selected-test proof.",
            "Do not treat Stage12130 support rows as canonical roots.",
            "Do not emit raw source paths, raw command text, raw logs, or raw file contents.",
            "Do not use network/dependency fetch or GPU training in this stage.",
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue_records = read_jsonl(STAGE12307)
    work_items = [make_work_item(record) for record in queue_records]
    work_items.sort(
        key=lambda row: (
            row["priority_rank"],
            row.get("language_family") or "",
            row.get("canonical_repo_family") or "",
        )
    )
    write_jsonl(OUT / "rust_cpp_selected_test_hydration_work_items.jsonl", work_items)

    language_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    top_priority = []
    for item in work_items:
        language_counts[item.get("language_family") or "unknown"] += 1
        route_counts[item["hydration_route"]] += 1
        priority_counts[str(item["priority_rank"])] += 1
        blocker_counts.update(item["blockers_before_admission"])
        if item["priority_rank"] <= 2:
            top_priority.append(
                {
                    "repo_family": item["repo_family"],
                    "canonical_repo_family": item["canonical_repo_family"],
                    "language_family": item["language_family"],
                    "route": item["hydration_route"],
                }
            )

    summary = {
        "stage": STAGE,
        "decision": "rust_cpp_selected_test_hydration_worklist_ready_training_blocked",
        "claim_boundary": "Hydration worklist only. No rows admitted, no tests executed, no hashes captured, no training/eval claim.",
        "training_allowed": False,
        "queue_records": len(queue_records),
        "work_items": len(work_items),
        "training_rows_emitted": 0,
        "admitted_roots": 0,
        "language_counts": dict(language_counts),
        "hydration_route_counts": dict(route_counts),
        "priority_counts": dict(priority_counts),
        "blocker_counts": dict(blocker_counts),
        "top_priority_items": top_priority,
        "subagent_findings_encoded": [
            "magic_enum and fast_float are closest C/C++ roots but require canonical rewrite from Stage12130 metadata.",
            "anyhow, predicates-rs, and toml are closest Rust roots but need source/test hash capture from recorded local checkouts.",
            "uuid/aho-corasick/quote/time need repo-family normalization before plan-backed hydration can be trusted.",
        ],
        "next_stage": {
            "stage": "stage12317_rust_cpp_hash_capture_and_canonical_rewrite",
            "purpose": "Execute deterministic no-network hash capture/canonical rewrite for priority 1-2 roots only.",
            "training_allowed": False,
        },
    }
    (OUT / "rust_cpp_selected_test_hydration_worklist_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "RUST_CPP_SELECTED_TEST_HYDRATION_WORKLIST_STAGE12315.md").write_text(
        "# Stage12315 Rust/C++ Selected-Test Hydration Worklist\n\n"
        "This stage ranks Stage12307 queue records for deterministic hydration. It does not admit rows.\n\n"
        "## Priority\n\n"
        "1. Rewrite `Neargye/magic_enum` and `fastfloat/fast_float` from Stage12130 metadata into canonical root candidates.\n"
        "2. Capture source/test hashes for `dtolnay/anyhow`, `assert-rs/predicates-rs`, and `toml-rs/toml` from recorded local checkouts.\n"
        "3. Normalize Rust repo-family aliases before trusting later queue records.\n\n"
        "## Boundary\n\n"
        "No root becomes train/eval/source-heldout eligible until commit, selected verifier command/log, source/test hashes, lineage, and non-singleton semantic candidates are attached and audited.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
