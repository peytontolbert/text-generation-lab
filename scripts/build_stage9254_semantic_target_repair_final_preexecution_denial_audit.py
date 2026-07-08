#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields
    from manifest_path_validator import validate_manifest_input_path
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields  # type: ignore
    from scripts.manifest_path_validator import validate_manifest_input_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9254
NAME = "stage9254_semantic_target_repair_final_preexecution_denial_audit"
SOURCES = {
    "stage9249": ROOT / "runs/summaries/stage9249_semantic_bounded_decoder_target_repair_package.json",
    "stage9250": ROOT / "runs/summaries/stage9250_semantic_bounded_decoder_target_repair_audit.json",
    "stage9251": ROOT / "runs/summaries/stage9251_semantic_target_repair_target_100m_contract_only_preflight.json",
    "stage9252": ROOT / "runs/summaries/stage9252_semantic_target_repair_bounded_decoder_execution_review.json",
}
TICKET = ROOT / "runs/local/artifacts/stage9252_semantic_target_repair_bounded_decoder_execution_review/semantic_target_repair_bounded_decoder_execution_review_inactive.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "semantic_target_repair_final_preexecution_denial_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SEMANTIC_TARGET_REPAIR_FINAL_PREEXECUTION_DENIAL_AUDIT_STAGE9254.md"

REQUIRED_DENIED = {
    "run_trainer",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "run_backward",
    "create_optimizer",
    "generate_model_output",
    "write_checkpoint",
    "export_checkpoint",
    "open_runtime",
    "call_gemma",
    "run_harness",
    "score_output",
    "emit_source_body",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
    "cleanup_checkpoints",
}

REQUIRED_ARG_FLAGS = {
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--max-decoder-tokens",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--output-dir",
    "--run-id",
    "--batch-size",
    "--max-encoder-tokens",
    "--learning-rate",
    "--implementation",
    "--probe-scale",
    "--model-config",
    "--tokenizer-json",
    "--tokenizer-config",
    "--tokenizer-hashlock",
    "--enable-generation-audit",
    "--max-generation-rows",
    "--max-generation-tokens",
    "--execution-authorized-for-recovery-probe",
}

REQUIRED_LIMITS = {
    "mode": "bounded_decoder_ce_probe",
    "probe_scale": "target_100m",
    "implementation": "transformer",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 768,
    "decoder_ce_weight": 1.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 0.0,
    "generation_audit_enabled": True,
    "max_generation_rows": 16,
    "max_generation_tokens": 96,
    "runtime": False,
    "gemma": False,
    "harness": False,
    "scoring": False,
    "source_body_emission": False,
    "final_checkpoint_export": False,
    "cleanup_checkpoints_after_probe": True,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def path_under_repo(path_text: str) -> bool:
    try:
        resolve_repo_path(path_text).resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def argv_value(argv: list[str], flag: str) -> str | None:
    try:
        idx = argv.index(flag)
    except ValueError:
        return None
    if idx + 1 >= len(argv):
        return None
    return str(argv[idx + 1])


def audit_ticket(ticket: dict[str, Any], summaries: dict[str, dict[str, Any]], registry: dict[str, Any], explicit_user_authorization_observed: bool = False) -> dict[str, Any]:
    failures: list[str] = []
    failures.extend(audit_diagnostic_ticket_fields(ticket))
    for name, summary in summaries.items():
        if summary.get("passed") is not True:
            failures.append(f"{name}_not_passed")
        if any((summary.get("authority") or {}).values()):
            failures.append(f"{name}_authority_open")
    if ticket.get("ticket_status") != "DESIGN_ONLY_INACTIVE":
        failures.append("ticket_not_design_only_inactive")
    for key in ["execution_authorized_now", "model_execution_authorized_now", "decoder_ce_training_authorized_now", "command_executable_now"]:
        if ticket.get(key) is not False:
            failures.append(f"{key}_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    if ticket.get("requires_explicit_user_authorization") is not True:
        failures.append("explicit_user_authorization_not_required")
    if explicit_user_authorization_observed is not False:
        failures.append("explicit_user_authorization_observed_in_denial_audit")
    if ticket.get("requires_fresh_pre_execution_audit") is not True:
        failures.append("fresh_pre_execution_audit_not_required")
    if any((ticket.get("authority") or {}).values()):
        failures.append("ticket_authority_open")
    denied = set(ticket.get("denied_operations_now") or [])
    missing_denied = sorted(REQUIRED_DENIED - denied)
    if missing_denied:
        failures.append(f"missing_denied_operations:{missing_denied}")
    limits = ticket.get("required_limits") or {}
    for key, expected in REQUIRED_LIMITS.items():
        if limits.get(key) != expected:
            failures.append(f"limit_mismatch:{key}")
    argv = [str(item) for item in ticket.get("future_argv") or []]
    missing_flags = sorted(flag for flag in REQUIRED_ARG_FLAGS if flag not in argv)
    if missing_flags:
        failures.append(f"missing_future_argv_flags:{missing_flags}")
    manifest = str(ticket.get("source_manifest_path") or "")
    manifest_validation = validate_manifest_input_path(manifest, repo_root=ROOT, must_exist=True)
    if not manifest_validation.get("allowed"):
        failures.append("manifest_path_not_allowed")
    manifest_path = resolve_repo_path(manifest)
    actual_manifest_sha = sha256_file(manifest_path) if manifest_path.exists() else ""
    expected_manifest_sha = str((summaries["stage9251"].get("metrics") or {}).get("manifest_sha256") or "")
    if actual_manifest_sha != expected_manifest_sha or ticket.get("source_manifest_sha256") != expected_manifest_sha:
        failures.append("manifest_sha_mismatch")
    if argv_value(argv, "--manifest") != manifest:
        failures.append("future_argv_manifest_mismatch")
    output_dir = str(ticket.get("future_output_dir") or "")
    if argv_value(argv, "--output-dir") != output_dir:
        failures.append("future_argv_output_dir_mismatch")
    if not path_under_repo(output_dir):
        failures.append("future_output_dir_not_under_repo")
    if "/arxiv" in output_dir:
        failures.append("future_output_dir_mentions_arxiv")
    if resolve_repo_path(output_dir).exists():
        failures.append("future_output_dir_already_exists")
    if argv_value(argv, "--run-id") != ticket.get("requested_stage_name"):
        failures.append("future_argv_run_id_mismatch")
    metrics = registry.get("metrics") or {}
    if int(metrics.get("latest_stage", -1)) not in {9252, STAGE}:
        failures.append(f"unexpected_registry_frontier:{metrics.get('latest_stage')}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "manifest_validation": manifest_validation,
        "actual_manifest_sha256": actual_manifest_sha,
        "expected_manifest_sha256": expected_manifest_sha,
        "future_output_dir_exists": resolve_repo_path(output_dir).exists(),
        "future_argv_flags_present": len(REQUIRED_ARG_FLAGS) - len(missing_flags),
        "future_argv_flags_required": len(REQUIRED_ARG_FLAGS),
        "missing_future_argv_flags": missing_flags,
        "denied_operations_present": len(REQUIRED_DENIED) - len(missing_denied),
        "denied_operations_required": len(REQUIRED_DENIED),
        "missing_denied_operations": missing_denied,
        "explicit_user_authorization_observed": explicit_user_authorization_observed,
        "current_execution_denied": ticket.get("execution_authorized_now") is False and explicit_user_authorization_observed is False,
    }


def negative_cases(ticket: dict[str, Any], summaries: dict[str, dict[str, Any]], registry: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[tuple[str, dict[str, Any], bool]] = []
    mutated = copy.deepcopy(ticket); cases.append(("explicit_authorization_observed", mutated, True))
    mutated = copy.deepcopy(ticket); mutated["execution_authorized_now"] = True; cases.append(("execution_opened", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["command_executable_now"] = True; cases.append(("command_executable", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["allowed_operations_now"] = ["run_trainer"]; cases.append(("operation_allowed", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["denied_operations_now"] = [item for item in mutated["denied_operations_now"] if item != "run_trainer"]; cases.append(("run_trainer_not_denied", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["required_limits"]["max_steps"] = 128; cases.append(("max_steps_widened", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["required_limits"]["runtime"] = True; cases.append(("runtime_opened", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["future_output_dir"] = "/arxiv/blocked"; cases.append(("arxiv_output", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["source_manifest_sha256"] = "bad"; cases.append(("manifest_hash_mismatch", mutated, False))
    mutated = copy.deepcopy(ticket); mutated["authority"]["model_execution_authorized_next"] = True; cases.append(("authority_open", mutated, False))
    results = []
    for name, candidate, observed_auth in cases:
        audit = audit_ticket(candidate, summaries, registry, explicit_user_authorization_observed=observed_auth)
        results.append({"case": name, "rejected": audit["passed"] is False, "failures": audit["failures"]})
    return results


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    summaries = {name: load_json(path) for name, path in SOURCES.items()}
    ticket = load_json(TICKET)
    registry = load_json(REGISTRY)
    audit = audit_ticket(ticket, summaries, registry)
    negatives = negative_cases(ticket, summaries, registry)
    if not all(item["rejected"] for item in negatives):
        audit["failures"].append("negative_cases_not_rejected")
        audit["passed"] = False
    AUDIT.write_text(json.dumps({**audit, "negative_cases": negatives}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives if item["rejected"]),
            "current_execution_denied": audit["current_execution_denied"],
            "explicit_user_authorization_observed": audit["explicit_user_authorization_observed"],
            "future_output_dir_exists": audit["future_output_dir_exists"],
            "manifest_sha_matches": audit["actual_manifest_sha256"] == audit["expected_manifest_sha256"],
            "future_argv_flags_present": audit["future_argv_flags_present"],
            "future_argv_flags_required": audit["future_argv_flags_required"],
            "denied_operations_present": audit["denied_operations_present"],
            "denied_operations_required": audit["denied_operations_required"],
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "decoder_ce_training_authorized_now": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "ticket": str(TICKET.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Final pre-execution denial audit passed: the repaired tiny probe is review-ready but current execution remains denied without explicit user authorization." if audit["passed"] else "Final pre-execution denial audit failed; do not execute Stage9253.",
        "next_best_step": "If the user explicitly authorizes one tiny execution, run Stage9253 exactly from the Stage9252 ticket; otherwise continue no-execution data/compiler work.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9254 Semantic Target Repair Final Pre-Execution Denial Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a no-execution final audit for the Stage9249/9251/9252 repaired bounded decoder path. It verifies that the future Stage9253 command is review-ready while current execution remains denied without explicit user authorization.",
        "",
        f"Current execution denied: `{audit['current_execution_denied']}`",
        f"Explicit user authorization observed: `{audit['explicit_user_authorization_observed']}`",
        f"Future output dir exists: `{audit['future_output_dir_exists']}`",
        f"Manifest hash matches Stage9251: `{audit['actual_manifest_sha256'] == audit['expected_manifest_sha256']}`",
        f"Future argv flags: `{audit['future_argv_flags_present']}` / `{audit['future_argv_flags_required']}`",
        f"Denied operations: `{audit['denied_operations_present']}` / `{audit['denied_operations_required']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}` / `{summary['metrics']['negative_cases']}`",
        "",
        "No trainer, model forward, backward pass, generation, checkpoint write, cleanup execution, runtime, Gemma, harness, scoring, source/body emission, mining, controller merge, or promotion is authorized by this stage.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
