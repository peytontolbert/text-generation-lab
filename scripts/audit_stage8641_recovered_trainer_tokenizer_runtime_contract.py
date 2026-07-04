#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs" / "summaries" / "stage8641_recovered_trainer_tokenizer_runtime_contract.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8641_recovered_trainer_tokenizer_runtime_contract"
TRAINER = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8592_reconstructed_bounded_decoder_ce_loss_mask" / "rows.jsonl"
TOKENIZER_POINTER = ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json"
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


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    pointer = json.loads(TOKENIZER_POINTER.read_text(encoding="utf-8"))
    help_res = run([sys.executable, str(TRAINER), "--help"])
    help_text = help_res.stdout + help_res.stderr
    trainer_src = TRAINER.read_text(encoding="utf-8")
    loop_src = (ROOT / "legacy_src" / "agentkernel_lite" / "training_loop.py").read_text(encoding="utf-8")
    data_src = (ROOT / "legacy_src" / "agentkernel_lite" / "training_data.py").read_text(encoding="utf-8")

    required_flags = [
        "--implementation",
        "--tokenizer-json",
        "--tokenizer-config",
        "--execution-authorized-for-recovery-probe",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
    ]
    missing_flags = [flag for flag in required_flags if flag not in help_text]
    gates: dict[str, bool] = {
        "trainer_help_ok": help_res.returncode == 0,
        "required_flags_present": not missing_flags,
        "trainer_static_passes_implementation": "implementation=args.implementation" in trainer_src,
        "trainer_static_passes_tokenizer": "tokenizer_json=args.tokenizer_json" in trainer_src and "tokenizer_config=args.tokenizer_config" in trainer_src,
        "loop_static_has_tiny_transformer_path": "tiny_transformer_runtime_path" in loop_src and "AgentKernelLiteTransformerSeq2Seq" in loop_src,
        "loop_static_uses_selected_tokenizer": "load_tokenizer" in loop_src and "vocab_size=tokenizer.vocab_size" in loop_src,
        "batcher_static_has_bpe_wrapper": "class AgentKernelBPETokenizer" in data_src and "Tokenizer.from_file" in data_src,
        "tokenizer_pointer_exists": TOKENIZER_POINTER.is_file(),
        "tokenizer_artifacts_exist": Path(pointer["primary_recovered_paths"]["tokenizer_json"]).is_file() and Path(pointer["primary_recovered_paths"]["tokenizer_config"]).is_file(),
        "tokenizer_pointer_vocab_matches_target": pointer.get("vocab_size") == 1506,
    }
    if missing_flags:
        errors.append(f"missing trainer flags: {missing_flags}")

    contract_out = OUT_DIR / "contract_only_probe"
    cmd = [
        sys.executable,
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "bounded_decoder_ce_probe",
        "--max-train-rows",
        "32",
        "--max-eval-rows",
        "16",
        "--max-strict-rows",
        "16",
        "--max-steps",
        "16",
        "--max-decoder-tokens",
        "768",
        "--decoder-ce-weight",
        "1.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(contract_out),
        "--run-id",
        "stage8641_contract_only",
        "--implementation",
        "transformer",
        "--tokenizer-json",
        pointer["primary_recovered_paths"]["tokenizer_json"],
        "--tokenizer-config",
        pointer["primary_recovered_paths"]["tokenizer_config"],
        "--contract-only",
    ]
    contract_res = run(cmd)
    contract_card: dict[str, Any] = {}
    if contract_res.returncode == 0:
        contract_card = json.loads(contract_res.stdout)
    else:
        errors.append("contract-only trainer invocation failed: " + contract_res.stderr[-800:])
    gates["contract_only_trainer_accepts_transformer_bpe"] = contract_res.returncode == 0 and bool(contract_card.get("passed"))
    gates["contract_only_no_execution"] = contract_card.get("model_execution_attempted") is False
    gates["contract_records_transformer"] = contract_card.get("implementation") == "transformer"
    gates["contract_records_bpe_tokenizer"] = contract_card.get("tokenizer_contract", {}).get("byte_fallback_used_when_unset") is False

    for key, value in gates.items():
        if not value:
            errors.append(f"gate failed: {key}")

    card = {
        "stage": 8641,
        "stage_name": "stage8641_recovered_trainer_tokenizer_runtime_contract",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "gates": gates,
        "errors": errors,
        "missing_flags": missing_flags,
        "tokenizer_pointer": str(TOKENIZER_POINTER.relative_to(ROOT)),
        "contract_only_output": str(contract_out.relative_to(ROOT)),
        "next_best_step": "Implement structured probe runtime loops and stronger telemetry/hash enforcement before data recovery or mining.",
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "runtime_contract_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
