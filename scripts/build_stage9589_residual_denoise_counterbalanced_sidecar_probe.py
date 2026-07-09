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
STAGE = 9589
NAME = "stage9589_residual_denoise_counterbalanced_sidecar_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9588_residual_denoise_counterbalanced_sidecar_shortcut_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9587_residual_denoise_counterbalanced_sidecar_manifest/residual_denoise_counterbalanced_sidecar_manifest.jsonl"
RUN_ROOT = ROOT / "runs/local/artifacts" / NAME
CONTRACT_DIR = RUN_ROOT / "contract_preflight"
RUN_DIR = RUN_ROOT / "counterbalanced_sidecar_probe"
AUDIT = RUN_ROOT / "residual_denoise_structured_decision_sidecar_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCED_SIDECAR_PROBE_STAGE9589.md"
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


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "structured_policy_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "60", "--max-eval-rows", "16", "--max-strict-rows", "20",
        "--max-steps", "80", "--batch-size", "2", "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--eval-interval", "8", "--restore-best-structured-state",
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


def latest_split(records: list[dict[str, Any]], split: str) -> dict[str, Any]:
    selected = [record for record in records if record.get("split") == split and not record.get("checkpoint_eval")]
    if selected:
        return selected[-1]
    selected = [record for record in records if record.get("split") == split]
    return selected[-1] if selected else {}


def main() -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9584_not_passed")
    if len(rows) != 96:
        failures.append("manifest_row_count_not_96")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("loss_mask") or {}).get("suffix_choice_ce") is not True for row in rows):
        failures.append("missing_suffix_choice_ce_rows")
    if any((row.get("loss_mask") or {}).get("decoder_ce") or (row.get("loss_mask") or {}).get("denoise_ce") for row in rows):
        failures.append("decoder_or_denoise_loss_rows_present")

    if not failures:
        contract = subprocess.run(command(output_dir=CONTRACT_DIR, run_id="stage9589_contract_preflight", contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    contract_card = load_json(CONTRACT_DIR / "probe_contract_audit.json")
    if contract_card and contract_card.get("passed") is not True:
        failures.append("contract_card_not_passed")

    if not failures:
        run = subprocess.run(command(output_dir=RUN_DIR, run_id="stage9589_counterbalanced_sidecar_probe", contract_only=False), cwd=ROOT, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            failures.append("execution_failed")
    else:
        run = None

    execution = load_json(RUN_DIR / "execution_result.json")
    eval_records = [json.loads(line) for line in (RUN_DIR / "eval_loss_by_checkpoint.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()] if (RUN_DIR / "eval_loss_by_checkpoint.jsonl").exists() else []
    eval_final = latest_split(eval_records, "eval")
    strict_final = latest_split(eval_records, "strict_eval")
    eval_exact = ((eval_final.get("field_exact") or {}).get("suffix_choice") or {}).get("exact")
    strict_exact = ((strict_final.get("field_exact") or {}).get("suffix_choice") or {}).get("exact")
    pass_gate = eval_exact is not None and strict_exact is not None and eval_exact >= 0.95 and strict_exact >= 0.95
    if run is not None and not execution:
        failures.append("missing_execution_result")
    decoder_ce_rows = int(execution.get("decoder_ce_rows") or 0) if execution else None
    denoise_ce_rows = int(execution.get("denoise_ce_rows") or 0) if execution else None
    if execution and decoder_ce_rows != 0:
        failures.append("decoder_ce_rows_present")
    if execution and denoise_ce_rows != 0:
        failures.append("denoise_ce_rows_present")
    if execution and execution.get("runtime_executed") is not False:
        failures.append("runtime_executed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "contract_returncode": None if contract is None else contract.returncode,
        "execution_returncode": None if run is None else run.returncode,
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "eval_suffix_choice_exact": eval_exact,
        "strict_suffix_choice_exact": strict_exact,
        "eval_joint_proxy_exact": eval_final.get("joint_proxy_exact"),
        "strict_joint_proxy_exact": strict_final.get("joint_proxy_exact"),
        "pass_gate": pass_gate,
        "decoder_ce_rows": decoder_ce_rows,
        "denoise_ce_rows": denoise_ce_rows,
        "runtime_executed": execution.get("runtime_executed"),
        "widening_authorized": False,
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
        "decision": "Ran a capped target_100M structured suffix_choice sidecar probe for the residual-denoise boundary repair decision.",
        "next_best_step": "If the counterbalanced sidecar passes, compile sidecar-gated denoise rendering rows; otherwise inspect row-level logits and add harder verifier-evidence rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9589 Residual Denoise Counterbalanced Sidecar Probe", "", f"Passed: `{audit['passed']}`", f"Eval suffix choice exact: `{eval_exact}`", f"Strict suffix choice exact: `{strict_exact}`", f"Pass gate: `{pass_gate}`", "", "Decoder, denoise, runtime, export, harness, and promotion remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "eval_suffix_choice_exact": eval_exact, "strict_suffix_choice_exact": strict_exact, "pass_gate": pass_gate, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
