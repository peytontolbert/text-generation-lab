#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data/agentkernel-seq2seq-text-lab")
OUT_DIR = ROOT / "runs/local/artifacts/stage10412_multilingual_dataset_scale_audit"

FRONTIER_EVAL = ROOT / "runs/local/artifacts/stage10404_generic_policy_frontier_eval/language_conditioned_frontier_eval.json"
GEMMA_COMPARE = ROOT / "runs/local/artifacts/stage10406_gemma_same_frontier_comparison/gemma_same_frontier_comparison.json"
SUCCESSOR_INVENTORY = ROOT / "runs/local/artifacts/stage10409_review_blocked_successor_inventory/review_blocked_successor_inventory.json"
SUCCESSOR_SALVAGE = ROOT / "runs/local/artifacts/stage10410_ai_adjudicated_successor_salvage/ai_adjudicated_successor_salvage.json"
RUST_ATLAS = ROOT / "runs/local/artifacts/stage10411_fresh_rust_disjoint_root_candidate_atlas/fresh_rust_disjoint_root_candidate_atlas.json"
RUST_DISCOVERY = ROOT / "runs/local/artifacts/stage10125_true_source_backed_rust_root_discovery_manifest/true_source_backed_rust_root_discovery_manifest.json"
RUST_PREVIEW = ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview_manifest.json"

PROBE_MANIFESTS = {
    "stage10369": ROOT / "runs/local/artifacts/stage10369_honest_frontier_diagnostic_execution_request/honest_frontier_diagnostic_manifest.jsonl",
    "stage10376": ROOT / "runs/local/artifacts/stage10376_residual_semantic_support_execution_request/residual_semantic_support_manifest.jsonl",
    "stage10378": ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl",
    "stage10396": ROOT / "runs/local/artifacts/stage10396_multilingual_residual_contrast_execution_request/multilingual_residual_contrast_manifest.jsonl",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def count_manifest(path: Path) -> dict[str, int | dict[str, int]]:
    counts = {"total_rows": 0, "train_rows": 0, "strict_eval_rows": 0, "eval_rows": 0}
    if not path.exists():
        return counts
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            counts["total_rows"] += 1
            split = str(row.get("split") or row.get("package_split") or row.get("manifest_split") or "train")
            normalized = "strict_eval" if split == "strict" else split
            if normalized == "train":
                counts["train_rows"] += 1
            elif normalized == "strict_eval":
                counts["strict_eval_rows"] += 1
            elif normalized == "eval":
                counts["eval_rows"] += 1
    return counts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    frontier = load_json(FRONTIER_EVAL)
    gemma = load_json(GEMMA_COMPARE)
    successor_inventory = load_json(SUCCESSOR_INVENTORY)
    successor_salvage = load_json(SUCCESSOR_SALVAGE)
    rust_atlas = load_json(RUST_ATLAS)
    rust_discovery = load_json(RUST_DISCOVERY)
    rust_preview = load_json(RUST_PREVIEW)

    probe_counts = {stage: count_manifest(path) for stage, path in PROBE_MANIFESTS.items()}

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": 10412,
        "stage_name": "stage10412_multilingual_dataset_scale_audit",
        "frontier_status": {
            "strict_eval_rows": frontier["correct"],
            "policy_accuracy": frontier["accuracy"],
            "policy_name": frontier["policy"],
            "same_frontier_gemma_accuracy": gemma["gemma_accuracy"],
            "same_frontier_delta": gemma["delta_hundred_m_minus_gemma"],
            "per_language_rows": {k: v["rows"] for k, v in gemma["per_language"].items()},
        },
        "recent_probe_manifest_counts": probe_counts,
        "successor_expansion_status": {
            "review_blocked_non_frontier_counts": successor_inventory["review_blocked_non_frontier_counts"],
            "targeted_successor_rows_admitted": successor_salvage["targeted_admitted_count"],
            "targeted_successor_rows_by_language": {
                "python": 2,
                "c_cpp": 1,
                "web_js_ts_html": 1,
                "rust": 0,
            },
        },
        "rust_expansion_status": {
            "discovery_candidate_root_count": rust_discovery["metrics"]["candidate_root_count"],
            "preview_root_bundles": rust_preview["metrics"]["preview_root_bundles"],
            "fresh_root_count": rust_atlas["metrics"]["fresh_root_count"],
            "fresh_review_ready_count": rust_atlas["metrics"]["fresh_review_ready_count"],
            "fresh_with_test_files": rust_atlas["metrics"]["fresh_with_test_files"],
            "best_fresh_candidate": rust_atlas["top_fresh_candidates"][0]["candidate_root_id"],
        },
        "claim_boundary": [
            "The current multilingual win is still a bounded 47-row frontier, not yet a broad maintainer-grade dataset result.",
            "Recent training/eval loops remain compact manifest probes rather than large-scale software-maintenance pretraining.",
            "Non-frontier support has improved in Python/C++/web, but Rust still needs a fresh reviewed root to keep dataset scaling honest across all four languages.",
        ],
        "next_dataset_scaling_priorities": [
            "Build and adjudicate a fresh Rust maintainer root from candle::candle-flash-attn or the next-best fresh verifier-anchored candidate.",
            "Convert the strongest remaining Python/C++ review-blocked successors into honest abstention or singleton support rows only where prompt-visible evidence justifies it.",
            "Build at least one pure-web maintainer root beyond the mixed-language code_assist support path.",
            "Require future scaling rows to carry explicit verifier/test anchors and visible evidence support, not just more bounded-choice permutations.",
            "Track not only accuracy but root count, repo count, verifier-anchor count, and margin above the closest distractor.",
        ],
    }

    (OUT_DIR / "multilingual_dataset_scale_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
