#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9684
NAME = "stage9684_v27_multilingual_eval_acceptance_contract"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9683_fixed_template_residual_router.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "v27_multilingual_eval_acceptance_contract.json"
GAP_MATRIX = OUT_DIR / "v27_completion_gap_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_MULTILINGUAL_EVAL_ACCEPTANCE_CONTRACT_STAGE9684.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EVAL_DOC = ROOT / "docs/recovery_v27_100m/06_eval_and_anti_cheat.md"

LANGUAGE_FAMILIES = [
    "python",
    "rust",
    "c_cpp",
    "web_js_ts_html",
]

EVAL_MODES = [
    "standalone_100m_weights",
    "full_product_harness",
]

MAINTAINER_SKILL_AREAS = [
    "intent_to_build_strategy",
    "repo_state_graph_navigation",
    "symbol_binding",
    "edit_localization",
    "patch_operator_selection",
    "bounded_argument_rendering",
    "verifier_expectation",
    "verifier_failure_repair_or_abstain",
    "final_user_facing_summary",
]

REQUIRED_SUPPORT_ARTIFACTS = {
    "golden_locked_eval_suite": ROOT / "scripts/golden_locked_eval_suite.py",
    "traced_eval_observability": ROOT / "scripts/traced_eval_observability.py",
    "semantic_equivalence_metamorphic_verifier": ROOT / "scripts/semantic_equivalence_metamorphic_verifier.py",
    "heldout_non_ce_decoder_eval_design": ROOT / "scripts/heldout_non_ce_decoder_eval_design_builder.py",
    "family_audit_design_schema": ROOT / "scripts/build_stage9229_family_audit_design_output_schema.py",
    "family_audit_design_schema_audit": ROOT / "scripts/build_stage9230_family_audit_design_output_schema_audit.py",
    "locked_benchmark_pack_manifest": ROOT / "scripts/build_stage8672_locked_benchmark_pack_manifest.py",
    "leakage_locked_eval_boundary": ROOT / "scripts/audit_stage8665_manifest_leakage_locked_eval_boundary.py",
    "dense_hybrid_retrieval_baseline": ROOT / "scripts/audit_stage8671_dense_hybrid_retrieval_baseline.py",
    "bm25_retrieval_baseline": ROOT / "scripts/audit_stage8666_repo_span_bm25_retrieval_baseline.py",
}

ANTI_CHEAT_REQUIREMENTS = [
    "hidden_reference_never_train_eligible",
    "target_text_absent_from_model_input",
    "label_coded_ids_rejected",
    "surface_marker_shortcut_baseline_below_ceiling",
    "requested_output_type_shortcut_baseline_below_ceiling",
    "metadata_only_baseline_below_ceiling",
    "graph_degree_baseline_below_ceiling",
    "query_node_id_baseline_below_ceiling",
    "split_semantic_overlap_zero_or_quarantined",
    "duplicate_semantic_key_zero_or_quarantined",
    "internal_token_leak_zero",
    "short_junk_zero",
    "repetition_guard_passed",
    "long_target_budget_gate_enforced",
    "runtime_and_gemma_outputs_not_ground_truth_without_authority",
    "same_harness_prompt_surface_for_100m_and_gemma",
]

REQUIRED_EVIDENCE_BY_MODE = {
    "standalone_100m_weights": [
        "frozen_export_or_checkpoint_hash",
        "standalone_generation_or_structured_action_outputs",
        "same_prompt_surface_gemma12b_outputs",
        "language_slice_scores",
        "expert_maintainer_rubric_scores",
        "anti_cheat_cards",
        "telemetry_bundle",
    ],
    "full_product_harness": [
        "harness_run_id",
        "same_task_pack_as_gemma12b",
        "tool_trace_spans",
        "verifier_results",
        "patch_minimality_or_abstain_scores",
        "expert_maintainer_rubric_scores",
        "anti_cheat_cards",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    artifact_presence = {name: path.exists() for name, path in REQUIRED_SUPPORT_ARTIFACTS.items()}
    missing_support = sorted(name for name, present in artifact_presence.items() if not present)
    acceptance_cells: list[dict[str, Any]] = []
    for mode in EVAL_MODES:
        for language in LANGUAGE_FAMILIES:
            for skill in MAINTAINER_SKILL_AREAS:
                acceptance_cells.append({
                    "mode": mode,
                    "language_family": language,
                    "skill_area": skill,
                    "required_evidence": REQUIRED_EVIDENCE_BY_MODE[mode],
                    "status": "missing_final_evidence",
                    "claim_ready": False,
                })

    gap_matrix = {
        "objective": "finish_v2_7_100m_software_maintainer_beats_gemma12b_standalone_and_harness",
        "source_frontier_stage": 9683,
        "language_families": LANGUAGE_FAMILIES,
        "eval_modes": EVAL_MODES,
        "maintainer_skill_areas": MAINTAINER_SKILL_AREAS,
        "acceptance_cells": acceptance_cells,
        "total_acceptance_cells": len(acceptance_cells),
        "claim_ready_cells": 0,
        "missing_final_evidence_cells": len(acceptance_cells),
    }
    GAP_MATRIX.write_text(json.dumps(gap_matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    contract = {
        "passed": source.get("passed") is True and not missing_support,
        "source_stage": 9683,
        "contract_name": "v27_multilingual_eval_acceptance_contract",
        "not_completion_claim": True,
        "completion_requires_all_acceptance_cells_claim_ready": True,
        "languages_required": LANGUAGE_FAMILIES,
        "eval_modes_required": EVAL_MODES,
        "maintainer_skill_areas_required": MAINTAINER_SKILL_AREAS,
        "anti_cheat_requirements": ANTI_CHEAT_REQUIREMENTS,
        "required_support_artifacts": {name: str(path.relative_to(ROOT)) for name, path in REQUIRED_SUPPORT_ARTIFACTS.items()},
        "support_artifact_presence": artifact_presence,
        "missing_support_artifacts": missing_support,
        "required_evidence_by_mode": REQUIRED_EVIDENCE_BY_MODE,
        "acceptance_rule": {
            "standalone": "100m_score_by_language_and_overall_must_exceed_gemma12b_same_surface_after_anti_cheat_gates",
            "harness": "100m_product_harness_score_by_language_and_overall_must_exceed_gemma12b_same_task_pack_after_anti_cheat_gates",
            "expert_maintainer": "rubric_scores_must_pass_all_required_skill_areas_with_failure_trace_attribution",
            "no_eval_hacking": "any anti_cheat_failure_blocks_completion_and_training_promotion",
        },
        "current_frontier_interpretation": {
            "fixed_template_residuals": "handled_by_stage9681_renderer_and_stage9683_router",
            "denoise_retry_queue_current_rows": 0,
            "decoder_generation_status": "not_broadly_quality_passing",
            "gemma_harness_status": "not_yet_authorized_or_scored",
            "completion_status": "not_complete",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9683_not_passed")
    if missing_support:
        failures.append("missing_required_support_artifacts")
    if not EVAL_DOC.exists():
        failures.append("missing_eval_recovery_doc")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": failures,
            "required_languages": len(LANGUAGE_FAMILIES),
            "required_eval_modes": len(EVAL_MODES),
            "required_skill_areas": len(MAINTAINER_SKILL_AREAS),
            "acceptance_cells": len(acceptance_cells),
            "claim_ready_cells": 0,
            "missing_final_evidence_cells": len(acceptance_cells),
            "support_artifacts_present": sum(int(v) for v in artifact_presence.values()),
            "support_artifacts_required": len(artifact_presence),
            "missing_support_artifacts": missing_support,
        },
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "gap_matrix": str(GAP_MATRIX.relative_to(ROOT)),
        },
        "decision": "Materialized the v2.7 multilingual Gemma/harness/expert-maintainer acceptance contract; this is not a completion claim.",
        "next_best_step": "Build Stage9685 locked multilingual task-pack skeleton for the acceptance cells, with hidden/promotion-only split roles and anti-cheat cards before any Gemma or harness execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9684 V2.7 Multilingual Eval Acceptance Contract",
        "",
        f"Passed: `{summary['passed']}`",
        f"Acceptance cells: `{len(acceptance_cells)}`",
        f"Claim-ready cells: `0`",
        "",
        "This stage converts the user objective into an explicit proof contract. It does not claim v2.7 is complete.",
        "",
        "Required languages:",
        *[f"- `{language}`" for language in LANGUAGE_FAMILIES],
        "",
        "Required modes:",
        *[f"- `{mode}`" for mode in EVAL_MODES],
        "",
        "Required maintainer skills:",
        *[f"- `{skill}`" for skill in MAINTAINER_SKILL_AREAS],
        "",
        "Completion is blocked until every language x mode x skill cell has same-surface 100M-vs-Gemma evidence, expert-maintainer rubric scoring, and anti-cheat cards.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": failures,
        "acceptance_cells": len(acceptance_cells),
        "claim_ready_cells": 0,
        "next_best_step": summary["next_best_step"],
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
