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
STAGE = 10991
NAME = "stage10991_evidence_lane_sampler_probe_request"
OUT_DIR = ARTIFACTS / NAME
REQUEST_JSON = OUT_DIR / "evidence_lane_sampler_probe_request.json"
COMMAND_JSON = OUT_DIR / "evidence_lane_sampler_probe_command.json"
MANIFEST_JSONL = OUT_DIR / "evidence_lane_sampler_probe_manifest.jsonl"

PACKAGE_JSON = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package" / "evidence_lane_sampler_support_package.json"
TRAIN_ROWS = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package" / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package" / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS = ARTIFACTS / "stage10990_evidence_lane_sampler_support_package" / "agentkernel_lite_encdec_stress_eval.jsonl"
INIT_RUNTIME = ARTIFACTS / "stage10960_clean_explicit_ledger_support_probe" / "runtime_model" / "runtime_model_bundle.json"
RUN_ID = "stage10992_evidence_lane_sampler_support_probe"
OUTPUT_DIR = "runs/local/artifacts/stage10992_evidence_lane_sampler_support_probe/bounded_decoder_probe"
RUNTIME_MODEL_DIR = "runs/local/artifacts/stage10992_evidence_lane_sampler_support_probe/runtime_model"


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
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    stress_rows = load_jsonl(STRESS_ROWS)
    manifest_rows = list(train_rows) + list(validation_rows) + list(strict_rows)
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
        "--max-eval-rows", str(len(validation_rows)),
        "--max-strict-rows", str(len(strict_rows)),
        "--max-steps", "128",
        "--batch-size", "2",
        "--learning-rate", "5e-6",
        "--max-encoder-tokens", "768",
        "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.2",
        "--bounded-choice-aux-weight", "1.0",
        "--bounded-choice-aux-source", "encoder_option_retrieval",
        "--bounded-choice-contrast-weight", "0.0",
        "--bounded-choice-contrast-margin", "0.05",
        "--bounded-decoder-train-sampler", "residual_family_balanced",
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
        "--preservation-kl-weight", "1.0",
        "--preservation-exempt-flag", "preservation_exempt",
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
        "decision": "evidence_lane_sampler_probe_ready",
        "claim_scope": [
            "Run one bounded decoder probe that changes optimization geometry rather than just adding more broad support rows.",
            "Use residual-family-balanced sampling plus anchor-only KL preservation to let evidence/verifier rows move without discarding the honest overlay.",
        ],
        "command": command,
        "run_id": RUN_ID,
        "manifest": rel(MANIFEST_JSONL),
        "output_dir": OUTPUT_DIR,
        "runtime_model_save_dir": RUNTIME_MODEL_DIR,
        "source_package": rel(PACKAGE_JSON),
        "initialize_from_runtime_model": rel(INIT_RUNTIME),
        "split_counts": {"train": len(train_rows), "eval": len(validation_rows), "strict_eval": len(strict_rows), "stress_excluded": len(stress_rows)},
        "required_honesty_gates": [
            "Validation and strict rows remain unchanged from stage10983.",
            "Primary residual rows are exempted from KL; preservation applies only to anchor rows.",
            "No fresh strict successor rows are trained in this stage.",
        ],
        "next_best_step": "Run the probe, then compare overlay preservation against movement on the expanded evidence successor family and the Python verifier-transition slice.",
    }
    write_json(REQUEST_JSON, payload)
    write_json(COMMAND_JSON, {"command": command})
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
