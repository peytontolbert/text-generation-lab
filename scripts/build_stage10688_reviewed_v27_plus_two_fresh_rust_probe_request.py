#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10688
NAME = "stage10688_reviewed_v27_plus_two_fresh_rust_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_v27_plus_two_fresh_rust_probe_manifest.jsonl"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_support_package.json"
TRAIN_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/agentkernel_lite_encdec_train.jsonl"
STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10684_reviewed_v27_plus_linux_rust_probe_audit/reviewed_v27_plus_linux_rust_probe_audit.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10683_reviewed_v27_plus_linux_rust_probe/runtime_model/runtime_model_bundle.json"

TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10689_reviewed_v27_plus_two_fresh_rust_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10689_reviewed_v27_plus_two_fresh_rust_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10689_reviewed_v27_plus_two_fresh_rust_probe/runtime_model"


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


def normalized_strict_rows() -> list[dict[str, Any]]:
    rows = []
    for row in load_jsonl(STRICT_ROWS_JSONL):
        updated = dict(row)
        updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        rows.append(updated)
    return rows


def build_command(train_count: int, strict_count: int) -> list[str]:
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
        "0",
        "--max-strict-rows",
        str(strict_count),
        "--max-steps",
        "24",
        "--batch-size",
        "2",
        "--learning-rate",
        "6e-6",
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
        str(RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    package = load_json(PACKAGE_JSON)
    baseline = load_json(BASELINE_AUDIT)
    train_rows = load_jsonl(TRAIN_ROWS_JSONL)
    strict_rows = normalized_strict_rows()
    manifest_rows = train_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    train_language_counts: dict[str, int] = {}
    rust_support_rows = []
    for row in train_rows:
        lang = str(row.get("language_family") or "unknown")
        train_language_counts[lang] = train_language_counts.get(lang, 0) + 1
        if lang == "rust":
            rust_support_rows.append(str(row.get("row_id") or ""))

    command = build_command(len(train_rows), len(strict_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_rows) and INIT_RUNTIME.exists(),
        "decision": "reviewed_v27_plus_two_fresh_rust_support_probe_ready",
        "claim_scope": [
            "Support-only probe from the preserved 22/24 reviewed v2.7 runtime after adding a second fresh Rust support root.",
            "Keep the strict 24-row reviewed multilingual set unchanged and test whether broader Rust support finally moves the frontier.",
        ],
        "source_artifacts": {
            "extended_support_package": display(PACKAGE_JSON),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "initialize_runtime_model": display(INIT_RUNTIME),
            "baseline_audit": display(BASELINE_AUDIT),
        },
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "strict_eval": len(strict_rows),
        },
        "train_language_counts": dict(sorted(train_language_counts.items())),
        "rust_support_rows": rust_support_rows,
        "promotion_gate": {
            "baseline_strict_accuracy": ((baseline.get("headline") or {}).get("current_hundred_m_strict_accuracy")),
            "require_strict_accuracy_gt_baseline": True,
            "require_zero_new_regressions": True,
            "strict_rows_unchanged": True,
        },
        "success_criteria": [
            "Strict constrained accuracy exceeds the preserved 22/24 reviewed v2.7 baseline.",
            "No new strict regressions appear on the unchanged 24-row multilingual strict set.",
            "If flat again, keep both new Rust roots as support-only inventory and stop treating same-size support probes as likely lift paths.",
        ],
        "required_honesty_gates": [
            "Both fresh Rust roots remain train-support-only.",
            "The source-derived candle-datasets verifier packet must not be upgraded into same-surface comparison evidence.",
            "Any improvement claim must come from the unchanged 24-row strict set.",
        ],
        "manifest": display(MANIFEST_JSONL),
        "command": command,
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    }
    write_json(REQUEST_JSON, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
