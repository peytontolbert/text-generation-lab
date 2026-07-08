#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9460
NAME = "stage9460_episode_step_target_100m_tiny_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9459_episode_step_target_100m_execution_authorization_review.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9460_episode_step_target_100m_tiny_probe"
EXECUTION = RUN_DIR / "execution_result.json"
AUDIT = RUN_DIR / "stage9460_tiny_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EPISODE_STEP_TARGET_100M_TINY_PROBE_AUDIT_STAGE9460.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    result = load_json(EXECUTION)
    failures: list[str] = []
    safety_failures: list[str] = []
    if source.get("passed") is not True or not source.get("metrics", {}).get("execution_authorized_for_next_stage"):
        safety_failures.append("source_stage9459_not_authorized")
    if not result:
        safety_failures.append("missing_execution_result")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    if impl.get("probe_scale") != "target_100m":
        safety_failures.append("not_target_100m_execution")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        safety_failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        safety_failures.append("final_checkpoint_exported")
    if result.get("required_artifacts_written") is not True:
        safety_failures.append("required_artifacts_not_written")
    missing_artifacts = [name for name in REQUIRED_ARTIFACTS if not (RUN_DIR / name).exists()]
    if missing_artifacts:
        safety_failures.append("missing_required_artifacts")
    row_logits = load_jsonl(RUN_DIR / "row_field_logits.jsonl")
    high_conf_wrong = [row for row in row_logits if row.get("high_confidence_wrong")]
    wrong_by_field = Counter(str(row.get("field")) for row in row_logits if row.get("correct") is False)
    eval_card = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    eval_split = eval_card.get("eval") if isinstance(eval_card.get("eval"), dict) else {}
    strict = eval_card.get("strict_eval") if isinstance(eval_card.get("strict_eval"), dict) else {}
    strict_joint = float(strict.get("joint_proxy_exact", 0.0) or 0.0)
    eval_joint = float(eval_split.get("joint_proxy_exact", 0.0) or 0.0)
    strict_field_exact = {
        key: value.get("exact") for key, value in (strict.get("field_exact") if isinstance(strict.get("field_exact"), dict) else {}).items()
        if isinstance(value, dict)
    }
    quality_pass = (
        strict_joint >= 0.80
        and all(float(value or 0.0) >= 0.80 for value in strict_field_exact.values())
        and len(high_conf_wrong) == 0
    )
    if not quality_pass:
        failures.append("quality_gate_not_passed")
    if safety_failures:
        failures.extend(safety_failures)
    audit = {
        "passed": not failures,
        "safety_passed": not safety_failures,
        "quality_passed": quality_pass,
        "failures": failures,
        "safety_failures": safety_failures,
        "source_stage": "stage9459_episode_step_target_100m_execution_authorization_review",
        "probe_scale": impl.get("probe_scale"),
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "mode": result.get("mode"),
        "train_rows": result.get("train_rows"),
        "eval_rows": result.get("eval_rows"),
        "strict_rows": result.get("strict_rows"),
        "eval_joint_proxy_exact": eval_joint,
        "strict_joint_proxy_exact": strict_joint,
        "strict_field_exact": strict_field_exact,
        "wrong_by_field": dict(sorted(wrong_by_field.items())),
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "required_artifacts_written": result.get("required_artifacts_written"),
        "missing_required_artifacts": missing_artifacts,
        "runtime_executed": result.get("runtime_executed"),
        "gemma_executed": result.get("gemma_executed"),
        "harness_executed": result.get("harness_executed"),
        "final_checkpoint_exported": result.get("final_checkpoint_exported"),
        "diagnosis": "Safe target-100M structured execution worked, but strict row predicts the successful prior for residual outcome/failure/value. Next curriculum should add observation-conditioned diagnosis or more contrastive residual support before widening.",
        "authority": dict(AUTHORITY_CLOSED),
        "model_execution_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "execution_result": str(EXECUTION.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9460 executed safely but failed quality on strict episode-step outcome/failure/value prediction.",
        "next_best_step": "Build Stage9461 observation-conditioned episode-step diagnosis manifest or counterbalanced residual-support rows before another target-100M execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage9460 Episode-Step Target-100M Tiny Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Safety passed: `{audit['safety_passed']}`",
        f"Quality passed: `{audit['quality_passed']}`",
        f"Strict joint proxy exact: `{strict_joint}`",
        f"Eval joint proxy exact: `{eval_joint}`",
        f"Wrong by field: `{dict(sorted(wrong_by_field.items()))}`",
        "",
        audit["diagnosis"],
        "",
        "Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.",
        "",
    ]))
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows)}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "safety_passed": audit["safety_passed"], "quality_passed": audit["quality_passed"], "strict_joint_proxy_exact": strict_joint}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
