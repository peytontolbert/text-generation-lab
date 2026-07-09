#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9692
NAME = "stage9692_v27_source_backed_multilingual_training_surface_reconciliation"
LOCKED_PACKS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_multilingual_task_pack_skeleton.json"
LOCKED_EXCLUSIONS = ROOT / "runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl"
LOCKED_GUARD = ROOT / "runs/summaries/stage9688_locked_eval_guard_graph_attachment.json"
RECONNECT = ROOT / "runs/summaries/stage9691_observe_repair_renderer_reconnect_decision.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GAP_MATRIX = OUT_DIR / "v27_source_backed_training_surface_gap_matrix.json"
SELECTION = OUT_DIR / "v27_next_training_package_selection.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_SOURCE_BACKED_MULTILINGUAL_TRAINING_SURFACE_RECONCILIATION_STAGE9692.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_SURFACES: dict[str, dict[str, Any]] = {
    "intent_to_build_strategy": {
        "status": "structured_ready_needs_multilingual_source_backing",
        "artifacts": [
            "runs/summaries/stage8630_intent_to_build_neutral_manifest.json",
            "runs/summaries/stage8631_intent_to_build_shortcut_baseline.json",
            "runs/summaries/stage8668_intent_to_build_copy_routed_manifest.json",
        ],
        "training_role": "structured_policy_head",
        "next_patch": "refresh intent-to-build as source-backed multilingual rows with locked-source guard and no visible copy semantic CE",
    },
    "repo_state_graph_navigation": {
        "status": "seed_ready_needs_navigation_objective",
        "artifacts": [
            "runs/local/artifacts/stage8601_arxiv_repo_capability_and_graph_seed/repo_state_graph_seed.jsonl",
            "runs/summaries/reconstructed_from_sessions/stage8539_reconstructed_from_session_index.json",
        ],
        "training_role": "repo_graph_navigation_head",
        "next_patch": "materialize graph-navigation rows: query/task observable -> active subgraph/candidate evidence route",
    },
    "symbol_binding": {
        "status": "source_backed_candidate_ready_needs_locked_guard_refresh",
        "artifacts": [
            "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit.json",
            "runs/local/artifacts/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit/shortcut_repair_manifest_audit_card.json",
        ],
        "training_role": "symbol_binding_ce",
        "next_patch": "compile repaired symbol-binding rows through curriculum compiler with locked-source exclusions and loss masks",
    },
    "edit_localization": {
        "status": "source_backed_candidate_ready_needs_locked_guard_refresh",
        "artifacts": [
            "runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json",
            "runs/local/artifacts/stage8766_source_backed_edit_localization_candidate_audit/schema_card.json",
            "runs/local/artifacts/stage8766_source_backed_edit_localization_candidate_audit/contamination_card.json",
        ],
        "training_role": "edit_localization_ce",
        "next_patch": "compile edit-localization candidates through curriculum compiler with locked-source exclusions and topology counterbalance checks",
    },
    "patch_operator_selection": {
        "status": "source_backed_candidate_ready_needs_locked_guard_refresh",
        "artifacts": [
            "runs/summaries/stage8775_source_backed_patch_operator_candidate_audit.json",
            "runs/local/artifacts/stage8775_source_backed_patch_operator_candidate_audit/schema_card.json",
            "runs/local/artifacts/stage8775_source_backed_patch_operator_candidate_audit/contamination_card.json",
        ],
        "training_role": "patch_operator_ce",
        "next_patch": "compile patch-operator candidates through curriculum compiler with locked-source exclusions and degree-profile counterbalance checks",
    },
    "bounded_argument_rendering": {
        "status": "decoder_candidate_ready_needs_locked_guard_refresh",
        "artifacts": [
            "runs/summaries/stage9240_source_backed_multilang_bounded_decoder_tiny_package.json",
            "runs/summaries/stage9241_multilang_source_backed_target_100m_contract_only_preflight.json",
        ],
        "training_role": "bounded_decoder_ce_after_structured_gates",
        "next_patch": "re-run bounded decoder package selection under Stage9688 locked guard before any execution",
    },
    "verifier_expectation": {
        "status": "missing_explicit_source_backed_objective",
        "artifacts": [],
        "training_role": "verifier_expectation_head",
        "next_patch": "build patch/operator -> expected verifier command/pass-condition rows before harness scoring",
    },
    "verifier_failure_repair_or_abstain": {
        "status": "source_backed_candidate_ready_needs_locked_guard_refresh",
        "artifacts": [
            "runs/summaries/stage8789_source_backed_verifier_repair_candidate_audit.json",
            "runs/local/artifacts/stage8789_source_backed_verifier_repair_candidate_audit/schema_card.json",
            "runs/local/artifacts/stage8789_source_backed_verifier_repair_candidate_audit/contamination_card.json",
        ],
        "training_role": "verifier_repair_ce",
        "next_patch": "compile verifier-repair candidates through curriculum compiler with locked-source exclusions and repair-action counterbalance checks",
    },
    "final_user_facing_summary": {
        "status": "missing_explicit_source_backed_objective",
        "artifacts": [],
        "training_role": "final_summary_renderer_or_bounded_decoder",
        "next_patch": "build verified-transition -> final user-facing summary rows only after verifier/repair state passes",
    },
}

READY_STATUSES = {
    "source_backed_candidate_ready_needs_locked_guard_refresh",
    "decoder_candidate_ready_needs_locked_guard_refresh",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_state(paths: list[str]) -> dict[str, bool]:
    return {path: (ROOT / path).exists() for path in paths}


def build_gap_matrix(locked_suite: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    packs = locked_suite.get("benchmark_packs") or []
    failures: list[str] = []
    skill_counts = Counter(str(pack.get("skill_area")) for pack in packs)
    language_counts = Counter(str(pack.get("language_family")) for pack in packs)
    mode_counts = Counter(str(pack.get("mode")) for pack in packs)
    skill_records: list[dict[str, Any]] = []
    for skill in sorted(skill_counts):
        surface = dict(SOURCE_SURFACES.get(skill) or {"status": "missing_mapping", "artifacts": [], "training_role": "unknown", "next_patch": "add explicit mapping"})
        artifacts = artifact_state(list(surface.get("artifacts") or []))
        missing = sorted(path for path, present in artifacts.items() if not present)
        if missing and surface.get("status") in READY_STATUSES:
            failures.append(f"missing_ready_artifact:{skill}")
        skill_records.append({
            "skill_area": skill,
            "locked_eval_cells": skill_counts[skill],
            "status": surface.get("status"),
            "training_role": surface.get("training_role"),
            "candidate_artifacts": artifacts,
            "missing_candidate_artifacts": missing,
            "next_patch": surface.get("next_patch"),
            "train_authority_open": False,
        })
    unmapped = sorted(set(skill_counts) - set(SOURCE_SURFACES))
    if unmapped:
        failures.append("unmapped_acceptance_skills")
    return {
        "objective": "v27_source_backed_training_surface_reconciliation",
        "locked_eval_cells": len(packs),
        "skill_records": skill_records,
        "skill_status_counts": dict(sorted(Counter(record["status"] for record in skill_records).items())),
        "skill_counts": dict(sorted(skill_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "ready_for_locked_guard_refresh_skills": sorted(record["skill_area"] for record in skill_records if record["status"] in READY_STATUSES),
        "needs_new_objective_skills": sorted(record["skill_area"] for record in skill_records if str(record["status"]).startswith("missing") or "needs_navigation_objective" in str(record["status"]) or "needs_multilingual_source_backing" in str(record["status"])),
        "authority": dict(AUTHORITY_CLOSED),
    }, failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    locked_suite = load_json(LOCKED_PACKS)
    locked_guard = load_json(LOCKED_GUARD)
    reconnect = load_json(RECONNECT)
    exclusions = read_jsonl(LOCKED_EXCLUSIONS)
    failures: list[str] = []
    if locked_guard.get("passed") is not True:
        failures.append("stage9688_locked_guard_not_passed")
    if reconnect.get("passed") is not True:
        failures.append("stage9691_reconnect_decision_not_passed")
    if len(exclusions) != 72:
        failures.append("locked_exclusion_count_not_72")
    gap, gap_failures = build_gap_matrix(locked_suite)
    failures.extend(gap_failures)

    ready_skills = gap["ready_for_locked_guard_refresh_skills"]
    missing_skills = gap["needs_new_objective_skills"]
    selection = {
        "selected_next_package": "locked_guarded_source_backed_multisurface_compiler_refresh",
        "reason": "Non-template residual queue is empty; the next real v2.7 work is to refresh recovered source-backed maintainer surfaces under the locked-source guard before any broad mining or execution.",
        "include_skill_areas": ready_skills,
        "exclude_until_objective_exists": missing_skills,
        "required_controls": [
            "--locked-source-exclusions runs/local/artifacts/stage9685_locked_multilingual_task_pack_skeleton/v27_locked_source_exclusions.jsonl",
            "loss masks created after locked-source exclusion",
            "authority closed for runtime/source/body/Gemma/harness/scoring/promotion",
            "shortcut and topology baselines rerun per surface",
            "target_100m contract-only preflight before execution",
        ],
        "do_not_do_next": [
            "broad repository mining",
            "Gemma comparison",
            "runtime harness execution",
            "decoder CE execution",
            "source/body emission",
            "promotion or checkpoint export",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    GAP_MATRIX.write_text(json.dumps(gap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SELECTION.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Build Stage9693 locked-guarded source-backed multisurface compiler refresh for symbol binding, edit localization, patch operator, verifier repair, and bounded argument rendering; keep intent/repo-navigation/verifier-expectation/final-summary as explicit gap objectives."
    metrics = {
        **dict(AUTHORITY_CLOSED),
        "failures": failures,
        "locked_eval_cells": gap["locked_eval_cells"],
        "locked_source_exclusions": len(exclusions),
        "ready_for_locked_guard_refresh_skill_count": len(ready_skills),
        "ready_for_locked_guard_refresh_skills": ready_skills,
        "needs_new_objective_skill_count": len(missing_skills),
        "needs_new_objective_skills": missing_skills,
        "skill_status_counts": gap["skill_status_counts"],
        "execution_authorized_next": False,
        "training_authorized_next": False,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": metrics,
        "artifacts": {
            "gap_matrix": str(GAP_MATRIX.relative_to(ROOT)),
            "selection": str(SELECTION.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Reconciled v2.7 locked acceptance cells against recovered trainable source-backed surfaces and selected a locked-guarded multisurface compiler refresh, not broad mining.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9692 V2.7 Source-Backed Multilingual Training Surface Reconciliation",
        "",
        f"Passed: `{summary['passed']}`",
        f"Locked eval cells: `{metrics['locked_eval_cells']}`",
        f"Locked source exclusions: `{metrics['locked_source_exclusions']}`",
        f"Ready for locked-guard refresh: `{ready_skills}`",
        f"Still missing explicit objectives/source-backed refresh: `{missing_skills}`",
        "",
        "Decision: the next real package is a locked-guarded source-backed multisurface compiler refresh. It should use the recovered symbol-binding, edit-localization, patch-operator, verifier-repair, and bounded-argument surfaces, then run target-100M contract-only preflight before any execution.",
        "",
        "Do not broaden mining or run Gemma/harness/decoder execution from this stage. Intent-to-build, repo-state graph navigation, verifier expectation, and final user-facing summary remain explicit gap objectives unless a later stage materializes source-backed rows for them.",
        "",
        "No runtime, source/body emission, Gemma, harness, scoring, model execution, checkpoint export, training execution, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "ready_skills": ready_skills,
        "missing_skills": missing_skills,
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
