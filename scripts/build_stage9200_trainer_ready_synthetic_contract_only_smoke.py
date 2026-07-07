#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from materialize_trainer_setup import materialize_training_setup

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9200
NAME = "stage9200_trainer_ready_synthetic_contract_only_smoke"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9199 = ROOT / "runs/summaries/stage9199_trainer_contract_ready_recovery_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_READY_SYNTHETIC_CONTRACT_ONLY_SMOKE_STAGE9200.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def objective_rows() -> list[dict[str, Any]]:
    return [
        {
            "row_id": "decoder_train_1",
            "semantic_key": "sem:decoder:1",
            "source_manifest": "synthetic://stage9200/objective_rows",
            "source_stage": STAGE,
            "objective_family": "bounded_decoder_ce",
            "split": "train",
            "language_family": "python",
            "surface": "PATCH_HUNK_ARGS",
            "task_phase": "repair",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": True,
            "decode_allowed": True,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "apply the one-line patch"},
        },
        {
            "row_id": "structured_eval_1",
            "semantic_key": "sem:structured:1",
            "source_manifest": "synthetic://stage9200/objective_rows",
            "source_stage": STAGE,
            "objective_family": "intent_to_build_strategy",
            "split": "eval",
            "language_family": "python",
            "surface": "MAINTAINER_EXPLANATION_ARGS",
            "task_phase": "analysis",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": False,
            "decode_allowed": False,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "structured label target"},
            "surface_role": "maintainer_explanation",
        },
        {
            "row_id": "denoise_strict_1",
            "semantic_key": "sem:denoise:1",
            "source_manifest": "synthetic://stage9200/objective_rows",
            "source_stage": STAGE,
            "objective_family": "output_repair_denoise",
            "split": "strict_eval",
            "language_family": "python",
            "surface": "REPAIR_PLAN_ARGS",
            "task_phase": "repair",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": True,
            "decode_allowed": False,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "denoise target"},
        },
    ]


def judge_rows() -> list[dict[str, Any]]:
    rows = []
    for row in objective_rows():
        rows.append(
            {
                "row_id": row["row_id"],
                "semantic_key": row["semantic_key"],
                "judge_reasons": [],
                "anti_cheat": {
                    "label_leak_checked": True,
                    "shortcut_baseline_max": 0.21,
                    "split_overlap_checked": True,
                    "raw_text_forbidden_checked": True,
                    "authority_closed_checked": True,
                    "target_not_in_input_checked": True,
                },
                "authority": {},
            }
        )
    return rows


def ranker_rows() -> list[dict[str, Any]]:
    return [
        {
            "row_id": "decoder_train_1",
            "semantic_key": "sem:decoder:1",
            "risk_bucket": "KEEP_BOUNDED_DECODER",
            "recommended_action": "KEEP_BOUNDED_DECODER",
            "reasons": [],
        },
        {
            "row_id": "structured_eval_1",
            "semantic_key": "sem:structured:1",
            "risk_bucket": "KEEP_STRUCTURED",
            "recommended_action": "KEEP_STRUCTURED",
            "reasons": [],
        },
        {
            "row_id": "denoise_strict_1",
            "semantic_key": "sem:denoise:1",
            "risk_bucket": "USE_FOR_DENOISE_REPAIR",
            "recommended_action": "USE_FOR_DENOISE_REPAIR",
            "reasons": [],
        },
    ]


def run_contract_only(command: list[str], output_dir: Path) -> dict[str, Any]:
    argv = [arg for arg in command if arg != "--execution-authorized-for-recovery-probe"]
    argv.append("--contract-only")
    completed = subprocess.run(
        [sys.executable, *argv[1:]],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    contract_audit = output_dir / "probe_contract_audit.json"
    return {
        "command": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "contract_audit_exists": contract_audit.is_file(),
        "cleanup_proof_exists": (output_dir / "cleanup_proof.json").is_file(),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def select_rows_for_mode(trainer_rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    structured_allowed = {
        "surface_role_ce",
        "repair_surface_ce",
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
    }
    for row in trainer_rows:
        mask = dict(row.get("loss_mask", {}))
        if mode == "bounded_decoder_ce_probe" and bool(mask.get("decoder_ce")):
            cloned = dict(row)
            cloned["loss_mask"] = {key: (key == "decoder_ce") for key in mask}
            selected.append(cloned)
        elif mode == "structured_policy_probe" and any(bool(mask.get(key)) for key in structured_allowed):
            cloned = dict(row)
            cloned["loss_mask"] = {key: (key in structured_allowed and bool(mask.get(key))) for key in mask}
            selected.append(cloned)
        elif mode == "denoise_repair_probe" and bool(mask.get("denoise_ce")):
            cloned = dict(row)
            cloned["loss_mask"] = {key: (key == "denoise_ce") for key in mask}
            selected.append(cloned)
    return selected


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_9199)
    setup_dir = OUT_DIR / "materialized_setup"
    result = materialize_training_setup(
        objective_rows(),
        judge_rows(),
        ranker_rows(),
        output_dir=setup_dir,
    )
    trainer_input = result["trainer_input"]
    trainer_rows = [
        json.loads(line)
        for line in (setup_dir / "trainer_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    smoke_results: list[dict[str, Any]] = []
    for command_spec in trainer_input["recommended_commands"]:
        mode = str(command_spec["mode"])
        mode_manifest = setup_dir / f"{mode}_manifest.jsonl"
        mode_rows = select_rows_for_mode(trainer_rows, mode)
        write_jsonl(mode_manifest, mode_rows)
        rewritten_command: list[str] = []
        idx = 0
        command = list(command_spec["command"])
        expected_output_dir = None
        while idx < len(command):
            token = command[idx]
            rewritten_command.append(token)
            if token == "--manifest":
                rewritten_command.append(str(mode_manifest))
                idx += 2
                continue
            if token == "--output-dir":
                expected_output_dir = Path(command[idx + 1])
                rewritten_command.append(command[idx + 1])
                idx += 2
                continue
            idx += 1
        smoke = run_contract_only(rewritten_command, expected_output_dir or (setup_dir / mode))
        smoke["mode"] = mode
        smoke["manifest"] = str(mode_manifest)
        smoke["manifest_rows"] = len(mode_rows)
        smoke_results.append(smoke)

    checks = {
        "source_stage9199_passed": source.get("passed") is True,
        "materialization_passed": result["passed"] is True,
        "route_cards_written": (setup_dir / "route_cards.jsonl").is_file(),
        "loss_mask_cards_written": (setup_dir / "loss_mask_cards.jsonl").is_file(),
        "trainer_rows_written": (setup_dir / "trainer_rows.jsonl").is_file(),
        "trainer_dry_run_input_written": (setup_dir / "trainer_dry_run_input.json").is_file(),
        "bounded_decoder_contract_only_passed": any(item["mode"] == "bounded_decoder_ce_probe" and item["returncode"] == 0 for item in smoke_results),
        "structured_contract_only_passed": any(item["mode"] == "structured_policy_probe" and item["returncode"] == 0 for item in smoke_results),
        "denoise_contract_only_passed": any(item["mode"] == "denoise_repair_probe" and item["returncode"] == 0 for item in smoke_results),
        "all_contract_audits_written": all(item["contract_audit_exists"] for item in smoke_results),
        "all_cleanup_proofs_written": all(item["cleanup_proof_exists"] for item in smoke_results),
    }
    failures = [key for key, value in checks.items() if value is not True]
    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "materialization_result": result,
        "contract_only_smokes": smoke_results,
        "decision": (
            "Materialized a synthetic trainer-ready package and proved the recovered trainer can consume it in "
            "contract-only mode across bounded decoder, structured, and denoise probe families. Trainer surface "
            "and package handoff are ready; remaining blockers are real-data package authorization and explicit execution."
        ),
        "next_best_step": (
            "Use an audited real manifest/loss-mask package and run one bounded contract-only trainer invocation "
            "against it before considering any explicit execution authorization."
        ),
    }
    audit_path = OUT_DIR / "trainer_ready_synthetic_contract_only_smoke.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "metrics": {
            "materialization_passed": result["passed"],
            "recommended_commands": len(trainer_input["recommended_commands"]),
            "contract_only_smokes": len(smoke_results),
            "contract_only_smokes_passed": sum(1 for item in smoke_results if item["returncode"] == 0),
            "failures": failures,
            "artifact_emission_authorized": False,
            "model_execution_authorized": False,
            "runtime_authorized": False,
        },
        "artifacts": {
            "audit": str(audit_path.relative_to(ROOT)) if audit_path.is_relative_to(ROOT) else str(audit_path),
            "doc": str(DOC.relative_to(ROOT)) if DOC.is_relative_to(ROOT) else str(DOC),
        },
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9200 Trainer-Ready Synthetic Contract-Only Smoke",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage materializes a synthetic trainer package and proves the recovered trainer consumes it in contract-only mode.",
                "",
                "Still closed:",
                "- artifact emission authorization for real packages",
                "- trainer/model execution",
                "- runtime",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
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
