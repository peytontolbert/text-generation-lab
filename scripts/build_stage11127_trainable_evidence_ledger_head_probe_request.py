#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11127
NAME = "stage11127_trainable_evidence_ledger_head_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "trainable_evidence_ledger_head_probe_request.json"
COMMAND_JSON = OUT_DIR / "trainable_evidence_ledger_head_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "trainable_evidence_ledger_head_probe_manifest.jsonl"

PACKAGE_DIR = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence"
PACKAGE_JSON = PACKAGE_DIR / "fresh_family_support_package_with_trainable_admitted_evidence.json"
TRAIN_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = PACKAGE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = PACKAGE_DIR / "added_admitted_evidence_rows_trainable.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11116_trainable_evidence_support_probe" / "runtime_model" / "runtime_model_bundle.json"
RESERVED_CANDIDATES = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
PROBE_OUT_DIR = ARTIFACTS / "stage11128_trainable_evidence_ledger_head_probe" / "bounded_decoder_probe"
RUNTIME_OUT_DIR = ARTIFACTS / "stage11128_trainable_evidence_ledger_head_probe" / "runtime_model"


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
    added_rows = load_jsonl(ADDED_ROWS_JSONL)
    reserved_candidates = load_jsonl(RESERVED_CANDIDATES)

    manifest_rows = train_rows + validation_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

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
        "64",
        "--batch-size",
        "2",
        "--learning-rate",
        "5e-6",
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "16",
        "--decoder-ce-weight",
        "0.2",
        "--bounded-choice-aux-weight",
        "1.0",
        "--bounded-choice-aux-source",
        "encoder_option_retrieval_evidence_ledger_head",
        "--bounded-choice-contrast-weight",
        "0.1",
        "--bounded-choice-contrast-margin",
        "0.05",
        "--bounded-decoder-train-sampler",
        "residual_family_balanced",
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
        "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_OUT_DIR.resolve()),
        "--initialize-from-runtime-model",
        str(RUNTIME_BUNDLE.resolve()),
        "--preservation-reference-runtime-model",
        str(RUNTIME_BUNDLE.resolve()),
        "--preservation-kl-weight",
        "0.05",
        "--no-final-checkpoint",
        "--output-dir",
        str(PROBE_OUT_DIR.resolve()),
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "trainable_evidence_ledger_head_probe_requested",
        "claim_scope": [
            "Train a persistent evidence-ledger bounded-choice scorer head with richer evidence-role features on the current stage11114 trainable evidence support package.",
            "Keep validation and strict successor surfaces unchanged, then score the untouched reserved residual bank to test evidence-role ledger scorer-objective alignment rather than support-row volume.",
        ],
        "source_artifacts": {
            "support_package": rel(PACKAGE_JSON),
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "reserved_candidates": rel(RESERVED_CANDIDATES),
            "added_support_rows": rel(ADDED_ROWS_JSONL),
        },
        "metrics": {
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "stress_rows_excluded_from_manifest": len(stress_rows),
            "reserved_candidates": len(reserved_candidates),
            "trainable_evidence_rows_added": len(added_rows),
            "trainable_evidence_repo_count": len({str(row.get("repo_family") or "") for row in added_rows}),
        },
        "training_contract": {
            "bounded_choice_aux_source": "encoder_option_retrieval_evidence_ledger_head",
            "bounded_choice_contrast_weight": 0.1,
            "bounded_decoder_train_sampler": "residual_family_balanced",
            "initialize_from_runtime_model": rel(RUNTIME_BUNDLE),
            "runtime_model_save_dir": rel(RUNTIME_OUT_DIR),
            "loader_requirement": "runtime loader now reconstructs saved bounded-choice scorer heads, including evidence-ledger heads",
        },
        "promotion_gates": [
            "Strict successor accuracy must stay at or above 22/23, validation must stay at or above 20/23, and reserved evidence must move beyond 4/9 before promotion.",
            "Validation successor accuracy must improve above 20/23 or stay stable while reserved residual improves.",
            "Reserved residual bank must improve above 5/10 and reserved evidence above 4/9 before this is considered a frontier improvement.",
            "If strict regresses or reserved remains flat, treat this as architecture-negative and move to a dedicated evidence-role/ledger head with stronger row geometry.",
        ],
        "next_best_step": "Execute this request, then run the stage11129 postrun audit over successor validation/strict and reserved residual candidates.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "command_json": rel(COMMAND_JSON),
            "manifest_jsonl": rel(MANIFEST_JSONL),
            "probe_output_dir": rel(PROBE_OUT_DIR),
            "runtime_model_dir": rel(RUNTIME_OUT_DIR),
        },
        "command": command,
        "package_snapshot": package.get("metrics"),
    }

    write_json(SUMMARY_JSON, summary)
    write_json(COMMAND_JSON, {"command": command})
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
