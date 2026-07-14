#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11227
NAME = "stage11227_balanced_candidate_validity_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "balanced_candidate_validity_probe_request.json"
COMMAND_JSON = OUT_DIR / "balanced_candidate_validity_probe_command.json"
MANIFEST = OUT_DIR / "balanced_candidate_validity_probe_manifest.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11198_role_focused_residual_support_package"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
ADDED = ARTIFACTS / "stage11226_balanced_candidate_validity_support/balanced_candidate_validity_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
BINARY_EVAL = ARTIFACTS / "stage11223_clean_residual_binary_candidate_validity_eval/binary_candidate_validity_eval_rows.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11227_balanced_candidate_validity_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "")


def main() -> None:
    base_train = load_jsonl(BASE_TRAIN)
    added = load_jsonl(ADDED)
    validation = load_jsonl(VALIDATION)
    strict = load_jsonl(STRICT)
    residual = load_jsonl(RESIDUAL_BANK)
    binary_eval = load_jsonl(BINARY_EVAL)

    eval_roots = {root_key(row) for row in validation + strict + residual + binary_eval}
    added_roots = {root_key(row) for row in added}
    overlaps = sorted(added_roots & eval_roots)
    if overlaps:
        raise SystemExit(f"added rows overlap eval/residual/binary roots: {overlaps[:5]}")

    train_rows = base_train + added
    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", validation), ("strict_eval", strict)):
        for row in rows:
            payload = dict(row)
            payload["split"] = split
            manifest_rows.append(payload)
    write_jsonl(MANIFEST, manifest_rows)

    command = [
        "env", "CUDA_VISIBLE_DEVICES=2", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train_rows)),
        "--max-eval-rows", str(len(validation)),
        "--max-strict-rows", str(len(strict)),
        "--max-steps", "128",
        "--batch-size", "4",
        "--learning-rate", "8e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "16",
        "--decoder-ce-weight", "0.1",
        "--bounded-choice-aux-weight", "1.75",
        "--bounded-choice-aux-source", "encoder_option_retrieval_verifier_conditioned",
        "--bounded-decoder-train-sampler", "residual_family_balanced",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "16",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(RUNTIME_OUT),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--preservation-kl-weight", "1.0",
        "--no-final-checkpoint",
        "--output-dir", str(PROBE_OUT),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "balanced_candidate_validity_probe_requested",
        "rationale": "Train on class-balanced binary evidence-validity support after Stage11224 exposed all-negative collapse.",
        "scorer_under_test": "encoder_option_retrieval_verifier_conditioned",
        "metrics": {
            "base_train_rows": len(base_train),
            "added_rows": len(added),
            "train_rows": len(train_rows),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "residual_rows_for_postrun": len(residual),
            "binary_eval_rows_for_postrun": len(binary_eval),
            "added_unique_roots": len(added_roots),
            "eval_residual_binary_root_overlaps": overlaps,
            "max_steps": 128,
            "batch_size": 4,
            "preservation_kl_weight": 1.0,
        },
        "promotion_gate_for_postrun": {
            "clean_strict_must_remain": "22/22",
            "clean_residual_must_not_regress": ">=5/10",
            "binary_eval_positive_recall_must_improve": ">0/9",
            "binary_eval_overall_must_not_be_negative_class_collapse": "positive and negative classes both nonzero correct",
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "added_rows": rel(ADDED),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
            "binary_eval": rel(BINARY_EVAL),
            "initialize_from_runtime": rel(INIT_RUNTIME),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "command_json": rel(COMMAND_JSON),
            "manifest_jsonl": rel(MANIFEST),
            "probe_output_dir": rel(PROBE_OUT),
            "runtime_model_dir": rel(RUNTIME_OUT),
        },
        "command": command,
    }
    write_json(COMMAND_JSON, {"command": command})
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
