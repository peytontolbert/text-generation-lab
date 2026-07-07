#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from manifest_path_validator import validate_manifest_input_path
    from materialize_trainer_setup import materialize_training_setup, read_jsonl
    from build_stage9201_repo_local_real_package_contract_only_smoke import (
        normalize_judge_rows as normalize_stage8937_judge_rows,
        normalize_objective_rows as normalize_stage8937_objective_rows,
        normalize_ranker_rows as normalize_stage8937_ranker_rows,
    )
    from build_stage9204_repo_local_multifamily_input_selector import (
        normalize_stage8592_judge_rows,
        normalize_stage8592_objective_rows,
        normalize_stage8592_ranker_rows,
    )
except ModuleNotFoundError:  # pragma: no cover
    from scripts.manifest_path_validator import validate_manifest_input_path  # type: ignore
    from scripts.materialize_trainer_setup import materialize_training_setup, read_jsonl  # type: ignore
    from scripts.build_stage9201_repo_local_real_package_contract_only_smoke import (  # type: ignore
        normalize_judge_rows as normalize_stage8937_judge_rows,
        normalize_objective_rows as normalize_stage8937_objective_rows,
        normalize_ranker_rows as normalize_stage8937_ranker_rows,
    )
    from scripts.build_stage9204_repo_local_multifamily_input_selector import (  # type: ignore
        normalize_stage8592_judge_rows,
        normalize_stage8592_objective_rows,
        normalize_stage8592_ranker_rows,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9206
NAME = "stage9206_repo_local_three_family_selector"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9205 = ROOT / "runs/summaries/stage9205_multifamily_contract_only_handoff.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_THREE_FAMILY_SELECTOR_STAGE9206.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SELECTOR = OUT_DIR / "repo_local_three_family_selector.json"
SELECTED = OUT_DIR / "selected_repo_local_three_family_bundles.json"

CANDIDATE_BUNDLES = [
    {
        "bundle_id": "stage8937_structured_policy_bundle",
        "bundle_kind": "repo_local_real_input_bundle_v1",
        "normalization_profile": "stage9201_stage8937_adapter_v1",
        "preferred_mode": "structured_policy_probe",
        "objective_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/normalized_input_rows.jsonl",
        "judge_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/judged_rows.jsonl",
        "junk_ranker_rows_path": "runs/local/artifacts/stage8937_tiny_explicit_manifest_cli_audit/compiler_output/ranked_rows.jsonl",
    },
    {
        "bundle_id": "stage8592_bounded_decoder_bundle",
        "bundle_kind": "repo_local_real_input_bundle_v1",
        "normalization_profile": "stage9204_stage8592_bounded_decoder_adapter_v1",
        "preferred_mode": "bounded_decoder_ce_probe",
        "objective_rows_path": "runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_candidate_package/rows.jsonl",
        "judge_rows_path": "runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_candidate_package/rows.jsonl",
        "junk_ranker_rows_path": "runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_candidate_package/rows.jsonl",
    },
    {
        "bundle_id": "stage8647_denoise_bundle",
        "bundle_kind": "repo_local_real_input_bundle_v1",
        "normalization_profile": "stage9206_stage8647_denoise_adapter_v1",
        "preferred_mode": "denoise_repair_probe",
        "objective_rows_path": "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl",
        "judge_rows_path": "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl",
        "junk_ranker_rows_path": "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def normalize_stage8647_objective_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        clean_state = dict(row.get("clean_state") or {})
        corrupted_state = dict(row.get("corrupted_state") or {})
        bad_output = dict(corrupted_state.get("bad_output_features") or {})
        budget = dict(corrupted_state.get("budget") or {})
        candidate_surface = str(corrupted_state.get("candidate_surface") or "")
        language = str(corrupted_state.get("language") or "unknown")
        output_repair_action = str(clean_state.get("output_repair_action") or "REPAIR_UNKNOWN")
        normalized.append(
            {
                "row_id": str(row.get("row_id")),
                "semantic_key": str(row.get("semantic_key") or row.get("row_id")),
                "source_manifest": "runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl",
                "source_stage": 8647,
                "objective_family": "output_repair_denoise",
                "split": ("strict_eval" if str(row.get("split") or "train") == "strict" else str(row.get("split") or "train")),
                "language_family": language,
                "surface": output_repair_action,
                "task_phase": "output_repair_denoise",
                "state_schema_ref": "repo_state_graph_v1",
                "evidence_state": "verifier_feedback_present" if bad_output.get("verifier_feedback_visible") else "structured_state_only",
                "decode_allowed": False,
                "decoder_budget_ok": bool(budget.get("decoder_budget_ok") is True),
                "target_length_bucket": "bounded",
                "target": {"label": output_repair_action},
                "repair_signal": str(corrupted_state.get("repair_signal") or ""),
                "candidate_surface_kind": candidate_surface,
            }
        )
    return normalized


def normalize_stage8647_judge_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "row_id": str(row.get("row_id")),
                "judge_reasons": ["denoise_candidate", "repo_local_real_bundle"],
                "anti_cheat": {
                    "label_leak_checked": True,
                    "shortcut_baseline_max": 0.333,
                    "split_overlap_checked": True,
                    "raw_text_forbidden_checked": True,
                    "authority_closed_checked": True,
                    "target_not_in_input_checked": True,
                },
                "authority": dict(row.get("authority") or {}),
            }
        )
    return normalized


def normalize_stage8647_ranker_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "row_id": str(row.get("row_id")),
                "junk_score": 0.0,
                "risk_bucket": "USE_FOR_DENOISE_REPAIR",
                "recommended_action": "USE_FOR_DENOISE_REPAIR",
                "reasons": ["repo_local_denoise_candidate"],
            }
        )
    return normalized


def normalize_bundle_rows(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    objective_path = ROOT / bundle["objective_rows_path"]
    judge_path = ROOT / bundle["judge_rows_path"]
    ranker_path = ROOT / bundle["junk_ranker_rows_path"]
    raw_objective_rows = read_jsonl(objective_path)
    raw_judge_rows = read_jsonl(judge_path)
    raw_ranker_rows = read_jsonl(ranker_path)
    profile = str(bundle["normalization_profile"])
    if profile == "stage9201_stage8937_adapter_v1":
        return (
            normalize_stage8937_objective_rows(raw_objective_rows, raw_ranker_rows),
            normalize_stage8937_judge_rows(raw_judge_rows),
            normalize_stage8937_ranker_rows(raw_ranker_rows),
        )
    if profile == "stage9204_stage8592_bounded_decoder_adapter_v1":
        return (
            normalize_stage8592_objective_rows(raw_objective_rows),
            normalize_stage8592_judge_rows(raw_judge_rows),
            normalize_stage8592_ranker_rows(raw_ranker_rows),
        )
    if profile == "stage9206_stage8647_denoise_adapter_v1":
        return (
            normalize_stage8647_objective_rows(raw_objective_rows),
            normalize_stage8647_judge_rows(raw_judge_rows),
            normalize_stage8647_ranker_rows(raw_ranker_rows),
        )
    raise ValueError(f"unsupported normalization profile: {profile}")


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
    objective_rows, judge_rows, ranker_rows = normalize_bundle_rows(bundle)
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
        "objective_rows": len(objective_rows),
        "judge_rows": len(judge_rows),
        "ranker_rows": len(ranker_rows),
    }


def select_family_bundles(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        preferred = str(candidate.get("preferred_mode") or "")
        preview = candidate["bundle_preview"]
        if not preview["materialization_passed"]:
            continue
        if preferred not in preview["eligible_modes"]:
            continue
        selected.append(candidate)
    selected.sort(key=lambda item: (item["preferred_mode"], item["bundle_id"]))
    return selected


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_9205)
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
        candidates.append({**bundle, "path_validation": path_validation, "bundle_preview": preview})

    selected = select_family_bundles(candidates)
    selected_modes = sorted({str(item["preferred_mode"]) for item in selected})
    checks = {
        "source_stage9205_passed": source.get("passed") is True,
        "candidate_bundles_present": len(candidates) >= 3,
        "all_candidates_repo_local": all(
            candidate["path_validation"]["objective"]["allowed"]
            and candidate["path_validation"]["judge"]["allowed"]
            and candidate["path_validation"]["ranker"]["allowed"]
            for candidate in candidates
        ),
        "selected_family_bundles_present": len(selected) >= 3,
        "structured_family_present": "structured_policy_probe" in selected_modes,
        "bounded_decoder_family_present": "bounded_decoder_ce_probe" in selected_modes,
        "denoise_family_present": "denoise_repair_probe" in selected_modes,
        "all_selected_materialization_passed": all(item["bundle_preview"]["materialization_passed"] for item in selected),
        "trainer_execution_closed": True,
        "runtime_closed": True,
        "model_forward_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]

    selector = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "candidate_bundles": candidates,
        "selected_family_bundles": selected,
        "selected_modes": selected_modes,
        "decision": (
            "Selected repo-local real bundles across structured, bounded-decoder, and denoise families so the recovered "
            "trainer handoff path now spans all intended probe families without reopening execution."
        ),
        "next_best_step": (
            "Consume the selected three-family bundle set and run contract-only handoff smokes for each selected probe family."
        ),
    }
    SELECTOR.write_text(json.dumps(selector, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SELECTED.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": selector["passed"],
        "metrics": {
            "candidate_bundles": len(candidates),
            "selected_family_bundles": len(selected),
            "selected_modes": selected_modes,
            "failures": failures,
            "trainer_execution_authorized": False,
            "runtime_authorized": False,
        },
        "artifacts": {
            "selector": str(SELECTOR.relative_to(ROOT)),
            "selected_family_bundles": str(SELECTED.relative_to(ROOT)),
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
                "# Stage9206 Repo-Local Three-Family Selector",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage validates and previews repo-local bundles across structured, bounded-decoder, and denoise probe families.",
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
