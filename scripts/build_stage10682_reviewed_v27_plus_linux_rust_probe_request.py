#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10682
NAME = "stage10682_reviewed_v27_plus_linux_rust_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_v27_plus_linux_rust_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_v27_plus_linux_rust_probe_manifest.jsonl"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/reviewed_v27_plus_linux_rust_train_support_package.json"
TRAIN_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_train.jsonl"
STRICT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10681_reviewed_v27_plus_linux_rust_train_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage10672_dual_residual_targeted_probe_audit/dual_residual_targeted_probe_audit.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10671_dual_residual_targeted_probe/runtime_model/runtime_model_bundle.json"

TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10683_reviewed_v27_plus_linux_rust_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10683_reviewed_v27_plus_linux_rust_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10683_reviewed_v27_plus_linux_rust_probe/runtime_model"


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
    train_task_counts: dict[str, int] = {}
    added_linux_rows = []
    for row in train_rows:
        lang = str(row.get("language_family") or "unknown")
        task = str(row.get("task_type") or "unknown")
        train_language_counts[lang] = train_language_counts.get(lang, 0) + 1
        train_task_counts[task] = train_task_counts.get(task, 0) + 1
        if str(row.get("source_bundle_id") or "") == "stage10674::linux::rust":
            added_linux_rows.append(str(row.get("row_id") or ""))

    command = build_command(len(train_rows), len(strict_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(train_rows) and bool(strict_rows) and INIT_RUNTIME.exists(),
        "decision": "reviewed_v27_plus_linux_rust_support_probe_ready",
        "claim_scope": [
            "Support-only probe from the latest preserved 22/24 reviewed v2.7 runtime.",
            "Extend training with the newly admitted Linux Rust ACPI support root while keeping the reviewed 24-row strict set unchanged.",
            "Test whether added fresh Rust source-backed support improves multilingual strict behavior without any regression.",
        ],
        "source_artifacts": {
            "extended_support_package": display(PACKAGE_JSON),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "initialize_runtime_model": display(INIT_RUNTIME),
            "baseline_strict_audit": display(BASELINE_AUDIT),
        },
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(train_rows),
            "strict_eval": len(strict_rows),
        },
        "train_language_counts": dict(sorted(train_language_counts.items())),
        "train_task_counts": dict(sorted(train_task_counts.items())),
        "fresh_support_focus": {
            "added_root_id": "stage10674::linux::rust",
            "added_linux_train_rows": added_linux_rows,
            "selected_test_anchor": "samples/rust/rust_driver_platform.rs",
            "same_surface_eval_admissible": False,
            "train_support_only": True,
        },
        "strict_baseline_reference": {
            "baseline_hundred_m_strict_accuracy": ((baseline.get("headline") or {}).get("baseline_hundred_m_strict_accuracy")),
            "baseline_gemma_strict_accuracy": ((baseline.get("headline") or {}).get("baseline_gemma_strict_accuracy")),
            "baseline_strict_rows": (((baseline.get("package_effect") or {}).get("strict_rows")) or len(strict_rows)),
            "remaining_miss_row_ids": (((baseline.get("strict_eval_result") or {}).get("miss_summary")) or {}).get("miss_row_ids"),
        },
        "manifest": display(MANIFEST_JSONL),
        "command": command,
        "promotion_gate": {
            "require_strict_accuracy_gt_baseline": True,
            "baseline_strict_accuracy": ((baseline.get("headline") or {}).get("baseline_hundred_m_strict_accuracy")),
            "require_zero_new_regressions": True,
            "strict_rows_unchanged_from_stage10423": True,
            "keep_claim_train_support_only_if_flat": True,
        },
        "success_criteria": [
            "Strict constrained accuracy exceeds the preserved 22/24 reviewed v2.7 baseline.",
            "No new strict regressions appear on the unchanged 24-row multilingual strict set.",
            "If the score stays flat, the run remains diagnostic/support-only and does not change the stage10423 headline claim.",
        ],
        "required_honesty_gates": [
            "The six new Linux Rust rows remain train-support-only and do not enter strict or stress evaluation.",
            "Any reported improvement must come from the unchanged 24-row strict set, not from a changed eval package.",
            "No claim may upgrade Linux Rust support rows into same-surface comparison evidence without a second independent verifier-anchored Rust root.",
        ],
        "outputs": {
            "request_json": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
        },
    }
    write_json(REQUEST_JSON, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
