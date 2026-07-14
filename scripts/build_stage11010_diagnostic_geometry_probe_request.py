#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11010
NAME = "stage11010_diagnostic_geometry_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "diagnostic_geometry_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "diagnostic_geometry_probe_manifest.jsonl"
COMMAND_JSON = OUT_DIR / "diagnostic_geometry_probe_command.json"

PACKAGE_DIR = ARTIFACTS / "stage11009_diagnostic_geometry_curriculum_package"
INIT_RUNTIME = ARTIFACTS / "stage10985_clean_residual_family_support_probe" / "runtime_model" / "runtime_model_bundle.json"
RUN_NAME = "stage11011_diagnostic_geometry_probe"
RUN_DIR = ARTIFACTS / RUN_NAME
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    train_rows = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl")
    validation_rows = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    strict_rows = load_jsonl(PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    manifest_rows = [*train_rows, *validation_rows, *strict_rows]
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    cmd = [
        "env",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock",
        str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
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
        str(RUNTIME_OUT),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "0.25",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(PROBE_OUT),
        "--run-id",
        RUN_NAME,
    ]
    write_json(COMMAND_JSON, {"command": cmd})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "diagnostic_geometry_probe_requested",
        "claim_scope": [
            "Run one non-promotable geometry-absorption probe.",
            "Test whether direct exposure to same-root geometry variants moves the wider 27-row geometry bank at all.",
        ],
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "total_manifest_rows": len(manifest_rows),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "manifest_jsonl": rel(MANIFEST_JSONL),
            "command_json": rel(COMMAND_JSON),
            "probe_output_dir": rel(PROBE_OUT),
            "runtime_model_dir": rel(RUNTIME_OUT),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
