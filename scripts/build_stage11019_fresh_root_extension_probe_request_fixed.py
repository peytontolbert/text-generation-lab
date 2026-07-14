#!/usr/bin/env python3
"""Build a trainer-compatible probe request from the stage11016 extension package."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
EXT_DIR = ROOT / "runs/local/artifacts/stage11016_reviewed_v27_fresh_root_extension_package"
OUT_DIR = ROOT / "runs/local/artifacts/stage11019_fresh_root_extension_probe_request_fixed"
RUNTIME_INIT = ROOT / "runs/local/artifacts/stage10985_clean_residual_family_support_probe/runtime_model/runtime_model_bundle.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n")


def normalize_eval_row(row: dict, split_name: str) -> dict:
    out = dict(row)
    out["split"] = split_name
    out["package_split"] = None
    out["loss_mask"] = {"decoder_ce": True}
    out["disable_losses"] = []
    out["expected_enabled_loss"] = "decoder_ce"
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    train_rows = read_jsonl(EXT_DIR / "agentkernel_lite_encdec_train.jsonl")
    validation_rows = [normalize_eval_row(r, "eval") for r in read_jsonl(EXT_DIR / "agentkernel_lite_encdec_validation.jsonl")]
    strict_rows = [normalize_eval_row(r, "strict_eval") for r in read_jsonl(EXT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")]
    successor_eval_rows = [normalize_eval_row(r, "strict_eval") for r in read_jsonl(EXT_DIR / "agentkernel_lite_encdec_successor_eval.jsonl")]

    manifest_rows = train_rows + validation_rows + strict_rows
    manifest_path = OUT_DIR / "fresh_root_extension_probe_manifest.jsonl"
    successor_eval_path = OUT_DIR / "fresh_root_extension_successor_eval.jsonl"
    command_path = OUT_DIR / "fresh_root_extension_probe_command.json"
    summary_path = OUT_DIR / "fresh_root_extension_probe_request_fixed.json"

    write_jsonl(manifest_path, manifest_rows)
    write_jsonl(successor_eval_path, successor_eval_rows)

    command = {
        "command": [
            "env",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            "/data/agentkernel-seq2seq-text-lab/legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--repo-root",
            "/data/agentkernel-seq2seq-text-lab",
            "--manifest",
            str(manifest_path),
            "--mode",
            "bounded_decoder_ce_probe",
            "--probe-scale",
            "target_100m",
            "--implementation",
            "transformer",
            "--model-config",
            "/data/agentkernel-seq2seq-text-lab/configs/model/agentkernel_100m_seq2seq_recovered_target.json",
            "--tokenizer-json",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
            "--tokenizer-config",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
            "--tokenizer-hashlock",
            "/data/agentkernel-seq2seq-text-lab/configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json",
            "--execution-authorized-for-recovery-probe",
            "--max-train-rows",
            str(len(train_rows)),
            "--max-eval-rows",
            str(len(validation_rows)),
            "--max-strict-rows",
            str(len(strict_rows)),
            "--max-steps",
            "96",
            "--batch-size",
            "2",
            "--learning-rate",
            "5e-6",
            "--max-encoder-tokens",
            "768",
            "--max-decoder-tokens",
            "8",
            "--decoder-ce-weight",
            "0.2",
            "--bounded-choice-aux-weight",
            "1.0",
            "--bounded-choice-aux-source",
            "encoder_option_retrieval",
            "--bounded-choice-contrast-weight",
            "0.0",
            "--bounded-choice-contrast-margin",
            "0.05",
            "--bounded-decoder-train-sampler",
            "cyclic",
            "--structured-aux-weight",
            "0.0",
            "--denoise-weight",
            "0.0",
            "--eos-loss-weight",
            "4.0",
            "--enable-generation-audit",
            "--max-generation-rows",
            "12",
            "--max-generation-tokens",
            "8",
            "--require-loss-mask-enforcement-audit",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage11020_fresh_root_extension_probe_fixed/runtime_model",
            "--initialize-from-runtime-model",
            str(RUNTIME_INIT),
            "--preservation-reference-runtime-model",
            str(RUNTIME_INIT),
            "--preservation-kl-weight",
            "0.25",
            "--no-final-checkpoint-export",
            "--skip-final-model-save",
            "1",
            "--output-dir",
            "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage11020_fresh_root_extension_probe_fixed/bounded_decoder_probe",
            "--run-id",
            "stage11020_fresh_root_extension_probe_fixed",
        ]
    }
    command_path.write_text(json.dumps(command, indent=2, ensure_ascii=True) + "\n")

    summary = {
        "stage": 11019,
        "stage_name": "stage11019_fresh_root_extension_probe_request_fixed",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "passed": True,
        "decision": "fresh_root_extension_probe_requested_fixed",
        "claim_scope": [
            "Run one trainer-compatible bounded support probe on the alias-safe reviewed-v2.7 extension package.",
            "Keep the current 23-row anti-cheat-clean canary fixed while adding 13 honest fresh support rows to train.",
            "Normalize validation to eval and enable decoder_ce loss masks on all eval rows to satisfy the probe contract.",
            "Audit the separate 2-row Rust successor-eval slice after the run without mixing it into train or headline strict."
        ],
        "runtime_initialization": str(RUNTIME_INIT),
        "metrics": {
            "train_rows": len(train_rows),
            "eval_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "successor_eval_rows": len(successor_eval_rows),
            "total_manifest_rows": len(manifest_rows),
        },
        "outputs": {
            "manifest_jsonl": str(manifest_path),
            "successor_eval_jsonl": str(successor_eval_path),
            "command_json": str(command_path),
            "probe_output_dir": "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage11020_fresh_root_extension_probe_fixed/bounded_decoder_probe",
            "runtime_model_dir": "/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage11020_fresh_root_extension_probe_fixed/runtime_model",
            "summary_json": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
