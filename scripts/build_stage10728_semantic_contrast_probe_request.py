#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10728
NAME = "stage10728_semantic_contrast_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "semantic_contrast_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "semantic_contrast_probe_manifest.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_DIR = ROOT / "runs/local/artifacts/stage10727_semantic_contrast_support_package"
BASE_RUNTIME = ROOT / "runs/local/artifacts/stage10710_rewritten_plus_reviewed_probe_execution_repaired/runtime_model/runtime_model_bundle.json"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    train_rows = load_jsonl(PACKAGE_DIR / "train_rows.jsonl")
    eval_rows = load_jsonl(PACKAGE_DIR / "eval_rows.jsonl")
    strict_rows = load_jsonl(PACKAGE_DIR / "strict_rows.jsonl")

    frontload_ids = [
        str(row["row_id"])
        for row in train_rows
        if row.get("semantic_repair_role") in {
            "promotable_disjoint_verifier_seed",
            "fresh_reviewed_semantic_contrast_seed",
            "honesty_only_abstention_seed",
            "honesty_abstention_seed",
        }
    ]
    frontloaded = [row for row in train_rows if str(row["row_id"]) in frontload_ids]
    remainder = [row for row in train_rows if str(row["row_id"]) not in frontload_ids]
    manifest_rows = frontloaded + remainder + eval_rows + strict_rows

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Launch the next honest multilingual probe after adding Python and Rust semantic-contrast support.",
            "Guarantee sampling of the new semantic repair rows by frontloading them and raising the step budget beyond full-train coverage.",
        ],
        "command": [
            "env",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "AGENTKERNEL_TRAIN_DEVICE=cuda",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            "/data/agentkernel-seq2seq-text-lab/legacy_src/scripts/train_agentkernel_lite_encdec.py",
            "--repo-root",
            "/data/agentkernel-seq2seq-text-lab",
            "--manifest",
            str(MANIFEST_JSONL),
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
            str(len(eval_rows)),
            "--max-strict-rows",
            str(len(strict_rows)),
            "--max-steps",
            "192",
            "--batch-size",
            "2",
            "--learning-rate",
            "1e-5",
            "--max-encoder-tokens",
            "1024",
            "--max-decoder-tokens",
            "256",
            "--decoder-ce-weight",
            "1.0",
            "--bounded-choice-aux-weight",
            "0.2",
            "--bounded-choice-aux-source",
            "encoder_option_retrieval",
            "--structured-aux-weight",
            "0.0",
            "--denoise-weight",
            "0.0",
            "--eos-loss-weight",
            "2.0",
            "--enable-generation-audit",
            "--max-generation-rows",
            str(len(eval_rows)),
            "--max-generation-tokens",
            "128",
            "--require-loss-mask-enforcement-audit",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            str(OUT_DIR / "runtime_model"),
            "--initialize-from-runtime-model",
            str(BASE_RUNTIME),
            "--preservation-reference-runtime-model",
            str(BASE_RUNTIME),
            "--preservation-kl-weight",
            "1.5",
            "--no-final-checkpoint-export",
            "--skip-final-model-save",
            "1",
            "--output-dir",
            str(OUT_DIR / "bounded_decoder_probe"),
            "--run-id",
            "stage10728_semantic_contrast_probe",
        ],
        "frontload_audit": {
            "frontloaded_prefix_length": len(frontloaded),
            "frontloaded_row_ids": frontload_ids,
            "train_rows": len(train_rows),
            "batch_size": 2,
            "max_steps": 192,
            "sample_budget": 384,
        },
        "headline_findings": [
            "This request adds both Python verifier semantic-contrast support and Rust citation semantic-contrast support to the execution-repaired train split.",
            "The frontloaded prefix includes all promotable Python semantic verifier rows, the reviewed Rust flash-attn semantic contrast row, and both honesty-only abstention rows.",
            "The sample budget now exceeds the full train split, so a repeat of the stage10719 unsampled-support failure mode should be impossible.",
        ],
        "known_limits": [
            "The strict frontier remains only 24 rows.",
            "Python and Rust are still under-scaled relative to the six-fresh-root target in stage10724.",
            "Any observed improvement remains train-side until fresh heldout roots are replenished and evaluated.",
        ],
        "next_best_step": "Run this request, then compare against stage10721 on the repaired overlay and inspect whether Python B-vs-C or Rust E-vs-F finally move without regressions.",
        "outputs": {
            "manifest_jsonl": display(MANIFEST_JSONL),
            "request_json": display(REQUEST_JSON),
        },
    }

    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "frontloaded_prefix_length": request["frontload_audit"]["frontloaded_prefix_length"],
            "artifact": display(REQUEST_JSON),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
