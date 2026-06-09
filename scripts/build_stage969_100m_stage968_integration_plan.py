#!/usr/bin/env python3
"""Build the 100M integration plan for the Stage968 KBPP interface."""

from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def exists(path: str) -> bool:
    return Path(path).exists()


def main() -> None:
    stage968 = json.loads((ROOT / "runs/local/artifacts/stage968_loadable_pair_router_summary.json").read_text())
    candidate_bases = [
        {
            "name": "v430_best_balanced_access_branch",
            "checkpoint": "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_v430_answer_card_retrieval_heads_only_from_v424/model/model.safetensors",
            "reason": "Best old balanced semantic-access branch; retrieval-only params changed and app behavior preserved.",
        },
        {
            "name": "v424_best_general_controller_branch",
            "checkpoint": "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_v424_fixed_stream_from_v423/model/model.safetensors",
            "reason": "Best old general controller branch before retrieval-side experiments.",
        },
        {
            "name": "v429_encoder_access_branch",
            "checkpoint": "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_v429_answer_card_retrieval_from_v424/model/model.safetensors",
            "reason": "Higher old answer-card top1 than v430, but perturbs shared encoder and slightly regresses NLL.",
        },
        {
            "name": "v415_structured_json_head_from_v410_fallback",
            "checkpoint": "/data/agent_kernel_lite/artifacts/pocketpal_controller_100m_v415_structured_json_head_from_v410/model/model.safetensors",
            "reason": "Newest discovered fallback checkpoint in /data/agent_kernel_lite/artifacts. Older than v424/v430, but present and can unblock a conservative Stage968 smoke.",
        },
        {
            "name": "v410_decoder_lastblock_drift_align_fallback",
            "checkpoint": "/data/agent_kernel_lite/artifacts/pocketpal_controller_100m_v410_decoder_lastblock_drift_align_from_v409/model/model.safetensors",
            "reason": "Known historical base for later branches. Older and weaker than v424/v430, but present if v415 is unsuitable.",
        },
    ]
    for base in candidate_bases:
        base["checkpoint_exists"] = exists(base["checkpoint"])

    selected = next((base for base in candidate_bases if base["checkpoint_exists"]), None)
    train_manifest = str((ROOT / "runs/local/tmp/stage960_relation_qslot_hardened_surface/agentkernel_lite_encdec_dataset_manifest.json").resolve())
    stage968_scorer = str((ROOT / "scripts/score_stage968_loadable_pair_router.py").resolve())
    first_smoke_command = None
    if selected:
        first_smoke_command = [
            "/home/peyton/miniconda3/envs/ai/bin/python",
            "legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--dataset-manifest",
            train_manifest,
            "--output-dir",
            "runs/local/artifacts/pocketpal_controller_100m_stage969_stage968_kbpp_smoke",
            "--preset",
            "agentkernel-lite-100m",
            "--init-from-checkpoint",
            selected["checkpoint"],
            "--retrieval-head-dim",
            "128",
            "--freeze-decoder",
            "1",
            "--freeze-token-embeddings",
            "1",
            "--trainable-name-include",
            "retrieval|encoder.5|encoder_norm|enc_norm",
            "--max-steps",
            "20",
            "--batch-size",
            "2",
            "--eval-every",
            "10",
            "--max-eval-batches",
            "8",
            "--learning-rate",
            "5e-6",
            "--dry-run",
            "0",
            "--export-browser-bitnet",
            "0",
        ]

    if selected is None:
        decision = (
            "Do not start the new 100M KBPP run until a base 100M checkpoint is present. "
            "Stage968 is ready as the scorer/interface gate; the current workspace is missing "
            "the expected v424/v429/v430 model.safetensors files."
        )
        next_best_steps = [
            "Locate or restore the v430 or v424 100M model.safetensors checkpoint.",
            "Run Stage968 scorer as a preflight gate on Stage960 targets.",
            "Launch a 20-step frozen-decoder 100M smoke only after the base checkpoint exists.",
            "Evaluate with Stage968 plus existing app/NLL gates before any longer 100M run.",
        ]
    else:
        decision = (
            "The expected v424/v429/v430 checkpoints are still absent, but a fallback 100M "
            "checkpoint is present. Stage968 is ready as the scorer/interface gate, and a "
            "conservative frozen-decoder 20-step smoke can start from the selected fallback base."
        )
        next_best_steps = [
            "Run Stage968 scorer as a preflight gate on Stage960 targets.",
            "Launch the 20-step frozen-decoder 100M smoke from the selected fallback base.",
            "Evaluate with Stage968 plus existing app/NLL gates before any longer 100M run.",
            "Restore v430 or v424 later if the fallback branch is unsuitable.",
        ]

    summary = {
        "artifact_kind": "stage969_100m_stage968_integration_plan",
        "status": "blocked_missing_100m_base_checkpoint" if selected is None else "ready_for_100m_smoke",
        "timestamp": int(time.time()),
        "stage968_current_result": {
            "target_answer_exact": [
                stage968["split_scores"]["eval"]["answer"],
                stage968["split_scores"]["eval"]["exact"],
            ],
            "implied_full_answer_exact": stage968["implied_full_answer_exact"],
            "router_parameter_count": stage968["router_parameter_count"],
            "scorer_summary": "runs/local/artifacts/stage968_loadable_pair_router_summary.json",
            "router_state": "runs/local/artifacts/stage966_pair_arity_router_state.pt",
        },
        "candidate_100m_bases": candidate_bases,
        "selected_base": selected,
        "train_manifest": train_manifest,
        "stage968_scorer": stage968_scorer,
        "first_smoke_command": first_smoke_command,
        "acceptance_gates": {
            "stage968_eval_reproduction_before_training": [328, 311],
            "after_100m_smoke_min_target_answer_exact": [328, 311],
            "no_decoder_regression_gate": "Run existing direct app/NLL gates if a 100M checkpoint is available; do not promote if v424/v430 app behavior regresses.",
            "strict_model_owned_gate": "If fixed primitive is disallowed, replace qpair/dpair set intersection with a learned equality/count module and require the same 328/311 target gate.",
        },
        "decision": decision,
        "next_best_steps": next_best_steps,
    }
    output = ROOT / "runs/local/artifacts/stage969_100m_stage968_integration_plan.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
