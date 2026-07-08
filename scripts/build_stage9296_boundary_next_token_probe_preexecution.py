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
STAGE = 9296
NAME = "stage9296_boundary_next_token_probe_preexecution"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9295_boundary_next_token_telemetry_patch_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9290_one_next_token_suffix_manifest/one_next_token_suffix_manifest.jsonl"
OUTPUT_DIR = ROOT / "runs/local/artifacts/stage9297_boundary_next_token_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "boundary_next_token_probe_preexecution_audit.json"
COMMAND_JSON = OUT_DIR / "stage9297_boundary_next_token_probe_command.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDARY_NEXT_TOKEN_PROBE_PREEXECUTION_STAGE9296.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
EXPECTED_MANIFEST_SHA = "f0c15145c5f4b49705e611bf47a293e3df98254fc9209332772e9b941a2cf04c"

AUTHORITY_RUN = dict(AUTHORITY_CLOSED)
AUTHORITY_RUN["model_execution_authorized_next"] = True
AUTHORITY_RUN["denoise_ce_training_authorized_next"] = True

COMMAND = [
    "conda", "run", "-n", "trellis", "python", str(TRAINER),
    "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
    "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
    "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
    "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
    "--max-train-rows", "4", "--max-eval-rows", "1", "--max-strict-rows", "1",
    "--max-steps", "16", "--batch-size", "2", "--learning-rate", "1e-5",
    "--max-encoder-tokens", "256", "--max-decoder-tokens", "96",
    "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
    "--enable-generation-audit", "--max-generation-rows", "6", "--max-generation-tokens", "32",
    "--generation-prefix-field", "model_input.bridge_priming_span", "--generation-audit-splits", "train,eval,strict_eval",
    "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
    "--execution-authorized-for-recovery-probe", "--output-dir", str(OUTPUT_DIR), "--run-id", "stage9297_boundary_next_token_probe",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def has_pair(flag: str, value: str) -> bool:
    return any(COMMAND[i] == flag and COMMAND[i + 1] == value for i in range(len(COMMAND) - 1))


def audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    command_text = " ".join(COMMAND)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9295_not_passed")
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    if metrics.get("writes_boundary_logits_artifact") is not True:
        failures.append("boundary_logits_patch_not_confirmed")
    if sha256(MANIFEST) != EXPECTED_MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if len(rows) != 6:
        failures.append("manifest_row_count_not_6")
    if not str(OUTPUT_DIR.resolve()).startswith(str((ROOT / "runs/local/artifacts").resolve())) or "/arxiv" in str(OUTPUT_DIR):
        failures.append("unsafe_output_dir")
    required_pairs = {
        "--mode": "denoise_repair_probe", "--probe-scale": "target_100m", "--max-train-rows": "4",
        "--max-eval-rows": "1", "--max-strict-rows": "1", "--max-steps": "16",
        "--max-decoder-tokens": "96", "--decoder-ce-weight": "0.0", "--denoise-weight": "1.0",
        "--generation-prefix-field": "model_input.bridge_priming_span", "--generation-audit-splits": "train,eval,strict_eval",
        "--output-dir": str(OUTPUT_DIR),
    }
    for flag, value in required_pairs.items():
        if not has_pair(flag, value):
            failures.append(f"missing_pair:{flag}={value}")
    for flag in ["--execution-authorized-for-recovery-probe", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--enable-generation-audit"]:
        if flag not in COMMAND:
            failures.append(f"missing_flag:{flag}")
    for forbidden in ["--runtime-authorized", "--gemma", "--harness", "--scoring", "--export-final-checkpoint", "--decoder-ce-weight 1.0"]:
        if forbidden in command_text:
            failures.append(f"forbidden_command_surface:{forbidden}")
    return {
        "passed": not failures,
        "failures": failures,
        "manifest_rows": len(rows),
        "manifest_sha256": sha256(MANIFEST),
        "command": COMMAND,
        "command_ready": not failures,
        "will_execute_now": False,
        "authorized_next_stage": 9297,
        "required_postrun_artifact": "boundary_next_token_logits.jsonl",
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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": authority_counts}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    card = audit()
    AUDIT.write_text(json.dumps({k: v for k, v in card.items() if k != "command"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    COMMAND_JSON.write_text(json.dumps({"command": COMMAND, "cwd": str(ROOT), "env": "trellis"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": card["passed"],
        "authority": card["authority"],
        "metrics": {**{key: bool(card["authority"].get(key, False)) for key in AUTHORITY_CLOSED}, "command_ready": card["command_ready"], "will_execute_now": False, "authorized_next_stage": 9297, "manifest_rows": card["manifest_rows"], "required_postrun_artifact": card["required_postrun_artifact"], "failures": len(card["failures"])},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "command": str(COMMAND_JSON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Prepared boundary next-token telemetry rerun command; not executed in this stage.",
        "next_best_step": "Execute Stage9297 boundary next-token probe under trellis, then audit expected suffix-token rank and top-k.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9296 Boundary Next-Token Probe Preexecution", "", f"Passed: `{card['passed']}`", "Command artifact prepares Stage9297 but does not execute it.", "Required post-run artifact: `boundary_next_token_logits.jsonl`", ""]) , encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
