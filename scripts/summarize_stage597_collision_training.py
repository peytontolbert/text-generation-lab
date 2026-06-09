#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
CANDIDATE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage597_stage525_collision_conditioned_lr1e5_steps300"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def compact(result: dict[str, Any]) -> dict[str, Any]:
    stats = result.get("structured_key_hard_filter_stats", {})
    out = {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
    }
    if stats:
        out["hard_filter_stats"] = stats
    return out


def build_summary() -> dict[str, Any]:
    base_no = load(BASE / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    base_hard = load(BASE / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(CANDIDATE / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    cand_hard = load(CANDIDATE / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CANDIDATE / "agentkernel_lite_encdec_manifest.json")
    summary = {
        "artifact_kind": "stage597_collision_training_summary",
        "baseline": "stage525_on_stage596_collision_probe",
        "candidate": "stage597_stage525_collision_conditioned_lr1e5_steps300",
        "bundle_dir": str(CANDIDATE.relative_to(ROOT)),
        "checkpoint": str((CANDIDATE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 300,
            "cumulative_steps": 2700,
            "learning_rate": 1e-5,
            "retrieval_operation_gated_contrastive": True,
            "eval_loss_step_300": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
            "parameter_count": manifest["parameter_count"],
        },
        "baseline_no_filter": compact(base_no),
        "candidate_no_filter": compact(cand_no),
        "baseline_hard_filter": compact(base_hard),
        "candidate_hard_filter": compact(cand_hard),
        "deltas": {
            "no_filter_exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "no_filter_answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "no_filter_mrr": cand_no["mean_reciprocal_rank"] - base_no["mean_reciprocal_rank"],
            "no_filter_exact_bits_per_param": bits_per_param(cand_no, "exact") - bits_per_param(base_no, "exact"),
            "no_filter_answer_bits_per_param": bits_per_param(cand_no, "answer") - bits_per_param(base_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
            "hard_filter_neural_top1_masked": cand_hard["structured_key_hard_filter_stats"]["neural_top1_masked_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["neural_top1_masked_by_hard_filter"],
        },
        "decision": "accepted_as_collision_probe_micro_gain",
        "finding": (
            "A 300-step 16k continuation on the collision-conditioned dataset produces a small genuine neural gain on the "
            "harder no-filter strict eval and reduces the number of deterministic hard-filter corrections needed. The gain is "
            "not enough to solve collision-conditioned KBPP, but it confirms Stage596 is a useful non-saturated training surface."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    base_no = summary["baseline_no_filter"]
    cand_no = summary["candidate_no_filter"]
    base_hard = summary["baseline_hard_filter"]["hard_filter_stats"]
    cand_hard = summary["candidate_hard_filter"]["hard_filter_stats"]
    doc = f"""# Stage597 Collision Training

Artifact: `runs/local/artifacts/stage597_collision_training_summary.json`

## Result

Stage597 continued Stage525 for `300` steps on the Stage596 collision-conditioned dataset.

No-filter strict full-corpus operation-gated exact/answer moved from `{base_no['exact_top1']}` / `{base_no['answer_top1']}` to `{cand_no['exact_top1']}` / `{cand_no['answer_top1']}`.

Hard-filter exact/answer stayed at `{summary['candidate_hard_filter']['exact_top1']}` / `{summary['candidate_hard_filter']['answer_top1']}`, but required fewer corrections: `{base_hard['top1_corrected_by_hard_filter']}` -> `{cand_hard['top1_corrected_by_hard_filter']}`.

## Decision

`accepted_as_collision_probe_micro_gain`

## Finding

{summary['finding']}
"""
    (ROOT / "docs/stage597_collision_training.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage597_collision_training_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
