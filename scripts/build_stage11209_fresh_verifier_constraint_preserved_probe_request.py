#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11209
NAME = "stage11209_fresh_verifier_constraint_preserved_probe_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_verifier_constraint_preserved_probe_request.json"
COMMAND_JSON = OUT_DIR / "fresh_verifier_constraint_preserved_probe_command.json"
MANIFEST = OUT_DIR / "fresh_verifier_constraint_preserved_probe_manifest.jsonl"

BASE_PACKAGE = ARTIFACTS / "stage11198_role_focused_residual_support_package"
BASE_TRAIN = BASE_PACKAGE / "agentkernel_lite_encdec_train.jsonl"
VALIDATION = BASE_PACKAGE / "agentkernel_lite_encdec_validation.jsonl"
STRICT = BASE_PACKAGE / "agentkernel_lite_encdec_strict_eval.jsonl"
ADDED = ARTIFACTS / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"
RESIDUAL_BANK = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json"
RUN_DIR = ARTIFACTS / "stage11209_fresh_verifier_constraint_preserved_probe"
PROBE_OUT = RUN_DIR / "bounded_decoder_probe"
RUNTIME_OUT = RUN_DIR / "runtime_model"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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

    eval_roots = {root_key(row) for row in validation + strict + residual}
    added_roots = {root_key(row) for row in added}
    overlaps = sorted(added_roots & eval_roots)
    if overlaps:
        raise SystemExit(f"added rows overlap eval/residual roots: {overlaps[:5]}")

    train_rows = base_train + added
    manifest_rows: list[dict[str, Any]] = []
    for split, rows in (("train", train_rows), ("eval", validation), ("strict_eval", strict)):
        for row in rows:
            payload = dict(row)
            payload["split"] = split
            manifest_rows.append(payload)
    write_jsonl(MANIFEST, manifest_rows)

    preservation_kl_weight = "1.0"
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
        "--preservation-kl-weight", preservation_kl_weight,
        "--no-final-checkpoint",
        "--output-dir", str(PROBE_OUT),
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_verifier_constraint_preserved_probe_requested",
        "rationale": (
            "Stage11208 improved the clean residual successor from 5/10 to 6/10 but regressed "
            "the clean strict canary from 22/22 to 21/22. This request keeps the same manifest "
            "and scorer but restores preservation KL against the Stage11200 runtime."
        ),
        "scorer_under_test": "encoder_option_retrieval_verifier_conditioned",
        "metrics": {
            "base_train_rows": len(base_train),
            "added_rows": len(added),
            "train_rows": len(train_rows),
            "validation_rows": len(validation),
            "strict_rows": len(strict),
            "residual_rows_for_postrun": len(residual),
            "added_unique_roots": len(added_roots),
            "eval_residual_root_overlaps": overlaps,
            "max_steps": 128,
            "batch_size": 4,
            "preservation_kl_weight": float(preservation_kl_weight),
        },
        "promotion_gate_for_postrun": {
            "strict_must_remain": "22/22",
            "residual_must_exceed_stage11196": ">=6/10",
            "residual_should_beat_gemma": ">7/10 row accuracy or improved cluster with no strict regression",
        },
        "source_artifacts": {
            "base_train": rel(BASE_TRAIN),
            "added_rows": rel(ADDED),
            "validation": rel(VALIDATION),
            "strict": rel(STRICT),
            "residual_bank": rel(RESIDUAL_BANK),
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
