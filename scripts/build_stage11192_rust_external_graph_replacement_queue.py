#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11192
NAME = "stage11192_rust_external_graph_replacement_queue"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_external_graph_replacement_queue.json"
QUEUE_JSONL = OUT_DIR / "rust_external_graph_replacement_work_items.jsonl"
BLOCKED_JSONL = OUT_DIR / "rust_external_graph_blocked_candidates.jsonl"

REPLACEMENT_GAPS = ARTIFACTS / "stage11189_reserved_residual_replacement_source_miner/replacement_source_gaps.jsonl"
EXPORTS = {
    "rust-analyzer": Path("/data/repository_library/exports/rust-analyzer/rust-analyzer.artifacts.jsonl"),
    "prusti-dev": Path("/data/repository_library/exports/prusti-dev/prusti-dev.artifacts.jsonl"),
    "rust": Path("/data/repository_library/exports/rust/rust.artifacts.jsonl"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def artifact_path(uri: str) -> str:
    return uri.split("/artifact/", 1)[-1]


def is_rs(path: str) -> bool:
    return path.endswith(".rs")


def is_test_path(path: str) -> bool:
    lower = path.lower()
    return any(part in lower for part in ["/tests/", "tests/", "test_", "_test", "src/tests", "benches/", "/test/"]) or lower.endswith("tests.rs") or lower.endswith("test.rs")


def is_candidate_path(path: str) -> bool:
    lower = path.lower()
    return is_rs(path) and not is_test_path(path) and any(part in lower for part in ["src/", "crates/", "compiler/", "library/", "prusti-"])


def choose_paths(repo: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    paths = [artifact_path(str(row.get("uri") or "")) for row in artifacts if row.get("type") == "source"]
    rs_paths = [path for path in paths if is_rs(path)]
    candidates = [path for path in rs_paths if is_candidate_path(path)]
    tests = [path for path in rs_paths if is_test_path(path)]
    # Symptom/call-path seed should be a third, non-test source path near a subsystem but not the candidate path.
    symptom_pool = [path for path in candidates if any(token in path.lower() for token in ["diagnostic", "parser", "hir", "mir", "verify", "lint", "type", "lower", "resolve"])]
    if not symptom_pool:
        symptom_pool = candidates[1:]
    candidate_path = candidates[0] if candidates else None
    verifier_path = tests[0] if tests else None
    symptom_path = next((path for path in symptom_pool if path != candidate_path and path != verifier_path), None)
    blockers = []
    if not candidate_path:
        blockers.append("missing_non_test_rust_candidate_path")
    if not verifier_path:
        blockers.append("missing_rust_test_or_bench_path")
    if not symptom_path:
        blockers.append("missing_distinct_symptom_or_call_path_seed")
    return {
        "repo_id": repo,
        "candidate_path": candidate_path,
        "verifier_path": verifier_path,
        "symptom_path": symptom_path,
        "rs_paths_count": len(rs_paths),
        "candidate_paths_count": len(candidates),
        "test_paths_count": len(tests),
        "blockers": blockers,
    }


def make_work_item(gap: dict[str, Any], seed: dict[str, Any], slot: int) -> dict[str, Any]:
    role = gap["target_gold_value"]
    return {
        "work_item_id": f"stage11192::{seed['repo_id']}::rust_replacement_slot_{slot}::{role}",
        "stage": STAGE,
        "admit_role": "reserved_residual_rust_replacement_materialization_candidate",
        "replacement_for_blocked_row_id": gap.get("blocked_row_id"),
        "language_family": "rust",
        "repo_family": seed["repo_id"],
        "repo_id": seed["repo_id"],
        "source_family_id": "repository_library_external_rust_graph_exports",
        "source_artifacts": {
            "artifacts_jsonl": rel(EXPORTS[seed["repo_id"]]),
        },
        "target_task_type": "evidence_citation",
        "target_gold_value": role,
        "seed_role_paths": {
            "candidate_change_surface": seed["candidate_path"],
            "verifier_and_test_constraint": seed["verifier_path"],
            "symptom_or_call_path_analogue": seed["symptom_path"],
        },
        "source_inventory_counts": {
            "rs_paths": seed["rs_paths_count"],
            "candidate_paths": seed["candidate_paths_count"],
            "test_paths": seed["test_paths_count"],
        },
        "required_materialization": [
            "Resolve each seed path to source snippets or graph spans before row construction.",
            "Attach a verifier/test or benchmark anchor; do not use file names alone as gold evidence.",
            "Expose candidate, verifier/test, and symptom/call-path as distinct visible evidence items.",
            "If the symptom/call-path seed cannot be justified as causal evidence, block the row instead of admitting it.",
            "Use opaque shuffled options and keep this row out of train support until a strict replacement split is frozen.",
        ],
        "train_eval_policy": "not_trainable_not_scoreable_until_graph_spans_and_anti_cheat_review_pass",
    }


def main() -> None:
    gaps = [row for row in load_jsonl(REPLACEMENT_GAPS) if row.get("language_family") == "rust"]
    seeds: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for repo, path in EXPORTS.items():
        artifacts = load_jsonl(path)
        seed = choose_paths(repo, artifacts)
        if seed["blockers"]:
            blocked.append(seed)
        else:
            seeds.append(seed)
    selected: list[dict[str, Any]] = []
    used_repos: set[str] = set()
    for idx, gap in enumerate(gaps, start=1):
        seed = next((item for item in seeds if item["repo_id"] not in used_repos), None)
        if seed is None:
            break
        selected.append(make_work_item(gap, seed, idx))
        used_repos.add(seed["repo_id"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(selected) == len(gaps) and not blocked,
        "decision": "rust_external_graph_replacement_queue_ready" if len(selected) == len(gaps) else "rust_external_graph_supply_partial",
        "promotion_eligible": False,
        "reason_not_promotion_eligible": "These are graph-backed materialization work items, not admitted rows; snippets/verifier anchors and anti-cheat review are still required.",
        "source_artifacts": {
            "replacement_gaps": rel(REPLACEMENT_GAPS),
            "exports": {repo: rel(path) for repo, path in EXPORTS.items()},
        },
        "counts": {
            "rust_gaps": len(gaps),
            "selected_work_items": len(selected),
            "blocked_seed_repos": len(blocked),
            "selected_by_gold_value": {value: sum(1 for item in selected if item["target_gold_value"] == value) for value in sorted({item["target_gold_value"] for item in selected})},
            "selected_repos": [item["repo_id"] for item in selected],
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "queue_jsonl": rel(QUEUE_JSONL),
            "blocked_jsonl": rel(BLOCKED_JSONL),
        },
        "next_best_step": "Materialize graph spans/snippets for these three Rust work items, then run the same admission audit used for stage11191 before adding them to the clean residual successor bank.",
    }
    write_jsonl(QUEUE_JSONL, selected)
    write_jsonl(BLOCKED_JSONL, blocked)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
