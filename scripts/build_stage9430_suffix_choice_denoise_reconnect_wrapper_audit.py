#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9430
NAME = "stage9430_suffix_choice_denoise_reconnect_wrapper_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9429_suffix_choice_denoise_reconnect_wrapper_design.json"
WRAPPER = (
    ROOT
    / "runs/local/artifacts/stage9429_suffix_choice_denoise_reconnect_wrapper_design/"
    / "suffix_choice_denoise_reconnect_wrapper_design.json"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_choice_denoise_reconnect_wrapper_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_DENOISE_RECONNECT_WRAPPER_AUDIT_STAGE9430.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_FLAGS = (
    "--repo-root",
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
    "--skip-final-model-save",
    "--output-dir",
    "--run-id",
    "--contract-only",
)
FORBIDDEN_TOKENS = ("rm", "rmdir", "unlink", "shred", "git", "reset")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    wrapper = load_json(WRAPPER)
    command = [str(part) for part in wrapper.get("command", [])]
    constraints = wrapper.get("constraints") if isinstance(wrapper.get("constraints"), dict) else {}

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9429_not_passed")
    missing_flags = [flag for flag in REQUIRED_FLAGS if flag not in command]
    if missing_flags:
        failures.append("missing_required_command_flags")
    forbidden_present = [token for token in FORBIDDEN_TOKENS if token in command]
    if forbidden_present:
        failures.append("forbidden_command_tokens_present")
    if constraints.get("mode") != "denoise_repair_probe":
        failures.append("bad_mode")
    for key, expected in {
        "max_train_rows": 9,
        "max_eval_rows": 5,
        "max_strict_rows": 4,
        "max_steps": 0,
        "decoder_ce_weight": 0.0,
        "structured_aux_weight": 0.0,
        "denoise_weight": 0.0,
        "candidate_rows": 9,
        "quarantined_rows": 7,
        "candidate_quarantine_overlap": 0,
        "contract_only": True,
        "no_final_checkpoint_export": True,
        "skip_final_model_save": True,
        "cleanup_checkpoints_after_probe": True,
    }.items():
        if constraints.get(key) != expected:
            failures.append(f"constraint_{key}_mismatch")
    if any(bool((wrapper.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED):
        failures.append("authority_flags_open")

    trainer = Path(wrapper.get("trainer", ""))
    help_missing: list[str] = []
    help_ok = False
    if trainer.is_file():
        result = subprocess.run([sys.executable, str(trainer), "--help"], text=True, capture_output=True, check=False)
        help_text = result.stdout + result.stderr
        help_missing = [flag for flag in REQUIRED_FLAGS if flag not in help_text]
        help_ok = result.returncode == 0 and not help_missing
        if not help_ok:
            failures.append("trainer_help_missing_required_flags")
    else:
        failures.append("trainer_missing")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_stage": "stage9429_suffix_choice_denoise_reconnect_wrapper_design",
        "missing_required_flags": missing_flags,
        "forbidden_command_tokens_present": forbidden_present,
        "trainer_help_exposes_required_flags": help_ok,
        "trainer_help_missing_flags": help_missing,
        "candidate_rows": constraints.get("candidate_rows"),
        "quarantined_rows": constraints.get("quarantined_rows"),
        "candidate_quarantine_overlap": constraints.get("candidate_quarantine_overlap"),
        "max_steps": constraints.get("max_steps"),
        "decoder_ce_weight": constraints.get("decoder_ce_weight"),
        "structured_aux_weight": constraints.get("structured_aux_weight"),
        "denoise_weight": constraints.get("denoise_weight"),
        "contract_only": constraints.get("contract_only"),
        "future_execution_authorization_required": True,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "contract-only wrapper is safe if passed; no model execution or loss is authorized",
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Audited the Stage9429 contract-only denoise reconnect wrapper. The command surface is present, "
            "candidate/quarantine overlap is zero, max_steps is zero, and all loss weights are zero."
        ),
        "next_best_step": (
            "Run the contract-only wrapper preflight and capture its validation card; do not authorize denoise "
            "execution until that preflight passes and a separate execution review is written."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9430 Suffix Choice Denoise Reconnect Wrapper Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Candidate rows: `{audit['candidate_rows']}`",
                f"Candidate/quarantine overlap: `{audit['candidate_quarantine_overlap']}`",
                f"Max steps: `{audit['max_steps']}`",
                f"Denoise weight: `{audit['denoise_weight']}`",
                "",
                "This audit does not execute training or generation. The next step is contract-only preflight only.",
                "",
            ]
        )
    )

    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row
        for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": summary["passed"],
                "metrics": {
                    "candidate_rows": audit["candidate_rows"],
                    "overlap": audit["candidate_quarantine_overlap"],
                    "max_steps": audit["max_steps"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
