#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage525_stage502_rule_replay_lr1e4_steps300"
STAGE597 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage597_stage525_collision_conditioned_lr1e5_steps300"
STAGE598 = ROOT / "runs/local/artifacts/knowledge_compression_moe_residual_10k_stage598_stage597_collision_conditioned_lr1e5_steps300"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def bits_per_param(result: dict[str, Any], kind: str) -> float:
    density = result["verified_density"]
    return density[f"{kind}_verified_bits"] / density["parameter_count"]


def row(label: str, bundle: Path, cumulative_steps: int) -> dict[str, Any]:
    no_filter = load(bundle / "retrieval_eval_stage596_collision_full_corpus_operation_gated.json")
    hard = load(bundle / "retrieval_eval_stage596_collision_full_corpus_operation_gated_structured_hard_filter.json")
    hard_stats = hard["structured_key_hard_filter_stats"]
    return {
        "label": label,
        "bundle_dir": str(bundle.relative_to(ROOT)),
        "cumulative_steps": cumulative_steps,
        "no_filter_exact_top1": no_filter["top1_accuracy"],
        "no_filter_answer_top1": no_filter["answer_top1_accuracy"],
        "no_filter_mrr": no_filter["mean_reciprocal_rank"],
        "no_filter_exact_bits_per_param": bits_per_param(no_filter, "exact"),
        "no_filter_answer_bits_per_param": bits_per_param(no_filter, "answer"),
        "hard_filter_exact_top1": hard["top1_accuracy"],
        "hard_filter_answer_top1": hard["answer_top1_accuracy"],
        "hard_filter_corrections": hard_stats["top1_corrected_by_hard_filter"],
        "hard_filter_masked_neural_top1": hard_stats["neural_top1_masked_by_hard_filter"],
        "hard_filter_damage": hard_stats["top1_damaged_by_hard_filter"],
    }


def build_summary() -> dict[str, Any]:
    rows = [
        row("stage525_baseline_on_stage596", BASE, 2400),
        row("stage597_collision_300step", STAGE597, 2700),
        row("stage598_collision_600step", STAGE598, 3000),
    ]
    base, stage597, stage598 = rows
    manifest = load(STAGE598 / "agentkernel_lite_encdec_manifest.json")
    summary = {
        "artifact_kind": "stage598_collision_continuation_summary",
        "dataset_manifest": "runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json",
        "candidate": "stage598_stage597_collision_conditioned_lr1e5_steps300",
        "checkpoint": str((STAGE598 / "checkpoints/step_00000300.pt").relative_to(ROOT)),
        "training": {
            "stage597_steps": 300,
            "stage598_steps": 300,
            "cumulative_steps": 3000,
            "learning_rate": 1e-5,
            "eval_loss_stage597_step_300": load(STAGE597 / "agentkernel_lite_encdec_manifest.json")["training_summary"]["eval_history"][-1]["eval_loss"],
            "eval_loss_stage598_step_300": manifest["training_summary"]["eval_history"][-1]["eval_loss"],
            "parameter_count": manifest["parameter_count"],
        },
        "curve": rows,
        "stage598_vs_stage525": {
            "no_filter_exact_top1_delta": stage598["no_filter_exact_top1"] - base["no_filter_exact_top1"],
            "no_filter_answer_top1_delta": stage598["no_filter_answer_top1"] - base["no_filter_answer_top1"],
            "no_filter_exact_bits_per_param_delta": stage598["no_filter_exact_bits_per_param"] - base["no_filter_exact_bits_per_param"],
            "no_filter_answer_bits_per_param_delta": stage598["no_filter_answer_bits_per_param"] - base["no_filter_answer_bits_per_param"],
            "hard_filter_correction_delta": stage598["hard_filter_corrections"] - base["hard_filter_corrections"],
            "hard_filter_masked_neural_top1_delta": stage598["hard_filter_masked_neural_top1"] - base["hard_filter_masked_neural_top1"],
        },
        "stage598_vs_stage597": {
            "no_filter_exact_top1_delta": stage598["no_filter_exact_top1"] - stage597["no_filter_exact_top1"],
            "no_filter_answer_top1_delta": stage598["no_filter_answer_top1"] - stage597["no_filter_answer_top1"],
            "hard_filter_correction_delta": stage598["hard_filter_corrections"] - stage597["hard_filter_corrections"],
        },
        "decision": "accepted_as_collision_probe_best_so_far",
        "finding": (
            "A second 300-step continuation keeps improving the collision-conditioned no-filter score and further reduces deterministic "
            "hard-filter corrections. This confirms the Stage596 probe is measuring learnable neural collision resolution, not just "
            "lookup-key access. The gap remains large on direct_fact/entity_context/two_hop, so the next gain should target those "
            "collision families with operation-balanced replay or value-anchor supervision."
        ),
    }
    return summary


def write_doc(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage598 Collision Continuation",
        "",
        "Artifact: `runs/local/artifacts/stage598_collision_continuation_summary.json`",
        "",
        "## Result",
        "",
        "| run | steps | no-filter exact | no-filter answer | hard-filter corrections |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in summary["curve"]:
        lines.append(
            f"| `{item['label']}` | `{item['cumulative_steps']}` | `{item['no_filter_exact_top1']}` | "
            f"`{item['no_filter_answer_top1']}` | `{item['hard_filter_corrections']}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "`accepted_as_collision_probe_best_so_far`",
            "",
            "## Finding",
            "",
            summary["finding"],
            "",
        ]
    )
    (ROOT / "docs/stage598_collision_continuation.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    summary = build_summary()
    output = ROOT / "runs/local/artifacts/stage598_collision_continuation_summary.json"
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
