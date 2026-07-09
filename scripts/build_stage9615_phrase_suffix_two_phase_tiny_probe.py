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
STAGE = 9615
NAME = "stage9615_phrase_suffix_two_phase_tiny_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9614_phrase_suffix_two_phase_contract_preflight.json"
PHASE1_MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
PHASE2_MANIFEST = ROOT / "runs/local/artifacts/stage9613_phrase_level_suffix_support_manifest/phrase_level_suffix_support_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "two_phase_probe"
AUDIT = OUT_DIR / "phrase_suffix_two_phase_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_SUFFIX_TWO_PHASE_TINY_PROBE_STAGE9615.md"
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


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command() -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(PHASE1_MANIFEST),
        "--phase2-manifest",
        str(PHASE2_MANIFEST),
        "--mode",
        "two_phase_suffix_denoise_reconnect_probe",
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
        "--max-train-rows",
        "60",
        "--max-eval-rows",
        "16",
        "--max-strict-rows",
        "20",
        "--max-steps",
        "400",
        "--batch-size",
        "2",
        "--learning-rate",
        "2e-4",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "8",
        "--phase2-max-train-rows",
        "18",
        "--phase2-max-eval-rows",
        "6",
        "--phase2-max-strict-rows",
        "4",
        "--phase2-max-steps",
        "48",
        "--phase2-max-decoder-tokens",
        "96",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "1.0",
        "--eos-loss-weight",
        "1.0",
        "--eval-interval",
        "8",
        "--restore-best-structured-state",
        "--enable-generation-audit",
        "--max-generation-rows",
        "12",
        "--max-generation-tokens",
        "48",
        "--generation-prefix-field",
        GENERATION_PREFIX_FIELD,
        "--generation-audit-splits",
        "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR),
        "--run-id",
        "stage9615_phrase_suffix_two_phase_probe",
        "--execution-authorized-for-recovery-probe",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9606_not_passed")
    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("execution_failed")
    result = load_json(RUN_DIR / "execution_result.json")
    if not result:
        failures.append("missing_execution_result")
    phase2_quality = result.get("phase2_quality") if isinstance(result.get("phase2_quality"), dict) else {}
    phase1_exact = result.get("phase1_eval_suffix_choice_exact")
    phase1_strict = result.get("phase1_strict_suffix_choice_exact")
    if result and result.get("model_reused_in_memory_between_phases") is not True:
        failures.append("model_not_reused_in_memory")
    if result and result.get("checkpoint_export_allowed_between_phases") is not False:
        failures.append("checkpoint_handoff_not_blocked")
    if result and result.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")
    if result and result.get("runtime_executed") is not False:
        failures.append("runtime_executed")
    if result and result.get("final_checkpoint_exported") is not False:
        failures.append("final_checkpoint_exported")
    quality_gate = (
        phase1_exact == 1.0
        and phase1_strict == 1.0
        and phase2_quality.get("contentful_generation_rate") == 1.0
        and (phase2_quality.get("short_or_junk_rate") in {0, 0.0, None})
        and (phase2_quality.get("degenerate_repetition_rate") in {0, 0.0, None})
        and (phase2_quality.get("generated_internal_token_rows") in {0, None})
        and (phase2_quality.get("generation_prefix_start_rate") == 1.0)
    )
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "trainer_returncode": None if run is None else run.returncode,
        "phase1_eval_suffix_choice_exact": phase1_exact,
        "phase1_strict_suffix_choice_exact": phase1_strict,
        "phase2_generated_rows": phase2_quality.get("generated_rows"),
        "phase2_contentful_generation_rate": phase2_quality.get("contentful_generation_rate"),
        "phase2_short_or_junk_rate": phase2_quality.get("short_or_junk_rate"),
        "phase2_degenerate_repetition_rate": phase2_quality.get("degenerate_repetition_rate"),
        "phase2_generated_internal_token_rows": phase2_quality.get("generated_internal_token_rows"),
        "phase2_target_prefix_match_rate": phase2_quality.get("target_prefix_match_rate"),
        "phase2_generation_prefix_field": phase2_quality.get("generation_prefix_field"),
        "phase2_generation_prefix_start_rate": phase2_quality.get("generation_prefix_start_rate"),
        "quality_gate": quality_gate,
        "model_reused_in_memory_between_phases": result.get("model_reused_in_memory_between_phases"),
        "checkpoint_export_allowed_between_phases": result.get("checkpoint_export_allowed_between_phases"),
        "decoder_ce_rows": result.get("decoder_ce_rows"),
        "denoise_ce_rows": result.get("denoise_ce_rows"),
        "runtime_executed": result.get("runtime_executed"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Audit Stage9615 generation samples and token losses; if quality passes, design a controlled phrase-suffix integration probe, otherwise patch the remaining failure bucket."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Executed the phrase-suffix in-memory two-phase suffix-choice plus residual-denoise tiny probe under closed runtime/export authority.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9615 Phrase-Suffix Two-Phase Tiny Probe",
                "",
                f"Passed: `{audit['passed']}`",
                f"Quality gate: `{quality_gate}`",
                f"Phase1 eval/strict suffix exact: `{phase1_exact}` / `{phase1_strict}`",
                f"Phase2 contentful rate: `{audit['phase2_contentful_generation_rate']}`",
                f"Phase2 target prefix match rate: `{audit['phase2_target_prefix_match_rate']}`",
                f"Phase2 generation prefix start rate: `{audit['phase2_generation_prefix_start_rate']}`",
                f"Decoder CE rows: `{audit['decoder_ce_rows']}`",
                f"Runtime executed: `{audit['runtime_executed']}`",
                "",
                "Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": audit["passed"],
                "quality_gate": quality_gate,
                "failures": failures,
                "phase1_eval": phase1_exact,
                "phase1_strict": phase1_strict,
                "phase2_contentful": audit["phase2_contentful_generation_rate"],
                "phase2_prefix": audit["phase2_target_prefix_match_rate"],
                "prefix_start": audit["phase2_generation_prefix_start_rate"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
