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
STAGE = 9614
NAME = "stage9614_phrase_suffix_two_phase_contract_preflight"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9613_phrase_level_suffix_support_manifest.json"
PHASE1_MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
PHASE2_MANIFEST = ROOT / "runs/local/artifacts/stage9613_phrase_level_suffix_support_manifest/phrase_level_suffix_support_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "two_phase_contract"
AUDIT = OUT_DIR / "phrase_suffix_two_phase_contract_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_SUFFIX_TWO_PHASE_CONTRACT_PREFLIGHT_STAGE9614.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
GENERATION_PREFIX_FIELD = "model_input.active_generation_prefix_span"
TMPDIR = Path("/data/tmp")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
        "--max-steps", "0", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8",
        "--phase2-max-train-rows", "18", "--phase2-max-eval-rows", "6", "--phase2-max-strict-rows", "4",
        "--phase2-max-steps", "0", "--phase2-max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--eval-interval", "1", "--restore-best-structured-state",
        "--enable-generation-audit", "--max-generation-rows", "12", "--max-generation-tokens", "48",
        "--generation-prefix-field", GENERATION_PREFIX_FIELD,
        "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9614_phrase_suffix_two_phase_contract",
        "--contract-only",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    phase1_rows = load_jsonl(PHASE1_MANIFEST)
    phase2_rows = load_jsonl(PHASE2_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9609_not_passed")
    if len(phase1_rows) != 96:
        failures.append("phase1_rows_not_96")
    if len(phase2_rows) != 28:
        failures.append("phase2_rows_not_28")
    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("two_phase_contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card:
        failures.append("missing_probe_contract_audit")
    elif card.get("passed") is not True:
        failures.append("probe_contract_not_passed")
    if card.get("generation_prefix_field") != GENERATION_PREFIX_FIELD:
        failures.append("generation_prefix_field_not_recorded")
    if card.get("contract_only") is not True:
        failures.append("contract_only_not_recorded")
    if card.get("model_execution_attempted") is not False:
        failures.append("model_execution_attempted")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase1_manifest": str(PHASE1_MANIFEST.relative_to(ROOT)),
        "phase2_manifest": str(PHASE2_MANIFEST.relative_to(ROOT)),
        "phase1_rows": len(phase1_rows),
        "phase2_rows": len(phase2_rows),
        "returncode": None if run is None else run.returncode,
        "contract_passed": card.get("passed"),
        "contract_only": card.get("contract_only"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "generation_prefix_field": card.get("generation_prefix_field"),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "nonzero_execution_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If execution is explicitly authorized, run a tiny Stage9615 phrase-suffix two-phase probe with phase2 caps 18/6/4 and generation-prefix-field enabled."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Validated the two-phase trainer contract against the phrase-level suffix support manifest. No model execution occurred.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9614 Phrase Suffix Two-Phase Contract Preflight",
        "",
        f"Passed: `{audit['passed']}`",
        f"Phase 2 rows: `{audit['phase2_rows']}`",
        f"Contract passed: `{audit['contract_passed']}`",
        f"Generation prefix field: `{audit['generation_prefix_field']}`",
        "",
        "Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
