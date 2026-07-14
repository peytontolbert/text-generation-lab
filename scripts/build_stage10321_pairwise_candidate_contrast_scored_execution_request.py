#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10321
NAME = "stage10321_pairwise_candidate_contrast_scored_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY_JSON = OUT_DIR / "pairwise_candidate_contrast_inventory.json"
MANIFEST_JSONL = OUT_DIR / "pairwise_candidate_contrast_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "pairwise_candidate_contrast_execution_request.json"
COMMAND_JSON = OUT_DIR / "pairwise_candidate_contrast_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10322_pairwise_candidate_contrast_scored_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10322_pairwise_candidate_contrast_scored_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10322_pairwise_candidate_contrast_scored_probe/runtime_model"
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

OPTION_RE = re.compile(r"^([A-Z])\. (.+)$")


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


def parse_options(prompt_text: str) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    in_options = False
    for raw_line in prompt_text.splitlines():
        line = raw_line.rstrip()
        if line == "Options:":
            in_options = True
            continue
        if not in_options:
            continue
        if line == "Answer:":
            break
        match = OPTION_RE.match(line)
        if match:
            options.append((match.group(1), match.group(2)))
    return options


def pairwise_prompt(base_prompt: str, left_label: str, left_value: str, right_label: str, right_value: str) -> str:
    return (
        base_prompt.rstrip()
        + "\nPairwise candidate contrast:\n"
        + f"LEFT candidate: {left_label}. {left_value}\n"
        + f"RIGHT candidate: {right_label}. {right_value}\n"
        + "Question: Which candidate is better supported by the visible evidence as the correct edit target?\n"
        + "Return LEFT or RIGHT only.\n"
        + "Answer:\n"
    )


def build_pairwise_rows(base_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        prompt = str(row.get("prompt_text") or "")
        options = parse_options(prompt)
        if len(options) < 2:
            continue
        gold = str(row.get("target_text") or "")
        option_map = {label: value for label, value in options}
        gold_value = option_map.get(gold)
        if gold_value is None:
            continue
        distractors = [(label, value) for label, value in options if label != gold]
        inventory_rows.append({
            "row_id": row.get("row_id"),
            "language_family": key[0],
            "task_type": key[1],
            "option_count": len(options),
            "distractor_count": len(distractors),
            "source_bundle_id": row.get("source_bundle_id"),
        })
        for distractor_label, distractor_value in distractors:
            anti_cheat = json.loads(json.dumps(row.get("anti_cheat") or {}))
            anti_cheat["pairwise_candidate_contrast_train_only"] = True
            anti_cheat["strict_eval_unchanged"] = True
            left_right_specs = [
                ("LEFT", gold, gold_value, distractor_label, distractor_value),
                ("RIGHT", distractor_label, distractor_value, gold, gold_value),
            ]
            for target, left_label, left_value, right_label, right_value in left_right_specs:
                orientation = "gold_left" if target == "LEFT" else "gold_right"
                new_rows.append({
                    "row_id": f"{row['row_id']}::pairwise_candidate_contrast::{distractor_label}::{orientation}",
                    "semantic_key": f"{row.get('semantic_key')}::pairwise_candidate_contrast::{distractor_label}::{orientation}",
                    "language_family": row.get("language_family"),
                    "route": "KEEP_BOUNDED_DECODER",
                    "objective_family": "bounded_decoder_ce",
                    "surface": "maintainer_bundle_pairwise_candidate_contrast",
                    "task_type": f"{row.get('task_type')}__pairwise_candidate_contrast",
                    "split": "train",
                    "prompt_text": pairwise_prompt(prompt, left_label, left_value, right_label, right_value),
                    "input_text": pairwise_prompt(prompt, left_label, left_value, right_label, right_value),
                    "query_text": f"{row.get('query_text')}::pairwise_candidate_contrast::{distractor_label}::{orientation}",
                    "target_text": target,
                    "decoder_text": target,
                    "target_token_len": len(target.encode('utf-8')),
                    "loss_mask": {"decoder_ce": True},
                    "expected_enabled_loss": "decoder_ce",
                    "disable_losses": [],
                    "source_skill_area": "maintainer_bundle_pairwise_candidate_contrast",
                    "source_stage": STAGE,
                    "source_row_id": row.get("row_id"),
                    "source_bundle_id": row.get("source_bundle_id"),
                    "standalone_projection_source": {
                        "projection_mode": "pairwise_candidate_contrast_auxiliary",
                        "projection_stage": STAGE,
                        "source_target_label": gold,
                        "source_target_value": gold_value,
                        "distractor_label": distractor_label,
                        "distractor_value": distractor_value,
                        "left_candidate": {"label": left_label, "value": left_value},
                        "right_candidate": {"label": right_label, "value": right_value},
                        "binary_target": target,
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
    aux_rows, inventory_rows = build_pairwise_rows(base_rows)
    train_rows = [row for row in base_rows if row.get("split") == "train"]
    strict_rows = [row for row in base_rows if row.get("split") == "strict_eval"]
    other_rows = [row for row in base_rows if row.get("split") not in {"train", "strict_eval"}]
    merged = list(aux_rows) + train_rows + strict_rows + other_rows
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
        "pairwise_aux_rows": len(aux_rows),
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
        "decision": "pairwise_candidate_contrast_scored_probe_ready",
        "manifest": display(MANIFEST_JSONL),
        "rows": len(merged),
        "split_counts": split_counts,
        "language_counts": dict(sorted(language_counts.items())),
        "pairwise_aux_rows": len(aux_rows),
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
        "goal": "Train explicit gold-vs-distractor semantic discrimination on the weak python/web action-taking slices and measure whether it changes the final constrained decision boundary.",
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "pairwise_aux_rows": len(aux_rows),
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
