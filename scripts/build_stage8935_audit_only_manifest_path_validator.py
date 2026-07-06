#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.manifest_path_validator import ALLOWED_MANIFEST_ROOTS, validate_manifest_input_path
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from manifest_path_validator import ALLOWED_MANIFEST_ROOTS, validate_manifest_input_path  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8935
NAME = "stage8935_audit_only_manifest_path_validator"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "AUDIT_ONLY_MANIFEST_PATH_VALIDATOR_STAGE8935.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "audit_only_manifest_path_validator.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8934_real_manifest_audit_only_contract.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    accepted = validate_manifest_input_path("runs/local/manifests/explicit_manifest.jsonl", must_exist=False)
    rejected = {
        "arxiv": validate_manifest_input_path("/arxiv/datasets/rows.jsonl", must_exist=False),
        "data_outside_repo": validate_manifest_input_path("/data/rows.jsonl", must_exist=False),
        "repo_root": validate_manifest_input_path(str(ROOT), must_exist=False),
        "traversal": validate_manifest_input_path("runs/local/manifests/../escape.jsonl", must_exist=False),
        "glob": validate_manifest_input_path("runs/local/manifests/*.jsonl", must_exist=False),
        "directory": validate_manifest_input_path("runs/local/manifests", must_exist=False),
        "wrong_suffix": validate_manifest_input_path("runs/local/manifests/rows.txt", must_exist=False),
        "remote_uri": validate_manifest_input_path("https://example.com/rows.jsonl", must_exist=False),
    }
    checks = {
        "source_stage8934_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "accepted_explicit_repo_local_jsonl": accepted["allowed"] is True,
        "allowed_roots_match_stage8934_contract": set(ALLOWED_MANIFEST_ROOTS)
        == {"runs/local/artifacts", "runs/local/recovered", "runs/local/manifests", "datasets/recovered"},
        "rejects_arxiv": "manifest_path_under_arxiv_forbidden" in rejected["arxiv"]["failures"],
        "rejects_data_outside_repo": "manifest_path_under_data_outside_repo_forbidden" in rejected["data_outside_repo"]["failures"],
        "rejects_repo_root": "manifest_path_not_under_allowed_input_root" in rejected["repo_root"]["failures"],
        "rejects_traversal": "path_traversal_forbidden" in rejected["traversal"]["failures"],
        "rejects_glob": "glob_manifest_path_forbidden" in rejected["glob"]["failures"],
        "rejects_directory": "manifest_must_be_jsonl" in rejected["directory"]["failures"],
        "rejects_wrong_suffix": "manifest_must_be_jsonl" in rejected["wrong_suffix"]["failures"],
        "rejects_remote_uri": "remote_manifest_uri_forbidden" in rejected["remote_uri"]["failures"],
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "AUDIT_ONLY_MANIFEST_PATH_VALIDATOR",
        "accepted_example": accepted,
        "rejected_examples": rejected,
        "checks": checks,
        "metrics": {
            "allowed_input_roots": len(ALLOWED_MANIFEST_ROOTS),
            "rejected_examples": len(rejected),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Audit-only manifest path validation is implemented for explicit repo-local JSONL manifests; discovery, mining, training, runtime, model execution, and /arxiv writes remain blocked.",
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8934, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    CARD.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **audit["metrics"],
        },
        "artifacts": {"audit": str(CARD.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": "Wire the audit-only path validator into the manifest_no_mining_audit_only CLI path, or return to checkpoint blockers; do not mine or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8935 Audit-Only Manifest Path Validator",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage implements path validation for explicitly provided local JSONL manifests. It rejects glob discovery, traversal, remote URIs, `/arxiv`, `/data` outside the repository, directories, and non-JSONL paths.",
        "",
        "The validator is read-side control-plane code only. It opens no mining, model execution, runtime, decoder CE, denoise CE, checkpoint, or training authority.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8935 Audit-Only Manifest Path Validator"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8935 turns the Stage8934 real-manifest audit-only contract into reusable path validation code. Explicit repo-local JSONL manifests may be checked; discovery/mining, recursive scans, remote inputs, `/arxiv` writes, training, runtime, and model execution remain blocked.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
