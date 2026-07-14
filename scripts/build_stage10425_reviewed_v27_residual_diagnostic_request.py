#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10425
NAME = "stage10425_reviewed_v27_residual_diagnostic_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "reviewed_v27_residual_diagnostic_request.json"
MANIFEST_JSONL = OUT_DIR / "reviewed_v27_residual_diagnostic_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10421_reviewed_multilingual_v27_target100m_execution_request/reviewed_multilingual_v27_target100m_manifest.jsonl"
COMPARISON_ROWS = ROOT / "runs/local/artifacts/stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl"
BASE_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"

RUN_ID = "stage10426_reviewed_v27_residual_diagnostic_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts" / RUN_ID / "bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts" / RUN_ID / "runtime_model"


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


def main() -> None:
    base_rows = load_jsonl(BASE_MANIFEST)
    base_by_id = {str(row.get("row_id") or ""): row for row in base_rows}
    comparison_rows = load_jsonl(COMPARISON_ROWS)

    target_miss_ids = [
        str(row.get("row_id") or "")
        for row in comparison_rows
        if (row.get("hundred_m_correct") is False)
    ]
    target_miss_ids.sort()

    if len(target_miss_ids) != 2:
        raise SystemExit(f"expected 2 residual 100M miss rows, found {len(target_miss_ids)}")

    diagnostic_rows: list[dict[str, Any]] = list(base_rows)
    replay_rows: list[dict[str, Any]] = []
    for row_id in target_miss_ids:
        source = dict(base_by_id[row_id])
        replay = dict(source)
        replay["row_id"] = f"{row_id}::diagnostic_train_replay"
        replay["split"] = "train"
        replay["split_role"] = "diagnostic_same_surface_train"
        replay["train_support_only"] = True
        replay["strict_eval_eligible"] = False
        replay["same_surface_diagnostic_support"] = True
        replay["promotion_candidate"] = False
        replay["diagnostic_parent_row_id"] = row_id
        replay_rows.append(replay)
    diagnostic_rows.extend(replay_rows)
    write_jsonl(MANIFEST_JSONL, diagnostic_rows)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "Materialized a narrow non-promotable residual diagnostic request that replays only the two remaining strict reviewed-v2.7 miss rows into train while preserving the original eval and strict splits for regression tracking.",
        "claim_scope": "diagnostic_only_non_promotable_same_surface_support",
        "initialize_from_runtime_model": display(BASE_RUNTIME),
        "manifest": display(MANIFEST_JSONL),
        "rows": len(diagnostic_rows),
        "split_counts": {
            "train": sum(1 for row in diagnostic_rows if str(row.get("split") or "") == "train"),
            "eval": sum(1 for row in diagnostic_rows if str(row.get("split") or "") == "eval"),
            "strict_eval": sum(1 for row in diagnostic_rows if str(row.get("split") or "") == "strict_eval"),
        },
        "target_miss_row_ids": target_miss_ids,
        "diagnostic_replay_rows": [str(row.get("row_id") or "") for row in replay_rows],
        "success_criteria": [
            "At least one of the two residual strict miss rows flips to correct.",
            "No more than one new strict regression is introduced.",
            "The run is reported as non-promotable because it uses same-surface diagnostic support.",
        ],
        "required_honesty_gates": [
            "This request must not be used to upgrade the main reviewed-v2.7 claim path.",
            "The two replay rows are exact same-surface diagnostic support and make the run non-promotable by design.",
            "The original stage10423 same-manifest result remains the honest promotable baseline for reviewed-v2.7.",
        ],
        "command": [
            "env",
            "TMPDIR=/data/tmp",
            "TEMP=/data/tmp",
            "TMP=/data/tmp",
            "conda",
            "run",
            "-n",
            "trellis",
            "python",
            str((ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py").resolve()),
            "--repo-root",
            str(ROOT),
            "--manifest",
            str(MANIFEST_JSONL.resolve()),
            "--mode",
            "bounded_decoder_ce_probe",
            "--probe-scale",
            "target_100m",
            "--implementation",
            "transformer",
            "--model-config",
            str((ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json").resolve()),
            "--tokenizer-json",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json").resolve()),
            "--tokenizer-config",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json").resolve()),
            "--tokenizer-hashlock",
            str((ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json").resolve()),
            "--execution-authorized-for-recovery-probe",
            "--max-train-rows",
            "11",
            "--max-eval-rows",
            "24",
            "--max-strict-rows",
            "24",
            "--max-steps",
            "16",
            "--batch-size",
            "2",
            "--learning-rate",
            "4e-6",
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
            str(RUNTIME_MODEL_DIR.resolve()),
            "--initialize-from-runtime-model",
            str(BASE_RUNTIME.resolve()),
            "--preservation-reference-runtime-model",
            str(BASE_RUNTIME.resolve()),
            "--preservation-kl-weight",
            "2.0",
            "--no-final-checkpoint-export",
            "--skip-final-model-save",
            "1",
            "--output-dir",
            str(OUTPUT_DIR.resolve()),
            "--run-id",
            RUN_ID,
        ],
        "next_best_step": "Run the stage10426 diagnostic probe only if you want to test whether the final two misses are directly recoverable; keep any positive result separate from the promotable reviewed-v2.7 headline.",
    }

    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "artifacts": {"request": display(REQUEST_JSON), "manifest": display(MANIFEST_JSONL)},
            "decision": request["decision"],
            "next_best_step": request["next_best_step"],
            "created_at_utc": request["created_at_utc"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
