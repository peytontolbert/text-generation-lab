#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from diagnostic_ticket_contract import AUTHORITY_CLOSED
from manifest_path_validator import validate_manifest_input_path
from materialize_trainer_setup import materialize_training_setup, read_jsonl
from build_stage9201_repo_local_real_package_contract_only_smoke import (
    normalize_judge_rows,
    normalize_objective_rows,
    normalize_ranker_rows,
)

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9202
NAME = "stage9202_repo_local_real_input_selector"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9201 = ROOT / "runs/summaries/stage9201_repo_local_real_package_contract_only_smoke.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_REAL_INPUT_SELECTOR_STAGE9202.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SELECTOR = OUT_DIR / "repo_local_real_input_selector.json"
SELECTED = OUT_DIR / "selected_repo_local_real_input_bundle.json"


CANDIDATE_BUNDLES = [
    {
        "bundle_id": "stage8937_tiny_explicit_manifest_cli_audit",
        "bundle_kind": "repo_local_real_input_bundle_v1",
        "normalization_profile": "stage9201_stage8937_adapter_v1",
        "objective_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/normalized_input_rows.jsonl",
        "judge_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/judged_rows.jsonl",
        "junk_ranker_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/ranked_rows.jsonl",
    }
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_bundle_paths(bundle: dict[str, Any]) -> dict[str, Any]:
    objective = validate_manifest_input_path(bundle["objective_rows_path"], repo_root=ROOT, must_exist=True)
    judge = validate_manifest_input_path(bundle["judge_rows_path"], repo_root=ROOT, must_exist=True)
    ranker = validate_manifest_input_path(bundle["junk_ranker_rows_path"], repo_root=ROOT, must_exist=True)
    return {
        "objective": objective,
        "judge": judge,
        "ranker": ranker,
        "paths_valid": objective["allowed"] and judge["allowed"] and ranker["allowed"],
    }


def materialization_preview(bundle: dict[str, Any], preview_dir: Path) -> dict[str, Any]:
    objective_path = ROOT / bundle["objective_rows_path"]
    judge_path = ROOT / bundle["judge_rows_path"]
    ranker_path = ROOT / bundle["junk_ranker_rows_path"]
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
        output_dir=preview_dir,
    )
    trainer_input = result["trainer_input"]
    modes = [item["mode"] for item in trainer_input["recommended_commands"]]
    return {
        "materialization_passed": result["passed"],
        "route_audit": result["route_audit"],
        "loss_audit": result["loss_audit"],
        "trainer_audit": result["trainer_audit"],
        "trainer_input": trainer_input,
        "eligible_modes": modes,
        "objective_rows": len(raw_objective_rows),
        "judge_rows": len(raw_judge_rows),
        "ranker_rows": len(raw_ranker_rows),
    }


def choose_bundle(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    passed = [c for c in candidates if c["bundle_preview"]["materialization_passed"]]
    if not passed:
        return None
    passed.sort(
        key=lambda item: (
            len(item["bundle_preview"]["eligible_modes"]),
            item["bundle_preview"]["objective_rows"],
        ),
        reverse=True,
    )
    return passed[0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_9201)
    candidates: list[dict[str, Any]] = []
    for bundle in CANDIDATE_BUNDLES:
        path_validation = validate_bundle_paths(bundle)
        preview = materialization_preview(bundle, OUT_DIR / bundle["bundle_id"] / "materialization_preview") if path_validation["paths_valid"] else {
            "materialization_passed": False,
            "eligible_modes": [],
            "objective_rows": 0,
            "judge_rows": 0,
            "ranker_rows": 0,
        }
        candidates.append(
            {
                **bundle,
                "path_validation": path_validation,
                "bundle_preview": preview,
            }
        )

    selected = choose_bundle(candidates)
    checks = {
        "source_stage9201_passed": source.get("passed") is True,
        "candidate_bundles_present": len(candidates) > 0,
        "all_candidates_repo_local": all(
            candidate["path_validation"]["objective"]["allowed"]
            and candidate["path_validation"]["judge"]["allowed"]
            and candidate["path_validation"]["ranker"]["allowed"]
            for candidate in candidates
        ),
        "selected_bundle_present": selected is not None,
        "selected_bundle_materialization_passed": bool(selected and selected["bundle_preview"]["materialization_passed"]),
        "selected_bundle_has_eligible_modes": bool(selected and selected["bundle_preview"]["eligible_modes"]),
        "selected_bundle_paths_under_repo": bool(
            selected
            and selected["path_validation"]["objective"]["root_label"] is not None
            and selected["path_validation"]["judge"]["root_label"] is not None
            and selected["path_validation"]["ranker"]["root_label"] is not None
        ),
        "trainer_execution_closed": True,
        "model_forward_closed": True,
        "runtime_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]

    selector = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "candidate_bundles": candidates,
        "selected_bundle_id": selected["bundle_id"] if selected else None,
        "selected_bundle": selected,
        "decision": (
            "Selected a reusable repo-local real input bundle by validating local manifest paths and previewing "
            "materialization under the recovered route-card/loss-mask contract. No trainer execution, model forward, "
            "runtime, or explicit execution authorization was opened."
        ),
        "next_best_step": (
            "Feed the selected bundle into the next contract-only real probe family handoff, or add another repo-local "
            "candidate bundle and let the selector choose between them."
        ),
    }

    SELECTOR.write_text(json.dumps(selector, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if selected is not None:
        SELECTED.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": selector["passed"],
        "metrics": {
            "candidate_bundles": len(candidates),
            "selected_bundle_present": selected is not None,
            "selected_bundle_materialization_passed": bool(selected and selected["bundle_preview"]["materialization_passed"]),
            "selected_bundle_eligible_modes": len(selected["bundle_preview"]["eligible_modes"]) if selected else 0,
            "trainer_execution_authorized": False,
            "runtime_authorized": False,
            "failures": failures,
        },
        "artifacts": {
            "selector": str(SELECTOR.relative_to(ROOT)),
            "selected_bundle": str(SELECTED.relative_to(ROOT)) if selected is not None else None,
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": selector["decision"],
        "next_best_step": selector["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9202 Repo-Local Real Input Selector",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage validates repo-local candidate bundles, previews materialization under the recovered contract,",
                "and selects one reusable real-input bundle without invoking the trainer.",
                "",
                "Still closed:",
                "- trainer execution",
                "- model forward",
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
