#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE599 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage599_stage598_collision_weakop_replay_value_anchor_lr5e6_steps300"
STAGE600 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage600_stage599_entity_twohop_replay_value_anchor_lr5e6_steps300"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def op_delta(base: dict[str, Any], cand: dict[str, Any], op: str) -> dict[str, Any]:
    base_op = base["by_operation"][op]
    cand_op = cand["by_operation"][op]
    return {
        "baseline_exact_top1": base_op["top1_accuracy"],
        "candidate_exact_top1": cand_op["top1_accuracy"],
        "exact_top1_delta": cand_op["top1_accuracy"] - base_op["top1_accuracy"],
        "baseline_answer_top1": base_op["answer_top1_accuracy"],
        "candidate_answer_top1": cand_op["answer_top1_accuracy"],
        "answer_top1_delta": cand_op["answer_top1_accuracy"] - base_op["answer_top1_accuracy"],
        "baseline_mrr": base_op["mean_reciprocal_rank"],
        "candidate_mrr": cand_op["mean_reciprocal_rank"],
        "mrr_delta": cand_op["mean_reciprocal_rank"] - base_op["mean_reciprocal_rank"],
    }


def build_summary() -> dict[str, Any]:
    base_no = load(STAGE599 / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    base_hard = load(STAGE599 / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(STAGE600 / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    cand_hard = load(STAGE600 / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(STAGE600 / "agentkernel_lite_encdec_manifest.json")
    summary = {
        "artifact_kind": "stage600_entity_twohop_summary",
        "candidate": "stage600_stage599_entity_twohop_replay_value_anchor_lr5e6_steps300",
        "bundle_dir": str(STAGE600.relative_to(ROOT)),
        "checkpoint": str((STAGE600 / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage600_entity_twohop_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "eval_manifest": "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "training": {
            "init_from": str((STAGE599 / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 300,
            "cumulative_steps": 3600,
            "learning_rate": 5e-6,
            "retrieval_value_anchor_weight": 0.1,
            "retrieval_value_anchor_operation_ids": [5, 10],
            "eval_loss_step_300": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage599": {
            "exact_top1": base_no["top1_accuracy"],
            "answer_top1": base_no["answer_top1_accuracy"],
            "exact_bits_per_param": bits_per_param(base_no, "exact"),
            "answer_bits_per_param": bits_per_param(base_no, "answer"),
            "hard_filter_corrections": base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "candidate_stage600": {
            "exact_top1": cand_no["top1_accuracy"],
            "answer_top1": cand_no["answer_top1_accuracy"],
            "exact_bits_per_param": bits_per_param(cand_no, "exact"),
            "answer_bits_per_param": bits_per_param(cand_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "deltas_vs_stage599": {
            "exact_top1": cand_no["top1_accuracy"] - base_no["top1_accuracy"],
            "answer_top1": cand_no["answer_top1_accuracy"] - base_no["answer_top1_accuracy"],
            "exact_bits_per_param": bits_per_param(cand_no, "exact") - bits_per_param(base_no, "exact"),
            "answer_bits_per_param": bits_per_param(cand_no, "answer") - bits_per_param(base_no, "answer"),
            "hard_filter_corrections": cand_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"]
            - base_hard["structured_key_hard_filter_stats"]["top1_corrected_by_hard_filter"],
        },
        "target_operation_deltas": {
            "entity_context": op_delta(base_no, cand_no, "entity_context"),
            "two_hop_owner_region": op_delta(base_no, cand_no, "two_hop_owner_region"),
        },
        "decision": "rejected_as_new_collision_frontier_but_twohop_positive",
        "finding": (
            "Entity/two-hop replay with stronger value anchoring is mixed. It improves two-hop collision resolution materially, "
            "but global exact drops slightly, hard-filter corrections rise by one, and entity_context regresses. This suggests "
            "two-hop benefits from more exposure, while entity_context needs a schema redesign rather than heavier replay."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage599"]
    cand = summary["candidate_stage600"]
    entity = summary["target_operation_deltas"]["entity_context"]
    twohop = summary["target_operation_deltas"]["two_hop_owner_region"]
    doc = f"""# Stage600 Entity/Two-Hop Replay

Artifact: `runs/local/artifacts/stage600_entity_twohop_summary.json`

## Result

Stage600 continued Stage599 for `300` steps on heavy `entity_context`/`two_hop_owner_region` replay with value-anchor weight `0.1`.

Global no-filter exact/answer moved from `{base['exact_top1']}` / `{base['answer_top1']}` to `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Hard-filter corrections moved from `{base['hard_filter_corrections']}` to `{cand['hard_filter_corrections']}`.

## Target Ops

- `entity_context`: exact/answer `{entity['candidate_exact_top1']}` / `{entity['candidate_answer_top1']}`; exact delta `{entity['exact_top1_delta']}`
- `two_hop_owner_region`: exact/answer `{twohop['candidate_exact_top1']}` / `{twohop['candidate_answer_top1']}`; exact delta `{twohop['exact_top1_delta']}`

## Decision

`rejected_as_new_collision_frontier_but_twohop_positive`

## Finding

{summary['finding']}
"""
    (ROOT / "docs/stage600_entity_twohop.md").write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage600_entity_twohop_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
