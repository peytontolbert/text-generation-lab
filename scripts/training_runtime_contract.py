from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

TRAINING_RUNTIME_COMPONENTS = {
    "tokenizer": {
        "kind": "byte",
        "contract": "encode/decode UTF-8 bytes; preserve budget accounting; no learned tokenizer required",
    },
    "manifest_dataset": {
        "contract": "load JSONL rows, split by train/eval/strict_eval, enforce row caps before batching",
    },
    "loss_mask_enforcer": {
        "contract": "compute only row-authorized losses; forbidden losses must be exactly zero contribution",
    },
    "bounded_decoder_batcher": {
        "contract": "batch input_state/target_ref rows; never copy raw target text into encoder input",
    },
    "model_forward": {
        "contract": "100M seq2seq forward over encoder packet and bounded decoder targets",
        "status": "not_reimplemented",
    },
    "optimizer_step": {
        "contract": "zero_grad -> backward -> clip/log grad norms -> step; disabled until execution authorization",
        "status": "not_reimplemented",
    },
    "telemetry_writer": {
        "contract": "write loss, eval, token, gate, sample, delta, cleanup artifacts every probe",
    },
    "checkpoint_policy": {
        "contract": "no final checkpoint export; temporary checkpoints only under marked output_dir/checkpoints",
    },
}

REQUIRED_TELEMETRY = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]

MODULE_DELTA_EXPECTATIONS = {
    "structured_probe": {
        "decoder_delta": "near_zero_unless_decoder_loss_enabled",
        "structured_heads_delta": "nonzero_when_structured_losses_enabled",
        "encoder_delta": "bounded",
    },
    "bounded_decoder_ce_probe": {
        "decoder_delta": "nonzero_allowed",
        "structured_heads_delta": "near_zero",
        "runtime_or_export_delta": "not_applicable",
    },
    "denoise_repair_probe": {
        "decoder_delta": "nonzero_allowed_for_repair_surface",
        "structured_heads_delta": "near_zero_unless_aux_enabled",
    },
}


def build_contract(plan: dict[str, Any]) -> dict[str, Any]:
    mode = str(plan.get("mode", "unknown"))
    return {
        "contract_name": "agentkernel_100m_training_runtime_contract_v1",
        "plan_name": plan.get("plan_name"),
        "mode": mode,
        "components": TRAINING_RUNTIME_COMPONENTS,
        "required_telemetry": REQUIRED_TELEMETRY,
        "module_delta_expectations": MODULE_DELTA_EXPECTATIONS.get(mode, MODULE_DELTA_EXPECTATIONS["bounded_decoder_ce_probe"]),
        "execution_implementation_status": {
            "dataset_loader_contract": "specified",
            "loss_mask_enforcer_contract": "specified",
            "telemetry_writer_contract": "specified",
            "model_forward": "not_restored",
            "optimizer_step": "not_restored",
            "checkpoint_export": "forbidden",
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "rebuild telemetry writer and tiny model forward/backward only after this contract is audited",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a non-executing training runtime contract from a training plan.")
    parser.add_argument("--training-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = json.loads(args.training_plan.read_text(encoding="utf-8"))
    contract = build_contract(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(contract, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
