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
STAGE = 9258
NAME = "stage9258_repo_state_metadata_inventory_preflight_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9257_repo_state_compiler_cache_metadata_fixture_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "repo_state_metadata_inventory_preflight_design.json"
AUDIT = OUT_DIR / "repo_state_metadata_inventory_preflight_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_STATE_METADATA_INVENTORY_PREFLIGHT_DESIGN_STAGE9258.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

INVENTORY_FIELDS = [
    "repo_id",
    "commit_hash",
    "path_id",
    "relative_path_hash",
    "file_extension",
    "language_hint",
    "size_bytes",
    "mtime_bucket",
    "content_sha256",
    "candidate_extractors",
    "cache_layers_requested",
    "body_read_authorized",
    "runtime_authorized",
    "arxiv_root_access_authorized",
]

DENIED_OPERATIONS = [
    "read_source_body",
    "read_arxiv_repository_body",
    "write_arxiv",
    "execute_runtime",
    "run_tests",
    "emit_decoder_text",
    "train_model",
    "export_checkpoint",
    "follow_symlink_outside_repo_root",
    "delete_any_path",
]

NEGATIVE_CASES = [
    {"case_id": "body_read_true", "patch": {"read_source_bodies_now": True}, "expected_rejection": "read_source_bodies_now"},
    {"case_id": "arxiv_root_true", "patch": {"read_arxiv_now": True}, "expected_rejection": "read_arxiv_now"},
    {"case_id": "runtime_true", "patch": {"runtime_authorized_now": True}, "expected_rejection": "runtime_authorized_now"},
    {"case_id": "absolute_arxiv_path", "patch": {"input_root": "/arxiv/repositories"}, "expected_rejection": "input_root_forbidden"},
    {"case_id": "missing_hash", "patch": {"require_content_hash_without_reading_body": False}, "expected_rejection": "require_content_hash_without_reading_body"},
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "design_status": "NO_EXECUTION_METADATA_ONLY_PREFLIGHT",
        "source_stage": 9257,
        "purpose": "Design the first real repo-state compiler inventory preflight while keeping source-body reads and /arxiv access closed.",
        "input_root": "future:explicit_repo_root_not_arxiv",
        "output_root": "runs/local/artifacts/repo_state_metadata_inventory/<run_id>/",
        "inventory_fields": INVENTORY_FIELDS,
        "denied_operations": DENIED_OPERATIONS,
        "controls": {
            "metadata_only": True,
            "read_source_bodies_now": False,
            "read_arxiv_now": False,
            "write_arxiv_now": False,
            "runtime_authorized_now": False,
            "training_authorized_now": False,
            "model_execution_authorized_now": False,
            "body_emission_authorized_now": False,
            "decoder_ce_authorized_now": False,
            "require_opaque_ids": True,
            "require_content_hash_without_reading_body": True,
            "require_symlink_boundary_check": True,
            "require_safe_cleanup_single_entrypoint": True,
        },
        "preflight_outputs": [
            "metadata_inventory_rows.jsonl",
            "inventory_cell_card.json",
            "extractor_plan_without_body_reads.json",
            "cache_key_preview.jsonl",
            "blocked_operations_card.json",
        ],
        "negative_cases": NEGATIVE_CASES,
        "authority": dict(AUTHORITY_CLOSED),
    }


def apply_patch_case(design: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    candidate = json.loads(json.dumps(design))
    for key, value in patch.items():
        if key in candidate.get("controls", {}):
            candidate["controls"][key] = value
        else:
            candidate[key] = value
    return candidate


def audit_design(design: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    controls = design.get("controls") or {}
    if source.get("passed") is not True:
        failures.append("source_stage9257_not_passed")
    if design.get("design_status") != "NO_EXECUTION_METADATA_ONLY_PREFLIGHT":
        failures.append("wrong_design_status")
    expected_false = [
        "read_source_bodies_now",
        "read_arxiv_now",
        "write_arxiv_now",
        "runtime_authorized_now",
        "training_authorized_now",
        "model_execution_authorized_now",
        "body_emission_authorized_now",
        "decoder_ce_authorized_now",
    ]
    for key in expected_false:
        if controls.get(key) is not False:
            failures.append(f"control_not_false:{key}")
    expected_true = [
        "metadata_only",
        "require_opaque_ids",
        "require_content_hash_without_reading_body",
        "require_symlink_boundary_check",
        "require_safe_cleanup_single_entrypoint",
    ]
    for key in expected_true:
        if controls.get(key) is not True:
            failures.append(f"control_not_true:{key}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    fields = set(design.get("inventory_fields") or [])
    for required in ["repo_id", "commit_hash", "path_id", "content_sha256", "body_read_authorized", "arxiv_root_access_authorized"]:
        if required not in fields:
            failures.append(f"missing_inventory_field:{required}")
    scan_payload = {key: value for key, value in design.items() if key not in {"denied_operations"}}
    serialized = json.dumps(scan_payload, sort_keys=True).lower()
    for token in ["source_text", "decoder_text", "target_text", "expected_answer", "hidden_eval", "locked_eval"]:
        if token in serialized:
            failures.append(f"forbidden_token:{token}")
    if "/arxiv" in str(design.get("input_root", "")).lower():
        failures.append("input_root_forbidden")
    for denied in DENIED_OPERATIONS:
        if denied not in design.get("denied_operations", []):
            failures.append(f"missing_denied_operation:{denied}")
    return {"passed": not failures, "failures": failures, "authority": dict(AUTHORITY_CLOSED)}


def audit_negative_cases(design: dict[str, Any]) -> dict[str, Any]:
    rejected = 0
    results: list[dict[str, Any]] = []
    for case in design.get("negative_cases") or []:
        candidate = apply_patch_case(design, case["patch"])
        audit = audit_design(candidate, {"passed": True})
        ok = audit["passed"] is False and case["expected_rejection"] in " ".join(audit["failures"])
        rejected += int(ok)
        results.append({"case_id": case["case_id"], "rejected": ok, "failures": audit["failures"]})
    return {"negative_cases": len(results), "negative_cases_rejected": rejected, "results": results}


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
    source = load_json(SOURCE_SUMMARY)
    design = build_design()
    audit = audit_design(design, source)
    negative = audit_negative_cases(design)
    passed = audit["passed"] and negative["negative_cases_rejected"] == negative["negative_cases"]
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps({"passed": passed, "audit": audit, "negative": negative}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "inventory_fields": len(INVENTORY_FIELDS),
            "denied_operations": len(DENIED_OPERATIONS),
            "negative_cases": negative["negative_cases"],
            "negative_cases_rejected": negative["negative_cases_rejected"],
            "read_source_bodies_now": False,
            "read_arxiv_now": False,
            "runtime_authorized_now": False,
            "training_authorized_now": False,
        },
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed metadata-only repo-state inventory preflight; source bodies, /arxiv, runtime, training, and model execution remain closed." if passed else "Metadata-only repo-state inventory preflight design failed.",
        "next_best_step": "Build the metadata-only repo inventory runner against a synthetic tmp repo fixture; still forbid source-body capture, /arxiv access, runtime, training, and model execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9258 Repo-State Metadata Inventory Preflight Design",
                "",
                "Stage9258 designs the first real preflight surface for the repo-state compiler.",
                "",
                "It remains metadata-only: no source bodies, no `/arxiv`, no runtime, no training, no decoder CE, and no model execution.",
                "",
                "The intended runner may list metadata, hashes, language hints, and extractor plans, but it must not materialize raw code text or training targets.",
                "",
                f"Inventory fields: {len(INVENTORY_FIELDS)}",
                f"Denied operations: {len(DENIED_OPERATIONS)}",
                f"Negative cases rejected: {negative['negative_cases_rejected']}/{negative['negative_cases']}",
                f"Passed: {passed}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": passed, "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
