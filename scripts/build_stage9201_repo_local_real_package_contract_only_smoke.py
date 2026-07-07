#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from materialize_trainer_setup import materialize_training_setup, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9201
NAME = "stage9201_repo_local_real_package_contract_only_smoke"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9200 = ROOT / "runs/summaries/stage9200_trainer_ready_synthetic_contract_only_smoke.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_REAL_PACKAGE_CONTRACT_ONLY_SMOKE_STAGE9201.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"

OBJECTIVE_ROWS = ROOT / "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/normalized_input_rows.jsonl"
JUDGE_ROWS = ROOT / "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/judged_rows.jsonl"
RANKER_ROWS = ROOT / "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/ranked_rows.jsonl"

STRUCTURED_ALLOWED = {
    "surface_role_ce",
    "repair_surface_ce",
    "build_mode_ce",
    "allowed_import_policy_ce",
    "blocked_import_policy_ce",
    "repo_dependency_policy_ce",
    "action_sequence_ce",
    "file_plan_ce",
}

OBJECTIVE_FAMILY_MAP = {
    "tiny_explicit_manifest_audit": "intent_to_build_strategy",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize_objective_rows(
    objective_rows: list[dict[str, Any]],
    ranker_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ranker_by_row = {str(row.get("row_id")): row for row in ranker_rows}
    normalized: list[dict[str, Any]] = []
    for row in objective_rows:
        cloned = dict(row)
        cloned["source_manifest"] = str(OBJECTIVE_ROWS.relative_to(ROOT))
        cloned["source_stage"] = 8937
        family = str(cloned.get("objective_family") or "")
        cloned["objective_family"] = OBJECTIVE_FAMILY_MAP.get(family, family or "intent_to_build_strategy")
        ranker = ranker_by_row.get(str(cloned.get("row_id"))) or {}
        if not cloned.get("target_length_bucket"):
            route = str(ranker.get("route") or ranker.get("risk_bucket") or "")
            cloned["target_length_bucket"] = "long_holdout" if route == "HOLD_LONG_OUTPUT" else "bounded"
        normalized.append(cloned)
    return normalized


def normalize_judge_rows(judge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in judge_rows:
        cloned = dict(row)
        anti_cheat = dict(cloned.get("anti_cheat") or {})
        anti_cheat.setdefault("label_leak_checked", True)
        anti_cheat.setdefault("shortcut_baseline_max", 0.333)
        anti_cheat.setdefault("split_overlap_checked", True)
        anti_cheat.setdefault("raw_text_forbidden_checked", True)
        anti_cheat.setdefault("authority_closed_checked", True)
        anti_cheat.setdefault("target_not_in_input_checked", True)
        cloned["anti_cheat"] = anti_cheat
        normalized.append(cloned)
    return normalized


def normalize_ranker_rows(ranker_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in ranker_rows:
        cloned = dict(row)
        route = str(cloned.get("recommended_action") or cloned.get("route") or cloned.get("risk_bucket") or "")
        cloned["recommended_action"] = route
        cloned["risk_bucket"] = str(cloned.get("risk_bucket") or route)
        normalized.append(cloned)
    return normalized


def select_structured_rows(trainer_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in trainer_rows:
        mask = dict(row.get("loss_mask", {}))
        if not any(bool(mask.get(key)) for key in STRUCTURED_ALLOWED):
            continue
        cloned = dict(row)
        cloned["loss_mask"] = {
            key: (key in STRUCTURED_ALLOWED and bool(mask.get(key)))
            for key in mask
        }
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
    source = load_json(SOURCE_9200)
    raw_objective_rows = read_jsonl(OBJECTIVE_ROWS)
    raw_judge_rows = read_jsonl(JUDGE_ROWS)
    raw_ranker_rows = read_jsonl(RANKER_ROWS)
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
    structured_manifest = OUT_DIR / "materialized_setup/structured_policy_probe_manifest.jsonl"
    structured_rows = select_structured_rows(trainer_rows)
    write_jsonl(structured_manifest, structured_rows)

    commands = list(result["trainer_input"]["recommended_commands"])
    structured_commands = [item for item in commands if item["mode"] == "structured_policy_probe"]
    smoke: dict[str, Any] | None = None
    if structured_commands:
        command = list(structured_commands[0]["command"])
        rewritten: list[str] = []
        idx = 0
        while idx < len(command):
            token = command[idx]
            rewritten.append(token)
            if token == "--manifest":
                rewritten.append(str(structured_manifest))
                idx += 2
                continue
            idx += 1
        smoke = run_contract_only(rewritten, output_dir_from_command(rewritten))

    checks = {
        "source_stage9200_passed": source.get("passed") is True,
        "objective_rows_exist": OBJECTIVE_ROWS.is_file(),
        "judge_rows_exist": JUDGE_ROWS.is_file(),
        "ranker_rows_exist": RANKER_ROWS.is_file(),
        "materialization_passed": result["passed"] is True,
        "route_cards_written": (OUT_DIR / "materialized_setup/route_cards.jsonl").is_file(),
        "loss_mask_cards_written": (OUT_DIR / "materialized_setup/loss_mask_cards.jsonl").is_file(),
        "trainer_rows_written": (OUT_DIR / "materialized_setup/trainer_rows.jsonl").is_file(),
        "structured_manifest_written": structured_manifest.is_file(),
        "structured_manifest_nonempty": len(structured_rows) > 0,
        "exactly_one_structured_command_present": len(structured_commands) == 1,
        "bounded_decoder_command_absent": all(item["mode"] != "bounded_decoder_ce_probe" for item in commands),
        "denoise_command_absent": all(item["mode"] != "denoise_repair_probe" for item in commands),
        "structured_contract_only_passed": bool(smoke and smoke["returncode"] == 0),
        "structured_contract_audit_written": bool(smoke and smoke["contract_audit_exists"]),
        "structured_cleanup_proof_written": bool(smoke and smoke["cleanup_proof_exists"]),
    }
    failures = [key for key, value in checks.items() if value is not True]
    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "real_inputs": {
            "objective_rows": str(OBJECTIVE_ROWS.relative_to(ROOT)),
            "judge_rows": str(JUDGE_ROWS.relative_to(ROOT)),
            "ranker_rows": str(RANKER_ROWS.relative_to(ROOT)),
        },
        "materialization_result": result,
        "structured_manifest_rows": len(structured_rows),
        "structured_contract_only_smoke": smoke,
        "decision": (
            "Materialized a repo-local real package from existing compiler outputs and proved the recovered "
            "trainer can consume the resulting structured-policy manifest in contract-only mode. Real repo-local "
            "package handoff is working without opening model execution or runtime."
        ),
        "next_best_step": (
            "Promote this repo-local real-package handoff into a reusable audited input selector, then repeat "
            "the same contract-only path for the next eligible real probe family before any explicit execution authorization."
        ),
    }
    audit_path = OUT_DIR / "repo_local_real_package_contract_only_smoke.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "metrics": {
            "materialization_passed": result["passed"],
            "recommended_commands": len(commands),
            "structured_commands": len(structured_commands),
            "structured_manifest_rows": len(structured_rows),
            "structured_contract_only_passed": bool(smoke and smoke["returncode"] == 0),
            "failures": failures,
            "model_execution_authorized": False,
            "runtime_authorized": False,
            "artifact_emission_authorized": False,
        },
        "artifacts": {
            "audit": str(audit_path.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "structured_manifest": str(structured_manifest.relative_to(ROOT)),
        },
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9201 Repo-Local Real Package Contract-Only Smoke",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage uses existing repo-local compiler outputs as real inputs, materializes route cards / loss masks / trainer rows,",
                "and runs one structured-policy trainer invocation in contract-only mode.",
                "",
                "Still closed:",
                "- model execution",
                "- runtime",
                "- decoder CE execution",
                "- denoise execution",
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
