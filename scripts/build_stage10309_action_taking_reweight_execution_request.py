#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10309
NAME = "stage10309_action_taking_reweight_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
INVENTORY_JSON = OUT_DIR / "action_taking_reweight_inventory.json"
MANIFEST_JSONL = OUT_DIR / "action_taking_reweight_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "action_taking_reweight_execution_request.json"
COMMAND_JSON = OUT_DIR / "action_taking_reweight_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10303_hf_local_support_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10310_action_taking_reweight_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10310_action_taking_reweight_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10310_action_taking_reweight_probe/runtime_model"
MAX_STEPS = 48
LEARNING_RATE = "8e-6"

FOCUS_DUPLICATES = {
    ("python", "symptom_localization"): 2,
    ("python", "patch_impact"): 2,
    ("python", "minimal_fix_selection"): 2,
    ("python", "verifier_outcome"): 4,
    ("web_js_ts_html", "symptom_localization"): 2,
    ("web_js_ts_html", "patch_impact"): 2,
    ("web_js_ts_html", "minimal_fix_selection"): 2,
    ("rust", "evidence_citation"): 1,
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


def duplicate_train_rows(base_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    added_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for row in base_rows:
        if row.get("split") != "train":
            continue
        if row.get("surface") != "maintainer_bundle_compact_bounded_choice":
            continue
        lang = str(row.get("language_family") or "")
        task = str(row.get("task_type") or "")
        duplicates = FOCUS_DUPLICATES.get((lang, task), 0)
        if duplicates <= 0:
            continue
        inventory_rows.append({
            "row_id": row.get("row_id"),
            "language_family": lang,
            "task_type": task,
            "duplicates_added": duplicates,
            "source_bundle_id": row.get("source_bundle_id"),
            "source_stage": row.get("source_stage"),
        })
        for index in range(duplicates):
            clone = json.loads(json.dumps(row))
            clone["row_id"] = f"{row['row_id']}::action_reweight::{index:02d}"
            clone["semantic_key"] = f"{row.get('semantic_key')}::action_reweight::{index:02d}"
            anti_cheat = clone.get("anti_cheat") if isinstance(clone.get("anti_cheat"), dict) else {}
            anti_cheat["hard_negative_reweight_train_only"] = True
            anti_cheat["strict_eval_unchanged"] = True
            anti_cheat["focus_reason"] = "python_web_action_taking_and_rust_evidence_frontier_gaps"
            clone["anti_cheat"] = anti_cheat
            clone["reweight_metadata"] = {
                "projection_stage": STAGE,
                "focus_language_family": lang,
                "focus_task_type": task,
                "duplicate_index": index,
                "duplicate_count": duplicates,
                "reweight_family": "action_taking_frontier",
            }
            added_rows.append(clone)
    return added_rows, inventory_rows


def command(split_counts: dict[str, int]) -> list[str]:
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
        "--max-steps", str(MAX_STEPS),
        "--batch-size", "2",
        "--learning-rate", LEARNING_RATE,
        "--max-encoder-tokens", "768",
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
    added_rows, inventory_rows = duplicate_train_rows(base_rows)
    merged = list(base_rows) + added_rows
    write_jsonl(MANIFEST_JSONL, merged)
    split_counts = {"train": 0, "strict_eval": 0, "eval": 0, "other": 0}
    language_counts: dict[str, int] = {}
    for row in merged:
        split = str(row.get("split") or "")
        split_counts[split if split in split_counts else "other"] += 1
        lang = str(row.get("language_family") or "")
        language_counts[lang] = language_counts.get(lang, 0) + 1
    focus_summary: dict[str, int] = {}
    for item in inventory_rows:
        key = f"{item['language_family']}::{item['task_type']}"
        focus_summary[key] = focus_summary.get(key, 0) + int(item["duplicates_added"])
    cmd = command(split_counts)
    inventory = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "base_manifest": display(BASE_MANIFEST),
        "selected_focus_rows": inventory_rows,
        "focus_duplicate_policy": [
            {"language_family": lang, "task_type": task, "duplicates_per_row": dup}
            for (lang, task), dup in sorted(FOCUS_DUPLICATES.items())
        ],
        "strict_eval_unchanged": True,
    }
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "warm_start_action_taking_reweight_ready",
        "manifest": display(MANIFEST_JSONL),
        "rows": len(merged),
        "split_counts": split_counts,
        "language_counts": dict(sorted(language_counts.items())),
        "focus_reweight_counts": focus_summary,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "max_steps": MAX_STEPS,
        "learning_rate": LEARNING_RATE,
        "run_id": RUN_ID,
        "output_dir": OUTPUT_DIR,
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10307 and the earlier frontier probes",
            "only train rows are duplicated and no admitted or strict eval rows are moved into train",
            "focus is restricted to Python and web action-taking slices plus rust evidence citation, matching observed failure modes",
            "the reweight stage is an objective change, not a benchmark change",
        ],
        "next_best_step": "run one focused warm-start probe and check whether action-taking accuracy moves on the unchanged strict frontier",
        "command": cmd,
    }
    write_json(INVENTORY_JSON, inventory)
    write_json(REQUEST_JSON, request)
    write_json(COMMAND_JSON, {"command": cmd, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(SUMMARY, {
        "stage": STAGE,
        "passed": True,
        "inventory": display(INVENTORY_JSON),
        "request": display(REQUEST_JSON),
        "manifest": display(MANIFEST_JSONL),
        "rows": len(merged),
        "added_train_duplicates": len(added_rows),
        "split_counts": split_counts,
    })
    return {
        "inventory": inventory,
        "request": request,
        "added_train_duplicates": len(added_rows),
        "rows": len(merged),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps({
        "stage": STAGE,
        "passed": True,
        "inventory": display(INVENTORY_JSON),
        "request": display(REQUEST_JSON),
        "added_train_duplicates": result["added_train_duplicates"],
        "rows": result["rows"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
