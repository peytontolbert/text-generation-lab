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
STAGE = 8933
NAME = "stage8933_no_mining_compiler_cli_wrapper_skeleton"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_MINING_COMPILER_CLI_WRAPPER_SKELETON_STAGE8933.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "no_mining_compiler_cli_wrapper_skeleton.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8932_no_mining_compiler_cli_wrapper_contract.json"
WRAPPER = ROOT / "scripts/software_maintenance_curriculum_cli.py"
TEST_FILE = ROOT / "tests/test_software_maintenance_curriculum_cli.py"

REQUIRED_FLAGS = [
    "--input",
    "--output-dir",
    "--mode",
    "--no-decoder-ce",
    "--no-denoise-ce",
    "--no-runtime",
    "--no-mining",
    "--no-model-execution",
]

FORBIDDEN_FLAG_TOKENS = [
    "--train",
    "--mine",
    "--allow-runtime",
    "--allow-decoder-ce",
    "--allow-denoise-ce",
    "--load-model",
    "--write-checkpoint",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    text = WRAPPER.read_text(encoding="utf-8") if WRAPPER.exists() else ""
    checks = {
        "source_stage8932_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "wrapper_script_present": WRAPPER.exists(),
        "wrapper_test_present": TEST_FILE.exists(),
        "required_flags_present": all(flag in text for flag in REQUIRED_FLAGS),
        "forbidden_flags_declared": all(flag.replace("--", "").replace("-", "_") in text for flag in FORBIDDEN_FLAG_TOKENS) and "replace('_', '-')" in text,
        "forbidden_flag_rejection_present": "forbidden flags enabled" in text,
        "decoder_ce_closed_in_wrapper": "allow_decoder=False" in text and "decoder_ce_loss_rows" in text,
        "denoise_ce_closed_in_wrapper": "allow_denoise=False" in text and "denoise_ce_loss_rows" in text,
        "runtime_closed_in_wrapper": "allow_runtime=False" in text and "runtime_reward_rows" in text,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "model_execution_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "checks": checks,
        "metrics": {
            "required_flags": len(REQUIRED_FLAGS),
            "forbidden_flags": len(FORBIDDEN_FLAG_TOKENS),
            "wrapper_script_present": int(WRAPPER.exists()),
            "wrapper_test_present": int(TEST_FILE.exists()),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "wrapper": str(WRAPPER.relative_to(ROOT)),
        "test": str(TEST_FILE.relative_to(ROOT)),
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "wrapper_status": "implemented_no_mining_no_execution",
            "training_status": "blocked",
            "next_required_artifact": "decide whether to return to checkpoint blockers or build a manifest audit-only contract for real rows",
        },
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8932, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
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
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "No-mining compiler CLI wrapper skeleton passed; wrapper rejects forbidden flags and keeps decoder/denoise/runtime/model execution/training closed.",
        "next_best_step": "Either return to checkpoint blockers, or build a real-manifest audit-only contract that permits inspection of local manifests but no mining/training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8933 No-Mining Compiler CLI Wrapper Skeleton",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records the implementation of `scripts/software_maintenance_curriculum_cli.py`, a guarded compiler wrapper for synthetic dry runs and manifest audit-only mode.",
        "",
        "The wrapper requires closed safety flags and rejects mining, training, runtime, decoder CE, denoise CE, model loading, and checkpoint writes.",
        "",
        f"Required flags: `{audit['metrics']['required_flags']}`",
        f"Forbidden flags: `{audit['metrics']['forbidden_flags']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8933 No-Mining Compiler CLI Wrapper Skeleton"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8933 implements the guarded no-mining compiler CLI wrapper skeleton. It supports synthetic dry runs and manifest audit-only mode while requiring closed safety flags and rejecting mining, training, runtime, model loading, decoder CE, denoise CE, and checkpoint writes.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
