#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11199
NAME = "stage11199_role_focused_residual_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "role_focused_residual_probe_request.json"
COMMAND_JSON = OUT_DIR / "role_focused_residual_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "role_focused_residual_probe_manifest.jsonl"

PACKAGE_DIR = ARTIFACTS / "stage11198_role_focused_residual_support_package"
PACKAGE_JSON = PACKAGE_DIR / "role_focused_residual_support_package.json"
TRAIN_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
ADDED_JSONL = PACKAGE_DIR / "added_role_focused_support_rows.jsonl"
RUNTIME_BUNDLE = ARTIFACTS / "stage11186_contract_evidence_ledger_head_probe/runtime_model/runtime_model_bundle.json"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
PROBE_OUT_DIR = ARTIFACTS / "stage11200_role_focused_residual_probe/bounded_decoder_probe"
RUNTIME_OUT_DIR = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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
    if not package.get("passed"):
        raise SystemExit("stage11198 package did not pass")
    train = load_jsonl(TRAIN_JSONL)
    validation = load_jsonl(VALIDATION_JSONL)
    strict = load_jsonl(STRICT_JSONL)
    added = load_jsonl(ADDED_JSONL)
    residual = load_jsonl(RESIDUAL_BANK)
    manifest = [*train, *validation, *strict]
    write_jsonl(MANIFEST_JSONL, manifest)
    command = [
        "env",
        "CUDA_VISIBLE_DEVICES=2",
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str((ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py").resolve()),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL.resolve()),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str((ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json").resolve()),
        "--tokenizer-json", str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json").resolve()),
        "--tokenizer-config", str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json").resolve()),
        "--tokenizer-hashlock", str((ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json").resolve()),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train)),
        "--max-eval-rows", str(len(validation)),
        "--max-strict-rows", str(len(strict)),
        "--max-steps", "96",
        "--batch-size", "2",
        "--learning-rate", "8e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.25",
        "--bounded-choice-aux-source", "encoder_option_retrieval_evidence_ledger_head",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_OUT_DIR.resolve()),
        "--initialize-from-runtime-model", str(RUNTIME_BUNDLE.resolve()),
        "--preservation-reference-runtime-model", str(RUNTIME_BUNDLE.resolve()),
        "--preservation-kl-weight", "0.0",
        "--no-final-checkpoint",
        "--output-dir", str(PROBE_OUT_DIR.resolve()),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "role_focused_residual_probe_requested",
        "claim_scope": [
            "Diagnostic pressure probe for verifier/test-constraint and symptom/call-path evidence roles.",
            "No residual successor bank rows are in train; replacement rows remain held out for postrun scoring.",
            "No promotion unless clean strict is preserved and residual successor score improves over 5/10 and beats Gemma 7/10.",
        ],
        "metrics": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "added_role_focused_rows": len(added),
            "residual_successor_rows_for_postrun": len(residual),
        },
        "source_artifacts": {
            "support_package": rel(PACKAGE_JSON),
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "added_rows": rel(ADDED_JSONL),
            "residual_bank": rel(RESIDUAL_BANK),
        },
        "required_honesty_gates": [
            "Clean strict must remain 22/22 under productized scorer.",
            "Clean validation must be reported separately.",
            "Clean residual successor bank must be scored same-manifest without entering train.",
            "Gemma comparison from stage11197 remains the residual baseline to beat.",
        ],
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
