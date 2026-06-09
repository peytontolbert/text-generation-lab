#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage599_stage598_collision_weakop_replay_value_anchor_lr5e6_steps300"
CAND = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage601_stage599_entity_field_context_lr5e6_steps300"
OUT = ROOT / "runs/local/artifacts/stage601_entity_field_context_summary.json"
DOC = ROOT / "docs/stage601_entity_field_context.md"


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


def compact(result: dict[str, Any], hard: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "exact_top1": result["top1_accuracy"],
        "answer_top1": result["answer_top1_accuracy"],
        "mrr": result["mean_reciprocal_rank"],
        "exact_bits_per_param": bits_per_param(result, "exact"),
        "answer_bits_per_param": bits_per_param(result, "answer"),
    }
    if hard is not None:
        stats = hard["structured_key_hard_filter_stats"]
        out["hard_filter_exact_top1"] = hard["top1_accuracy"]
        out["hard_filter_answer_top1"] = hard["answer_top1_accuracy"]
        out["hard_filter_corrections"] = stats["top1_corrected_by_hard_filter"]
        out["hard_filter_damage"] = stats["top1_damaged_by_hard_filter"]
        out["multi_candidate_queries"] = stats["queries_with_multiple_exact_key_candidates"]
    return out


def build_summary() -> dict[str, Any]:
    base_no = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated.json")
    base_hard = load(BASE / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_structured_hard_filter.json")
    cand_no = load(CAND / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated.json")
    cand_hard = load(CAND / "retrieval_eval_stage601_entity_field_context_full_corpus_operation_gated_structured_hard_filter.json")
    manifest = load(CAND / "agentkernel_lite_encdec_manifest.json")
    dataset = load(ROOT / "runs/local/artifacts/stage601_entity_field_context_dataset.json")
    return {
        "artifact_kind": "stage601_entity_field_context_summary",
        "candidate": "stage601_stage599_entity_field_context_lr5e6_steps300",
        "bundle_dir": str(CAND.relative_to(ROOT)),
        "checkpoint": str((CAND / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "dataset_manifest": "runs/local/tmp/pocketpal_stage601_entity_field_context_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "dataset_analysis": dataset["analysis"],
        "training": {
            "init_from": str((BASE / "checkpoints/step_00000300.pt").relative_to(ROOT)),
            "steps": 300,
            "cumulative_steps": 3600,
            "learning_rate": 5e-6,
            "retrieval_value_anchor_weight": 0.05,
            "retrieval_value_anchor_operation_ids": [10],
            "eval_loss_step_300": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
        },
        "baseline_stage599": compact(base_no, base_hard),
        "candidate_stage601": compact(cand_no, cand_hard),
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
            "direct_fact": op_delta(base_no, cand_no, "direct_fact"),
            "rule_case_intersection_count": op_delta(base_no, cand_no, "rule_case_intersection_count"),
            "set_intersection_member": op_delta(base_no, cand_no, "set_intersection_member"),
        },
        "decision": "accepted_as_entity_schema_probe_not_global_collision_frontier",
        "finding": (
            "Field-level entity context is a better schema than whole-entity context for collision learning: Stage599 already "
            "improves from the old whole-card entity-context exact score, and Stage601 adds another small no-filter gain on "
            "entity_context while reducing hard-filter corrections. It is not a new global collision frontier because some "
            "non-target operation margins regress. The next route should keep field-level entity cards but mix Stage596 replay "
            "or lower the entity-only anchor to avoid direct_fact/set tradeoffs."
        ),
    }


def write_doc(summary: dict[str, Any]) -> None:
    base = summary["baseline_stage599"]
    cand = summary["candidate_stage601"]
    entity = summary["target_operation_deltas"]["entity_context"]
    doc = f"""# Stage601 Entity Field Context

Artifact: `runs/local/artifacts/stage601_entity_field_context_summary.json`

## Result

Stage601 converted `entity_context` into field-level answer cards and continued Stage599 for `300` steps with value-anchor weight `0.05` on op ID `10`.

No-filter exact/answer moved from `{base['exact_top1']}` / `{base['answer_top1']}` to `{cand['exact_top1']}` / `{cand['answer_top1']}`.

Entity-context field exact/answer moved from `{entity['baseline_exact_top1']}` / `{entity['baseline_answer_top1']}` to `{entity['candidate_exact_top1']}` / `{entity['candidate_answer_top1']}`.

Hard-filter exact/answer stayed `{cand['hard_filter_exact_top1']}` / `{cand['hard_filter_answer_top1']}`, while corrections moved from `{base['hard_filter_corrections']}` to `{cand['hard_filter_corrections']}`.

## Decision

`accepted_as_entity_schema_probe_not_global_collision_frontier`

## Finding

{summary['finding']}
"""
    DOC.write_text(doc, encoding="utf-8")


def main() -> None:
    summary = build_summary()
    OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
