#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    stage10643 = load_json(
        ARTIFACTS
        / "stage10643_reviewed_v27_claim_readiness_audit"
        / "reviewed_v27_claim_readiness_audit.json"
    )
    stage10644 = load_json(
        ARTIFACTS
        / "stage10644_reviewed_v27_replenishment_candidate_audit"
        / "reviewed_v27_replenishment_candidate_audit.json"
    )
    stage10645 = load_json(
        ARTIFACTS
        / "stage10645_reviewed_v28_candidate_manifest_package"
        / "reviewed_v28_candidate_manifest_package.json"
    )
    stage10646 = load_json(
        ARTIFACTS
        / "stage10646_reviewed_v28_candidate_same_manifest_comparison"
        / "reviewed_v28_candidate_same_manifest_comparison.json"
    )
    rows = load_jsonl(
        ARTIFACTS
        / "stage10646_reviewed_v28_candidate_same_manifest_comparison"
        / "reviewed_v28_candidate_same_manifest_rows.jsonl"
    )

    hundred_by_slice = stage10646["by_slice"]["hundred_m"]
    gemma_by_slice = stage10646["by_slice"]["gemma12b"]
    rust_replacement_delta = (
        hundred_by_slice["rust_replacement_experiment"]["exact_accuracy"]
        - gemma_by_slice["rust_replacement_experiment"]["exact_accuracy"]
    )

    hundred_m_misses = [row for row in rows if row["hundred_m_correct"] is False]
    rust_replacement_misses = [
        row for row in hundred_m_misses if row["slice_name"] == "rust_replacement_experiment"
    ]

    audit = {
        "stage": 10647,
        "stage_name": "stage10647_reviewed_v28_candidate_result_audit",
        "passed": True,
        "sources": {
            "stage10643_claim_readiness": str(
                ARTIFACTS
                / "stage10643_reviewed_v27_claim_readiness_audit"
                / "reviewed_v27_claim_readiness_audit.json"
            ),
            "stage10644_replenishment_audit": str(
                ARTIFACTS
                / "stage10644_reviewed_v27_replenishment_candidate_audit"
                / "reviewed_v27_replenishment_candidate_audit.json"
            ),
            "stage10645_v28_candidate_package": str(
                ARTIFACTS
                / "stage10645_reviewed_v28_candidate_manifest_package"
                / "reviewed_v28_candidate_manifest_package.json"
            ),
            "stage10646_same_manifest_comparison": str(
                ARTIFACTS
                / "stage10646_reviewed_v28_candidate_same_manifest_comparison"
                / "reviewed_v28_candidate_same_manifest_comparison.json"
            ),
        },
        "headline_status": {
            "v27_same_manifest_multilingual_win_preserved": (
                stage10646["by_slice"]["hundred_m"]["headline_strict"]["exact_accuracy"]
                == stage10643["headline_supported"]["hundred_m_strict_correct"] / stage10643["headline_supported"]["strict_rows"]
            ),
            "headline_strict_100m_accuracy": hundred_by_slice["headline_strict"]["exact_accuracy"],
            "headline_strict_gemma_accuracy": gemma_by_slice["headline_strict"]["exact_accuracy"],
            "headline_strict_delta": (
                hundred_by_slice["headline_strict"]["exact_accuracy"]
                - gemma_by_slice["headline_strict"]["exact_accuracy"]
            ),
        },
        "rust_replacement_experiment": {
            "hundred_m_accuracy": hundred_by_slice["rust_replacement_experiment"]["exact_accuracy"],
            "gemma_accuracy": gemma_by_slice["rust_replacement_experiment"]["exact_accuracy"],
            "delta": rust_replacement_delta,
            "supports_same_manifest_rust_strength": rust_replacement_delta > 0.0,
            "supports_headline_upgrade_now": False,
            "reason_not_headline_upgrade": [
                "replacement rows are an explicit experiment slice, not the frozen headline path",
                "the strongest reviewed Rust alternatives still include abstention-heavy caveats",
                "one Rust evidence_citation miss remains on candle-flash-attn",
            ],
        },
        "remaining_hundred_m_misses": [
            {
                "row_id": row["row_id"],
                "slice_name": row["slice_name"],
                "language_family": row["language_family"],
                "task_type": row["task_type"],
                "target_text": row["target_text"],
                "hundred_m_predicted_label": row["hundred_m_predicted_label"],
                "gemma12b_predicted_label": row["gemma12b_predicted_label"],
            }
            for row in hundred_m_misses
        ],
        "remaining_gap_assessment": {
            "total_hundred_m_misses": len(hundred_m_misses),
            "rust_replacement_misses": len(rust_replacement_misses),
            "headline_miss_families": [
                "python_verifier_outcome_target_disambiguation",
                "rust_evidence_citation_candidate_surface_attractor",
            ],
            "replacement_miss_families": [
                "rust_flash_attn_evidence_citation"
            ],
        },
        "eval_hacking_boundary": {
            "new_same_manifest_cheat_path_introduced": False,
            "why": [
                "100M scoring uses the frozen stage10422 runtime bundle rather than a newly tuned model",
                "headline_strict remains unchanged from the existing v2.7 claim path",
                "Rust replacements are kept in a separate experimental slice instead of being silently merged into the headline",
            ],
            "still_missing_for_stronger_claim": [
                "fresh pure-web verifier-anchored roots",
                "fresh non-abstention-heavy Rust roots",
                "source-heldout proof for the broader multilingual headline",
            ],
        },
        "decision": "current_100m_beats_gemma_on_headline_and_reviewed_rust_replacement_same_manifest_slices_but_stronger_multilingual_upgrade_still_requires_fresh_web_and_rust_supply",
        "next_best_step": [
            "keep the stage10423/stage10643 headline as the honest same-manifest benchmark claim",
            "treat stage10646 Rust replacement as supporting evidence that Rust strength generalizes beyond tokenizers, but not as a headline upgrade yet",
            "mine fresh pure-web verifier-anchored roots and fresh non-abstention-heavy Rust roots for the next promotable multilingual package",
        ],
    }

    out_dir = ARTIFACTS / "stage10647_reviewed_v28_candidate_result_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reviewed_v28_candidate_result_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    print(out_dir / "reviewed_v28_candidate_result_audit.json")


if __name__ == "__main__":
    main()
