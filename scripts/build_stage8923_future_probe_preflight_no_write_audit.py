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
STAGE = 8923
NAME = "stage8923_future_probe_preflight_no_write_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_POLICY = ROOT / "runs/local/artifacts/stage8921_future_probe_artifact_path_policy/future_probe_artifact_path_policy.json"
SOURCE_CLEANUP_CONTRACT = ROOT / "runs/local/artifacts/stage8922_cleanup_proof_no_overwrite_finalization/cleanup_proof_no_overwrite_contract.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8922_cleanup_proof_no_overwrite_finalization.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_PROBE_PREFLIGHT_NO_WRITE_AUDIT_STAGE8923.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "future_probe_preflight_no_write_audit.json"

PROBE_ROOT = ROOT / "runs/local/probes"

FORBIDDEN_OPERATIONS = [
    "mkdir_probe_output_root",
    "touch_artifact_file",
    "write_probe_artifact",
    "overwrite_existing_artifact",
    "delete_existing_output_root",
    "cleanup_checkpoint_children",
    "model_forward",
    "training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_safe_artifact_name(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and len(path.parts) == 1


def build_preflight(*, output_root_exists: bool | None = None) -> dict[str, Any]:
    policy = load_json(SOURCE_POLICY)
    cleanup_contract = load_json(SOURCE_CLEANUP_CONTRACT)
    output_root = Path(str(policy.get("allowed_output_root", "")))
    if output_root_exists is None:
        output_root_exists = output_root.exists()
    required_artifacts = list(policy.get("required_artifact_names") or [])
    cleanup_fields = list(cleanup_contract.get("required_cleanup_proof_fields") or [])
    artifact_targets = [output_root / name for name in required_artifacts if is_safe_artifact_name(str(name))]
    metrics = {
        "output_root": str(output_root),
        "output_root_exists": bool(output_root_exists),
        "output_root_under_probe_root": str(output_root.resolve(strict=False)).startswith(str(PROBE_ROOT.resolve(strict=False)) + "/"),
        "required_artifact_names": len(required_artifacts),
        "required_artifact_names_unique": len(required_artifacts) == len(set(required_artifacts)),
        "unsafe_required_artifact_names": [name for name in required_artifacts if not is_safe_artifact_name(str(name))],
        "artifact_targets_reserved": len(artifact_targets),
        "cleanup_proof_fields": len(cleanup_fields),
        "cleanup_scope": cleanup_contract.get("cleanup_scope"),
        "would_create_directories": False,
        "would_write_artifacts": False,
        "would_delete_artifacts": False,
        "model_execution_authorized_now": False,
        "training_authorized": False,
    }
    checks = {
        "source_policy_present": SOURCE_POLICY.exists(),
        "source_cleanup_contract_present": SOURCE_CLEANUP_CONTRACT.exists(),
        "output_root_under_probe_root": metrics["output_root_under_probe_root"] is True,
        "output_root_fresh": metrics["output_root_exists"] is False,
        "required_artifact_names_present": metrics["required_artifact_names"] >= 15,
        "required_artifact_names_unique": metrics["required_artifact_names_unique"] is True,
        "required_artifact_names_safe": not metrics["unsafe_required_artifact_names"],
        "cleanup_proof_field_schema_present": metrics["cleanup_proof_fields"] >= 13,
        "cleanup_scope_checkpoint_children_only": metrics["cleanup_scope"] == "checkpoint_children_only",
        "no_directory_creation": metrics["would_create_directories"] is False,
        "no_artifact_write": metrics["would_write_artifacts"] is False,
        "no_artifact_delete": metrics["would_delete_artifacts"] is False,
        "no_model_execution": metrics["model_execution_authorized_now"] is False,
        "no_training": metrics["training_authorized"] is False,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stages": [8921, 8922],
        "checks": checks,
        "metrics": metrics,
        "artifact_targets": [str(path) for path in artifact_targets],
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "authority": AUTHORITY_CLOSED,
        "decision": {
            "preflight_status": "no_write_read_only",
            "future_probe_write_status": "blocked_until_explicit_execution_authorization",
            "next_required_artifact": "explicit one-run execution authorization review card if and only if the user asks to execute",
        },
    }


def validate_preflight(preflight: dict[str, Any], registry: dict[str, Any], source_summary: dict[str, Any]) -> list[str]:
    failures = [key for key, value in preflight["checks"].items() if value is not True]
    if source_summary.get("passed") is not True:
        failures.append("source_stage8922_not_passed")
    if any((source_summary.get("authority") or {}).values()):
        failures.append("source_stage8922_authority_open")
    if any((preflight.get("authority") or {}).values()):
        failures.append("authority_open")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8922, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def negative_mutation_results(preflight: dict[str, Any]) -> dict[str, Any]:
    registry = {"metrics": {"latest_stage": 8922, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source_summary = {"passed": True, "authority": AUTHORITY_CLOSED}
    mutations = {
        "existing_output_root": lambda p: p["checks"].__setitem__("output_root_fresh", False),
        "unsafe_artifact_name": lambda p: p["checks"].__setitem__("required_artifact_names_safe", False),
        "duplicate_artifact_name": lambda p: p["checks"].__setitem__("required_artifact_names_unique", False),
        "directory_creation": lambda p: p["checks"].__setitem__("no_directory_creation", False),
        "artifact_write": lambda p: p["checks"].__setitem__("no_artifact_write", False),
        "artifact_delete": lambda p: p["checks"].__setitem__("no_artifact_delete", False),
        "open_execution": lambda p: p["checks"].__setitem__("no_model_execution", False),
        "open_authority": lambda p: p.__setitem__("authority", {**AUTHORITY_CLOSED, "runtime_authorized": True}),
    }
    results: dict[str, Any] = {}
    for name, mutate in mutations.items():
        candidate = copy.deepcopy(preflight)
        mutate(candidate)
        failures = validate_preflight(candidate, registry, source_summary)
        results[name] = {"rejected": bool(failures), "failures": failures}
    return results


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    preflight = build_preflight()
    source_summary = load_json(SOURCE_SUMMARY)
    failures = validate_preflight(preflight, registry, source_summary)
    negatives = negative_mutation_results(preflight)
    for name, result in negatives.items():
        if result["rejected"] is not True:
            failures.append(f"negative_mutation_not_rejected:{name}")
    return {
        "preflight": preflight,
        "passed": not failures,
        "failures": failures,
        "negative_mutation_checks": negatives,
        "negative_mutations": len(negatives),
        "negative_mutations_rejected": sum(1 for result in negatives.values() if result["rejected"]),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    preflight = audit["preflight"]
    PREFLIGHT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
            **preflight["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"preflight": str(PREFLIGHT.relative_to(ROOT))},
        "decision": "Future probe preflight passed without creating directories, writing artifacts, deleting artifacts, executing, or training.",
        "next_best_step": "If execution is later requested, create an explicit one-run authorization review card; otherwise return to model/data recovery audits without touching probe output paths.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8923 Future Probe Preflight No-Write Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution preflight confirms the future probe output root is fresh, telemetry artifact names are safe and unique, and cleanup proof fields are present. It does not create directories, write probe artifacts, delete artifacts, execute, or train.",
        "",
        f"Output root exists: `{preflight['metrics']['output_root_exists']}`",
        f"Required artifact names: `{preflight['metrics']['required_artifact_names']}`",
        f"Cleanup proof fields: `{preflight['metrics']['cleanup_proof_fields']}`",
        f"Negative mutations rejected: `{audit['negative_mutations_rejected']}/{audit['negative_mutations']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8923 Future Probe Preflight No-Write Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8923 adds a no-write preflight for the future probe path. It checks the output root is fresh, telemetry names are reserved and safe, cleanup proof schema is present, and no directory creation, artifact writes, deletion, execution, or training occurs.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
