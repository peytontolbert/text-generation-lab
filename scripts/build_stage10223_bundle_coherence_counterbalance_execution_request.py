#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10223
NAME = "stage10223_bundle_coherence_counterbalance_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "bundle_coherence_counterbalance_execution_request.json"
COMMAND_JSON = OUT_DIR / "bundle_coherence_counterbalance_command.json"
MANIFEST = OUT_DIR / "bundle_coherence_counterbalance_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PACKAGE = ROOT / "runs/local/artifacts/stage10222_bundle_coherence_counterbalance_package/bundle_coherence_counterbalance_package.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
RUN_ID = "stage10224_bundle_coherence_counterbalance_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10215_python_contrast_counterbalance_probe/runtime_model/runtime_model_bundle.json"
MAX_STEPS = 16
LEARNING_RATE = "1e-5"


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def merged_rows(package: dict[str, Any]) -> list[dict[str, Any]]:
    train = load_jsonl(ROOT / str(package.get("train_dataset_path") or ""))
    strict_eval = load_jsonl(ROOT / str(package.get("eval_dataset_path") or ""))
    return train + strict_eval


def command(split_counts: dict[str, int]) -> list[str]:
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
        str(MANIFEST),
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
        str(split_counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(split_counts.get("strict_eval", 0)),
        "--max-steps",
        str(MAX_STEPS),
        "--batch-size",
        "2",
        "--learning-rate",
        LEARNING_RATE,
        "--max-encoder-tokens",
        "768",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.25",
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
        "16",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(ROOT / OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def build_request() -> dict[str, Any]:
    package = load_json(PACKAGE)
    rows = merged_rows(package)
    write_jsonl(MANIFEST, rows)
    split_counts = {"train": 0, "eval": 0, "strict_eval": 0, "other": 0}
    language_counts: dict[str, int] = {}
    for row in rows:
        split = str(row.get("split") or "")
        split_counts[split if split in split_counts else "other"] += 1
        language = str(row.get("language_family") or "")
        language_counts[language] = language_counts.get(language, 0) + 1
    cmd = command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_package": display(PACKAGE),
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "split_counts": split_counts,
        "language_counts": dict(sorted(language_counts.items())),
        "max_steps": MAX_STEPS,
        "learning_rate": LEARNING_RATE,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "command": cmd,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
        "request_status": "warm_start_execution_ready",
        "artifact_purpose": "warm-started bundle-coherence counterbalance probe layered on the stage10213 frontier",
        "required_honesty_gates": [
            "strict eval rows must remain identical to stage10213, stage10200, and stage10149",
            "bundle-coherence counterbalance rows remain train-only and auxiliary",
            "unsupported reviewed failure families remain evaluation-only",
            "stage10142 standalone decoder contract audit remains binding for any score claim",
        ],
    }
    REQUEST.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": cmd, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST), "manifest": display(MANIFEST), "rows": len(rows), "split_counts": split_counts, "language_counts": dict(sorted(language_counts.items())), "max_steps": MAX_STEPS, "initialize_from_runtime_model": display(INIT_RUNTIME)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    request = build_request()
    print(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST), "manifest": display(MANIFEST), "rows": request["rows"], "max_steps": MAX_STEPS, "initialize_from_runtime_model": display(INIT_RUNTIME)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
