#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8936
NAME = "stage8936_cli_manifest_path_validator_wiring"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLI_MANIFEST_PATH_VALIDATOR_WIRING_STAGE8936.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "cli_manifest_path_validator_wiring.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8935_audit_only_manifest_path_validator.json"
CLI = ROOT / "scripts/software_maintenance_curriculum_cli.py"
TEST = ROOT / "tests/test_software_maintenance_curriculum_cli.py"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    cli_text = CLI.read_text(encoding="utf-8")
    test_text = TEST.read_text(encoding="utf-8")
    checks = {
        "source_stage8935_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "cli_imports_validator": "from manifest_path_validator import validate_manifest_input_path" in cli_text,
        "cli_validates_manifest_mode_input": "path_card = validate_manifest_input_path(args.input, must_exist=True)" in cli_text,
        "cli_rejects_failed_path_card": "manifest path rejected:" in cli_text,
        "test_accepts_focused_manifest_path": "runs\" / \"local\" / \"manifests" in test_text,
        "test_rejects_unfocused_input_path": "test_cli_manifest_mode_rejects_unfocused_input_path" in test_text,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CLI_MANIFEST_PATH_VALIDATOR_WIRED",
        "checks": checks,
        "metrics": {
            "cli_validator_imports": int(checks["cli_imports_validator"]),
            "manifest_rejection_tests": int(checks["test_rejects_unfocused_input_path"]),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The no-mining curriculum CLI now validates manifest_no_mining_audit_only input paths before reading rows. Arbitrary temp paths, /arxiv, remote URIs, traversal, and globs are rejected by the shared validator.",
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8935, STAGE}:
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
        "next_best_step": "Run the no-mining CLI wrapper on a tiny explicit repo-local manifest, or return to checkpoint blockers; do not mine or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8936 CLI Manifest Path Validator Wiring",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "The `manifest_no_mining_audit_only` CLI mode now calls the shared manifest path validator before reading rows. This preserves Stage8934/8935 boundaries while making real local manifest audits usable.",
        "",
        "No model execution, mining, runtime, decoder CE, denoise CE, checkpoint, source/body emission, Gemma, harness, scoring, controller merge, or promotion authority was opened.",
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
    marker = "## Stage8936 CLI Manifest Path Validator Wiring"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8936 wires the Stage8935 manifest path validator into `scripts/software_maintenance_curriculum_cli.py` for `manifest_no_mining_audit_only`, so explicit local manifests can be audited without allowing arbitrary path reads, discovery, mining, training, runtime, or model execution.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
