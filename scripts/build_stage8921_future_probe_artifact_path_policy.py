#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8921
NAME = "stage8921_future_probe_artifact_path_policy"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8913_future_live_ticket_builder_skeleton/future_stage8890_live_ticket_template_inactive.json"
SOURCE_AUDIT = ROOT / "runs/summaries/stage8915_future_ticket_pre_execution_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_PROBE_ARTIFACT_PATH_POLICY_STAGE8921.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
POLICY = OUT_DIR / "future_probe_artifact_path_policy.json"
AUDIT = OUT_DIR / "future_probe_artifact_path_policy_audit.json"

ALLOWED_OUTPUT_ROOT = ROOT / "runs/local/probes/stage8890_tiny_structured_policy_probe_candidate"
FORBIDDEN_PATH_PREFIXES = [
    ROOT,
    ROOT / "runs/summaries",
    ROOT / "docs",
    ROOT / "scripts",
    ROOT / "tests",
    Path("/arxiv"),
    Path("/data"),
    Path("/"),
]
FORBIDDEN_WRITE_KINDS = {
    "checkpoint",
    "final_checkpoint",
    "promotion_marker",
    "runtime_result",
    "gemma_score",
    "harness_score",
    "source_body",
    "hidden_reference_artifact",
    "locked_eval_artifact",
    "model_output_for_product",
}
ALLOWED_WRITE_KINDS = {
    "diagnostic_jsonl",
    "diagnostic_json",
    "cleanup_proof",
    "failure_bucket_card",
    "structured_probe_telemetry_after_future_explicit_authorization_only",
}
REQUIRED_ARTIFACT_NAMES = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "module_delta_norms.json",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_relative_safe_name(name: str) -> bool:
    p = Path(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and len(p.parts) == 1


def build_policy() -> dict[str, Any]:
    return {
        "policy_status": "NO_EXECUTION_TEMPLATE_ONLY",
        "allowed_output_root": str(ALLOWED_OUTPUT_ROOT),
        "allowed_output_root_must_not_exist_before_run": True,
        "no_overwrite_existing": True,
        "create_parents_allowed": True,
        "allowed_write_kinds": sorted(ALLOWED_WRITE_KINDS),
        "forbidden_write_kinds": sorted(FORBIDDEN_WRITE_KINDS),
        "required_artifact_names": list(REQUIRED_ARTIFACT_NAMES),
        "forbidden_path_prefixes": [str(path) for path in FORBIDDEN_PATH_PREFIXES],
        "path_traversal_forbidden": True,
        "absolute_artifact_names_forbidden": True,
        "symlink_follow_forbidden": True,
        "checkpoint_export_forbidden": True,
        "runtime_result_forbidden": True,
        "source_body_forbidden": True,
        "hidden_or_locked_eval_artifacts_forbidden": True,
        "model_execution_authorized_now": False,
        "training_authorized": False,
        "authority": AUTHORITY_CLOSED,
    }


def audit_artifact_path_policy(policy: dict[str, Any], *, root_exists: bool | None = None) -> list[str]:
    failures: list[str] = []
    allowed_root = Path(str(policy.get("allowed_output_root", "")))
    try:
        allowed_resolved = allowed_root.resolve(strict=False)
    except RuntimeError:
        failures.append("allowed_output_root_resolution_failed")
        allowed_resolved = allowed_root
    expected = ALLOWED_OUTPUT_ROOT.resolve(strict=False)
    if allowed_resolved != expected:
        failures.append("allowed_output_root_mismatch")
    if not str(allowed_resolved).startswith(str((ROOT / "runs/local/probes").resolve(strict=False)) + "/"):
        failures.append("allowed_output_root_not_under_probe_root")
    if policy.get("allowed_output_root_must_not_exist_before_run") is not True:
        failures.append("fresh_output_root_not_required")
    if root_exists is None:
        root_exists = allowed_root.exists()
    if root_exists:
        failures.append("allowed_output_root_already_exists")
    if policy.get("no_overwrite_existing") is not True:
        failures.append("no_overwrite_existing_not_required")
    if policy.get("path_traversal_forbidden") is not True:
        failures.append("path_traversal_not_forbidden")
    if policy.get("absolute_artifact_names_forbidden") is not True:
        failures.append("absolute_artifact_names_not_forbidden")
    if policy.get("symlink_follow_forbidden") is not True:
        failures.append("symlink_follow_not_forbidden")
    allowed = set(policy.get("allowed_write_kinds") or [])
    forbidden = set(policy.get("forbidden_write_kinds") or [])
    if not ALLOWED_WRITE_KINDS.issubset(allowed):
        failures.append("missing_allowed_write_kinds")
    if not FORBIDDEN_WRITE_KINDS.issubset(forbidden):
        failures.append("missing_forbidden_write_kinds")
    if allowed & forbidden:
        failures.append("write_kind_allowed_and_forbidden_overlap")
    for flag in ["checkpoint_export_forbidden", "runtime_result_forbidden", "source_body_forbidden", "hidden_or_locked_eval_artifacts_forbidden"]:
        if policy.get(flag) is not True:
            failures.append(f"{flag}_not_true")
    for name in policy.get("required_artifact_names") or []:
        if not is_relative_safe_name(str(name)):
            failures.append(f"unsafe_required_artifact_name:{name}")
    if set(policy.get("required_artifact_names") or []) != set(REQUIRED_ARTIFACT_NAMES):
        failures.append("required_artifact_names_mismatch")
    if policy.get("model_execution_authorized_now") is not False:
        failures.append("model_execution_authorized_now_not_false")
    if policy.get("training_authorized") is not False:
        failures.append("training_authorized_not_false")
    if any((policy.get("authority") or {}).values()):
        failures.append("authority_open")
    return failures


def negative_mutation_results(policy: dict[str, Any]) -> dict[str, Any]:
    mutations = {
        "path_traversal_root": lambda p: p.__setitem__("allowed_output_root", str(ALLOWED_OUTPUT_ROOT / ".." / "escape")),
        "arxiv_root": lambda p: p.__setitem__("allowed_output_root", "/arxiv/probes/bad"),
        "repo_root": lambda p: p.__setitem__("allowed_output_root", str(ROOT)),
        "existing_root": lambda p: None,
        "allow_checkpoint": lambda p: p["allowed_write_kinds"].append("checkpoint"),
        "missing_forbidden_hidden": lambda p: p.__setitem__("forbidden_write_kinds", [x for x in p["forbidden_write_kinds"] if x != "hidden_reference_artifact"]),
        "unsafe_artifact_name": lambda p: p["required_artifact_names"].append("../escape.json"),
        "open_authority": lambda p: p.__setitem__("authority", {**AUTHORITY_CLOSED, "runtime_authorized": True}),
    }
    results: dict[str, Any] = {}
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(policy)
        mutate(candidate)
        failures = audit_artifact_path_policy(candidate, root_exists=(name == "existing_root"))
        results[name] = {"rejected": bool(failures), "failures": failures}
    return results


def build_audit(registry: dict[str, Any], source_ticket: dict[str, Any], source_audit: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("source_ticket_not_inactive")
    if source_audit.get("passed") is not True:
        failures.append("source_stage8915_not_passed")
    if any((source_audit.get("authority") or {}).values()):
        failures.append("source_stage8915_authority_open")
    policy_failures = audit_artifact_path_policy(policy, root_exists=False)
    if policy_failures:
        failures.append(f"policy_failed:{policy_failures}")
    negatives = negative_mutation_results(policy)
    for name, result in negatives.items():
        if result["rejected"] is not True:
            failures.append(f"negative_mutation_not_rejected:{name}")
    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8918, 8919, 8920, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "policy_failures": policy_failures,
        "negative_mutation_checks": negatives,
        "negative_mutations_rejected": sum(1 for r in negatives.values() if r["rejected"]),
        "required_artifact_names": len(REQUIRED_ARTIFACT_NAMES),
        "forbidden_write_kinds": len(FORBIDDEN_WRITE_KINDS),
        "allowed_write_kinds": len(ALLOWED_WRITE_KINDS),
        "registry_latest_stage_observed": latest,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    source_ticket = load_json(SOURCE_TICKET)
    source_audit = load_json(SOURCE_AUDIT)
    policy = build_policy()
    audit = build_audit(registry, source_ticket, source_audit, policy)
    POLICY.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": audit["failures"],
            "policy_failures": len(audit["policy_failures"]),
            "negative_mutations": len(audit["negative_mutation_checks"]),
            "negative_mutations_rejected": audit["negative_mutations_rejected"],
            "required_artifact_names": audit["required_artifact_names"],
            "forbidden_write_kinds": audit["forbidden_write_kinds"],
            "allowed_write_kinds": audit["allowed_write_kinds"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"policy": str(POLICY.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Future probe artifact path policy passed; future outputs are constrained to a fresh scoped probe directory with unsafe write classes denied. No execution is opened." if audit["passed"] else "Future probe artifact path policy failed.",
        "next_best_step": "Use this policy in any future explicitly authorized one-run probe before artifact writes; next no-execution work can target cleanup proof and no-overwrite finalization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8921 Future Probe Artifact Path Policy",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution policy constrains future authorized probe artifacts to a fresh scoped directory under `runs/local/probes/` and rejects path traversal, `/arxiv`, repo-root writes, checkpoint/promotion/runtime/source outputs, hidden refs, and overwrite behavior.",
        "",
        "No execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, scoring, controller merge, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8921 Future Probe Artifact Path Policy"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8921 constrains any future authorized probe outputs to a fresh scoped `runs/local/probes/stage8890...` directory and rejects overwrite, path traversal, `/arxiv`, repo-root, checkpoint, promotion, runtime, hidden-ref, and source/body artifact writes.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
