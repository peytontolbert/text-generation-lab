#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10347
NAME = "stage10347_warm_citation_adapter_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST_JSONL = OUT_DIR / "warm_citation_adapter_manifest.jsonl"
REQUEST_JSON = OUT_DIR / "warm_citation_adapter_execution_request.json"
COMMAND_JSON = OUT_DIR / "warm_citation_adapter_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl"
WEB_MANIFEST = ROOT / "runs/local/artifacts/stage10331_web_action_only_replenishment_execution_request/web_action_only_replenishment_manifest.jsonl"
PYTHON_MANIFEST = ROOT / "runs/local/artifacts/stage10333_python_mirrormind_exact_geometry_execution_request/python_mirrormind_exact_geometry_manifest.jsonl"
CONTRAST_MANIFEST = ROOT / "runs/local/artifacts/stage10229_evidence_coherence_narrow_execution_request/evidence_coherence_narrow_manifest.jsonl"
RUST_WEAKNESS_MANIFEST = ROOT / "runs/local/artifacts/stage10248_weakness_counterbalance_execution_request/weakness_counterbalance_manifest.jsonl"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10342_unresolved_family_focus_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

RUN_ID = "stage10348_warm_citation_adapter_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10348_warm_citation_adapter_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10348_warm_citation_adapter_probe/runtime_model"
MAX_STEPS = 32
LEARNING_RATE = "8e-6"
BATCH_SIZE = 2


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


def clone_row(row: dict[str, Any], *, stage_prefix: str, query_suffix: str) -> dict[str, Any]:
    new_row = json.loads(json.dumps(row))
    new_row["row_id"] = f"{stage_prefix}::{row['row_id']}"
    new_row["semantic_key"] = f"{stage_prefix}::{row.get('semantic_key', row['row_id'])}"
    new_row["source_stage"] = STAGE
    new_row["query_text"] = f"{row.get('query_text', 'balanced')}::{query_suffix}"
    if "standalone_projection_source" in new_row:
        claim = new_row["standalone_projection_source"].setdefault("claim_boundary", {})
        claim["train_support_only"] = True
        claim["same_surface_eval_admissible"] = False
        claim["balanced_successor_support"] = True
    anti = new_row.setdefault("anti_cheat", {})
    anti["train_support_only"] = True
    anti["balanced_successor_support"] = True
    auth = new_row.setdefault("authority", {})
    auth["promotion_ready"] = False
    auth["model_execution_authorized_next"] = False
    return new_row


def main() -> None:
    base_rows = load_jsonl(BASE_MANIFEST)
    web_rows = load_jsonl(WEB_MANIFEST)
    python_rows = load_jsonl(PYTHON_MANIFEST)
    contrast_rows = load_jsonl(CONTRAST_MANIFEST)
    rust_weakness_rows = load_jsonl(RUST_WEAKNESS_MANIFEST)

    base_strict_rows = [row for row in base_rows if row.get("split") == "strict_eval"]

    web_support_rows = [
        row
        for row in web_rows
        if row.get("row_id", "").startswith("stage10331::") and row.get("split") == "train"
    ]
    python_candidate_rows = [
        row
        for row in python_rows
        if row.get("row_id", "").startswith("stage10333::")
        and row.get("split") == "train"
        and row.get("task_type") in {"symptom_localization", "patch_impact", "minimal_fix_selection"}
    ]
    python_verifier_rows = [
        row
        for row in base_rows
        if row.get("split") == "train"
        and row.get("language_family") == "python"
        and row.get("task_type") == "verifier_outcome"
    ]
    cpp_citation_rows = [
        row
        for row in base_rows
        if row.get("split") == "train"
        and row.get("language_family") == "c_cpp"
        and row.get("task_type") == "evidence_citation"
    ]
    rust_citation_rows = [
        row
        for row in base_rows
        if row.get("split") == "train"
        and row.get("language_family") == "rust"
        and row.get("task_type") == "evidence_citation"
    ]
    cpp_contrast_rows = [
        row
        for row in contrast_rows
        if row.get("split") == "train"
        and row.get("language_family") == "c_cpp"
        and row.get("task_type") == "evidence_citation"
        and "::contrast::" in row.get("row_id", "")
    ]
    rust_contrast_rows = [
        row
        for row in contrast_rows
        if row.get("split") == "train"
        and row.get("language_family") == "rust"
        and row.get("task_type") == "evidence_citation"
        and "::contrast::" in row.get("row_id", "")
        and "refresh" in row.get("row_id", "")
    ]
    rust_weakness_support_rows = [
        row
        for row in rust_weakness_rows
        if row.get("split") == "train"
        and row.get("language_family") == "rust"
        and row.get("task_type") == "evidence_citation"
        and "::weakness::" in row.get("row_id", "")
    ]

    frontloaded_rows = (
        cpp_citation_rows
        + cpp_contrast_rows
        + rust_citation_rows
        + rust_contrast_rows
        + rust_weakness_support_rows
        + python_verifier_rows
    )
    combined_rows = frontloaded_rows + base_strict_rows
    write_jsonl(MANIFEST_JSONL, combined_rows)

    command = [
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
        str(len([row for row in combined_rows if row.get("split") == "train"])),
        "--max-eval-rows",
        "0",
        "--max-strict-rows",
        str(len(base_strict_rows)),
        "--max-steps",
        str(MAX_STEPS),
        "--batch-size",
        str(BATCH_SIZE),
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

    split_counts: dict[str, int] = {}
    language_counts: dict[str, int] = {}
    for row in combined_rows:
        split = str(row.get("split", "unknown"))
        split_counts[split] = split_counts.get(split, 0) + 1
        lang = str(row.get("language_family", "unknown"))
        language_counts[lang] = language_counts.get(lang, 0) + 1

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "citation_family_focus_successor_ready",
        "manifest": display(MANIFEST_JSONL),
        "source_manifests": {
            "base": display(BASE_MANIFEST),
            "python_successor": display(PYTHON_MANIFEST),
            "citation_contrast": display(CONTRAST_MANIFEST),
            "rust_weakness": display(RUST_WEAKNESS_MANIFEST),
        },
        "rows": len(combined_rows),
        "split_counts": split_counts,
        "language_counts": language_counts,
        "frontloaded_support_rows": {
            "cpp_citation_rows": len(cpp_citation_rows),
            "cpp_contrast_rows": len(cpp_contrast_rows),
            "rust_citation_rows": len(rust_citation_rows),
            "rust_contrast_rows": len(rust_contrast_rows),
            "rust_weakness_rows": len(rust_weakness_support_rows),
            "python_verifier_rows": len(python_verifier_rows),
        },
        "max_steps": MAX_STEPS,
        "learning_rate": LEARNING_RATE,
        "initialize_from_runtime_model": display(INIT_RUNTIME),
        "required_honesty_gates": [
            "strict eval rows remain identical to stage10307/stage10308",
            "warm start must begin from the repaired stage10342 runtime frontier",
            "python verifier anchors remain present so the stage10342 repair is not discarded",
            "citation support adds contrast and weakness rows instead of only replaying the unresolved base permutations",
        ],
        "next_best_step": "run one warm citation adapter probe from stage10342 and check whether citation-only support can improve c_cpp/rust without losing the repaired python verifier rows",
        "command": command,
        "output_dir": OUTPUT_DIR,
        "run_id": RUN_ID,
    }

    write_json(REQUEST_JSON, request)
    write_json(COMMAND_JSON, {"command": command, "cwd": str(ROOT), "env": "trellis", "tmpdir": str(TMPDIR)})
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": True,
            "artifact": display(REQUEST_JSON),
            "next_best_step": request["next_best_step"],
        },
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": True,
                "artifact": display(REQUEST_JSON),
                "frontloaded_support_rows": request["frontloaded_support_rows"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
