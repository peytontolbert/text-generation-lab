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
STAGE = 9650
NAME = "stage9650_same_prefix_contrast_tiny_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9649_same_prefix_contrast_manifest.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9649_same_prefix_contrast_manifest/same_prefix_contrast_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUN_DIR = OUT_DIR / "episode_step_probe"
AUDIT = OUT_DIR / "same_prefix_contrast_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SAME_PREFIX_CONTRAST_TINY_PROBE_STAGE9650.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
EXPECTED_FIELDS = {"episode_boundary_match", "episode_target_prefix_match"}
REQUIRED = ["loss_by_step.jsonl", "eval_loss_by_checkpoint.jsonl", "row_field_logits.jsonl", "row_field_losses.jsonl", "row_gradient_norms.jsonl", "activation_summary.jsonl", "feature_ablation_attribution.jsonl", "activation_patch_recovery.jsonl", "row_dynamics_history.jsonl", "field_exact_by_cell.json", "field_label_vocabs.json", "structured_confusion_matrix.json", "module_delta_norms.json", "failure_bucket_card.json", "cleanup_proof.json"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "4", "--max-eval-rows", "4", "--max-strict-rows", "4", "--max-steps", "384", "--batch-size", "2", "--learning-rate", "3e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--eval-interval", "16", "--restore-best-structured-state", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9650_same_prefix_contrast_probe", "--execution-authorized-for-recovery-probe"]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def field_exact(split_card: dict[str, Any]) -> dict[str, float]:
    field_card = split_card.get("field_exact") if isinstance(split_card.get("field_exact"), dict) else {}
    return {key: float(value.get("exact") or 0.0) for key, value in field_card.items() if key in EXPECTED_FIELDS and isinstance(value, dict)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    failures: list[str] = []
    safety_failures: list[str] = []
    if source.get("passed") is not True:
        safety_failures.append("stage9649_not_passed")
    prefix_baselines = source_metrics.get("prefix_baselines") if isinstance(source_metrics.get("prefix_baselines"), dict) else {}
    if prefix_baselines and max(float(value) for value in prefix_baselines.values()) != 0.5:
        safety_failures.append("stage9649_prefix_shortcut_not_blocked")

    run = subprocess.run(command(), cwd=ROOT, text=True, capture_output=True, check=False) if not safety_failures else None
    if run is not None and run.returncode != 0:
        safety_failures.append("execution_failed")
    result = load_json(RUN_DIR / "execution_result.json")
    if not result:
        safety_failures.append("missing_execution_result")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    if missing:
        safety_failures.append("missing_required_artifacts")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    if float(module_delta.get("decoder_delta_norm") or 0.0) != 0.0:
        safety_failures.append("decoder_delta_nonzero")

    logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    observed_fields = {str(row.get("field")) for row in logits}
    unexpected_fields = sorted(observed_fields - EXPECTED_FIELDS)
    if unexpected_fields:
        safety_failures.append("unexpected_field_logits_present")
    wrong_by_field = Counter(str(row.get("field")) for row in logits if row.get("correct") is False)
    pred_pairs = Counter(f"{row.get('split')}::{row.get('field')}::{row.get('target')}=>{row.get('pred')}" for row in logits if row.get("correct") is False)
    high_conf_wrong = [row for row in logits if row.get("high_confidence_wrong")]
    eval_card = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    eval_split = eval_card.get("eval") if isinstance(eval_card.get("eval"), dict) else {}
    strict = eval_card.get("strict_eval") if isinstance(eval_card.get("strict_eval"), dict) else {}
    eval_exact = field_exact(eval_split)
    strict_exact = field_exact(strict)
    eval_joint = float(eval_split.get("joint_proxy_exact", 0.0) or 0.0)
    strict_joint = float(strict.get("joint_proxy_exact", 0.0) or 0.0)
    quality_pass = bool(eval_joint == 1.0 and all(v == 1.0 for v in eval_exact.values()) and len(eval_exact) == len(EXPECTED_FIELDS) and not high_conf_wrong)
    if not quality_pass:
        failures.append("quality_gate_not_passed")
    if safety_failures:
        failures.extend(safety_failures)
    audit = {"passed": not failures, "safety_passed": not safety_failures, "quality_passed": quality_pass, "failures": failures, "safety_failures": safety_failures, "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT)), "trainer_returncode": None if run is None else run.returncode, "probe_scale": impl.get("probe_scale"), "estimated_parameter_count": impl.get("estimated_parameter_count"), "mode": result.get("mode"), "train_rows": result.get("train_rows"), "eval_rows": result.get("eval_rows"), "strict_rows": result.get("strict_rows"), "eval_joint_proxy_exact": eval_joint, "strict_joint_proxy_exact": strict_joint, "eval_field_exact": eval_exact, "strict_field_exact": strict_exact, "wrong_by_field": dict(sorted(wrong_by_field.items())), "top_wrong_pred_pairs": dict(pred_pairs.most_common(20)), "high_confidence_wrong_rows": len(high_conf_wrong), "unexpected_fields": unexpected_fields, "missing_required_artifacts": missing, "decoder_delta_norm": module_delta.get("decoder_delta_norm"), "runtime_executed": result.get("runtime_executed"), "gemma_executed": result.get("gemma_executed"), "harness_executed": result.get("harness_executed"), "final_checkpoint_exported": result.get("final_checkpoint_exported"), "authority": dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If Stage9650 passes, widen to a 24-row same-prefix contrast probe; if it fails, inspect structured head direction and consider direct comparator feature injection."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT)), "execution_result": str((RUN_DIR / "execution_result.json").relative_to(ROOT))}, "decision": "Same-prefix contrast target-100M probe executed safely." if not safety_failures else "Safety failed; do not use probe result.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9650 Same-Prefix Contrast Tiny Probe", "", f"Passed: `{audit['passed']}`", f"Safety passed: `{audit['safety_passed']}`", f"Quality passed: `{audit['quality_passed']}`", f"Eval/strict joint: `{eval_joint}` / `{strict_joint}`", f"Eval field exact: `{eval_exact}`", f"Strict field exact: `{strict_exact}`", f"Wrong by field: `{dict(sorted(wrong_by_field.items()))}`", "", "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "safety_passed": audit["safety_passed"], "quality_passed": audit["quality_passed"], "eval_joint_proxy_exact": eval_joint, "strict_joint_proxy_exact": strict_joint, "eval_field_exact": eval_exact, "strict_field_exact": strict_exact, "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if safety_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
