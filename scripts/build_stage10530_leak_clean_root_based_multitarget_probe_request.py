#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10530
NAME = "stage10530_leak_clean_root_based_multitarget_probe_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "leak_clean_root_based_multitarget_probe_request.json"
MANIFEST_JSONL = OUT_DIR / "leak_clean_root_based_multitarget_probe_manifest.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage10528_cleaned_heldout_anticheat_successor/cleaned_heldout_anticheat_successor.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10528_cleaned_heldout_anticheat_successor/cleaned_multitarget_bootstrap_with_heldout_rows.jsonl"
STRUCTURED_AUDIT = ROOT / "runs/local/artifacts/stage10529_structured_projection_supply_audit/structured_projection_supply_audit.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

RUN_ID = "stage10530_leak_clean_root_based_multitarget_probe"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = ROOT / "runs/local/artifacts/stage10530_leak_clean_root_based_multitarget_probe/runtime_model"

ALLOWED_TRAIN_SPLITS = {
    "train_bootstrap_bounded",
    "train_bootstrap_geometry",
    "train_bootstrap_long_context",
    "train_teacher_long_context",
}


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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def with_probe_fields(row: dict[str, Any], split: str) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = split
    updated["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux", "bounded_choice_aux"]
    updated["expected_enabled_loss"] = "decoder_ce"
    updated["loss_mask"] = {"decoder_ce": True}
    updated["objective_family"] = "root_based_multitarget_decoder_ce"
    updated["decoder_text"] = updated.get("target_text", "")
    updated["prompt_text"] = updated.get("input_text", "")
    updated["target_token_len"] = max(1, len(str(updated.get("target_text", "")).split()))
    return updated


def train_row_allowed(row: dict[str, Any]) -> bool:
    anti_cheat = dict(row.get("anti_cheat") or {})
    if anti_cheat.get("prompt_target_leak") is True:
        return False
    if str(row.get("target_subtype") or "") == "verifier_outcome":
        return False
    return True


def build_command(train_count: int, eval_count: int, strict_count: int) -> list[str]:
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
        str(eval_count),
        "--max-strict-rows",
        str(strict_count),
        "--max-steps",
        "256",
        "--batch-size",
        "2",
        "--learning-rate",
        "2e-5",
        "--max-encoder-tokens",
        "1024",
        "--max-decoder-tokens",
        "256",
        "--decoder-ce-weight",
        "1.0",
        "--bounded-choice-aux-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--eos-loss-weight",
        "2.0",
        "--enable-generation-audit",
        "--max-generation-rows",
        "24",
        "--max-generation-tokens",
        "128",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir",
        str(RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-reference-runtime-model",
        str(INIT_RUNTIME),
        "--preservation-kl-weight",
        "1.0",
        "--no-final-checkpoint-export",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(OUTPUT_DIR),
        "--run-id",
        RUN_ID,
    ]


def main() -> None:
    source_manifest = load_json(SOURCE_MANIFEST)
    rows = load_jsonl(SOURCE_ROWS)
    structured_audit = load_json(STRUCTURED_AUDIT) if STRUCTURED_AUDIT.exists() else {}

    raw_train_rows = [row for row in rows if row["split_component"] in ALLOWED_TRAIN_SPLITS]
    dropped_train_rows = [row for row in raw_train_rows if not train_row_allowed(row)]
    kept_train_rows = [with_probe_fields(row, "train") for row in raw_train_rows if train_row_allowed(row)]
    eval_rows = [with_probe_fields(row, "eval") for row in rows if row["split_component"] == "validation_bootstrap_bounded"]
    strict_rows = [with_probe_fields(row, "strict_eval") for row in rows if row["split_component"] == "strict_eval_long_context_heldout"]
    manifest_rows = kept_train_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    dropped_by_subtype = dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in dropped_train_rows).items()))
    kept_by_subtype = dict(sorted(Counter(str(row.get("target_subtype") or "unknown") for row in kept_train_rows).items()))
    command = build_command(len(kept_train_rows), len(eval_rows), len(strict_rows))
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(kept_train_rows) and bool(strict_rows),
        "decision": "leak_clean_root_based_multitarget_probe_ready",
        "claim_scope": [
            "Leak-clean successor request for the root-based multitarget bootstrap curriculum.",
            "Drops train rows with prompt-target leakage and excludes current verifier_outcome rows from training.",
            "Post-run strict scoring still speaks only to the 36 bootstrap-heldout multilingual rows.",
        ],
        "source_package": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "structured_audit": str(STRUCTURED_AUDIT.relative_to(ROOT)),
        "manifest": str(MANIFEST_JSONL.relative_to(ROOT)),
        "run_id": RUN_ID,
        "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
        "runtime_model_dir": str(RUNTIME_MODEL_DIR.relative_to(ROOT)),
        "rows": len(manifest_rows),
        "split_counts": {
            "train": len(kept_train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
        },
        "train_cleanup": {
            "raw_train_rows": len(raw_train_rows),
            "kept_train_rows": len(kept_train_rows),
            "dropped_train_rows": len(dropped_train_rows),
            "dropped_by_target_subtype": dropped_by_subtype,
            "kept_by_target_subtype": kept_by_subtype,
        },
        "language_counts_by_split": {
            "train": dict(sorted(Counter(row.get("language_family", "unknown") for row in kept_train_rows).items())),
            "eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in eval_rows).items())),
            "strict_eval": dict(sorted(Counter(row.get("language_family", "unknown") for row in strict_rows).items())),
        },
        "strict_target_subtypes": dict(sorted(Counter(row.get("target_subtype", "unknown") for row in strict_rows).items())),
        "command": command,
        "required_honesty_gates": [
            "stage10528 cleaned anti-cheat successor remains the source package",
            "train rows with anti_cheat.prompt_target_leak=true are excluded",
            "all verifier_outcome rows are excluded from train until a fresh non-leaky builder exists",
            "strict rows remain limited to decisive_evidence and retrieve_answer_abstain",
            "post-run Gemma comparison must use the same 36 strict rows",
        ],
        "known_limits": [
            "This still does not create heldout verifier_outcome or patch_sketch scoring; those need fresh non-leaky roots.",
            "Rust and web heldout depth remain modest.",
            "Patch_sketch, repair_intent, and next_action are support-only structured curriculum from current artifacts.",
        ],
        "next_best_step": (
            "Run this leak-clean successor instead of promoting stage10523. "
            "Then compare the resulting runtime against Gemma on the same 36 strict heldout rows and check the 24-row repaired-v2.7 canary for regression."
        ),
        "structured_projection_guidance": structured_audit.get("candidacy_by_subtype") or {},
        "manifest_snapshot": {
            "strict_rows_by_language": source_manifest["metrics"]["strict_rows_by_language"],
            "strict_rows_by_target_subtype": source_manifest["metrics"]["strict_rows_by_target_subtype"],
        },
    }
    write_json(REQUEST_JSON, request)
    write_json(SUMMARY_JSON, request)
    print(json.dumps({"stage": STAGE, "passed": request["passed"], "dropped_train_rows": len(dropped_train_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
