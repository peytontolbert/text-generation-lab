#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10325
NAME = "stage10325_retrieval_hard_negative_pair_scored_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY_JSON = OUT_DIR / "retrieval_hard_negative_pair_inventory.json"
MANIFEST_JSONL = OUT_DIR / "retrieval_hard_negative_pair_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "retrieval_hard_negative_pair_execution_request.json"
COMMAND_JSON = OUT_DIR / "retrieval_hard_negative_pair_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10326_retrieval_hard_negative_pair_scored_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10326_retrieval_hard_negative_pair_scored_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10326_retrieval_hard_negative_pair_scored_probe/runtime_model"
LEARNING_RATE = "8e-6"
BATCH_SIZE = 2
MAX_ENCODER_TOKENS = 896

FOCUS = {
    ("python", "symptom_localization"),
    ("python", "patch_impact"),
    ("python", "minimal_fix_selection"),
    ("python", "verifier_outcome"),
    ("web_js_ts_html", "symptom_localization"),
    ("web_js_ts_html", "patch_impact"),
    ("web_js_ts_html", "minimal_fix_selection"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
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


def prompt_prefix(prompt_text: str) -> str:
    marker = "\nOptions:\n"
    if marker in prompt_text:
        return prompt_text.split(marker, 1)[0].rstrip()
    return prompt_text.rstrip()


def option_similarity(gold_value: str, distractor_value: str) -> tuple[int, int, int, str]:
    gold_path = gold_value.strip()
    distractor_path = distractor_value.strip()
    gold_parts = [part for part in gold_path.split("/") if part]
    distractor_parts = [part for part in distractor_path.split("/") if part]
    same_dir = int(len(gold_parts) > 1 and len(distractor_parts) > 1 and gold_parts[:-1] == distractor_parts[:-1])
    gold_ext = gold_parts[-1].split(".")[-1] if gold_parts and "." in gold_parts[-1] else ""
    distractor_ext = distractor_parts[-1].split(".")[-1] if distractor_parts and "." in distractor_parts[-1] else ""
    same_ext = int(bool(gold_ext) and gold_ext == distractor_ext)
    gold_stem_tokens = set((gold_parts[-1].replace(".", "_").split("_")) if gold_parts else [])
    distractor_stem_tokens = set((distractor_parts[-1].replace(".", "_").split("_")) if distractor_parts else [])
    token_overlap = len({tok for tok in gold_stem_tokens & distractor_stem_tokens if tok})
    return same_dir, same_ext, token_overlap, distractor_path


def best_distractor(options: list[dict[str, str]], gold_value: str) -> dict[str, str] | None:
    distractors = [option for option in options if str(option.get("value") or "") != gold_value]
    if not distractors:
        return None
    return max(
        distractors,
        key=lambda option: option_similarity(gold_value, str(option.get("value") or "")),
    )


def pair_prompt(base_prompt: str, left_value: str, right_value: str) -> str:
    prefix = prompt_prefix(base_prompt)
    return (
        prefix
        + "\nOptions:\n"
        + f"A. {left_value}\n"
        + f"B. {right_value}\n"
        + "Answer:\n"
    )


def build_pair_rows(base_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    new_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for row in base_rows:
        if row.get("split") != "train":
            continue
        key = (str(row.get("language_family") or ""), str(row.get("task_type") or ""))
        if key not in FOCUS:
            continue
        if row.get("surface") != "maintainer_bundle_compact_bounded_choice":
            continue
        projection = row.get("standalone_projection_source") or {}
        options = [option for option in (projection.get("opaque_options") or []) if isinstance(option, dict)]
        gold_value = str(projection.get("gold_value") or "").strip()
        if len(options) < 2 or not gold_value:
            continue
        distractor = best_distractor(options, gold_value)
        if distractor is None:
            continue
        distractor_value = str(distractor.get("value") or "").strip()
        inventory_rows.append({
            "row_id": row.get("row_id"),
            "language_family": key[0],
            "task_type": key[1],
            "gold_value": gold_value,
            "distractor_value": distractor_value,
            "source_bundle_id": row.get("source_bundle_id"),
        })
        permutations = [
            ("A", gold_value, distractor_value, "gold_left"),
            ("B", distractor_value, gold_value, "gold_right"),
        ]
        for target_label, left_value, right_value, orientation in permutations:
            anti_cheat = json.loads(json.dumps(row.get("anti_cheat") or {}))
            anti_cheat["retrieval_hard_negative_pair_train_only"] = True
            anti_cheat["strict_eval_unchanged"] = True
            new_rows.append({
                "row_id": f"{row['row_id']}::retrieval_hard_negative_pair::{orientation}",
                "semantic_key": f"{row.get('semantic_key')}::retrieval_hard_negative_pair::{orientation}",
                "language_family": row.get("language_family"),
                "route": "KEEP_BOUNDED_DECODER",
                "objective_family": "bounded_decoder_ce",
                "surface": "maintainer_bundle_retrieval_hard_negative_pair",
                "task_type": f"{row.get('task_type')}__retrieval_hard_negative_pair",
                "split": "train",
                "prompt_text": pair_prompt(str(row.get("prompt_text") or ""), left_value, right_value),
                "input_text": pair_prompt(str(row.get("prompt_text") or ""), left_value, right_value),
                "query_text": f"{row.get('query_text')}::retrieval_hard_negative_pair::{orientation}",
                "target_text": target_label,
                "decoder_text": target_label,
                "target_token_len": 1,
                "loss_mask": {"decoder_ce": True},
                "expected_enabled_loss": "decoder_ce",
                "disable_losses": [],
                "source_skill_area": "maintainer_bundle_retrieval_hard_negative_pair",
                "source_stage": STAGE,
                "source_row_id": row.get("row_id"),
                "source_bundle_id": row.get("source_bundle_id"),
                "standalone_projection_source": {
                    "projection_mode": "retrieval_hard_negative_pair_auxiliary",
                    "projection_stage": STAGE,
                    "gold_value": gold_value,
                    "opaque_options": [
                        {"label": "A", "value": left_value},
                        {"label": "B", "value": right_value},
                    ],
                    "hard_negative_value": distractor_value,
                },
                "authority": row.get("authority"),
                "anti_cheat": anti_cheat,
            })
    return new_rows, inventory_rows


def full_pass_steps(train_rows: int) -> int:
    return max(1, math.ceil(train_rows / BATCH_SIZE))


def command(split_counts: dict[str, int]) -> list[str]:
    max_steps = full_pass_steps(split_counts.get("train", 0))
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
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
        "--max-train-rows", str(split_counts.get("train", 0)),
        "--max-eval-rows", "0",
        "--max-strict-rows", str(split_counts.get("strict_eval", 0)),
        "--max-steps", str(max_steps),
        "--batch-size", str(BATCH_SIZE),
        "--learning-rate", LEARNING_RATE,
        "--max-encoder-tokens", str(MAX_ENCODER_TOKENS),
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "16",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]


def build() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    pair_rows, inventory_rows = build_pair_rows(base_rows)
    train_rows = [row for row in base_rows if row.get("split") == "train"]
    strict_rows = [row for row in base_rows if row.get("split") == "strict_eval"]
    other_rows = [row for row in base_rows if row.get("split") not in {"train", "strict_eval"}]
    merged = list(pair_rows) + train_rows + strict_rows + other_rows
    write_jsonl(MANIFEST_JSONL, merged)
    split_counts = {"train": 0, "strict_eval": 0, "eval": 0, "other": 0}
    language_counts: dict[str, int] = {}
    for row in merged:
        split = str(row.get("split") or "")
        split_counts[split if split in split_counts else "other"] += 1
        lang = str(row.get("language_family") or "")
        language_counts[lang] = language_counts.get(lang, 0) + 1
    max_steps = full_pass_steps(split_counts["train"])
    cmd = command(split_counts)
    inventory = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "base_manifest": display(BASE_MANIFEST),
        "retrieval_hard_negative_pair_rows": len(pair_rows),
        "focus_source_rows": inventory_rows,
        "strict_eval_unchanged": True,
        "batch_size": BATCH_SIZE,
        "full_pass_max_steps": max_steps,
    }
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "retrieval_hard_negative_pair_scored_probe_ready",
        "manifest": display(MANIFEST_JSONL),
        "rows": len(merged),
        "split_counts": split_counts,
        "language_counts": dict(sorted(language_counts.items())),
        "retrieval_hard_negative_pair_rows": len(pair_rows),
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "max_steps": max_steps,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "runtime_model_dir": RUNTIME_MODEL_DIR,
        "command_json": display(COMMAND_JSON),
        "inventory_json": display(INVENTORY_JSON),
        "strict_eval_target_rows": split_counts["strict_eval"],
        "goal": "Directly supervise the encoder option-retrieval head on close train-split gold-vs-distractor candidate pairs for weak python/web action-taking surfaces.",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "retrieval_hard_negative_pair_rows": len(pair_rows),
        "max_steps": max_steps,
        "train_rows": split_counts["train"],
        "strict_rows": split_counts["strict_eval"],
        "run_id": RUN_ID,
    }
    write_json(INVENTORY_JSON, inventory)
    write_json(COMMAND_JSON, {"command": cmd})
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY, summary)
    return request


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
