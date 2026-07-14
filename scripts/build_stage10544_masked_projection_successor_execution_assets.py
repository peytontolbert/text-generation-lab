#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10544
NAME = "stage10544_masked_projection_successor_execution_assets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "masked_projection_successor_execution_assets.json"
REQUEST_PATH = OUT_DIR / "masked_projection_successor_probe_request.json"
QUEUE_PATH = OUT_DIR / "masked_projection_successor_gemma_queue.json"
PACKETS_PATH = OUT_DIR / "masked_projection_successor_gemma_packets.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_DIR = ROOT / "runs/local/artifacts/stage10543_masked_projection_successor_package"
MANIFEST_PATH = PACKAGE_DIR / "masked_projection_successor_rows.jsonl"
TRAIN_ROWS_PATH = PACKAGE_DIR / "train_rows.jsonl"
VALIDATION_ROWS_PATH = PACKAGE_DIR / "validation_rows.jsonl"
STRICT_ROWS_PATH = PACKAGE_DIR / "strict_eval_rows.jsonl"
PACKAGE_SUMMARY = PACKAGE_DIR / "masked_projection_successor_package.json"

INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10531_long_target_cap_corrected_probe/runtime_model/runtime_model_bundle.json"
PRESERVE_RUNTIME = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"
PROBE_OUTPUT_DIR = ROOT / "runs/local/artifacts/stage10545_masked_projection_successor_probe/bounded_decoder_probe"
PROBE_RUNTIME_DIR = ROOT / "runs/local/artifacts/stage10545_masked_projection_successor_probe/runtime_model"

MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
GEMMA_MODEL_ID = "gemma3:12b"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def surface_hash(rows: list[dict[str, Any]]) -> str:
    minimal = [
        {
            "row_id": str(r.get("row_id") or ""),
            "input_text": str(r.get("input_text") or ""),
            "target_text": str(r.get("target_text") or ""),
            "target_subtype": str(r.get("target_subtype") or ""),
        }
        for r in sorted(rows, key=lambda item: str(item.get("row_id") or ""))
    ]
    return sha256(json.dumps(minimal, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train_rows = load_jsonl(TRAIN_ROWS_PATH)
    validation_rows = load_jsonl(VALIDATION_ROWS_PATH)
    strict_rows = load_jsonl(STRICT_ROWS_PATH)
    package = load_json(PACKAGE_SUMMARY)

    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "decision": "masked_projection_successor_probe_ready",
        "passed": True,
        "manifest": display(MANIFEST_PATH),
        "source_package": display(PACKAGE_SUMMARY),
        "run_id": "stage10545_masked_projection_successor_probe",
        "output_dir": display(PROBE_OUTPUT_DIR),
        "runtime_model_dir": display(PROBE_RUNTIME_DIR),
        "rows": len(train_rows) + len(validation_rows) + len(strict_rows),
        "split_counts": {
            "train": len(train_rows),
            "eval": len(validation_rows),
            "strict_eval": len(strict_rows),
        },
        "language_counts_by_split": {
            "train": count_by(train_rows, "language_family"),
            "eval": count_by(validation_rows, "language_family"),
            "strict_eval": count_by(strict_rows, "language_family"),
        },
        "strict_target_subtypes": count_by(strict_rows, "target_subtype"),
        "claim_scope": [
            "Same root-split bootstrap successor built from the stage10543 masked projection package.",
            "Strict rows measure exact generation on shorter source-backed targets: retrieve_answer_abstain, decisive_evidence_top1, and verifier_outcome_masked.",
            "This is the next honest seq2seq promotion candidate after the 0/36 long-list failure on stage10532.",
        ],
        "known_limits": [
            "Validation remains tiny and rust-heavy.",
            "This does not yet solve realistic patch_sketch or repair_intent heldout scoring.",
            "The old 36-row long-list decisive_evidence slice remains a harder downstream frontier and should not be replaced as a challenge set.",
        ],
        "required_honesty_gates": [
            "stage10543 successor package must remain unchanged with zero prompt-target leaks",
            "root split violations must remain zero",
            "same-manifest Gemma comparison must use the exact 54 strict rows from stage10543",
            "24-row repaired v2.7 canary must be rerun after the probe to catch bounded-choice regression",
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
            str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
            "--repo-root",
            str(ROOT),
            "--manifest",
            str(MANIFEST_PATH),
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
            str(len(train_rows)),
            "--max-eval-rows",
            str(len(validation_rows)),
            "--max-strict-rows",
            str(len(strict_rows)),
            "--max-steps",
            "256",
            "--batch-size",
            "1",
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
            "256",
            "--require-loss-mask-enforcement-audit",
            "--allow-runtime-model-save-for-harness",
            "--runtime-model-save-dir",
            str(PROBE_RUNTIME_DIR),
            "--initialize-from-runtime-model",
            str(INIT_RUNTIME),
            "--preservation-reference-runtime-model",
            str(PRESERVE_RUNTIME),
            "--preservation-kl-weight",
            "1.0",
            "--no-final-checkpoint-export",
            "--skip-final-model-save",
            "1",
            "--output-dir",
            str(PROBE_OUTPUT_DIR),
            "--run-id",
            "stage10545_masked_projection_successor_probe",
        ],
        "next_best_step": "Run this target-100M probe, then compare the resulting runtime against Gemma on the same 54 strict successor rows and rerun the stage10533 canary audit for regression.",
    }

    packet = {
        "claim_scope": [
            "Same-surface seq2seq generation on the strict rows from the stage10543 masked projection successor package.",
            "Rows are limited to retrieve_answer_abstain, decisive_evidence_top1, and verifier_outcome_masked.",
            "This is a bootstrap-heldout successor comparison, not the full maintainer benchmark endpoint.",
        ],
        "row_count": len(strict_rows),
        "language_counts": count_by(strict_rows, "language_family"),
        "target_subtype_counts": count_by(strict_rows, "target_subtype"),
        "surface_hash": surface_hash(strict_rows),
        "strict_rows": display(STRICT_ROWS_PATH),
        "source_manifest_summary": display(PACKAGE_SUMMARY),
    }

    packets = []
    for row in strict_rows:
        packets.append(
            {
                "row_id": str(row.get("row_id") or ""),
                "language_family": str(row.get("language_family") or ""),
                "repo_id": str(row.get("repo_id") or ""),
                "target_subtype": str(row.get("target_subtype") or ""),
                "target_text": str(row.get("target_text") or ""),
                "input_text": str(row.get("input_text") or ""),
                "model_id": GEMMA_MODEL_ID,
                "queue_stage": STAGE,
                "queue_name": NAME,
            }
        )

    queue = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "model_id": GEMMA_MODEL_ID,
        "queue_entries": [
            {
                "cell_key": "masked_projection_successor::strict54::same_surface_gemma12b",
                "language_family": "multilingual",
                "priority_rank": 1,
                "priority_reason": "Run Gemma on the exact same 54 strict successor rows used by the masked projection target-100M probe.",
                "gemma_execution_authorized_now": False,
                "ready_for_gemma_when_authorized": True,
                "remaining_blockers": ["explicit_gemma_execution_authorization"],
                "same_surface_packet": packet,
                "review_packet_paths": {
                    "strict_rows": display(STRICT_ROWS_PATH),
                    "packets": display(PACKETS_PATH),
                },
            }
        ],
        "next_best_step": "Run the local Ollama Gemma comparator on this exact 54-row successor slice, then compare it directly against the matching target-100M probe output.",
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_package": display(PACKAGE_SUMMARY),
        "probe_request": display(REQUEST_PATH),
        "gemma_queue": display(QUEUE_PATH),
        "gemma_packets": display(PACKETS_PATH),
        "decision": "execution_assets_materialized",
        "summary": {
            "strict_rows": len(strict_rows),
            "strict_surface_hash": packet["surface_hash"],
            "strict_language_counts": packet["language_counts"],
            "strict_target_subtype_counts": packet["target_subtype_counts"],
        },
        "next_best_step": request["next_best_step"],
    }

    write_json(REQUEST_PATH, request)
    write_json(QUEUE_PATH, queue)
    write_jsonl(PACKETS_PATH, packets)
    write_json(SUMMARY_PATH, summary)
    write_json(SUMMARY_REF, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
