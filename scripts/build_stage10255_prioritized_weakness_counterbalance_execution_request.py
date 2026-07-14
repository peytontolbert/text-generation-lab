#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10255
NAME = "stage10255_prioritized_weakness_counterbalance_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "prioritized_weakness_counterbalance_execution_request.json"
COMMAND_JSON = OUT_DIR / "prioritized_weakness_counterbalance_command.json"
MANIFEST = OUT_DIR / "prioritized_weakness_counterbalance_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE = ROOT / "runs/local/artifacts/stage10252_weakness_counterbalance_successor_package/weakness_counterbalance_successor_package.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10256_prioritized_weakness_counterbalance_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10256_prioritized_weakness_counterbalance_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10256_prioritized_weakness_counterbalance_probe/runtime_model"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10224_bundle_coherence_counterbalance_probe/runtime_model/runtime_model_bundle.json"
MAX_STEPS = 12
LEARNING_RATE = "8e-6"


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


def prioritized_train_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    replenishment = [row for row in rows if bool((row.get("anti_cheat") or {}).get("replenishment_train_only"))]
    rest = [row for row in rows if not bool((row.get("anti_cheat") or {}).get("replenishment_train_only"))]
    out: list[dict[str, Any]] = []
    if not replenishment:
        return rows
    while replenishment or rest:
        if replenishment:
            out.append(replenishment.pop(0))
        if replenishment:
            out.append(replenishment.pop(0))
        if rest:
            out.append(rest.pop(0))
    return out


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
    train = load_jsonl(ROOT / str(package.get("train_dataset_path") or ""))
    strict_eval = load_jsonl(ROOT / str(package.get("eval_dataset_path") or ""))
    ordered_train = prioritized_train_rows(train)
    rows = ordered_train + strict_eval
    write_jsonl(MANIFEST, rows)

    split_counts = {"train": len(ordered_train), "eval": 0, "strict_eval": len(strict_eval), "other": 0}
    first_train_row_ids = [str(row.get("row_id") or "") for row in ordered_train[:12]]
    first_window_replenishment = sum(1 for row in ordered_train[:24] if bool((row.get("anti_cheat") or {}).get("replenishment_train_only")))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_package": display(PACKAGE),
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "split_counts": split_counts,
        "max_steps": MAX_STEPS,
        "learning_rate": LEARNING_RATE,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
        "ordering_strategy": "frontload_replenishment_rows_into_first_step_window",
        "first_train_row_ids": first_train_row_ids,
        "replenishment_rows_in_first_24_train_examples": first_window_replenishment,
        "command": command(split_counts),
        "required_honesty_gates": [
            "exact stage10242 miss rows remain strict-eval holdout only",
            "prioritization changes exposure order only; it does not add heldout rows into train",
            "web miss families remain uncovered and should not be interpreted as repaired by this probe",
        ],
    }
    write_json(REQUEST, payload)
    write_json(COMMAND_JSON, {"command": payload["command"], "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(SUMMARY, {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "request": display(REQUEST),
        "manifest": display(MANIFEST),
        "rows": len(rows),
        "replenishment_rows_in_first_24_train_examples": first_window_replenishment,
    })
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_request()
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "request": display(REQUEST),
        "manifest": display(MANIFEST),
        "replenishment_rows_in_first_24_train_examples": payload["replenishment_rows_in_first_24_train_examples"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
