from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10506_fresh_python_rust_frontier_request"

SCALING_QUEUE = ROOT / "runs/local/artifacts/stage10505_multilingual_residual_root_scaling_queue/multilingual_residual_root_scaling_queue.json"
SCALING_TARGETS = ROOT / "runs/local/artifacts/stage10505_multilingual_residual_root_scaling_queue/multilingual_residual_root_scaling_targets.jsonl"
V27_PACKAGE = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
PROMOTION_GATE = ROOT / "runs/local/artifacts/stage10461_reviewed_v27_residual_promotion_gate/reviewed_v27_residual_promotion_gate.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    scaling_queue = load_json(SCALING_QUEUE)
    scaling_targets = load_jsonl(SCALING_TARGETS)
    v27_package = load_json(V27_PACKAGE)
    promotion_gate = load_json(PROMOTION_GATE)

    python_targets = [row for row in scaling_targets if row["language_family"] == "python"]
    rust_targets = [row for row in scaling_targets if row["language_family"] == "rust"]

    frontier_request = {
        "stage": 10506,
        "stage_name": "stage10506_fresh_python_rust_frontier_request",
        "goal_shift": [
            "Treat the repaired 24-row v2.7 strict overlay as a regression gate, not the main optimization target.",
            "Build broader fresh heldout frontiers where the 100M model can beat Gemma on unseen maintainer-bundle decisions.",
            "Use the current Python and Rust residuals as canaries for dataset quality, not as the main headline objective.",
        ],
        "current_context": {
            "v27_strict_eval_rows": v27_package["metrics"]["strict_eval_rows"],
            "v27_root_records": v27_package["metrics"]["root_records"],
            "live_repaired_overlay_accuracy": scaling_queue["current_frontier_status"]["strict_accuracy"],
            "promotion_gate_passed": promotion_gate["passed"],
        },
        "frontiers": {
            "python_verifier_bvc_frontier_v1": {
                "row_budget": {"min": 100, "max": 200},
                "split_percentages": {
                    "train_support": [0.60, 0.70],
                    "validation": [0.15, 0.20],
                    "strict_heldout": [0.15, 0.20],
                },
                "core_failure_mode": "B-vs-C selected-test confusion where candidate-change context tempts one test but the true verifier/test constraint supports another",
                "required_row_shape": [
                    "verifier_outcome perspective only",
                    "3 or more plausible test-file options",
                    "same repo family and same naming-style hard negatives",
                    "selected-test anchor present but not exposed verbatim before options",
                    "no single-option or degenerate verifier rows",
                    "close sibling wrong target remains tempting after leak cleanup",
                ],
                "anti_cheat_gates": [
                    "no literal gold test path in header or visible evidence before options",
                    "prompt_target_leak false",
                    "candidate order permutation coverage",
                    "same-root train/eval separation",
                    "same repo-family hard negatives in heldout",
                ],
                "seed_supply": [
                    row["bundle_id"] for row in python_targets if row["status"] == "execution_ready_promotable_support"
                ],
                "blocked_supply": [
                    {
                        "bundle_id": row["bundle_id"],
                        "status": row["status"],
                        "blockers": row["blockers"],
                    }
                    for row in python_targets
                    if row["status"] != "execution_ready_promotable_support"
                ],
            },
            "rust_citation_ef_frontier_v1": {
                "row_budget": {"min": 50, "max": 100},
                "split_percentages": {
                    "train_support": [0.60, 0.70],
                    "validation": [0.15, 0.20],
                    "strict_heldout": [0.15, 0.20],
                },
                "core_failure_mode": "symptom_or_call_path_analogue should beat verifier_and_test_constraint while candidate_change_surface remains a tempting wrong evidence choice",
                "required_row_shape": [
                    "evidence_citation perspective only",
                    "both symptom_or_call_path_analogue and verifier_and_test_constraint visible as options",
                    "candidate_change_surface remains a tempting negative",
                    "non-tokenizers repo family required",
                    "selected-test, trace, or verifier anchor attached whenever recoverable",
                    "no visible evidence key may state the gold answer verbatim",
                ],
                "anti_cheat_gates": [
                    "no candidate_change_surface string leak as the gold answer",
                    "prompt_target_leak false",
                    "same-root train/eval separation",
                    "non-tokenizers strict heldout rows",
                    "option-semantic balance across repos",
                ],
                "seed_supply": [
                    row["bundle_id"] for row in rust_targets if row["status"] == "builder_target_not_yet_materialized"
                ],
                "diagnostic_support_only": [
                    {
                        "bundle_id": row["bundle_id"],
                        "status": row["status"],
                        "blockers": row["blockers"],
                    }
                    for row in rust_targets
                    if row["status"] != "builder_target_not_yet_materialized"
                ],
            },
        },
        "scoring_contract": {
            "regression_gate": [
                "no regression on repaired 24-row v2.7 strict overlay",
                "overlay prompt_target_leak remains false",
            ],
            "promotion_metrics": [
                "fresh_python_verifier_heldout_acc",
                "fresh_rust_citation_heldout_acc",
                "combined_fresh_frontier_acc",
                "gemma_same_rows_accuracy",
                "heldout_margin_distribution",
            ],
            "promotion_requirements": [
                "strict overlay remains at least 22/24",
                "fresh heldout improves over prior fresh-frontier baseline",
                "100M beats Gemma on the exact same fresh heldout rows",
                "leak audit clean on all promoted heldout rows",
            ],
        },
        "freeform_decoder_boundary": [
            "Keep freeform decoding as a separate curriculum.",
            "Prioritize bounded choice first, then canonical spans, then short rationale templates, then edit intents.",
            "Do not use freeform patch generation as the primary path for proving maintainer-grade capability at 100M yet.",
        ],
        "recommended_next_stages": [
            "stage10507_python_verifier_bvc_frontier_builder",
            "stage10508_rust_citation_ef_frontier_builder",
            "stage10509_fresh_frontier_same_rows_gemma_comparison_request",
        ],
    }

    (ARTIFACT_DIR / "fresh_python_rust_frontier_request.json").write_text(
        json.dumps(frontier_request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
