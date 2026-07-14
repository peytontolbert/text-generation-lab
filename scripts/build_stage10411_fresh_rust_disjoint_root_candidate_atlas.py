#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas"
SOURCE = ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_candidates.jsonl"
REVIEW_PACKETS = ROOT / "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets"

ALREADY_REVIEWED = {
    "tokenizers::tokenizers",
    "candle::candle-core",
    "candle::candle-nn",
    "candle::candle-examples",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_review_statuses() -> dict[str, dict]:
    statuses: dict[str, dict] = {}
    if not REVIEW_PACKETS.is_dir():
        return statuses
    for packet in REVIEW_PACKETS.iterdir():
        rubric_path = packet / "expert_maintainer_rubric_review.json"
        anti_path = packet / "anti_cheat_review_card.json"
        gold_path = packet / "perspective_gold_adjudication.json"
        if not (rubric_path.exists() and anti_path.exists() and gold_path.exists()):
            continue
        rubric = json.loads(rubric_path.read_text())
        anti = json.loads(anti_path.read_text())
        gold = json.loads(gold_path.read_text())
        bundle_id = str(rubric.get("bundle_id") or "")
        candidate_root_id = bundle_id.replace("stage10126::", "").rsplit("::", 1)[0] if bundle_id else ""
        statuses[candidate_root_id] = {
            "bundle_id": bundle_id,
            "bundle_valid_for_eval": rubric.get("bundle_valid_for_eval"),
            "anti_cheat_admissible": anti.get("admissible_for_same_surface_comparison"),
            "gold_ready": gold.get("bundle_gold_ready_for_eval"),
            "decision_rationale": rubric.get("decision_rationale"),
        }
    return statuses


def atlas_row(row: dict, review_statuses: dict[str, dict]) -> dict:
    root_id = row["candidate_root_id"]
    reviewed = review_statuses.get(root_id)
    is_reviewed = reviewed is not None
    implementation_vs_test = "implementation_vs_test" in (row.get("competition_geometries") or [])
    test_count = int(row.get("test_file_count") or 0)
    build_count = int(row.get("build_file_count") or 0)
    support_count = int(row.get("support_file_count") or 0)
    richness = int(row.get("richness_score") or 0)
    rust_file_count = int(row.get("rust_file_count") or 0)

    freshness_bonus = 4 if not is_reviewed else 0
    verifier_anchor_bonus = 4 if test_count > 0 else 0
    geometry_bonus = 3 if implementation_vs_test else 0
    build_penalty = -2 if build_count > 0 and test_count == 0 else 0
    support_penalty = -1 if support_count > implementation_vs_test + 10 else 0
    scale_bonus = 2 if rust_file_count >= 4 else 0
    priority_score = richness + freshness_bonus + verifier_anchor_bonus + geometry_bonus + build_penalty + support_penalty + scale_bonus

    recommendation = "fresh_bundle_candidate"
    if is_reviewed and reviewed.get("bundle_valid_for_eval") is False:
        recommendation = "reviewed_invalid_do_not_reuse_directly"
    elif is_reviewed and reviewed.get("bundle_valid_for_eval") is True:
        recommendation = "already_in_reviewed_inventory"
    elif test_count == 0 and not implementation_vs_test:
        recommendation = "fresh_candidate_but_needs_stronger_verifier_anchor"

    return {
        "candidate_root_id": root_id,
        "repo_id": row.get("repo_id"),
        "package_root": row.get("package_root"),
        "review_ready_for_bundle_construction": row.get("review_ready_for_bundle_construction"),
        "competition_geometries": row.get("competition_geometries"),
        "richness_score": richness,
        "test_file_count": test_count,
        "build_file_count": build_count,
        "support_file_count": support_count,
        "implementation_file_count": int(row.get("implementation_file_count") or 0),
        "rust_file_count": rust_file_count,
        "sample_span_ids": row.get("sample_span_ids"),
        "candidate_paths_preview": row.get("candidate_paths_preview"),
        "already_reviewed": is_reviewed,
        "review_status": reviewed,
        "priority_score": priority_score,
        "recommendation": recommendation,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(SOURCE)
    review_statuses = load_review_statuses()
    atlas = [atlas_row(row, review_statuses) for row in rows]
    atlas.sort(key=lambda row: (-row["priority_score"], row["candidate_root_id"]))

    fresh = [row for row in atlas if row["candidate_root_id"] not in ALREADY_REVIEWED]
    fresh_sorted = sorted(fresh, key=lambda row: (-row["priority_score"], row["candidate_root_id"]))
    top_fresh = fresh_sorted[:8]

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": 10411,
        "stage_name": "stage10411_fresh_rust_disjoint_root_candidate_atlas",
        "source_artifact": str(SOURCE.relative_to(ROOT)),
        "metrics": {
            "candidate_root_count": len(atlas),
            "already_reviewed_root_count": sum(1 for row in atlas if row["already_reviewed"]),
            "fresh_root_count": len(fresh),
            "fresh_review_ready_count": sum(1 for row in fresh if row["review_ready_for_bundle_construction"]),
            "fresh_with_test_files": sum(1 for row in fresh if row["test_file_count"] > 0),
            "fresh_with_implementation_vs_test_geometry": sum(
                1 for row in fresh if "implementation_vs_test" in (row["competition_geometries"] or [])
            ),
            "recommendation_counts": dict(Counter(row["recommendation"] for row in fresh)),
        },
        "top_fresh_candidates": top_fresh,
        "claim_boundary": [
            "This atlas ranks fresh Rust roots beyond the two admitted and two invalid reviewed bundles; it does not itself create a new maintainer bundle.",
            "Freshness alone is not enough. Candidates without tests or verifier anchors still need stronger evidence materialization before they should enter scoring.",
        ],
        "next_best_step": "Build the next Rust maintainer preview from the top fresh candidate with the strongest verifier-anchor story, then adjudicate it before any broader Rust-vs-Gemma claim.",
        "recommended_first_builder_targets": [
            "tokenizers::bindings/node",
            "candle::candle-flash-attn",
            "git::contrib/libgit-rs",
        ],
    }

    (OUT_DIR / "fresh_rust_disjoint_root_candidate_atlas.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT_DIR / "fresh_rust_disjoint_root_candidate_rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in fresh_sorted)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
