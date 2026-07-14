#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11070
NAME = "stage11070_a_prior_and_python_verifier_diagnostic_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "a_prior_and_python_verifier_diagnostic_probe_request.json"
COMMAND_JSON = OUT_DIR / "a_prior_and_python_verifier_diagnostic_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "a_prior_and_python_verifier_diagnostic_probe_manifest.jsonl"

PACKAGE_DIR = ARTIFACTS / "stage11069_a_prior_and_python_verifier_diagnostic_package"
PACKAGE_JSON = PACKAGE_DIR / "a_prior_and_python_verifier_diagnostic_package.json"
TRAIN_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
CONTAMINATED_RESERVED_JSON = PACKAGE_DIR / "contaminated_reserved_rows.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11063_ready_lane_fresh_support_probe" / "runtime_model" / "runtime_model_bundle.json"
PROBE_OUT_DIR = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe"
RUNTIME_OUT_DIR = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = load_jsonl(TRAIN_JSONL)
    validation_rows = load_jsonl(VALIDATION_JSONL)
    strict_rows = load_jsonl(STRICT_JSONL)
    stress_rows = load_jsonl(STRESS_JSONL)
    contaminated_reserved = load_json(CONTAMINATED_RESERVED_JSON)

    manifest_rows = train_rows + validation_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = [
        "env",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str((ROOT / "legacy_src" / "scripts" / "train_agentkernel_lite_encdec.py").resolve()),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST_JSONL.resolve()),
        "--mode",
        "bounded_decoder_ce_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str((ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json").resolve()),
        "--tokenizer-json",
        str((ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506" / "tokenizer.json").resolve()),
        "--tokenizer-config",
        str((ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506" / "tokenizer_config.json").resolve()),
        "--tokenizer-hashlock",
        str((ROOT / "configs" / "tokenizer" / "agentkernel_bpe_1506_recovered_pointer.json").resolve()),
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
        str(RUNTIME_OUT_DIR.resolve()),
        "--initialize-from-runtime-model",
        str(RUNTIME_BUNDLE.resolve()),
        "--preservation-reference-runtime-model",
        str(RUNTIME_BUNDLE.resolve()),
        "--preservation-kl-weight",
        "0.1",
        "--no-final-checkpoint",
        "--output-dir",
        str(PROBE_OUT_DIR.resolve()),
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "a_prior_and_python_verifier_diagnostic_probe_requested",
        "claim_scope": [
            "Run one diagnostic bounded probe targeting the explicit-ledger A-prior defect and the Python verifier-transition boundary from the latest clean runtime.",
            "Keep cleaned validation/strict as the main canary while explicitly excluding contaminated reserved rows from any postrun generalization claim.",
        ],
        "source_artifacts": {
            "diagnostic_package": rel(PACKAGE_JSON),
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "contaminated_reserved_json": rel(CONTAMINATED_RESERVED_JSON),
        },
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "stress_rows_excluded_from_manifest": len(stress_rows),
            "contaminated_reserved_rows": len(contaminated_reserved),
            "rows_added": package.get("metrics", {}).get("rows_added_total"),
        },
        "required_honesty_gates": [
            "Cleaned validation/strict remain the only main canary surfaces.",
            "The two contaminated reserved rows cannot be used for postrun generalization claims on this branch.",
            "Any improvement on same-surface evidence clone rows is diagnostic only.",
        ],
        "next_best_step": "Execute this request, then audit cleaned validation/strict plus the uncontaminated reserved subset and report the Python verifier strict miss separately.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "command_json": rel(COMMAND_JSON),
            "manifest_jsonl": rel(MANIFEST_JSONL),
            "probe_output_dir": rel(PROBE_OUT_DIR),
            "runtime_model_dir": rel(RUNTIME_OUT_DIR),
        },
        "command": command,
    }

    write_json(SUMMARY_JSON, summary)
    write_json(COMMAND_JSON, {"command": command})
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
