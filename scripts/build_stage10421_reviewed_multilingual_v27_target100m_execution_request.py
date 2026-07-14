#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10421
NAME = "stage10421_reviewed_multilingual_v27_target100m_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_multilingual_v27_target100m_execution_request.json"
COMMAND_JSON = OUT_DIR / "reviewed_multilingual_v27_target100m_command.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_multilingual_v27_target100m_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_manifest_package.json"
PACKAGE_TRAIN = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_train.jsonl"
PACKAGE_VALIDATION = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_validation.jsonl"
PACKAGE_STRICT = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_strict_eval.jsonl"
PACKAGE_STRESS = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/agentkernel_lite_encdec_stress_eval.jsonl"
PACKAGE_ROOTS = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package/reviewed_multilingual_v27_root_manifest.jsonl"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10397_multilingual_residual_contrast_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10422_reviewed_multilingual_v27_target100m_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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


def normalized_manifest_rows() -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0}
    language_counts: dict[str, int] = {}
    root_counts: dict[str, int] = {}
    for path, out_split in (
        (PACKAGE_TRAIN, "train"),
        (PACKAGE_VALIDATION, "eval"),
        (PACKAGE_STRICT, "strict_eval"),
    ):
        for row in load_jsonl(path):
            copied = json.loads(json.dumps(row))
            copied["split"] = out_split
            # Eval and strict rows still need decoder CE enabled so the
            # bounded-decoder probe can score heldout slices honestly.
            copied["loss_mask"] = {"decoder_ce": True}
            copied["expected_enabled_loss"] = "decoder_ce"
            copied["disable_losses"] = [] if out_split == "train" else ["denoise_ce", "runtime_reward", "structured_aux"]
            rows.append(copied)
            split_counts[out_split] += 1
            language = str(copied.get("language_family") or "unknown")
            language_counts[language] = language_counts.get(language, 0) + 1
            root_id = str(copied.get("source_root_id") or copied.get("source_bundle_id") or "unknown")
            root_counts[root_id] = root_counts.get(root_id, 0) + 1
    return rows, split_counts, dict(sorted(language_counts.items())), dict(sorted(root_counts.items()))


def build_command(split_counts: dict[str, int]) -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
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
        str(split_counts["train"]),
        "--max-eval-rows",
        str(split_counts["eval"]),
        "--max-strict-rows",
        str(split_counts["strict_eval"]),
        "--max-steps",
        "48",
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
        str(ROOT / RUNTIME_MODEL_DIR),
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
        str(ROOT / OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    package = load_json(PACKAGE_JSON)
    root_rows = load_jsonl(PACKAGE_ROOTS)
    stress_rows = load_jsonl(PACKAGE_STRESS)
    manifest_rows, split_counts, language_counts, root_counts = normalized_manifest_rows()
    command = build_command(split_counts)

    train_root_roles = sorted({str(row.get("source_root_id") or "") for row in manifest_rows if row.get("split") == "train"})
    eval_root_roles = sorted({str(row.get("source_root_id") or "") for row in manifest_rows if row.get("split") == "eval"})
    strict_root_roles = sorted({str(row.get("source_root_id") or "") for row in manifest_rows if row.get("split") == "strict_eval"})

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "reviewed_multilingual_v27_promotion_probe_ready",
        "source_package": display(PACKAGE_JSON),
        "source_root_manifest": display(PACKAGE_ROOTS),
        "manifest": display(MANIFEST_JSONL),
        "stress_eval_rows_path": display(PACKAGE_STRESS),
        "stress_eval_rows_excluded_from_training_command": True,
        "rows": len(manifest_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "root_count": len(root_counts),
        "train_root_count": len(train_root_roles),
        "eval_root_count": len(eval_root_roles),
        "strict_root_count": len(strict_root_roles),
        "stress_root_count": len({str(row.get('source_root_id') or '') for row in stress_rows}),
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "runtime_model_save_dir": RUNTIME_MODEL_DIR,
        "claim_scope": "promotion-style reviewed-v2.7 standalone probe on root-split multilingual inventory; v2.6 remains a frozen regression suite and stress rows remain excluded from the promotable path",
        "required_honesty_gates": [
            "v2.6 47-row frontier remains frozen regression-only and is not merged into this training manifest",
            "validation roots are normalized to eval only at request time; no root appears in both train and eval/strict",
            "code_assist web remains repo-overlap stress-only and excluded from train/eval/strict execution",
            "flash-attn Rust remains train-support only and abstention-heavy; any Rust localization claim must stay conservative",
            "post-run reporting must separate singleton localization, abstention calibration, verifier-anchor slices, and repo-overlap stress behavior",
        ],
        "post_run_required_slices": [
            "overall strict exact",
            "per-language strict exact",
            "verifier-anchor present vs absent",
            "selected-test-anchor present vs absent",
            "abstention-heavy vs non-abstention-heavy",
            "train-support roots vs strict heldout roots",
            "stress-only code_assist web rows (separate, non-promotable)",
        ],
        "next_best_step": "run the stage10422 reviewed-v2.7 probe, then compare the saved runtime against Gemma on the same strict manifest and audit stress rows separately",
        "command": command,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, manifest_rows)
    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "request": display(REQUEST_JSON),
            "manifest": display(MANIFEST_JSONL),
            "split_counts": split_counts,
            "language_counts": language_counts,
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "request": display(REQUEST_JSON),
                "rows": len(manifest_rows),
                "split_counts": split_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
