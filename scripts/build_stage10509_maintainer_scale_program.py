from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10509_maintainer_scale_program"

V27_PACKAGE = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
PYTHON_FRONTIER = ROOT / "runs/local/artifacts/stage10507_python_verifier_bvc_frontier_builder/python_verifier_bvc_frontier_builder.json"
RUST_FRONTIER = ROOT / "runs/local/artifacts/stage10508_rust_citation_ef_frontier_builder/rust_citation_ef_frontier_builder.json"
FRONTIER_REQUEST = ROOT / "runs/local/artifacts/stage10506_fresh_python_rust_frontier_request/fresh_python_rust_frontier_request.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    v27 = load_json(V27_PACKAGE)
    py_frontier = load_json(PYTHON_FRONTIER)
    rust_frontier = load_json(RUST_FRONTIER)
    frontier_request = load_json(FRONTIER_REQUEST)

    program = {
        "stage": 10509,
        "stage_name": "stage10509_maintainer_scale_program",
        "current_state": {
            "v27_strict_eval_rows": v27["metrics"]["strict_eval_rows"],
            "v27_root_records": v27["metrics"]["root_records"],
            "v27_row_language_counts": v27["metrics"]["row_language_counts"],
            "python_seed_verifier_rows": py_frontier["seed_supply_summary"]["seed_verifier_rows"],
            "rust_existing_unique_perm_rows": rust_frontier["seed_supply_summary"]["existing_unique_perm_rows"],
        },
        "thesis": [
            "The 100M seq2seq system should be trained as a full software-maintenance prediction stack, not merely a bounded-choice classifier.",
            "Long-context traces are most valuable as a data refinery that produces compressed prediction targets from large repo/session state.",
            "The bounded-choice frontier remains a measurement head and regression gate, but the scale program must expand into multi-target seq2seq supervision.",
        ],
        "scale_targets": {
            "root_targets": {
                "python": {"min": 2000, "max": 5000},
                "rust": {"min": 1000, "max": 3000},
                "c_cpp": {"min": 1000, "max": 3000},
                "web_js_ts_html": {"min": 1000, "max": 3000},
            },
            "row_targets": {
                "estimated_compact_rows_total": {"min": 50000, "max": 70000},
                "per_root_views": [
                    "symptom_localization",
                    "evidence_citation",
                    "verifier_outcome",
                    "patch_impact",
                    "minimal_fix_selection",
                    "abstention_insufficient_evidence",
                ],
            },
        },
        "three_tier_curriculum": {
            "tier_1_bounded_decisions": [
                "opaque labels",
                "candidate path selection",
                "selected test path selection",
                "evidence key selection",
                "abstention/honesty decisions",
            ],
            "tier_2_short_structured_outputs": [
                "JSON action plans",
                "selected files/tests/evidence spans",
                "repair intent strings",
                "verifier-conditioned structured outputs",
            ],
            "tier_3_constrained_generation": [
                "one-line rationale templates",
                "small patch sketches",
                "diff hunk selection",
                "next-action prediction",
                "verifier-conditioned patch text",
            ],
        },
        "long_context_refinery": {
            "role": "Use 5M+ token traces to generate compressed prediction targets rather than feeding the full trace directly to the 100M model.",
            "derived_targets": [
                "context_pack -> next useful action",
                "context_pack -> evidence chain",
                "context_pack -> failing or most relevant test",
                "context_pack -> repair intent",
                "partial trajectory -> next command or edit",
                "full trace -> bounded decision views",
                "noisy context -> corrected maintainer summary",
            ],
            "hard_negative_generation": [
                "nearby plausible wrong files",
                "same-family wrong tests",
                "same-looking evidence keys",
                "verifier/test constraint distractors",
                "candidate-change-surface temptations",
            ],
        },
        "promotion_contract": {
            "regression_gate": frontier_request["scoring_contract"]["regression_gate"],
            "fresh_frontier_metrics": frontier_request["scoring_contract"]["promotion_metrics"],
            "required_wins": [
                "100M beats Gemma on source-grounded fresh heldout rows overall",
                "100M wins in most key language slices, especially python/rust/c_cpp/web_js_ts_html",
                "accuracy, abstention precision, and verifier-outcome accuracy are all reported",
                "latency and cost are reported alongside accuracy",
            ],
            "anti_cheat_requirements": [
                "root and repo disjoint splits",
                "time/source-heldout where available",
                "prompt_target_leak false",
                "candidate permutation coverage",
                "same-manifest 100M vs Gemma comparisons",
            ],
        },
        "next_program_stages": [
            "stage10510_long_context_refinery_inventory",
            "stage10511_multitarget_seq2seq_corpus_schema",
            "stage10512_python_verifier_bvc_frontier_materializer",
            "stage10513_rust_citation_ef_frontier_materializer",
            "stage10514_multilingual_maintainer_frontier_v1_package",
        ],
    }

    (ARTIFACT_DIR / "maintainer_scale_program.json").write_text(
        json.dumps(program, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
