#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from materialize_trainer_setup import materialize_training_setup
    from build_stage9206_repo_local_three_family_selector import (
        normalize_bundle_rows,
    )
except ModuleNotFoundError:  # pragma: no cover
    from scripts.materialize_trainer_setup import materialize_training_setup  # type: ignore
    from scripts.build_stage9206_repo_local_three_family_selector import (  # type: ignore
        normalize_bundle_rows,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9207
NAME = "stage9207_three_family_contract_only_handoff"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9206 = ROOT / "runs/summaries/stage9206_repo_local_three_family_selector.json"
SELECTED_BUNDLES = ROOT / "runs/local/artifacts/stage9206_repo_local_three_family_selector/selected_repo_local_three_family_bundles.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "THREE_FAMILY_CONTRACT_ONLY_HANDOFF_STAGE9207.md"
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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
    source = load_json(SOURCE_9206)
    bundles = load_json(SELECTED_BUNDLES)
    bundle_results: list[dict[str, Any]] = []

    for bundle in bundles:
        bundle_id = str(bundle["bundle_id"])
        preferred_mode = str(bundle["preferred_mode"])
        objective_rows, judge_rows, ranker_rows = normalize_bundle_rows(bundle)
        bundle_out = OUT_DIR / bundle_id
        result = materialize_training_setup(
            objective_rows,
            judge_rows,
            ranker_rows,
            output_dir=bundle_out / "materialized_setup",
        )
        trainer_rows = read_jsonl(bundle_out / "materialized_setup/trainer_rows.jsonl")
        manifest_path = bundle_out / "materialized_setup" / f"{preferred_mode}_manifest.jsonl"
        mode_rows = select_rows_for_mode(trainer_rows, preferred_mode)
        write_jsonl(manifest_path, mode_rows)

        command_spec = None
        for item in result["trainer_input"]["recommended_commands"]:
            if item["mode"] == preferred_mode:
                command_spec = item
                break
        if command_spec is None:
            bundle_results.append(
                {
                    "bundle_id": bundle_id,
                    "preferred_mode": preferred_mode,
                    "materialization_passed": result["passed"],
                    "manifest_rows": len(mode_rows),
                    "smoke": None,
                }
            )
            continue

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
        bundle_results.append(
            {
                "bundle_id": bundle_id,
                "preferred_mode": preferred_mode,
                "materialization_passed": result["passed"],
                "manifest_rows": len(mode_rows),
                "smoke": smoke,
            }
        )

    checks = {
        "source_stage9206_passed": bool(source.get("passed") is True),
        "selected_bundles_present": isinstance(bundles, list) and len(bundles) >= 3,
        "structured_bundle_present": any(item["preferred_mode"] == "structured_policy_probe" for item in bundle_results),
        "bounded_bundle_present": any(item["preferred_mode"] == "bounded_decoder_ce_probe" for item in bundle_results),
        "denoise_bundle_present": any(item["preferred_mode"] == "denoise_repair_probe" for item in bundle_results),
        "all_materializations_passed": all(item["materialization_passed"] for item in bundle_results),
        "all_manifests_nonempty": all(item["manifest_rows"] > 0 for item in bundle_results),
        "all_smokes_passed": all(item["smoke"] and item["smoke"]["returncode"] == 0 for item in bundle_results),
        "all_contract_audits_written": all(item["smoke"] and item["smoke"]["contract_audit_exists"] for item in bundle_results),
        "all_cleanup_proofs_written": all(item["smoke"] and item["smoke"]["cleanup_proof_exists"] for item in bundle_results),
    }
    failures = [key for key, value in checks.items() if value is not True]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "bundle_results": bundle_results,
        "decision": (
            "Consumed the selected three-family bundle set and ran contract-only handoff smokes across structured, bounded-decoder, "
            "and denoise probe families without reopening model execution or runtime."
        ),
        "next_best_step": (
            "The repo-local trainer recovery path is now contract-only complete across all intended probe families. The next move is a bounded explicit execution-review path, not more handoff plumbing."
        ),
    }
    audit_path = OUT_DIR / "three_family_contract_only_handoff.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "metrics": {
            "bundle_results": len(bundle_results),
            "contract_only_smokes_passed": sum(1 for item in bundle_results if item["smoke"] and item["smoke"]["returncode"] == 0),
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
                "# Stage9207 Three-Family Contract-Only Handoff",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage proves contract-only handoff across structured, bounded-decoder, and denoise probe families",
                "using repo-local real bundles only.",
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
