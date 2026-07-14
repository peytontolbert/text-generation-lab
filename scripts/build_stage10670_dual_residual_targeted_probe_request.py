#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10670
NAME = "stage10670_dual_residual_targeted_probe_request"
OUT_DIR = ARTIFACTS / NAME
REQUEST_JSON = OUT_DIR / "dual_residual_targeted_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "dual_residual_targeted_probe_manifest.jsonl"
COMMAND_JSON = OUT_DIR / "dual_residual_targeted_probe_command.json"

PACKAGE_JSON = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/dual_residual_targeted_support_package.json"
TRAIN_ROWS = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/train_rows.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/validation_rows.jsonl"
STRICT_ROWS = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/strict_rows.jsonl"
STRESS_ROWS = ARTIFACTS / "stage10669_dual_residual_targeted_support_package/stress_rows.jsonl"

INIT_RUNTIME = ARTIFACTS / "stage10397_multilingual_residual_contrast_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10671_dual_residual_targeted_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10671_dual_residual_targeted_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10671_dual_residual_targeted_probe/runtime_model"


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


def with_probe_fields(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["disable_losses"] = [] if split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"]
    return updated


def build_command(train_count: int, eval_count: int, strict_count: int) -> list[str]:
    return [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis",
        "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(train_count),
        "--max-eval-rows", str(eval_count),
        "--max-strict-rows", str(strict_count),
        "--max-steps", "64",
        "--batch-size", "2",
        "--learning-rate", "6e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--preservation-kl-weight", "2.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = [with_probe_fields(row, "train") for row in load_jsonl(TRAIN_ROWS)]
    eval_rows = [with_probe_fields(row, "eval") for row in load_jsonl(VALIDATION_ROWS)]
    strict_rows = [with_probe_fields(row, "strict_eval") for row in load_jsonl(STRICT_ROWS)]
    stress_rows = load_jsonl(STRESS_ROWS)

    manifest_rows = [*train_rows, *eval_rows, *strict_rows]
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    command = build_command(len(train_rows), len(eval_rows), len(strict_rows))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "dual_residual_targeted_probe_ready",
        "source_package": rel(PACKAGE_JSON),
        "manifest": rel(MANIFEST_JSONL),
        "rows": len(manifest_rows),
        "split_counts": {"train": len(train_rows), "eval": len(eval_rows), "strict_eval": len(strict_rows)},
        "language_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("language_family") or "unknown") for row in strict_rows).items())),
        },
        "source_kind_counts_by_split": {
            "train": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in train_rows).items())),
            "eval": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("package_source_kind") or "unknown") for row in strict_rows).items())),
        },
        "stress_rows_excluded_from_manifest": len(stress_rows),
        "claim_scope": [
            "Run a narrower probe aimed directly at the remaining Python verifier and Rust citation residual families.",
            "Keep the reviewed v2.7 strict surface fixed while replacing broad support with dual-residual targeted support.",
        ],
        "required_honesty_gates": [
            "strict and validation rows remain unchanged from the reviewed v2.7 package",
            "support rows come only from promotable disjoint Python roots plus reviewed Rust flash-attn support",
            "stress overlap rows remain excluded",
            "any improvement must still beat 22/24 with zero regressions before promotion",
        ],
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_save_dir": RUNTIME_MODEL_DIR,
        "command": command,
        "next_best_step": "run the targeted probe and inspect whether the Python verifier miss flips while the Rust miss and other language slices remain stable",
    }

    write_json(REQUEST_JSON, payload)
    write_json(COMMAND_JSON, {"command": command})
    print(REQUEST_JSON)


if __name__ == "__main__":
    main()
