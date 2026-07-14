#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10369
NAME = "stage10369_honest_frontier_diagnostic_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "honest_frontier_diagnostic_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "honest_frontier_diagnostic_execution_request.json"
COMMAND_JSON = OUT_DIR / "honest_frontier_diagnostic_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

RUNTIME_SUMMARY = ROOT / "runs/local/artifacts/stage10367_quarantined_full_visible_runtime_inference/first_wave_bundle_inference_summary.json"
PAYLOAD = ROOT / "runs/local/artifacts/stage10366_quarantined_full_visible_runtime_payload/quarantined_full_visible_runtime_payload.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10359_anchored_citation_plus_pythonverifier_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10370_honest_frontier_diagnostic_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10370_honest_frontier_diagnostic_probe/bounded_decoder_probe"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def rotate(values: list[Any], shift: int) -> list[Any]:
    return values[shift:] + values[:shift]


def strict_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in payload.get("runs") or []:
        task_pack = run.get("task_pack") or {}
        for row in task_pack.get("rows") or []:
            if isinstance(row, dict):
                copy = json.loads(json.dumps(row))
                copy["split"] = "strict_eval"
                target_text = str(copy.get("target_text") or "")
                copy["decoder_text"] = target_text
                copy["target_token_len"] = len(target_text.encode("utf-8"))
                copy["loss_mask"] = {"decoder_ce": True}
                copy["expected_enabled_loss"] = "decoder_ce"
                copy["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
                projection = dict(copy.get("standalone_projection_source") or {})
                if not projection.get("opaque_options") and copy.get("opaque_options"):
                    projection["opaque_options"] = copy.get("opaque_options")
                copy["standalone_projection_source"] = projection
                rows.append(copy)
    return rows


def weak_rows(runtime_summary: dict[str, Any]) -> list[dict[str, Any]]:
    misses = []
    for result in runtime_summary.get("results") or []:
        adapter_payload = ROOT / str(result.get("adapter_payload") or "")
        bundle_predictions = adapter_payload.with_name("bundle_predictions.json")
        if not bundle_predictions.exists():
            continue
        pred_data = load_json(bundle_predictions)
        for row in pred_data.get("hundred_m") or []:
            if row.get("correct") is False:
                misses.append(row)
    return misses


def clone_train_row(base_row: dict[str, Any], *, stage_prefix: str, repeat_idx: int, perm_idx: int) -> dict[str, Any]:
    clone = json.loads(json.dumps(base_row))
    options = [item for item in (clone.get("opaque_options") or []) if isinstance(item, dict)]
    rotated = rotate(options, perm_idx)
    target_value = str(clone.get("gold_value") or "")
    target_label = ""
    for item in rotated:
        if str(item.get("value") or "") == target_value:
            target_label = str(item.get("label") or "")
            break
    if not target_label:
        raise ValueError(f"missing_target_label::{clone.get('row_id')}")
    clone["row_id"] = f"{stage_prefix}::{base_row['row_id']}::repeat_{repeat_idx:02d}::perm_{perm_idx:02d}"
    clone["semantic_key"] = f"{stage_prefix}::{base_row.get('row_id')}::perm_{perm_idx:02d}"
    clone["split"] = "train"
    clone["target_text"] = target_label
    clone["decoder_text"] = target_label
    clone["target_token_len"] = len(target_label.encode("utf-8"))
    clone["loss_mask"] = {"decoder_ce": True}
    clone["expected_enabled_loss"] = "decoder_ce"
    clone["disable_losses"] = []
    clone["query_text"] = f"{base_row.get('query_text','honest_frontier')}::diagnostic::{repeat_idx:02d}::{perm_idx:02d}"
    clone["opaque_options"] = rotated
    clone["standalone_projection_source"] = dict(clone.get("standalone_projection_source") or {})
    clone["standalone_projection_source"]["opaque_options"] = rotated
    claim = clone["standalone_projection_source"].setdefault("claim_boundary", {})
    claim["diagnostic_same_surface_train_only"] = True
    claim["same_surface_eval_admissible"] = False
    anti = clone.setdefault("anti_cheat", {})
    anti["diagnostic_same_surface_train_only"] = True
    anti["non_promotable_until_disjoint_rebuild"] = True
    auth = clone.setdefault("authority", {})
    auth["promotion_ready"] = False
    auth["model_execution_authorized_next"] = False
    return clone


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
        str(split_counts.get("train", 0)),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(split_counts.get("strict_eval", 0)),
        "--max-steps",
        "12",
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
        "8",
        "--max-generation-tokens",
        "8",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "2.0",
        "--output-dir",
        OUTPUT_DIR,
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    payload = load_json(PAYLOAD)
    runtime = load_json(RUNTIME_SUMMARY)
    strict_rows = strict_rows_from_payload(payload)
    strict_by_id = {str(row.get("row_id") or ""): row for row in strict_rows}
    miss_rows = weak_rows(runtime)
    selected_ids = [str(row.get("row_id") or "") for row in miss_rows]
    train_rows: list[dict[str, Any]] = []
    for row_id in selected_ids:
        base = strict_by_id[row_id]
        option_count = len(base.get("opaque_options") or [])
        for repeat_idx in range(2):
            for perm_idx in range(option_count):
                train_rows.append(
                    clone_train_row(
                        base,
                        stage_prefix="stage10369_diagnostic",
                        repeat_idx=repeat_idx,
                        perm_idx=perm_idx,
                    )
                )

    combined_rows = train_rows + strict_rows
    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for row in combined_rows:
        split = str(row.get("split") or "unknown")
        split_counts[split] = split_counts.get(split, 0) + 1
        lang = str(row.get("language_family") or "unknown")
        language_counts[lang] = language_counts.get(lang, 0) + 1
    command = build_command(split_counts)
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "honest_frontier_same_surface_diagnostic_ready",
        "manifest": display(MANIFEST_JSONL),
        "source_runtime_summary": display(RUNTIME_SUMMARY),
        "source_payload": display(PAYLOAD),
        "rows": len(combined_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "diagnostic_target_rows": selected_ids,
        "frontloaded_support_rows": len(train_rows),
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "required_honesty_gates": [
            "non-promotable diagnostic only because train rows clone same-surface honest eval structure",
            "success means at least one of the five honest misses flips to correct without giving back python verifier correctness on the repaired surface",
            "any gain must be rebuilt from disjoint roots before promotion",
        ],
        "next_best_step": "run one short diagnostic probe to test whether the saved bounded-choice runtime can escape the remaining honest misses at all",
        "command": command,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(MANIFEST_JSONL, combined_rows)
    write_json(COMMAND_JSON, {"command": command})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "request": display(REQUEST_JSON)})
    print(json.dumps({"stage": STAGE, "passed": True, "request": display(REQUEST_JSON), "train_rows": len(train_rows), "strict_rows": len(strict_rows)}, indent=2))


if __name__ == "__main__":
    main()
