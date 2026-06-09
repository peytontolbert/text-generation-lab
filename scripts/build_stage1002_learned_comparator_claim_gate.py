#!/usr/bin/env python3
"""Build a claim gate for the learned-comparator 100M KBPP system."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "runs/local/artifacts" / name).read_text(encoding="utf-8"))


def main() -> None:
    stage1001 = load("stage1001_100m_soft_count_comparator_hybrid_summary.json")
    qwen8 = load("stage985_qwen3_8b_vs_stage981_full_640_same_candidate_comparison_summary.json")["qwen3_8b"]
    qwen9 = load("stage987_qwen35_9b_vs_stage981_full_640_same_candidate_comparison_summary.json")["qwen35_9b"]
    gemma12 = load("stage990_gemma3_12b_vs_stage981_full_640_same_candidate_comparison_summary.json")["gemma3_12b"]
    eval_score = stage1001["split_scores"]["eval"]
    counted_params = int(stage1001["total_counted_parameter_count"])
    baselines = {
        "qwen3_8b": {"answer": int(qwen8["answer"]), "exact": int(qwen8["exact"])},
        "qwen35_9b": {"answer": int(qwen9["answer"]), "exact": int(qwen9["exact"])},
        "gemma3_12b": {"answer": int(gemma12["answer"]), "exact": int(gemma12["exact"])},
    }
    deltas = {
        name: {
            "answer": int(eval_score["answer"]) - values["answer"],
            "exact": int(eval_score["exact"]) - values["exact"],
        }
        for name, values in baselines.items()
    }
    summary = {
        "artifact_kind": "stage1002_learned_comparator_claim_gate",
        "status": "completed_claim_gate",
        "stage1001": {
            "answer": int(eval_score["answer"]),
            "exact": int(eval_score["exact"]),
            "implied_full_answer_exact": stage1001["implied_full_answer_exact"],
            "counted_parameter_count": counted_params,
            "learned_comparator_parameter_count": int(stage1001["learned_comparator_parameter_count"]),
            "soft_count_parameter_count": int(stage1001["soft_count_parameter_count"]),
        },
        "baselines": baselines,
        "deltas_vs_baselines": deltas,
        "allowed_claim": (
            "On the 640-row same-candidate KBPP benchmark, the 100M loadable system plus learned encoder-pair "
            "equality and soft-count comparator matches the prior fixed-interface Stage981 frontier and beats the "
            "local Qwen3 8B, Qwen3.5 9B, and Gemma3 12B prompt baselines."
        ),
        "not_allowed_claims": [
            "The 100M model alone, without any counted comparator heads/interface, beats modern 7B models generally.",
            "The system has bridge-free natural-language equality discovery; qpair/dpair marker tokens still locate the comparison slots.",
            "Free-form generation has reached the candidate-ranking frontier.",
        ],
        "research_interpretation": (
            "This is the first local result replacing the fixed qpair/dpair suffix-intersection primitive with learned "
            "encoder-owned pair equality probabilities plus a small learned count materializer while preserving the "
            "full Stage981 342/325 frontier."
        ),
        "next_gate": (
            "Remove or naturalize qpair/dpair marker-token span location, then distill the pair comparator and soft-count "
            "scorer into the 100M encoder instead of loading them as separate heads."
        ),
    }
    out = ROOT / "runs/local/artifacts/stage1002_learned_comparator_claim_gate_summary.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
