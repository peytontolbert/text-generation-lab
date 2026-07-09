#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9601
NAME = "stage9601_two_phase_trainer_contract_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9600_two_phase_suffix_denoise_contract_preflight.json"
PHASE1_MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
PHASE2_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT_DIR = OUT_DIR / "trainer_contract"
AUDIT = OUT_DIR / "two_phase_trainer_contract_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TWO_PHASE_TRAINER_CONTRACT_AUDIT_STAGE9601.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command() -> list[str]:
    return [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT),
        "--manifest", str(PHASE1_MANIFEST),
        "--phase2-manifest", str(PHASE2_MANIFEST),
        "--mode", "two_phase_suffix_denoise_reconnect_probe",
        "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG),
        "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "60", "--max-eval-rows", "16", "--max-strict-rows", "20",
        "--max-steps", "400", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8",
        "--phase2-max-train-rows", "29", "--phase2-max-eval-rows", "6", "--phase2-max-strict-rows", "6",
        "--phase2-max-steps", "16", "--phase2-max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--eval-interval", "8", "--restore-best-structured-state",
        "--enable-generation-audit", "--max-generation-rows", "12", "--max-generation-tokens", "48",
        "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(CONTRACT_DIR), "--run-id", "stage9601_two_phase_contract",
        "--contract-only",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9600_not_passed")
    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("trainer_contract_failed")
    card = load_json(CONTRACT_DIR / "probe_contract_audit.json")
    if card and card.get("passed") is not True:
        failures.append("trainer_contract_card_not_passed")
    if card and card.get("mode") != "two_phase_suffix_denoise_reconnect_probe":
        failures.append("wrong_contract_mode")
    phase1 = card.get("phase1_contract") if isinstance(card.get("phase1_contract"), dict) else {}
    phase2 = card.get("phase2_contract") if isinstance(card.get("phase2_contract"), dict) else {}
    if phase1 and phase1.get("passed") is not True:
        failures.append("phase1_contract_not_passed")
    if phase2 and phase2.get("passed") is not True:
        failures.append("phase2_contract_not_passed")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "contract_dir": str(CONTRACT_DIR.relative_to(ROOT)),
        "trainer_returncode": None if run is None else run.returncode,
        "trainer_contract_passed": card.get("passed"),
        "phase1_rows": card.get("phase1_rows"),
        "phase2_rows": card.get("phase2_rows"),
        "phase1_contract_passed": phase1.get("passed"),
        "phase2_contract_passed": phase2.get("passed"),
        "two_phase_in_memory_required": card.get("two_phase_in_memory_required"),
        "checkpoint_export_allowed_between_phases": card.get("checkpoint_export_allowed_between_phases"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "nonzero_execution_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Implement execution for two_phase_suffix_denoise_reconnect_probe so phase1 and phase2 share one in-memory model without checkpoint export."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "contract_dir": str(CONTRACT_DIR.relative_to(ROOT))},
        "decision": "Validated the new trainer command surface for the two-phase suffix-choice plus residual-denoise reconnect mode. No model execution occurred.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9601 Two-Phase Trainer Contract Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Trainer contract passed: `{audit['trainer_contract_passed']}`",
        f"Phase rows: `{audit['phase1_rows']}` / `{audit['phase2_rows']}`",
        f"Model execution attempted: `{audit['model_execution_attempted']}`",
        "",
        "This stage validates the recovered trainer's two-phase command contract only. Execution remains closed until the in-memory wrapper is implemented and audited.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
