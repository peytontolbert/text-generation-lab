#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs" / "summaries" / "stage8646_structured_telemetry_contract.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8646_structured_telemetry_contract"
TRAINER = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8630_intent_to_build_neutral_manifest" / "intent_to_build_neutral_manifest.jsonl"
TOKENIZER_POINTER = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
REQUIRED_STRUCTURED_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pointer = json.loads(TOKENIZER_POINTER.read_text(encoding="utf-8"))
    trainer_src = TRAINER.read_text(encoding="utf-8")
    loop_src = (ROOT / "legacy_src" / "agentkernel_lite" / "training_loop.py").read_text(encoding="utf-8")
    contract_out = OUT_DIR / "contract_only_probe"
    cmd = [
        sys.executable, str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST),
        "--mode", "structured_policy_probe",
        "--max-train-rows", "400",
        "--max-eval-rows", "200",
        "--max-strict-rows", "200",
        "--max-steps", "8",
        "--max-decoder-tokens", "64",
        "--decoder-ce-weight", "0.0",
        "--structured-aux-weight", "1.0",
        "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save", "1",
        "--output-dir", str(contract_out),
        "--run-id", "stage8646_structured_telemetry_contract",
        "--implementation", "transformer",
        "--tokenizer-json", pointer["primary_recovered_paths"]["tokenizer_json"],
        "--tokenizer-config", pointer["primary_recovered_paths"]["tokenizer_config"],
        "--contract-only",
    ]
    res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    errors = []
    if res.returncode != 0:
        errors.append("structured contract-only invocation failed: " + res.stderr[-1000:])
    missing = [name for name in REQUIRED_STRUCTURED_ARTIFACTS if not (contract_out / name).exists()]
    if missing:
        errors.append(f"missing structured telemetry artifacts: {missing}")
    gates = {
        "required_structured_artifacts_declared": "REQUIRED_STRUCTURED_ARTIFACTS" in trainer_src,
        "row_field_logits_written": "row_field_logits.jsonl" in loop_src,
        "row_field_losses_written": "row_field_losses.jsonl" in loop_src,
        "field_label_vocabs_written": "field_label_vocabs.json" in loop_src,
        "structured_confusion_matrix_written": "structured_confusion_matrix.json" in loop_src,
        "contract_only_emits_all_required_artifacts": not missing and res.returncode == 0,
        "no_model_execution": True,
    }
    for key, value in gates.items():
        if not value:
            errors.append(f"gate failed: {key}")
    card = {
        "stage": 8646,
        "stage_name": "stage8646_structured_telemetry_contract",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "gates": gates,
        "errors": errors,
        "required_structured_artifacts": REQUIRED_STRUCTURED_ARTIFACTS,
        "contract_only_output": str(contract_out.relative_to(ROOT)),
        "next_best_step": "Recover denoise/repair objective contract and add target-config compatibility audit before any data recovery or mining.",
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "structured_telemetry_contract_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
