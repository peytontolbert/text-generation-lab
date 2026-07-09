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
STAGE = 9570
NAME = "stage9570_residual_denoise_target_rendered_longer_capped_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9569_residual_denoise_target_rendered_quality_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
RUN_ROOT = ROOT / "runs/local/artifacts/stage9570_residual_denoise_target_rendered_longer_capped_probe"
CONTRACT_DIR = RUN_ROOT / "contract_preflight"
RUN_DIR = RUN_ROOT / "denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_target_rendered_longer_capped_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_TARGET_RENDERED_LONGER_CAPPED_PROBE_STAGE9570.md"
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
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def count_jsonl(path: Path) -> int:
    return len(load_jsonl(path))


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "29", "--max-eval-rows", "6", "--max-strict-rows", "6",
        "--max-steps", "80", "--batch-size", "2", "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "12", "--max-generation-tokens", "48",
        "--generation-audit-splits", "train,eval,strict_eval",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(output_dir), "--run-id", run_id,
    ]
    cmd.append("--contract-only" if contract_only else "--execution-authorized-for-recovery-probe")
    return cmd


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9569_not_passed")
    if (source.get("metrics") or {}).get("target_rendering_fixed") is not True:
        failures.append("stage9569_target_rendering_not_fixed")
    if (source.get("metrics") or {}).get("quality_gate_passed") is not False:
        failures.append("stage9569_quality_gate_unexpected")
    rows = load_jsonl(MANIFEST)
    if len(rows) != 41:
        failures.append("manifest_row_count_not_41")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("loss_mask") or {}).get("denoise_ce") is not True for row in rows):
        failures.append("denoise_loss_mask_missing")
    if any((row.get("loss_mask") or {}).get("decoder_ce") for row in rows):
        failures.append("decoder_ce_loss_present")
    if not failures:
        contract = subprocess.run(command(output_dir=CONTRACT_DIR, run_id="stage9570_contract_preflight", contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    contract_card = load_json(CONTRACT_DIR / "probe_contract_audit.json")
    if contract_card and contract_card.get("passed") is not True:
        failures.append("contract_card_not_passed")
    if not failures:
        run = subprocess.run(command(output_dir=RUN_DIR, run_id="stage9570_longer_capped_probe", contract_only=False), cwd=ROOT, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            failures.append("execution_failed")
    else:
        run = None
    execution = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    sample = load_json(RUN_DIR / "sample_generation_audit.json")
    step_rows = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    token_rows = load_jsonl(RUN_DIR / "row_token_loss.jsonl")
    if run is not None:
        if not execution:
            failures.append("missing_execution_result")
        elif execution.get("required_artifacts_written") is not True:
            failures.append("required_artifacts_not_written")
    if execution and execution.get("denoise_ce_rows") != 41:
        failures.append("denoise_ce_rows_not_41")
    if execution and execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")
    if execution and execution.get("runtime_executed") is not False:
        failures.append("runtime_executed")
    nonzero_loss_steps = sum(1 for row in step_rows if float(row.get("loss", 0.0)) > 0.0)
    final_loss = float(step_rows[-1]["loss"]) if step_rows else None
    first_loss = float(step_rows[0]["loss"]) if step_rows else None
    contentful_rate = quality.get("contentful_generation_rate")
    target_prefix_match_rate = quality.get("target_prefix_match_rate")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "contract_returncode": None if contract is None else contract.returncode,
        "execution_returncode": None if run is None else run.returncode,
        "contract_stdout_tail": "" if contract is None else contract.stdout[-3000:],
        "contract_stderr_tail": "" if contract is None else contract.stderr[-3000:],
        "execution_stdout_tail": "" if run is None else run.stdout[-3000:],
        "execution_stderr_tail": "" if run is None else run.stderr[-3000:],
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "first_loss": first_loss,
        "final_loss": final_loss,
        "nonzero_loss_steps": nonzero_loss_steps,
        "row_token_loss_rows": len(token_rows),
        "generated_rows": execution.get("generated_rows"),
        "contentful_generation_rate": contentful_rate,
        "short_or_junk_rate": execution.get("short_or_junk_rate"),
        "degenerate_repetition_rate": execution.get("degenerate_repetition_rate"),
        "target_prefix_match_rate": target_prefix_match_rate,
        "exact_match_rows": sample.get("exact_match_rows"),
        "unterminated_rate": sample.get("unterminated_rate"),
        "quality_gate_passed": bool(contentful_rate and contentful_rate > 0 and target_prefix_match_rate and target_prefix_match_rate > 0),
        "widening_authorized": False,
        "telemetry_counts": {
            "loss_by_step": count_jsonl(RUN_DIR / "loss_by_step.jsonl"),
            "row_token_loss": count_jsonl(RUN_DIR / "row_token_loss.jsonl"),
            "row_gradient_norms": count_jsonl(RUN_DIR / "row_gradient_norms.jsonl"),
            "activation_summary": count_jsonl(RUN_DIR / "activation_summary.jsonl"),
            "row_dynamics_history": count_jsonl(RUN_DIR / "row_dynamics_history.jsonl"),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Ran a capped longer target-rendered residual-denoise diagnostic probe. Widening remains closed regardless of quality.",
        "next_best_step": "Inspect Stage9570 quality. If generation is still malformed, patch target form and generation objective before widening.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9570 Residual Denoise Target-Rendered Longer Capped Probe", "", f"Passed: `{audit['passed']}`", f"Max steps: `{audit['max_steps']}`", f"First/final loss: `{first_loss}` / `{final_loss}`", f"Contentful generation rate: `{contentful_rate}`", f"Target prefix match rate: `{target_prefix_match_rate}`", "", "This is a diagnostic rerun only. Widening, decoder CE, runtime, Gemma, harness, source/body emission, and promotion remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "first_loss": first_loss, "final_loss": final_loss, "contentful_generation_rate": contentful_rate, "target_prefix_match_rate": target_prefix_match_rate, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
