#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9199
NAME = "stage9199_trainer_contract_ready_recovery_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9198 = ROOT / "runs/summaries/stage9198_trainer_setup_no_trainer_emit_execution_authorization_open_review_instance_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_CONTRACT_READY_RECOVERY_AUDIT_STAGE9199.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_contract_ready_recovery_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MATERIALIZER = ROOT / "scripts/materialize_trainer_setup.py"
SAFE_CLEANUP = ROOT / "scripts/safe_cleanup.py"
SAFE_PATHS = ROOT / "scripts/safe_paths.py"

REQUIRED_FLAGS = {
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--output-dir",
    "--contract-only",
    "--execution-authorized-for-recovery-probe",
}

REQUIRED_MODES = {
    "structured_policy_probe",
    "repo_graph_probe",
    "symbol_binding_probe",
    "edit_localization_probe",
    "patch_operator_probe",
    "verifier_repair_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9198) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest}}


def _help_text() -> str:
    return subprocess.run(
        [sys.executable, str(TRAINER), "--help"],
        check=True,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
    ).stdout


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9198)
    help_text = _help_text()
    flags_present = sorted(flag for flag in REQUIRED_FLAGS if flag in help_text)
    modes_present = sorted(mode for mode in REQUIRED_MODES if mode in help_text)
    checks = {
        "source_stage9198_passed": source.get("passed") is True,
        "registry_frontier_stage9198": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9198,
        "trainer_script_present": TRAINER.is_file(),
        "materializer_present": MATERIALIZER.is_file(),
        "safe_cleanup_present": SAFE_CLEANUP.is_file() and SAFE_PATHS.is_file(),
        "required_flags_present": set(flags_present) == REQUIRED_FLAGS,
        "required_modes_present": set(modes_present) == REQUIRED_MODES,
        "bounded_decoder_mode_present": "bounded_decoder_ce_probe" in help_text,
        "contract_only_present": "--contract-only" in help_text,
        "execution_flag_present": "--execution-authorized-for-recovery-probe" in help_text,
        "final_export_block_present": "--no-final-checkpoint-export" in help_text,
        "cleanup_flag_present": "--cleanup-checkpoints-after-probe" in help_text,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "metrics": {
            "required_flags": len(REQUIRED_FLAGS),
            "required_flags_present": len(flags_present),
            "required_modes": len(REQUIRED_MODES),
            "required_modes_present": len(modes_present),
            "trainer_contract_ready": not failures,
            "trainer_runtime_authorized": False,
            "artifact_emission_authorized": False,
            "model_execution_authorized": False,
        },
        "decision": (
            "Recovered trainer is contract-ready: required CLI surface, supported probe modes, "
            "materializer handoff, and safe cleanup modules are present. Remaining blockers are "
            "authorization and audited manifest/loss-mask inputs, not trainer surface recovery."
        ),
        "next_best_step": (
            "Treat trainer surface recovery as complete. Next work should focus on audited manifest/loss-mask "
            "materialization and a deliberate execution authorization, not more trainer-surface gate nesting."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "metrics": {**audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9199 Trainer Contract-Ready Recovery Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage consolidates trainer-surface recovery. The recovered trainer now has the expected contract surface.",
                "",
                "Still closed:",
                "- artifact emission",
                "- trainer/model execution",
                "- runtime",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
