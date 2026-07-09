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
STAGE = 9600
NAME = "stage9600_two_phase_suffix_denoise_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9599_suffix_choice_residual_denoise_reconnect_design.json"
SIDECAR_MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
DENOISE_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PHASE1_DIR = OUT_DIR / "phase1_suffix_choice_contract"
PHASE2_DIR = OUT_DIR / "phase2_residual_denoise_contract"
AUDIT = OUT_DIR / "two_phase_suffix_denoise_contract_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TWO_PHASE_SUFFIX_DENOISE_CONTRACT_PREFLIGHT_STAGE9600.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def base_cmd(*, manifest: Path, mode: str, output_dir: Path, run_id: str, max_train: int, max_eval: int, max_strict: int, decoder_weight: str, structured_weight: str, denoise_weight: str, max_decoder_tokens: str) -> list[str]:
    return [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(manifest),
        "--mode", mode, "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", str(max_train), "--max-eval-rows", str(max_eval), "--max-strict-rows", str(max_strict),
        "--max-steps", "0", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", max_decoder_tokens,
        "--decoder-ce-weight", decoder_weight, "--structured-aux-weight", structured_weight, "--denoise-weight", denoise_weight,
        "--eval-interval", "1", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(output_dir), "--run-id", run_id,
        "--contract-only",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    sidecar_rows = load_jsonl(SIDECAR_MANIFEST)
    denoise_rows = load_jsonl(DENOISE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9599_not_passed")
    if len(sidecar_rows) != 96:
        failures.append("sidecar_rows_not_96")
    if len(denoise_rows) != 41:
        failures.append("denoise_rows_not_41")

    phase1_cmd = base_cmd(
        manifest=SIDECAR_MANIFEST,
        mode="structured_policy_probe",
        output_dir=PHASE1_DIR,
        run_id="stage9600_phase1_suffix_choice_contract",
        max_train=60,
        max_eval=16,
        max_strict=20,
        decoder_weight="0.0",
        structured_weight="1.0",
        denoise_weight="0.0",
        max_decoder_tokens="8",
    )
    phase2_cmd = base_cmd(
        manifest=DENOISE_MANIFEST,
        mode="denoise_repair_probe",
        output_dir=PHASE2_DIR,
        run_id="stage9600_phase2_residual_denoise_contract",
        max_train=29,
        max_eval=6,
        max_strict=6,
        decoder_weight="0.0",
        structured_weight="0.0",
        denoise_weight="1.0",
        max_decoder_tokens="96",
    )
    phase1 = subprocess.run(phase1_cmd, cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if phase1 is not None and phase1.returncode != 0:
        failures.append("phase1_contract_failed")
    phase2 = subprocess.run(phase2_cmd, cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if phase2 is not None and phase2.returncode != 0:
        failures.append("phase2_contract_failed")
    phase1_card = load_json(PHASE1_DIR / "probe_contract_audit.json")
    phase2_card = load_json(PHASE2_DIR / "probe_contract_audit.json")
    if phase1_card and phase1_card.get("passed") is not True:
        failures.append("phase1_contract_card_not_passed")
    if phase2_card and phase2_card.get("passed") is not True:
        failures.append("phase2_contract_card_not_passed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase1_manifest": str(SIDECAR_MANIFEST.relative_to(ROOT)),
        "phase2_manifest": str(DENOISE_MANIFEST.relative_to(ROOT)),
        "phase1_returncode": None if phase1 is None else phase1.returncode,
        "phase2_returncode": None if phase2 is None else phase2.returncode,
        "phase1_contract_passed": phase1_card.get("passed"),
        "phase2_contract_passed": phase2_card.get("passed"),
        "phase1_model_execution_attempted": phase1_card.get("model_execution_attempted"),
        "phase2_model_execution_attempted": phase2_card.get("model_execution_attempted"),
        "phase1_dir": str(PHASE1_DIR.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "future_wrapper_still_needed": True,
        "nonzero_execution_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Patch the trainer with an audited two-phase in-memory wrapper that can run suffix_choice training before denoise repair without checkpoint export."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "phase1_dir": str(PHASE1_DIR.relative_to(ROOT)), "phase2_dir": str(PHASE2_DIR.relative_to(ROOT))},
        "decision": "Ran contract-only validation for both phases of the suffix-choice plus residual-denoise reconnect path. No model execution occurred.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9600 Two-Phase Suffix/Denoise Contract Preflight",
        "",
        f"Passed: `{audit['passed']}`",
        f"Phase 1 contract passed: `{audit['phase1_contract_passed']}`",
        f"Phase 2 contract passed: `{audit['phase2_contract_passed']}`",
        "",
        "This stage validates existing trainer contracts for the two pieces separately. It does not execute training and does not yet implement the in-memory two-phase wrapper.",
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
