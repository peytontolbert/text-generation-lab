#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9284
NAME = "stage9284_suffix_step_execution_review"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9283_suffix_step_contract_preflight.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9282_suffix_step_micro_overfit_manifest/suffix_step_micro_overfit_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REVIEW = OUT_DIR / "suffix_step_execution_review_card.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_STEP_EXECUTION_REVIEW_STAGE9284.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

AUTHORITY_NEXT = dict(AUTHORITY_CLOSED)
AUTHORITY_NEXT["model_execution_authorized_next"] = True
AUTHORITY_NEXT["denoise_ce_training_authorized_next"] = True

REQUIRED_LIMITS = {
    "mode": "denoise_repair_probe",
    "probe_scale": "target_100m",
    "max_train_rows": 5,
    "max_eval_rows": 1,
    "max_strict_rows": 2,
    "max_steps": 16,
    "batch_size_max": 2,
    "max_decoder_tokens": 160,
    "max_generation_rows": 8,
    "max_generation_tokens": 64,
    "decoder_ce_weight": 0.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 1.0,
    "runtime": False,
    "runtime_verifier_execution": False,
    "final_checkpoint_export": False,
    "cleanup_checkpoints_after_probe": True,
    "generation_prefix_field": "model_input.bridge_priming_span",
}

REQUIRED_FLAGS = [
    "--manifest",
    "--mode denoise_repair_probe",
    "--probe-scale target_100m",
    "--max-train-rows 5",
    "--max-eval-rows 1",
    "--max-strict-rows 2",
    "--max-steps 16",
    "--max-decoder-tokens 160",
    "--decoder-ce-weight 0.0",
    "--structured-aux-weight 0.0",
    "--denoise-weight 1.0",
    "--generation-prefix-field model_input.bridge_priming_span",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--execution-authorized-for-recovery-probe",
]

FORBIDDEN_OPERATIONS = [
    "decoder_ce_training",
    "runtime_execution",
    "runtime_verifier_execution",
    "source_emission",
    "body_emission",
    "gemma_execution",
    "harness_execution",
    "scoring",
    "final_checkpoint_export",
    "promotion",
    "controller_merge",
    "arxiv_cleanup",
    "repo_root_cleanup",
]

REQUIRED_POSTRUN_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "sample_generation_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def manifest_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def build_review() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    rows = load_jsonl(MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9283_not_passed")
    if metrics.get("trainer_contract_passed") is not True:
        failures.append("trainer_contract_not_passed")
    if metrics.get("suffix_step_execution_ready") is not True:
        failures.append("suffix_step_execution_not_ready")
    if metrics.get("loss_counts", {}).get("denoise_ce") != 8:
        failures.append("denoise_loss_count_not_8")
    if metrics.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_not_closed")
    if metrics.get("authority_rows") != 0 or metrics.get("unsafe_loss_rows") != 0:
        failures.append("manifest_safety_rows_nonzero")
    if metrics.get("missing_generation_prefix_rows") != 0 or metrics.get("prefix_target_mismatch_rows") != 0:
        failures.append("generation_prefix_contract_failed")
    if metrics.get("over_decoder_token_cap_rows") != 0:
        failures.append("decoder_token_cap_rows_nonzero")
    if len(rows) != REQUIRED_LIMITS["max_train_rows"] + REQUIRED_LIMITS["max_eval_rows"] + REQUIRED_LIMITS["max_strict_rows"]:
        failures.append("manifest_row_count_mismatch")
    review = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "failures": failures,
        "source_stage": 9283,
        "source_manifest": str(MANIFEST.relative_to(ROOT)),
        "source_manifest_sha256": manifest_sha256(MANIFEST),
        "execution_authorized_next": not failures,
        "authorization_scope": "one_tiny_suffix_step_denoise_probe_only",
        "authority": AUTHORITY_NEXT if not failures else dict(AUTHORITY_CLOSED),
        "required_limits": dict(REQUIRED_LIMITS),
        "required_flags": list(REQUIRED_FLAGS),
        "forbidden_operations": list(FORBIDDEN_OPERATIONS),
        "required_postrun_artifacts": list(REQUIRED_POSTRUN_ARTIFACTS),
        "explicit_user_authorization_observed": True,
        "safety_notes": [
            "Execution is limited to denoise_repair_probe on the Stage9282 suffix-step manifest.",
            "Decoder CE remains closed; this is not a free-form codegen or bounded-decoder CE milestone.",
            "Runtime, Gemma, harness, scoring, source/body emission, checkpoint export, promotion, and controller merge remain forbidden.",
            "Cleanup must be performed only through the trainer safe-cleanup path and must emit cleanup_proof.json.",
            "/arxiv and repo root deletion remain forbidden.",
        ],
    }
    return review


def validate_review(review: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    authority = review.get("authority") if isinstance(review.get("authority"), dict) else {}
    allowed_true = {"model_execution_authorized_next", "denoise_ce_training_authorized_next"}
    for key in AUTHORITY_CLOSED:
        value = bool(authority.get(key, False))
        if key in allowed_true:
            if review.get("passed") and value is not True:
                failures.append(f"required_authority_not_true:{key}")
        elif value:
            failures.append(f"forbidden_authority_true:{key}")
    if review.get("execution_authorized_next") is not review.get("passed"):
        failures.append("execution_authorized_next_mismatch")
    limits = review.get("required_limits") or {}
    for key, expected in REQUIRED_LIMITS.items():
        if limits.get(key) != expected:
            failures.append(f"limit_mismatch:{key}")
    for flag in REQUIRED_FLAGS:
        if flag not in (review.get("required_flags") or []):
            failures.append(f"missing_required_flag:{flag}")
    for op in FORBIDDEN_OPERATIONS:
        if op not in (review.get("forbidden_operations") or []):
            failures.append(f"missing_forbidden_operation:{op}")
    for artifact in REQUIRED_POSTRUN_ARTIFACTS:
        if artifact not in (review.get("required_postrun_artifacts") or []):
            failures.append(f"missing_required_postrun_artifact:{artifact}")
    if "/arxiv" in str(review.get("source_manifest")):
        failures.append("source_manifest_mentions_arxiv")
    return failures


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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": authority_counts}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    review = build_review()
    validation_failures = validate_review(review)
    if validation_failures:
        review["passed"] = False
        review["execution_authorized_next"] = False
        review["authority"] = dict(AUTHORITY_CLOSED)
        review["failures"] = list(review.get("failures") or []) + validation_failures
    REVIEW.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": review["passed"],
        "authority": review["authority"],
        "metrics": {
            **{key: bool(review["authority"].get(key, False)) for key in AUTHORITY_CLOSED},
            "execution_authorized_next": review["execution_authorized_next"],
            "review_failures": len(review.get("failures") or []),
            "source_stage": review["source_stage"],
            "manifest_rows": len(load_jsonl(MANIFEST)),
            "required_postrun_artifacts": len(REQUIRED_POSTRUN_ARTIFACTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
        },
        "artifacts": {"review": str(REVIEW.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT))},
        "decision": "Authorized exactly one next tiny suffix-step target-100M denoise probe." if review["passed"] else "Suffix-step execution review failed; do not run.",
        "next_best_step": "Run final pre-execution audit for the authorized suffix-step denoise probe, then execute only if it passes." if review["passed"] else "Fix review failures before any execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9284 Suffix-Step Execution Review",
            "",
            f"Passed: `{review['passed']}`",
            f"Execution authorized next: `{review['execution_authorized_next']}`",
            f"Scope: `{review['authorization_scope']}`",
            "",
            "Allowed next authority:",
            f"- model execution: `{bool(review['authority'].get('model_execution_authorized_next'))}`",
            f"- denoise CE training: `{bool(review['authority'].get('denoise_ce_training_authorized_next'))}`",
            "",
            "Still forbidden: decoder CE, runtime, Gemma, harness, scoring, source/body emission, checkpoint export, promotion, controller merge, /arxiv cleanup, and repo-root cleanup.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
