#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11040
NAME = "stage11040_residual_rebalance_root_expansion_queue"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "residual_rebalance_root_expansion_queue.json"
QUEUE_JSONL = OUT_DIR / "residual_rebalance_targets.jsonl"

POSTRUN_AUDIT = ARTIFACTS / "stage11038_successor_residual_postrun_audit" / "successor_residual_postrun_audit.json"
GEOMETRY_AUDIT = ARTIFACTS / "stage11039_successor_residual_geometry_audit" / "successor_residual_geometry_audit.json"
NEXT_ROOT_BUNDLE = ARTIFACTS / "stage11029_reviewed_multilingual_next_root_bundle_resolved" / "reviewed_multilingual_next_root_bundle_resolved.json"
MATERIALIZATION_REQUEST = ARTIFACTS / "stage10957_immediate_evidence_materialization_request" / "immediate_evidence_materialization_request.json"
SEED_QUEUE = ARTIFACTS / "stage10763_multilingual_root_admission_seed_manifest" / "first_wave_materialization_queue.jsonl"
BULK_QUEUE = ARTIFACTS / "stage10752_multilingual_bulk_root_materialization_queue" / "multilingual_bulk_root_materialization_queue.json"
V28_QUEUE = ARTIFACTS / "stage10433_reviewed_v28_residual_expansion_queue" / "reviewed_v28_residual_expansion_queue.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def select_seed_rows(
    rows: list[dict[str, Any]],
    *,
    lane: str,
    repo_family: str | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    for row in rows:
        if str(row.get("queue_lane") or "") != lane:
            continue
        if repo_family is not None and str(row.get("repo_family") or "") != repo_family:
            continue
        root_id = str(row.get("root_id") or "")
        if root_id in seen_roots:
            continue
        seen_roots.add(root_id)
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def materialization_target(
    *,
    queue_rank: int,
    lane: str,
    repo_family: str,
    root_id: str,
    source_row: dict[str, Any],
    rationale: str,
    required_shape: list[str],
    anti_cheat: list[str],
) -> dict[str, Any]:
    return {
        "queue_rank": queue_rank,
        "language_family": source_row.get("language_family"),
        "queue_lane": lane,
        "repo_family": repo_family,
        "repo_id": source_row.get("repo_id"),
        "root_id": root_id,
        "snapshot_id": source_row.get("snapshot_id"),
        "source_family_id": source_row.get("source_family_id"),
        "verifier_id": source_row.get("verifier_id"),
        "task_family": source_row.get("task_family"),
        "quality_tier": source_row.get("quality_tier"),
        "priority_score": source_row.get("priority_score"),
        "reason_codes": source_row.get("reason_codes"),
        "rationale": rationale,
        "required_shape": required_shape,
        "anti_cheat_requirements": anti_cheat,
    }


def main() -> None:
    postrun = load_json(POSTRUN_AUDIT)
    geometry = load_json(GEOMETRY_AUDIT)
    next_root = load_json(NEXT_ROOT_BUNDLE)
    materialization = load_json(MATERIALIZATION_REQUEST)
    bulk = load_json(BULK_QUEUE)
    v28 = load_json(V28_QUEUE)
    seed_rows = load_jsonl(SEED_QUEUE)

    queue: list[dict[str, Any]] = []

    parametergolf_candidates = select_seed_rows(seed_rows, lane="c_cpp", repo_family="parametergolf", limit=3)
    python_verifier_candidates = select_seed_rows(seed_rows, lane="python", repo_family="repository_library", limit=2)
    rust_candidates = select_seed_rows(seed_rows, lane="rust", repo_family=None, limit=3)
    web_candidates = select_seed_rows(seed_rows, lane="web_js_ts_html", repo_family="mem0", limit=2)

    rank = 1
    for row in parametergolf_candidates:
        queue.append(
            materialization_target(
                queue_rank=rank,
                lane="c_cpp_parametergolf_evidence_and_verifier",
                repo_family="parametergolf",
                root_id=str(row["root_id"]),
                source_row=row,
                rationale="Parametergolf remains 0/2 on the reserved evidence candidate bank and also contributes one validation evidence miss plus one validation verifier miss.",
                required_shape=[
                    "at least one verifier-ledger-positive evidence_citation row with candidate_change_surface as a plausible distractor",
                    "at least one counterexample where candidate_change_surface is genuinely correct",
                    "at least one verifier_outcome row with selected-test competition rather than singleton target",
                ],
                anti_cheat=[
                    "no target path leakage before options",
                    "selected-test anchors visible",
                    "candidate order shuffled across sibling rows",
                    "same-root rows stay in one split",
                ],
            )
        )
        rank += 1

    for row in python_verifier_candidates:
        queue.append(
            materialization_target(
                queue_rank=rank,
                lane="python_verifier_transition_expansion",
                repo_family="repository_library",
                root_id=str(row["root_id"]),
                source_row=row,
                rationale="The successor strict surface still misses the opaque Python verifier-transition row, so more disjoint FAIL_TO_PASS verifier-target competition roots are required.",
                required_shape=[
                    "multiple similar verifier/test candidates",
                    "explicit transition semantics such as FAIL_TO_PASS or NOT_EXERCISED",
                    "visible evidence that discriminates the gold verifier target without path leakage",
                ],
                anti_cheat=[
                    "opaque verifier target IDs",
                    "no literal gold test path before options",
                    "disjoint from current successor strict roots",
                    "selected-test or trace anchor retained",
                ],
            )
        )
        rank += 1

    rust_repo_rationales = {
        "tiktoken": "Fresh Rust evidence lane with selected-test preference and no current reviewed overlap.",
        "dbt-core": "Additional non-tokenizers Rust family to avoid aliasing or overfitting to one repo family.",
        "chroma": "Third Rust contrast family for broader evidence-role generalization.",
    }
    for row in rust_candidates:
        repo = str(row.get("repo_family") or "")
        queue.append(
            materialization_target(
                queue_rank=rank,
                lane="rust_non_aliased_evidence_replenishment",
                repo_family=repo,
                root_id=str(row["root_id"]),
                source_row=row,
                rationale=rust_repo_rationales.get(repo, "Fresh Rust evidence lane to replace aliased or under-proven reviewed rows."),
                required_shape=[
                    "non-aliased evidence_citation rows",
                    "selected-test or trace anchored visible evidence",
                    "candidate_change_surface as a tempting negative without duplicated visible span aliases",
                ],
                anti_cheat=[
                    "no duplicated visible span across gold and distractor roles",
                    "selected-test or verifier anchor required",
                    "root-split clean before training",
                ],
            )
        )
        rank += 1

    for row in web_candidates:
        queue.append(
            materialization_target(
                queue_rank=rank,
                lane="web_verifier_anchor_acquisition",
                repo_family="mem0",
                root_id=str(row["root_id"]),
                source_row=row,
                rationale="Web remains under-proven for promotable claims, so the next useful step is pure-web verifier-anchored supply rather than more overlap controls.",
                required_shape=[
                    "selected-test anchored pure-web row family",
                    "at least one evidence_citation and one verifier_outcome row",
                    "no dependence on previously consumed code_assist overlap roots",
                ],
                anti_cheat=[
                    "pure-web only for promotable path",
                    "no mixed-language shorthand claims",
                    "selected-test anchor visible without exposing answer tokens",
                ],
            )
        )
        rank += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_rebalance_root_expansion_queue_ready",
        "claim_scope": [
            "Translate the executed stage11037/11038 residual results into the next concrete root-expansion queue.",
            "Prioritize real root growth for the remaining blocker lanes instead of more narrow scorer tuning or tiny same-family support blends.",
        ],
        "source_artifacts": {
            "postrun_audit": rel(POSTRUN_AUDIT),
            "geometry_audit": rel(GEOMETRY_AUDIT),
            "reviewed_next_root_bundle": rel(NEXT_ROOT_BUNDLE),
            "materialization_request": rel(MATERIALIZATION_REQUEST),
            "seed_queue": rel(SEED_QUEUE),
            "bulk_queue": rel(BULK_QUEUE),
            "v28_queue": rel(V28_QUEUE),
        },
        "headline_findings": [
            "The executed successor branch stayed flat on the scored surface and only reached 5/10 on the reserved residual bank.",
            "Parametergolf is still the clearest C/C++ blocker at 0/2 reserved candidate accuracy and two heldout-family misses.",
            "The inserted Python verifier-transition successor is still the only strict miss, so more disjoint verifier-transition roots are now mandatory.",
            "Rust remains under-supplied for non-aliased evidence replenishment, and web still lacks promotable verifier-anchored breadth.",
        ],
        "metrics": {
            "current_successor_strict_accuracy": postrun["successor_surface_result"]["strict_accuracy"],
            "current_reserved_candidate_accuracy": postrun["reserved_candidate_result"]["overall"]["exact_accuracy"],
            "current_reserved_by_repo_family": {
                key: value["exact_accuracy"]
                for key, value in sorted(postrun["reserved_candidate_result"]["by_repo_family"].items())
            },
            "current_train_unique_roots": geometry["geometry"]["train_unique_roots"],
            "current_unique_roots_by_language": geometry["geometry"]["unique_roots_by_language"],
            "next_root_bundle_rows": next_root["metrics"]["bundle_rows"],
            "next_root_bundle_candidate_rows": next_root["metrics"]["candidate_rows"],
            "materialization_immediate_count": materialization["headline"]["immediate_materialization_count"],
            "bulk_queue_counts_by_language": bulk["queue_counts_by_language"],
            "selected_queue_targets": len(queue),
            "selected_queue_by_language": dict(sorted(Counter(str(row["language_family"]) for row in queue).items())),
        },
        "selected_targets": queue,
        "global_constraints": [
            "No new rows count toward frontier scale unless they are root-split clean and heldout-reserved before training.",
            "No language headline should be promoted unless fresh roots improve heldout accuracy without regressing the repaired overlay/successor canaries.",
            "Evidence rows must include a visible supporting distinction; verifier rows must include explicit transition semantics and multiple plausible targets.",
        ],
        "next_best_step": "Materialize this queue in order, starting with the three parametergolf roots and two Python verifier-transition roots, then assemble a rebalanced successor package only after those new roots pass anti-cheat review.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "queue_jsonl": rel(QUEUE_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(QUEUE_JSONL, queue)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
