#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10523
NAME = "stage10523_root_based_multitarget_bootstrap_probe_request_with_heldout"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "root_based_multitarget_bootstrap_probe_request_with_heldout.json"
MANIFEST_JSONL = OUT_DIR / "root_based_multitarget_bootstrap_probe_with_heldout_manifest.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/split_aware_multitarget_bootstrap_manifest_with_heldout.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/multitarget_bootstrap_with_heldout_rows.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10523_root_based_multitarget_bootstrap_probe_with_heldout"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10523_root_based_multitarget_bootstrap_probe_with_heldout/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10523_root_based_multitarget_bootstrap_probe_with_heldout/runtime_model"


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
    source_manifest = load_json(SOURCE_MANIFEST)
    rows = load_jsonl(SOURCE_ROWS)

    train_rows = [with_probe_fields(row, "train") for row in rows if row["split_component"] in {"train_bootstrap_bounded", "train_bootstrap_geometry", "train_bootstrap_long_context", "train_teacher_long_context"}]
    eval_rows = [with_probe_fields(row, "eval") for row in rows if row["split_component"] == "validation_bootstrap_bounded"]
    strict_rows = [with_probe_fields(row, "strict_eval") for row in rows if row["split_component"] == "strict_eval_long_context_heldout"]
    manifest_rows = train_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = build_command(len(train_rows), len(eval_rows), len(strict_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_rows),
        "decision": "root_based_multitarget_bootstrap_probe_with_heldout_ready",
        "claim_scope": [
            "Bootstrap training request aligned to the heldout-aware manifest.",
            "Post-run strict scoring can speak to the 36 eval-safe multilingual heldout rows only.",
            "Legacy reference rows are excluded from the probe manifest.",
        ],
        "source_package": str(SOURCE_MANIFEST.relative_to(ROOT)),
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
        "language_counts_by_split": {
            "train": dict(sorted(Counter(row.get("language_family", "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in strict_rows).items())),
        },
        "target_family_counts_by_split": {
            "train": dict(sorted(Counter(row.get("target_family", "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(row.get("target_family", "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(row.get("target_family", "unknown") for row in strict_rows).items())),
        },
        "strict_target_subtypes": dict(sorted(Counter(row.get("target_subtype", "unknown") for row in strict_rows).items())),
        "command": command,
        "required_honesty_gates": [
            "stage10521 root split audit remains zero-violation",
            "strict_eval_long_context_heldout rows remain out of train",
            "strict rows are limited to decisive_evidence and retrieve_answer_abstain target subtypes",
            "post-run Gemma comparison must use the same 36 strict rows",
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
        "known_limits": [
            "Strict heldout rows currently cover only evidence/abstention-style targets, not full verifier-outcome generation.",
            "Rust and web heldout depth remain modest.",
            "The runtime still uses bounded_decoder_ce_probe as the executable carrier mode for this curriculum.",
        ],
        "next_best_step": (
            "Run this heldout-aware bootstrap probe, then compare 100M and Gemma on the 36 strict eval-safe rows. "
            "After that, deepen Rust and web heldout supply and add non-leaky verifier-style rows."
        ),
        "manifest_snapshot": {
            "strict_rows_by_language": source_manifest["metrics"]["strict_rows_by_language"],
            "strict_rows_by_target_subtype": source_manifest["metrics"]["strict_rows_by_target_subtype"],
            "train_rows_by_language": source_manifest["metrics"]["train_rows_by_language"],
        },
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY_JSON, request)


if __name__ == "__main__":
    main()
