#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10518
NAME = "stage10518_root_based_multitarget_bootstrap_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "root_based_multitarget_bootstrap_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "root_based_multitarget_bootstrap_probe_manifest.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

BOOTSTRAP_MANIFEST = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/split_aware_multitarget_bootstrap_manifest.json"
BOOTSTRAP_ROWS = ROOT / "runs/local/artifacts/stage10517_split_aware_multitarget_bootstrap_manifest/multitarget_bootstrap_rows.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10518_root_based_multitarget_bootstrap_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10518_root_based_multitarget_bootstrap_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10518_root_based_multitarget_bootstrap_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def with_probe_fields(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux", "bounded_choice_aux"]
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["loss_mask"] = {"decoder_ce": True}
    updated["objective_family"] = "root_based_multitarget_decoder_ce"
    updated["decoder_text"] = updated.get("target_text", "")
    updated["prompt_text"] = updated.get("input_text", "")
    updated["target_token_len"] = max(1, len(str(updated.get("target_text", "")).split()))
    return updated


def build_command(train_count: int, eval_count: int, strict_count: int) -> list[str]:
    return [
        "env",
        "TMPDIR=/data/tmp",
        "TEMP=/data/tmp",
        "TMP=/data/tmp",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
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
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows",
        str(train_count),
        "--max-eval-rows",
        str(eval_count),
        "--max-strict-rows",
        str(strict_count),
        "--max-steps",
        "256",
        "--batch-size",
        "2",
        "--learning-rate",
        "2e-5",
        "--max-encoder-tokens",
        "1024",
        "--max-decoder-tokens",
        "256",
        "--decoder-ce-weight",
        "1.0",
        "--bounded-choice-aux-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "2.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "24",
        "--max-generation-tokens",
        "128",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "1.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    bootstrap_manifest = load_json(BOOTSTRAP_MANIFEST)
    rows = load_jsonl(BOOTSTRAP_ROWS)

    train_rows = [with_probe_fields(row, "train") for row in rows if row["split_component"] in {"train_bootstrap_bounded", "train_bootstrap_geometry", "train_bootstrap_long_context", "train_teacher_long_context"}]
    eval_rows = [with_probe_fields(row, "eval") for row in rows if row["split_component"] == "validation_bootstrap_bounded"]
    strict_rows = [with_probe_fields(row, "strict_eval") for row in rows if row["split_component"] == "reference_bounded_eval"]
    manifest_rows = train_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = build_command(len(train_rows), len(eval_rows), len(strict_rows))
    split_language_counts = {
        "train": dict(sorted(Counter(row.get("language_family", "unknown") for row in train_rows).items())),
        "eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in eval_rows).items())),
        "strict_eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in strict_rows).items())),
    }
    split_target_counts = {
        "train": dict(sorted(Counter(row.get("target_family", "unknown") for row in train_rows).items())),
        "eval": dict(sorted(Counter(row.get("target_family", "unknown") for row in eval_rows).items())),
        "strict_eval": dict(sorted(Counter(row.get("target_family", "unknown") for row in strict_rows).items())),
    }

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_rows),
        "decision": "root_based_multitarget_bootstrap_probe_ready",
        "claim_scope": [
            "Bootstrap training request for the first root-based seq2seq maintainer curriculum run.",
            "Not a promotable leaderboard claim by itself.",
            "Strict rows remain canary/reference slices only and must be interpreted as regression protection, not a fresh heldout frontier.",
        ],
        "source_package": str(BOOTSTRAP_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST_JSONL.relative_to(ROOT)),
        "run_id": RUN_ID,
        "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
        "runtime_model_dir": str(RUNTIME_MODEL_DIR.relative_to(ROOT)),
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
        },
        "language_counts_by_split": split_language_counts,
        "target_family_counts_by_split": split_target_counts,
        "command": command,
        "required_honesty_gates": [
            "stage10517 split-aware bootstrap manifest root audit remains zero-violation",
            "reference_bounded_eval rows remain out of train",
            "diagnostic rows remain excluded from the probe manifest",
            "post-run claims must separate bootstrap curriculum progress from multilingual heldout benchmark wins",
        ],
        "required_runtime_artifacts": [
            "execution_result.json",
            "sample_generation_audit.json",
            "short_output_probe.json",
            "failure_bucket_card.json",
            "cleanup_proof.json",
            "loss_by_step.jsonl",
            "eval_loss_by_checkpoint.jsonl",
        ],
        "curriculum_intent": {
            "train_teacher_long_context_role": "broaden seq2seq maintainer state prediction beyond bounded labels",
            "train_bootstrap_bounded_role": "preserve current multilingual maintainer-choice strengths",
            "validation_role": "light rust bounded validation seed only",
            "strict_reference_role": "canary regression check only",
        },
        "known_limits": [
            "Python has no fresh heldout rows in this bootstrap probe; it is train-heavy and benchmark-light.",
            "Rust and web training supply remain thinner than Python.",
            "This request uses bounded_decoder_ce_probe because the current runtime does not yet expose a dedicated root-based multi-target mode.",
        ],
        "next_best_step": (
            "Run this bootstrap probe, inspect generation and regression audits, then replenish fresh heldout Rust and web roots "
            "before treating any gains as multilingual benchmark progress over Gemma-12B."
        ),
        "bootstrap_manifest_snapshot": {
            "rows_by_split_component": bootstrap_manifest["metrics"]["rows_by_split_component"],
            "rows_by_language": bootstrap_manifest["metrics"]["rows_by_language"],
            "unique_train_roots": bootstrap_manifest["metrics"]["unique_train_roots"],
        },
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY_JSON, request)


if __name__ == "__main__":
    main()
