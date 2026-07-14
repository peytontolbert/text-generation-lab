#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11000
NAME = "stage11000_fresh_evidence_support_probe_request"
OUT_DIR = ARTIFACTS / NAME
REQUEST_JSON = OUT_DIR / "fresh_evidence_support_probe_request.json"
COMMAND_JSON = OUT_DIR / "fresh_evidence_support_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "fresh_evidence_support_probe_manifest.jsonl"

PACKAGE_JSON = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "fresh_evidence_branch_package.json"
TRAIN_ROWS = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "train_support_rows.jsonl"
OVERLAY_VAL_ROWS = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "overlay_validation_rows.jsonl"
OVERLAY_STRICT_ROWS = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "overlay_strict_rows.jsonl"
FRESH_CANDIDATE_ROWS = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "strict_candidate_rows.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage10985_clean_residual_family_support_probe" / "runtime_model" / "runtime_model_bundle.json"
RUN_ID = "stage11001_fresh_evidence_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage11001_fresh_evidence_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage11001_fresh_evidence_support_probe/runtime_model"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = load_jsonl(TRAIN_ROWS)
    overlay_val_rows = load_jsonl(OVERLAY_VAL_ROWS)
    overlay_strict_rows = load_jsonl(OVERLAY_STRICT_ROWS)
    fresh_candidate_rows = load_jsonl(FRESH_CANDIDATE_ROWS)
    manifest_rows = list(train_rows) + list(overlay_val_rows) + list(overlay_strict_rows)
    write_jsonl(MANIFEST_JSONL, manifest_rows)

    command = [
        "env", "TMPDIR=/data/tmp", "TEMP=/data/tmp", "TMP=/data/tmp",
        "conda", "run", "-n", "trellis", "python", str(ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root", str(ROOT),
        "--manifest", str(MANIFEST_JSONL),
        "--mode", "bounded_decoder_ce_probe",
        "--probe-scale", "target_100m",
        "--implementation", "transformer",
        "--model-config", str(ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"),
        "--tokenizer-json", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),
        "--tokenizer-config", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),
        "--tokenizer-hashlock", str(ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe",
        "--max-train-rows", str(len(train_rows)),
        "--max-eval-rows", str(len(overlay_val_rows)),
        "--max-strict-rows", str(len(overlay_strict_rows)),
        "--max-steps", "96",
        "--batch-size", "2",
        "--learning-rate", "5e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--bounded-choice-contrast-weight", "0.0",
        "--bounded-choice-contrast-margin", "0.05",
        "--bounded-decoder-train-sampler", "cyclic",
        "--structured-aux-weight", "0.0",
        "--denoise-weight", "0.0",
        "--eos-loss-weight", "4.0",
        "--enable-generation-audit",
        "--max-generation-rows", "12",
        "--max-generation-tokens", "8",
        "--require-loss-mask-enforcement-audit",
        "--allow-runtime-model-save-for-harness",
        "--runtime-model-save-dir", str(ROOT / RUNTIME_MODEL_DIR),
        "--initialize-from-runtime-model", str(INIT_RUNTIME),
        "--preservation-reference-runtime-model", str(INIT_RUNTIME),
        "--preservation-kl-weight", "0.25",
        "--no-final-checkpoint-export",
        "--skip-final-model-save", "1",
        "--output-dir", str(ROOT / OUTPUT_DIR),
        "--run-id", RUN_ID,
    ]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_evidence_support_probe_ready",
        "claim_scope": [
            "Run a small clean support probe on the 12 replenishment rows while keeping the stable overlay in-manifest for preservation checks.",
            "Judge progress primarily on the reserved fresh 3-root evidence candidate slice after the run, not on the stale overlay alone.",
        ],
        "command": command,
        "run_id": RUN_ID,
        "manifest": rel(MANIFEST_JSONL),
        "source_package": rel(PACKAGE_JSON),
        "initialize_from_runtime_model": rel(INIT_RUNTIME),
        "fresh_candidate_rows": rel(FRESH_CANDIDATE_ROWS),
        "split_counts": {"train": len(train_rows), "eval": len(overlay_val_rows), "strict_eval": len(overlay_strict_rows), "fresh_candidate_reserved": len(fresh_candidate_rows)},
        "required_honesty_gates": [
            "Fresh candidate rows remain out of train and are only used in postrun auditing.",
            "Overlay eval and strict rows remain unchanged from stage10998/stage10983.",
            "Any improvement claim must report both overlay preservation and fresh-candidate movement.",
        ],
        "next_best_step": "Run the probe, then audit the saved runtime on the fresh 3-root candidate slice plus overlay references to see whether the replenishment support rows actually teach the new evidence boundary.",
    }
    write_json(REQUEST_JSON, payload)
    write_json(COMMAND_JSON, {"command": command})
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
