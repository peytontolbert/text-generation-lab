#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from materialize_trainer_setup import materialize_training_setup, read_jsonl
from build_stage9201_repo_local_real_package_contract_only_smoke import (
    normalize_judge_rows,
    normalize_objective_rows,
    normalize_ranker_rows,
)

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9203
NAME = "stage9203_selected_bundle_contract_only_handoff"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9202 = ROOT / "runs/summaries/stage9202_repo_local_real_input_selector.json"
SELECTED_BUNDLE = ROOT / "runs/local/artifacts/stage9202_repo_local_real_input_selector/selected_repo_local_real_input_bundle.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SELECTED_BUNDLE_CONTRACT_ONLY_HANDOFF_STAGE9203.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

MODE_ALLOWED_LOSSES = {
    "structured_policy_probe": {
        "surface_role_ce",
        "repair_surface_ce",
        "build_mode_ce",
        "allowed_import_policy_ce",
        "blocked_import_policy_ce",
        "repo_dependency_policy_ce",
        "action_sequence_ce",
        "file_plan_ce",
    },
    "bounded_decoder_ce_probe": {"decoder_ce"},
    "denoise_repair_probe": {"denoise_ce"},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def bundle_paths(bundle: dict[str, Any]) -> tuple[Path, Path, Path]:
    return (
        ROOT / str(bundle["objective_rows_path"]),
        ROOT / str(bundle["judge_rows_path"]),
        ROOT / str(bundle["junk_ranker_rows_path"]),
    )


def select_rows_for_mode(trainer_rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    allowed = MODE_ALLOWED_LOSSES[mode]
    selected: list[dict[str, Any]] = []
    for row in trainer_rows:
        mask = dict(row.get("loss_mask", {}))
        if not any(bool(mask.get(key)) for key in allowed):
            continue
        cloned = dict(row)
        cloned["loss_mask"] = {key: (key in allowed and bool(mask.get(key))) for key in mask}
        selected.append(cloned)
    return selected


def output_dir_from_command(command: list[str]) -> Path:
    for idx, token in enumerate(command):
        if token == "--output-dir" and idx + 1 < len(command):
            return Path(command[idx + 1])
    raise ValueError("missing --output-dir in recommended command")


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
    return {
        "command": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "contract_audit_exists": (output_dir / "probe_contract_audit.json").is_file(),
        "cleanup_proof_exists": (output_dir / "cleanup_proof.json").is_file(),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_9202)
    bundle = load_json(SELECTED_BUNDLE)
    objective_path, judge_path, ranker_path = bundle_paths(bundle)

    raw_objective_rows = read_jsonl(objective_path)
    raw_judge_rows = read_jsonl(judge_path)
    raw_ranker_rows = read_jsonl(ranker_path)
    objective_rows = normalize_objective_rows(raw_objective_rows, raw_ranker_rows)
    judge_rows = normalize_judge_rows(raw_judge_rows)
    ranker_rows = normalize_ranker_rows(raw_ranker_rows)
    result = materialize_training_setup(
        objective_rows,
        judge_rows,
        ranker_rows,
        output_dir=OUT_DIR / "materialized_setup",
    )

    trainer_rows = read_jsonl(OUT_DIR / "materialized_setup/trainer_rows.jsonl")
    commands = list(result["trainer_input"]["recommended_commands"])
    smokes: list[dict[str, Any]] = []
    emitted_manifests: list[str] = []
    for command_spec in commands:
        mode = str(command_spec["mode"])
        manifest_path = OUT_DIR / "materialized_setup" / f"{mode}_manifest.jsonl"
        mode_rows = select_rows_for_mode(trainer_rows, mode)
        write_jsonl(manifest_path, mode_rows)
        emitted_manifests.append(str(manifest_path.relative_to(ROOT)))
        command = list(command_spec["command"])
        rewritten: list[str] = []
        idx = 0
        while idx < len(command):
            token = command[idx]
            rewritten.append(token)
            if token == "--manifest":
                rewritten.append(str(manifest_path))
                idx += 2
                continue
            idx += 1
        smoke = run_contract_only(rewritten, output_dir_from_command(rewritten))
        smoke["mode"] = mode
        smoke["manifest_rows"] = len(mode_rows)
        smokes.append(smoke)

    checks = {
        "source_stage9202_passed": source.get("passed") is True,
        "selected_bundle_present": bool(bundle),
        "objective_rows_exist": objective_path.is_file(),
        "judge_rows_exist": judge_path.is_file(),
        "ranker_rows_exist": ranker_path.is_file(),
        "materialization_passed": result["passed"] is True,
        "recommended_commands_present": len(commands) > 0,
        "all_emitted_manifests_written": all((ROOT / rel).is_file() for rel in emitted_manifests),
        "all_contract_only_smokes_passed": all(item["returncode"] == 0 for item in smokes),
        "all_contract_audits_written": all(item["contract_audit_exists"] for item in smokes),
        "all_cleanup_proofs_written": all(item["cleanup_proof_exists"] for item in smokes),
    }
    failures = [key for key, value in checks.items() if value is not True]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "selected_bundle_id": bundle.get("bundle_id"),
        "selected_bundle_normalization_profile": bundle.get("normalization_profile"),
        "real_inputs": {
            "objective_rows": str(objective_path.relative_to(ROOT)),
            "judge_rows": str(judge_path.relative_to(ROOT)),
            "ranker_rows": str(ranker_path.relative_to(ROOT)),
        },
        "materialization_result": result,
        "emitted_manifests": emitted_manifests,
        "contract_only_smokes": smokes,
        "decision": (
            "Consumed the Stage9202 selected bundle directly, materialized the trainer package under the recovered "
            "contract, and executed contract-only handoff smokes for every eligible mode without reopening model execution or runtime."
        ),
        "next_best_step": (
            "Add another repo-local candidate bundle with a different eligible mode, then let Stage9202/9203 repeat "
            "the same selected-bundle handoff path across multiple real probe families."
        ),
    }
    audit_path = OUT_DIR / "selected_bundle_contract_only_handoff.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "metrics": {
            "materialization_passed": result["passed"],
            "recommended_commands": len(commands),
            "contract_only_smokes": len(smokes),
            "contract_only_smokes_passed": sum(1 for item in smokes if item["returncode"] == 0),
            "failures": failures,
            "model_execution_authorized": False,
            "runtime_authorized": False,
        },
        "artifacts": {
            "audit": str(audit_path.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9203 Selected Bundle Contract-Only Handoff",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage consumes the Stage9202 selected bundle directly and runs the recovered contract-only handoff",
                "for every eligible probe mode without reopening model execution or runtime.",
                "",
                "Still closed:",
                "- model execution",
                "- runtime",
                "- explicit execution authorization",
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
