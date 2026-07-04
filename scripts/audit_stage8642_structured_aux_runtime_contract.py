#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "runs" / "summaries" / "stage8642_structured_aux_runtime_contract.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8642_structured_aux_runtime_contract"
TRAINER = ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py"
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8630_intent_to_build_neutral_manifest" / "intent_to_build_neutral_manifest.jsonl"
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pointer = json.loads(TOKENIZER_POINTER.read_text(encoding="utf-8"))
    loop_src = (ROOT / "legacy_src" / "agentkernel_lite" / "training_loop.py").read_text(encoding="utf-8")
    trainer_src = TRAINER.read_text(encoding="utf-8")
    output = OUT_DIR / "contract_only_probe"
    cmd = [
        sys.executable,
        str(TRAINER),
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
        "--output-dir", str(output),
        "--run-id", "stage8642_structured_contract_only",
        "--implementation", "transformer",
        "--tokenizer-json", pointer["primary_recovered_paths"]["tokenizer_json"],
        "--tokenizer-config", pointer["primary_recovered_paths"]["tokenizer_config"],
        "--contract-only",
    ]
    res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    errors = []
    card = {}
    if res.returncode == 0:
        card = json.loads(res.stdout)
    else:
        errors.append("structured contract-only trainer failed: " + res.stderr[-1000:])
    gates = {
        "structured_loop_function_present": "def run_structured_aux_probe" in loop_src,
        "structured_loss_map_present": "STRUCTURED_LOSS_TO_FIELD" in loop_src,
        "trainer_imports_structured_loop": "run_structured_aux_probe" in trainer_src,
        "trainer_allows_structured_modes_behind_gate": "args.mode in STRUCTURED_MODE_ALLOWED_LOSSES" in trainer_src,
        "contract_only_structured_policy_passes": res.returncode == 0 and bool(card.get("passed")),
        "contract_only_no_execution": card.get("model_execution_attempted") is False,
        "contract_records_transformer": card.get("implementation") == "transformer",
        "decoder_loss_zero": card.get("loss_counts", {}).get("decoder_ce") == 0,
    }
    for key, value in gates.items():
        if not value:
            errors.append(f"gate failed: {key}")
    summary = {
        "stage": 8642,
        "stage_name": "stage8642_structured_aux_runtime_contract",
        "passed": not errors,
        "authority": AUTHORITY_CLOSED,
        "model_execution_authorized": False,
        "decoder_ce_training_authorized": False,
        "gates": gates,
        "errors": errors,
        "contract_only_output": str(output.relative_to(ROOT)),
        "next_best_step": "Add real structured telemetry assertions and label-vocab/hash cards, then continue verifier-repair/denoise runtime reconstruction before data recovery.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "structured_runtime_contract_card.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
