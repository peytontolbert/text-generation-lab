#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9582
NAME = "stage9582_residual_denoise_neutral_boundary_decision_capped_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9581_residual_denoise_neutral_boundary_decision_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9581_residual_denoise_neutral_boundary_decision_manifest/residual_denoise_neutral_boundary_decision_manifest.jsonl"
RUN_ROOT = ROOT / "runs/local/artifacts" / NAME
CONTRACT_DIR = RUN_ROOT / "contract_preflight"
RUN_DIR = RUN_ROOT / "denoise_repair_probe"
AUDIT = RUN_ROOT / "residual_denoise_neutral_boundary_decision_capped_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_NEUTRAL_BOUNDARY_DECISION_CAPPED_PROBE_STAGE9582.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
GENERATION_PREFIX_FIELD = "model_input.repair_decision_prefix"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bucket(text: str) -> str:
    value = str(text)
    if value.startswith("REPAIR_DECISION=YES"):
        return "YES"
    if value.startswith("REPAIR_DECISION=NO"):
        return "NO"
    return "OTHER"


def command(*, output_dir: Path, run_id: str, contract_only: bool) -> list[str]:
    cmd = [
        "env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}",
        "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST),
        "--mode", "denoise_repair_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON),
        "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "30", "--max-eval-rows", "8", "--max-strict-rows", "10",
        "--max-steps", "80", "--batch-size", "2", "--learning-rate", "5e-5",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "96",
        "--decoder-ce-weight", "0.0", "--structured-aux-weight", "0.0", "--denoise-weight", "1.0", "--eos-loss-weight", "1.0",
        "--enable-generation-audit", "--max-generation-rows", "16", "--max-generation-tokens", "48",
        "--generation-audit-splits", "train,eval,strict_eval", "--generation-prefix-field", GENERATION_PREFIX_FIELD,
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
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9581_not_passed")
    if (source.get("metrics") or {}).get("generation_prefix_field") != GENERATION_PREFIX_FIELD:
        failures.append("stage9581_generation_prefix_field_mismatch")
    if len(rows) != 48:
        failures.append("manifest_row_count_not_48")
    if any(any((row.get("authority") or {}).values()) for row in rows):
        failures.append("authority_rows_present")
    if any((row.get("loss_mask") or {}).get("denoise_ce") is not True for row in rows):
        failures.append("missing_denoise_ce_rows")

    if not failures:
        contract = subprocess.run(command(output_dir=CONTRACT_DIR, run_id="stage9582_contract_preflight", contract_only=True), cwd=ROOT, text=True, capture_output=True, check=False)
        if contract.returncode != 0:
            failures.append("contract_preflight_failed")
    else:
        contract = None
    contract_card = load_json(CONTRACT_DIR / "probe_contract_audit.json")
    if contract_card and contract_card.get("passed") is not True:
        failures.append("contract_card_not_passed")

    if not failures:
        run = subprocess.run(command(output_dir=RUN_DIR, run_id="stage9582_neutral_boundary_decision_probe", contract_only=False), cwd=ROOT, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            failures.append("execution_failed")
    else:
        run = None

    execution = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    samples = (load_json(RUN_DIR / "sample_generation_audit.json").get("samples") or [])
    target_counts: Counter[str] = Counter()
    pred_counts: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = {}
    exact_rows = 0
    next_token_matches = 0
    next_token_available = 0
    for row in samples:
        target = bucket(str(row.get("target_text") or ""))
        pred = bucket(str(row.get("generated_text") or ""))
        target_counts[target] += 1
        pred_counts[pred] += 1
        confusion.setdefault(target, Counter())[pred] += 1
        exact_rows += int(bool(row.get("exact_match")))
        boundary_next = row.get("boundary_next_token") if isinstance(row.get("boundary_next_token"), dict) else {}
        if boundary_next.get("available"):
            next_token_available += 1
            next_token_matches += int(bool(boundary_next.get("match")))
    yes_target = target_counts.get("YES", 0)
    yes_recall = confusion.get("YES", Counter()).get("YES", 0) / yes_target if yes_target else None
    no_target = target_counts.get("NO", 0)
    no_recall = confusion.get("NO", Counter()).get("NO", 0) / no_target if no_target else None
    exact_rate = exact_rows / len(samples) if samples else 0.0
    next_token_match_rate = next_token_matches / next_token_available if next_token_available else None
    sample_balanced = target_counts.get("YES") == target_counts.get("NO") == 8
    class_gate_passed = (
        sample_balanced
        and yes_recall is not None
        and yes_recall >= 0.85
        and no_recall is not None
        and no_recall >= 0.85
        and next_token_match_rate is not None
        and next_token_match_rate >= 0.85
    )
    if run is not None and not execution:
        failures.append("missing_execution_result")
    if execution and execution.get("denoise_ce_rows") != 48:
        failures.append("denoise_ce_rows_not_48")
    if execution and execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")
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
        "generated_rows": execution.get("generated_rows"),
        "contentful_generation_rate": execution.get("contentful_generation_rate"),
        "target_prefix_match_rate": execution.get("target_prefix_match_rate"),
        "short_or_junk_rate": execution.get("short_or_junk_rate"),
        "degenerate_repetition_rate": execution.get("degenerate_repetition_rate"),
        "exact_rows": exact_rows,
        "exact_rate": exact_rate,
        "sample_balanced": sample_balanced,
        "target_counts": dict(sorted(target_counts.items())),
        "pred_counts": dict(sorted(pred_counts.items())),
        "confusion": {key: dict(sorted(value.items())) for key, value in sorted(confusion.items())},
        "yes_recall": yes_recall,
        "no_recall": no_recall,
        "boundary_next_token_available": next_token_available,
        "boundary_next_token_matches": next_token_matches,
        "boundary_next_token_match_rate": next_token_match_rate,
        "generation_prefix_field": GENERATION_PREFIX_FIELD,
        "class_gate_passed": class_gate_passed,
        "widening_authorized": False,
        "quality": quality,
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
        "decision": "Ran a capped target_100M denoise probe over the neutral YES/NO boundary-decision target surface.",
        "next_best_step": "If YES/NO recall passes, integrate the neutral repair-decision surface into the residual-denoise route; otherwise inspect class logits and build a small structured-head sidecar before decoder denoise.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9582 Residual Denoise Neutral Boundary Decision Capped Probe", "", f"Passed: `{audit['passed']}`", f"Sample balanced: `{sample_balanced}`", f"YES recall: `{yes_recall}`", f"NO recall: `{no_recall}`", f"Boundary next-token match rate: `{next_token_match_rate}`", f"Class gate passed: `{class_gate_passed}`", "", "The probe remains denoise-only and authority-closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "sample_balanced": sample_balanced, "yes_recall": yes_recall, "no_recall": no_recall, "boundary_next_token_match_rate": next_token_match_rate, "class_gate_passed": class_gate_passed, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
