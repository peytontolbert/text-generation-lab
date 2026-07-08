#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9285
NAME = "stage9285_suffix_step_final_preexecution_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9284_suffix_step_execution_review.json"
REVIEW = ROOT / "runs/local/artifacts/stage9284_suffix_step_execution_review/suffix_step_execution_review_card.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9282_suffix_step_micro_overfit_manifest/suffix_step_micro_overfit_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9286_suffix_step_denoise_probe"
RUN_DIR = OUTPUT_DIR / "denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_step_final_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9286_suffix_step_denoise_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_STEP_FINAL_PREEXECUTION_AUDIT_STAGE9285.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True

COMMAND = [
    "conda", "run", "-n", "trellis", "python", str(TRAINER),
    "--repo-root", str(ROOT),
    "--manifest", str(MANIFEST),
    "--mode", "denoise_repair_probe",
    "--probe-scale", "target_100m",
    "--implementation", "transformer",
    "--model-config", str(MODEL_CONFIG),
    "--tokenizer-json", str(TOKENIZER_JSON),
    "--tokenizer-config", str(TOKENIZER_CONFIG),
    "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
    "--max-train-rows", "5",
    "--max-eval-rows", "1",
    "--max-strict-rows", "2",
    "--max-steps", "16",
    "--batch-size", "2",
    "--learning-rate", "1e-5",
    "--max-encoder-tokens", "256",
    "--max-decoder-tokens", "160",
    "--decoder-ce-weight", "0.0",
    "--structured-aux-weight", "0.0",
    "--denoise-weight", "1.0",
    "--eos-loss-weight", "1.0",
    "--enable-generation-audit",
    "--max-generation-rows", "8",
    "--max-generation-tokens", "64",
    "--generation-prefix-field", "model_input.bridge_priming_span",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save", "1",
    "--execution-authorized-for-recovery-probe",
    "--output-dir", str(OUTPUT_DIR),
    "--run-id", "stage9286_suffix_step_denoise_probe",
]

FORBIDDEN_FLAGS = [
    "--runtime-authorized",
    "--gemma",
    "--harness",
    "--scoring",
    "--export-final-checkpoint",
    "--decoder-ce-weight 1.0",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def command_has_pair(flag: str, value: str) -> bool:
    for idx, token in enumerate(COMMAND[:-1]):
        if token == flag and COMMAND[idx + 1] == value:
            return True
    return False


def audit_preexecution() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    review = load_json(REVIEW)
    rows = load_jsonl(MANIFEST)
    command_text = " ".join(COMMAND)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9284_not_passed")
    if review.get("passed") is not True or review.get("execution_authorized_next") is not True:
        failures.append("review_did_not_authorize_execution_next")
    auth = review.get("authority") if isinstance(review.get("authority"), dict) else {}
    if auth.get("model_execution_authorized_next") is not True or auth.get("denoise_ce_training_authorized_next") is not True:
        failures.append("required_execution_authority_missing")
    for key in AUTHORITY_CLOSED:
        if key not in {"model_execution_authorized_next", "denoise_ce_training_authorized_next"} and bool(auth.get(key, False)):
            failures.append(f"forbidden_authority_true:{key}")
    if not TRAINER.exists() or not MODEL_CONFIG.exists() or not TOKENIZER_JSON.exists() or not TOKENIZER_CONFIG.exists() or not TOKENIZER_HASHLOCK.exists():
        failures.append("required_runtime_file_missing")
    if sha256(MANIFEST) != review.get("source_manifest_sha256"):
        failures.append("manifest_hash_mismatch")
    if len(rows) != 8:
        failures.append("manifest_row_count_not_8")
    if not under(OUTPUT_DIR, ROOT / "runs/local/artifacts") or str(OUTPUT_DIR.resolve()) == str(ROOT.resolve()) or "/arxiv" in str(OUTPUT_DIR):
        failures.append("unsafe_output_dir")
    required_pairs = {
        "--manifest": str(MANIFEST),
        "--mode": "denoise_repair_probe",
        "--probe-scale": "target_100m",
        "--max-train-rows": "5",
        "--max-eval-rows": "1",
        "--max-strict-rows": "2",
        "--max-steps": "16",
        "--max-decoder-tokens": "160",
        "--decoder-ce-weight": "0.0",
        "--structured-aux-weight": "0.0",
        "--denoise-weight": "1.0",
        "--generation-prefix-field": "model_input.bridge_priming_span",
        "--output-dir": str(OUTPUT_DIR),
    }
    for flag, value in required_pairs.items():
        if not command_has_pair(flag, value):
            failures.append(f"missing_command_pair:{flag}={value}")
    for flag in ["--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--execution-authorized-for-recovery-probe", "--enable-generation-audit"]:
        if flag not in COMMAND:
            failures.append(f"missing_command_flag:{flag}")
    for forbidden in FORBIDDEN_FLAGS:
        if forbidden in command_text:
            failures.append(f"forbidden_command_surface:{forbidden}")
    if command_has_pair("--decoder-ce-weight", "0.0") is not True:
        failures.append("decoder_ce_weight_not_zero")
    if command_has_pair("--denoise-weight", "1.0") is not True:
        failures.append("denoise_weight_not_one")
    return {
        "passed": not failures,
        "failures": failures,
        "source_stage": 9284,
        "manifest_rows": len(rows),
        "manifest_sha256": sha256(MANIFEST),
        "review_manifest_sha256": review.get("source_manifest_sha256"),
        "output_dir": str(OUTPUT_DIR),
        "run_dir": str(RUN_DIR),
        "command": COMMAND,
        "command_ready": not failures,
        "will_execute_now": False,
        "authorized_next_stage": 9286,
        "authority": AUTHORITY_RUN if not failures else dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": summary["authority"], "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    authority_counts = {key: 0 for key in AUTHORITY_CLOSED}
    for row in rows:
        auth = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key in authority_counts:
            authority_counts[key] += int(bool(auth.get(key, False)))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": authority_counts}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_preexecution()
    AUDIT.write_text(json.dumps({key: value for key, value in audit.items() if key != "command"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": COMMAND, "cwd": str(ROOT), "env": "trellis"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": audit["authority"],
        "metrics": {
            **{key: bool(audit["authority"].get(key, False)) for key in AUTHORITY_CLOSED},
            "command_ready": audit["command_ready"],
            "will_execute_now": audit["will_execute_now"],
            "authorized_next_stage": audit["authorized_next_stage"],
            "manifest_rows": audit["manifest_rows"],
            "failures": len(audit["failures"]),
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Final pre-execution audit passed for the one tiny suffix-step denoise probe; command is ready but not executed in this stage." if audit["passed"] else "Final pre-execution audit failed; do not execute.",
        "next_best_step": "Execute Stage9286 suffix-step denoise probe under trellis using the audited command, then immediately audit outputs." if audit["passed"] else "Fix final pre-execution failures before running.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9285 Suffix-Step Final Pre-Execution Audit",
            "",
            f"Passed: `{audit['passed']}`",
            f"Command ready: `{audit['command_ready']}`",
            f"Will execute now: `{audit['will_execute_now']}`",
            f"Authorized next stage: `{audit['authorized_next_stage']}`",
            f"Output dir: `{audit['output_dir']}`",
            "",
            "The command is written to the command artifact and must be executed exactly for Stage9286.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
