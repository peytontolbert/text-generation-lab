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
STAGE = 8922
NAME = "stage8922_cleanup_proof_no_overwrite_finalization"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_POLICY = ROOT / "runs/local/artifacts/stage8921_future_probe_artifact_path_policy/future_probe_artifact_path_policy.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8921_future_probe_artifact_path_policy.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLEANUP_PROOF_NO_OVERWRITE_FINALIZATION_STAGE8922.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PROOF_CONTRACT = OUT_DIR / "cleanup_proof_no_overwrite_contract.json"
AUDIT = OUT_DIR / "cleanup_proof_no_overwrite_audit.json"

ALLOWED_OUTPUT_ROOT = ROOT / "runs/local/probes/stage8890_tiny_structured_policy_probe_candidate"
MARKER_FILE = ".agentkernel_probe_output"
CHECKPOINT_DIR_NAME = "checkpoints"

REQUIRED_CLEANUP_PROOF_FIELDS = [
    "repo_root",
    "output_dir",
    "run_id",
    "marker_file",
    "checkpoint_dir",
    "dry_run",
    "removed",
    "removed_count",
    "kept_artifacts",
    "no_overwrite_existing",
    "output_root_preexisted",
    "cleanup_scope",
    "unsafe_paths_refused",
]

ALLOWED_CLEANUP_SCOPE = "checkpoint_children_only"

FORBIDDEN_CLEANUP_TARGETS = [
    str(ROOT),
    str(ROOT / "runs"),
    str(ROOT / "runs/local"),
    str(ROOT / "runs/local/probes"),
    "/data",
    "/arxiv",
    "/",
]

FORBIDDEN_OPERATIONS = [
    "rm -rf",
    "shutil.rmtree(repo_root)",
    "shutil.rmtree(output_dir)",
    "delete_parent_dir",
    "follow_symlink_outside_output_dir",
    "overwrite_existing_probe_output",
    "delete_arxiv",
    "delete_data_root",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_cleanup_contract() -> dict[str, Any]:
    source_policy = load_json(SOURCE_POLICY)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stage": 8921,
        "contract_status": "NO_EXECUTION_TEMPLATE_ONLY",
        "allowed_output_root": str(ALLOWED_OUTPUT_ROOT),
        "allowed_output_root_must_not_exist_before_run": True,
        "no_overwrite_existing": True,
        "required_marker_file": MARKER_FILE,
        "required_run_id_source": "explicit_future_probe_ticket",
        "cleanup_scope": ALLOWED_CLEANUP_SCOPE,
        "checkpoint_dir_name": CHECKPOINT_DIR_NAME,
        "required_cleanup_proof_fields": REQUIRED_CLEANUP_PROOF_FIELDS,
        "required_kept_artifacts": source_policy.get("required_artifact_names", []),
        "forbidden_cleanup_targets": FORBIDDEN_CLEANUP_TARGETS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "symlink_escape_must_be_refused": True,
        "wrong_marker_or_run_id_must_be_refused": True,
        "missing_marker_must_be_refused": True,
        "output_dir_itself_delete_forbidden": True,
        "parent_delete_forbidden": True,
        "repo_root_delete_forbidden": True,
        "arxiv_delete_forbidden": True,
        "data_root_delete_forbidden": True,
        "model_execution_authorized_now": False,
        "training_authorized": False,
        "authority": AUTHORITY_CLOSED,
    }


def audit_cleanup_contract(contract: dict[str, Any], *, source_summary: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage8921_not_passed")
    if any((source_summary.get("authority") or {}).values()):
        failures.append("source_stage8921_authority_open")
    if contract.get("contract_status") != "NO_EXECUTION_TEMPLATE_ONLY":
        failures.append("contract_status_not_no_execution")
    if Path(str(contract.get("allowed_output_root", ""))).resolve(strict=False) != ALLOWED_OUTPUT_ROOT.resolve(strict=False):
        failures.append("allowed_output_root_mismatch")
    if contract.get("allowed_output_root_must_not_exist_before_run") is not True:
        failures.append("fresh_output_root_not_required")
    if contract.get("no_overwrite_existing") is not True:
        failures.append("no_overwrite_existing_not_required")
    if contract.get("cleanup_scope") != ALLOWED_CLEANUP_SCOPE:
        failures.append("cleanup_scope_not_checkpoint_children_only")
    if contract.get("required_marker_file") != MARKER_FILE:
        failures.append("marker_file_mismatch")
    if set(contract.get("required_cleanup_proof_fields") or []) != set(REQUIRED_CLEANUP_PROOF_FIELDS):
        failures.append("required_cleanup_proof_fields_mismatch")
    if not contract.get("required_kept_artifacts"):
        failures.append("required_kept_artifacts_missing")
    for flag in [
        "symlink_escape_must_be_refused",
        "wrong_marker_or_run_id_must_be_refused",
        "missing_marker_must_be_refused",
        "output_dir_itself_delete_forbidden",
        "parent_delete_forbidden",
        "repo_root_delete_forbidden",
        "arxiv_delete_forbidden",
        "data_root_delete_forbidden",
    ]:
        if contract.get(flag) is not True:
            failures.append(f"{flag}_not_true")
    if contract.get("model_execution_authorized_now") is not False:
        failures.append("model_execution_authorized_now_not_false")
    if contract.get("training_authorized") is not False:
        failures.append("training_authorized_not_false")
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8921, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return {
        "passed": not failures,
        "failures": failures,
        "required_cleanup_proof_fields": len(REQUIRED_CLEANUP_PROOF_FIELDS),
        "required_kept_artifacts": len(contract.get("required_kept_artifacts") or []),
        "forbidden_cleanup_targets": len(FORBIDDEN_CLEANUP_TARGETS),
        "forbidden_operations": len(FORBIDDEN_OPERATIONS),
        "registry_latest_stage_observed": latest,
    }


def negative_mutation_results(contract: dict[str, Any]) -> dict[str, Any]:
    registry = {"metrics": {"latest_stage": 8921, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source_summary = {"passed": True, "authority": AUTHORITY_CLOSED}
    mutations = {
        "allow_overwrite": lambda c: c.__setitem__("no_overwrite_existing", False),
        "delete_output_dir": lambda c: c.__setitem__("cleanup_scope", "output_dir"),
        "drop_marker": lambda c: c.__setitem__("required_marker_file", ""),
        "allow_repo_root_delete": lambda c: c.__setitem__("repo_root_delete_forbidden", False),
        "allow_arxiv_delete": lambda c: c.__setitem__("arxiv_delete_forbidden", False),
        "open_training": lambda c: c.__setitem__("training_authorized", True),
        "open_authority": lambda c: c.__setitem__("authority", {**AUTHORITY_CLOSED, "runtime_authorized": True}),
        "drop_cleanup_fields": lambda c: c.__setitem__("required_cleanup_proof_fields", REQUIRED_CLEANUP_PROOF_FIELDS[:-1]),
    }
    results: dict[str, Any] = {}
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(contract)
        mutate(candidate)
        audit = audit_cleanup_contract(candidate, source_summary=source_summary, registry=registry)
        results[name] = {"rejected": not audit["passed"], "failures": audit["failures"]}
    return results


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    contract = build_cleanup_contract()
    source_summary = load_json(SOURCE_SUMMARY)
    audit = audit_cleanup_contract(contract, source_summary=source_summary, registry=registry)
    negatives = negative_mutation_results(contract)
    failures = list(audit["failures"])
    for name, result in negatives.items():
        if result["rejected"] is not True:
            failures.append(f"negative_mutation_not_rejected:{name}")
    return {
        "contract": contract,
        "audit": {
            **audit,
            "passed": not failures,
            "failures": failures,
            "negative_mutation_checks": negatives,
            "negative_mutations": len(negatives),
            "negative_mutations_rejected": sum(1 for result in negatives.values() if result["rejected"]),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    payload = build_audit(registry)
    contract = payload["contract"]
    audit = payload["audit"]
    PROOF_CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            "negative_mutations": audit["negative_mutations"],
            "negative_mutations_rejected": audit["negative_mutations_rejected"],
            "required_cleanup_proof_fields": audit["required_cleanup_proof_fields"],
            "required_kept_artifacts": audit["required_kept_artifacts"],
            "forbidden_cleanup_targets": audit["forbidden_cleanup_targets"],
            "forbidden_operations": audit["forbidden_operations"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"contract": str(PROOF_CONTRACT.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Cleanup-proof/no-overwrite finalization contract passed; future cleanup may only remove checkpoint children under a marked fresh probe output and must preserve telemetry artifacts. No cleanup executed.",
        "next_best_step": "Before any future probe, add a preflight that checks the fresh output root does not exist, required telemetry names are reserved, and cleanup proof can be emitted without deleting non-checkpoint artifacts.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8922 Cleanup Proof No-Overwrite Finalization",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution stage finalizes the cleanup proof contract for any future explicitly authorized probe.",
        "",
        "Cleanup remains scoped to checkpoint children only under a fresh, marked probe output directory. Existing output roots, repo roots, parent directories, `/data`, `/arxiv`, source/body artifacts, telemetry artifacts, and symlink escapes are forbidden.",
        "",
        f"Required cleanup proof fields: `{audit['required_cleanup_proof_fields']}`",
        f"Required kept artifacts: `{audit['required_kept_artifacts']}`",
        f"Negative mutations rejected: `{audit['negative_mutations_rejected']}/{audit['negative_mutations']}`",
        "",
        "No cleanup was executed by this stage.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8922 Cleanup Proof No-Overwrite Finalization"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8922 finalizes the cleanup-proof/no-overwrite contract for future explicitly authorized probes. It requires a fresh marked probe output directory, preserves telemetry artifacts, forbids `/arxiv`, `/data`, repo-root, parent, output-dir, and symlink escape deletion, and permits cleanup only for checkpoint children. No cleanup is executed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
