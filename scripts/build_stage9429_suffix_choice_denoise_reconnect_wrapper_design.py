#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9429
NAME = "stage9429_suffix_choice_denoise_reconnect_wrapper_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9428_suffix_choice_denoise_reconnect_design_audit.json"
CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage9427_suffix_choice_denoise_reconnect_design/"
    / "suffix_choice_denoise_reconnect_candidate_manifest.jsonl"
)
QUARANTINE = (
    ROOT
    / "runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/"
    / "suffix_choice_residual_quarantine_manifest.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WRAPPER = OUT_DIR / "suffix_choice_denoise_reconnect_wrapper_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_DENOISE_RECONNECT_WRAPPER_DESIGN_STAGE9429.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
PROBE_OUTPUT_DIR = ROOT / "runs/local/probes/stage9429_suffix_choice_denoise_reconnect_contract_only"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_command() -> list[str]:
    return [
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(CANDIDATES),
        "--mode",
        "denoise_repair_probe",
        "--max-train-rows",
        "9",
        "--max-eval-rows",
        "5",
        "--max-strict-rows",
        "4",
        "--max-steps",
        "0",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "0.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(PROBE_OUTPUT_DIR),
        "--run-id",
        "stage9429_contract_only",
        "--contract-only",
    ]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    source = load_json(SOURCE_SUMMARY)
    candidates = load_jsonl(CANDIDATES)
    quarantined = load_jsonl(QUARANTINE)
    candidate_ids = {str(row.get("source_row_id")) for row in candidates}
    quarantine_ids = {str(row.get("source_row_id")) for row in quarantined}

    command = build_command()
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9428_not_passed")
    if len(candidates) != 9:
        failures.append("bad_candidate_count")
    if len(quarantined) != 7:
        failures.append("bad_quarantine_count")
    if candidate_ids & quarantine_ids:
        failures.append("quarantined_row_in_candidate_manifest")
    if any(any(bool(value) for value in (row.get("loss_mask") or {}).values()) for row in candidates):
        failures.append("candidate_loss_mask_open")
    if any(row.get("generation_reconnect_allowed_now") for row in candidates):
        failures.append("candidate_generation_open")
    if any(any(bool((row.get("authority") or {}).get(key)) for key in AUTHORITY_CLOSED) for row in candidates):
        failures.append("candidate_authority_open")

    design = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "failures": failures,
        "claim_scope": "contract_only_suffix_choice_denoise_reconnect_wrapper_design",
        "repo_root": str(ROOT),
        "trainer": str(TRAINER),
        "manifest": str(CANDIDATES),
        "quarantine_manifest": str(QUARANTINE),
        "output_dir": str(PROBE_OUTPUT_DIR),
        "run_id": "stage9429_contract_only",
        "command": command,
        "constraints": {
            "mode": "denoise_repair_probe",
            "max_train_rows": 9,
            "max_eval_rows": 5,
            "max_strict_rows": 4,
            "max_steps": 0,
            "decoder_ce_weight": 0.0,
            "structured_aux_weight": 0.0,
            "denoise_weight": 0.0,
            "candidate_rows": len(candidates),
            "quarantined_rows": len(quarantined),
            "candidate_quarantine_overlap": len(candidate_ids & quarantine_ids),
            "contract_only": True,
            "no_final_checkpoint_export": True,
            "skip_final_model_save": True,
            "cleanup_checkpoints_after_probe": True,
        },
        "required_runtime_assertions": [
            "manifest_path_equals_stage9427_candidate_manifest",
            "source_row_ids_disjoint_from_stage9425_quarantine_manifest",
            "all_candidate_loss_masks_false",
            "decoder_ce_weight_zero",
            "denoise_weight_zero",
            "structured_aux_weight_zero",
            "max_steps_zero",
            "contract_only_true",
            "no_final_checkpoint_export_true",
        ],
        "required_artifacts_if_later_executed": [
            "contract_validation_card.json",
            "quarantine_overlap_check.json",
            "loss_mask_enforcement_audit.json",
            "cleanup_proof.json",
        ],
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": "Audit the contract-only denoise reconnect wrapper before any execution authorization review.",
    }
    WRAPPER.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "candidate_rows": len(candidates),
            "quarantined_rows": len(quarantined),
            "candidate_quarantine_overlap": len(candidate_ids & quarantine_ids),
            "max_steps": 0,
            "decoder_ce_weight": 0.0,
            "structured_aux_weight": 0.0,
            "denoise_weight": 0.0,
            "contract_only": True,
            "model_execution_authorized_now": False,
        },
        "artifacts": {
            "wrapper_design": str(WRAPPER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": (
            "Designed a contract-only denoise reconnect wrapper for the Stage9427 suffix-choice candidates. "
            "The command validates contract surfaces only: max_steps=0 and all training weights are zero."
        ),
        "next_best_step": design["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9429 Suffix Choice Denoise Reconnect Wrapper Design",
                "",
                f"Passed: `{design['passed']}`",
                "Mode: `denoise_repair_probe`",
                "Contract-only: `true`",
                "Max steps: `0`",
                "Decoder CE weight: `0.0`",
                "Structured aux weight: `0.0`",
                "Denoise weight: `0.0`",
                "",
                "The wrapper is intentionally non-executing. It exists to validate manifest/quarantine/loss-mask wiring before any separate execution authorization review.",
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
                    "candidate_rows": len(candidates),
                    "overlap": len(candidate_ids & quarantine_ids),
                    "max_steps": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
