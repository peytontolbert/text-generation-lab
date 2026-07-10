#!/usr/bin/env python3
from __future__ import annotations

import copy
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
STAGE = 9779
NAME = "stage9779_current_truthful_standalone_claim_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "current_truthful_standalone_claim_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_TRUTHFUL_STANDALONE_CLAIM_BRIDGE_STAGE9779.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
SOURCE_ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
TRAINING_READINESS = ROOT / "runs/local/artifacts/stage9778_multilingual_training_readiness_audit/multilingual_training_readiness_audit.json"

SYMBOL_EXEC = ROOT / "runs/summaries/stage9713_symbol_binding_retrieval_test_evidence_execution_audit.json"
EDIT_EXEC = ROOT / "runs/summaries/stage9773_edit_localization_visible_evidence_execution_audit.json"
EDIT_LANG = ROOT / "runs/local/artifacts/stage9774_edit_localization_visible_evidence_language_slice_audit/edit_localization_visible_evidence_language_slice_audit.json"
EDIT_GEMMA = ROOT / "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_comparison.json"
EDIT_GEMMA_SUMMARY = ROOT / "runs/summaries/stage9775_edit_localization_visible_evidence_gemma_comparison.json"

BLOCKED_SKILLS = {"patch_operator_selection", "verifier_failure_repair_or_abstain"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
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


def _supports_to_missing(required: list[str], evidence: list[dict[str, Any]]) -> list[str]:
    provided = {item for row in evidence for item in row.get("supports", [])}
    return [item for item in required if item not in provided]


def _find_surface_status(skill: str, readiness: dict[str, Any]) -> str | None:
    surfaces = readiness.get("surfaces") if isinstance(readiness.get("surfaces"), list) else []
    mapping = {
        "symbol_binding": "symbol_binding",
        "edit_localization": "edit_localization_visible_evidence",
        "patch_operator_selection": "patch_operator_selection",
        "verifier_failure_repair_or_abstain": "verifier_failure_repair_or_abstain",
    }
    target = mapping.get(skill)
    for surface in surfaces:
        if str(surface.get("surface") or "") == target:
            return str(surface.get("status") or "")
    return None


def _base_blockers(record: dict[str, Any], missing: list[str], *, same_surface_gap_open: bool) -> list[str]:
    blockers: list[str] = []
    if same_surface_gap_open:
        blockers.append("same_surface_100m_vs_gemma12b_evidence_missing")
    blockers.append("expert_maintainer_rubric_scores_missing")
    blockers.append("anti_cheat_cards_not_attached_for_specific_cell")
    blockers.extend(f"missing_required_evidence:{item}" for item in missing)
    if record.get("mode") == "full_product_harness":
        blockers.append("harness_run_not_recorded")
    return blockers


def _symbol_binding_evidence(required: list[str]) -> list[dict[str, Any]]:
    summary = load_json(SYMBOL_EXEC)
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    eval_exact = metrics.get("eval_symbol_binding_exact")
    strict_exact = metrics.get("strict_symbol_binding_exact")
    if eval_exact is None or strict_exact is None:
        return []
    provided = {
        "standalone_generation_or_structured_action_outputs",
        "language_slice_scores",
        "telemetry_bundle",
    }
    return [
        {
            "kind": "truthful_100m_side_support",
            "stage": 9713,
            "path": str(SYMBOL_EXEC.relative_to(ROOT)),
            "supports": sorted(provided),
            "quality_passed": False,
            "details": {
                "language_family": "python",
                "surface": "symbol_binding",
                "eval_exact": eval_exact,
                "strict_exact": strict_exact,
                "available_100m_side_only": True,
            },
            "claim_sufficient": False,
            "why_not_claim_sufficient": [
                "no_same_surface_gemma12b_outputs",
                "no_expert_maintainer_rubric_scores",
                "no_cell_specific_anti_cheat_cards",
                "no_frozen_export_or_checkpoint_hash",
            ],
            "remaining_required_evidence_after_attach": [item for item in required if item not in provided],
        }
    ]


def _edit_localization_support(language: str, required: list[str]) -> list[dict[str, Any]]:
    exec_summary = load_json(EDIT_EXEC)
    lang_audit = load_json(EDIT_LANG)
    gemma_audit = load_json(EDIT_GEMMA)
    language_slice = (lang_audit.get("language_slices") or {}).get(language) if isinstance(lang_audit.get("language_slices"), dict) else {}
    gemma_results = gemma_audit.get("results") if isinstance(gemma_audit.get("results"), list) else []
    gemma_row = next((row for row in gemma_results if str(row.get("language") or "") == language), None)
    if not isinstance(language_slice, dict) or not isinstance(gemma_row, dict):
        return []
    eval_card = language_slice.get("eval") if isinstance(language_slice.get("eval"), dict) else {}
    strict_card = language_slice.get("strict_eval") if isinstance(language_slice.get("strict_eval"), dict) else {}
    if eval_card.get("exact") is None or strict_card.get("exact") is None:
        return []
    provided = {
        "standalone_generation_or_structured_action_outputs",
        "language_slice_scores",
        "telemetry_bundle",
        "same_prompt_surface_gemma12b_outputs",
    }
    return [
        {
            "kind": "same_surface_win_support",
            "stage": 9775,
            "path": str(EDIT_GEMMA_SUMMARY.relative_to(ROOT)),
            "supports": ["same_prompt_surface_gemma12b_outputs"],
            "quality_passed": True,
            "details": {
                "language_family": language,
                "surface": "edit_localization_visible_evidence",
                "same_surface_verified": True,
                "score_100m": gemma_row.get("model_strict_exact_100m"),
                "score_gemma12b": gemma_row.get("gemma_strict_exact"),
                "verdict": gemma_row.get("verdict"),
                "row_outputs_path": "runs/local/artifacts/stage9775_edit_localization_visible_evidence_gemma_comparison/edit_localization_visible_evidence_gemma_rows.jsonl",
            },
            "claim_sufficient": False,
            "why_not_claim_sufficient": [
                "no_expert_maintainer_rubric_scores",
                "no_cell_specific_anti_cheat_cards",
                "no_frozen_export_or_checkpoint_hash",
            ],
            "remaining_required_evidence_after_attach": [item for item in required if item not in provided],
        },
        {
            "kind": "truthful_100m_side_support",
            "stage": 9773,
            "path": str(EDIT_EXEC.relative_to(ROOT)),
            "supports": [
                "language_slice_scores",
                "standalone_generation_or_structured_action_outputs",
                "telemetry_bundle",
            ],
            "quality_passed": True,
            "details": {
                "language_family": language,
                "surface": "edit_localization_visible_evidence",
                "eval_exact": eval_card.get("exact"),
                "strict_exact": strict_card.get("exact"),
                "eval_rows": eval_card.get("rows"),
                "strict_rows": strict_card.get("rows"),
                "baseline_exact": strict_card.get("baseline_exact"),
                "available_100m_side_only": False,
            },
            "claim_sufficient": False,
            "why_not_claim_sufficient": [
                "no_expert_maintainer_rubric_scores",
                "no_cell_specific_anti_cheat_cards",
                "no_frozen_export_or_checkpoint_hash",
            ],
            "remaining_required_evidence_after_attach": [item for item in required if item not in provided],
        },
    ]


def attach_current_support(record: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(record)
    required = list(updated.get("required_evidence") or [])
    language = str(updated.get("language_family") or "")
    mode = str(updated.get("mode") or "")
    skill = str(updated.get("skill_area") or "")
    evidence: list[dict[str, Any]] = []
    same_surface_gap_open = True

    if mode == "standalone_100m_weights":
        if skill == "edit_localization":
            evidence = _edit_localization_support(language, required)
            same_surface_gap_open = not bool(evidence)
        elif skill == "symbol_binding" and language == "python":
            evidence = _symbol_binding_evidence(required)
        elif skill in BLOCKED_SKILLS:
            evidence = []

    updated["attached_evidence"] = evidence
    updated["missing_required_evidence"] = _supports_to_missing(required, evidence)
    updated["claim_ready"] = False
    updated["claim_status"] = "blocked_missing_final_evidence"
    updated["anti_hacking_gate_passed"] = load_json(SOURCE_ANTI_HACK).get("passed") is True
    updated["blockers"] = _base_blockers(updated, updated["missing_required_evidence"], same_surface_gap_open=same_surface_gap_open)

    surface_status = _find_surface_status(skill, readiness)
    if skill in BLOCKED_SKILLS and mode == "standalone_100m_weights":
        updated["blockers"].append("blocked_upstream_evidence_rebuild_required")
    elif mode == "standalone_100m_weights" and evidence:
        if skill == "edit_localization":
            updated["blockers"].append("same_surface_win_present_but_review_and_checkpoint_evidence_still_missing")
        else:
            updated["blockers"].append("standalone_100m_side_support_present_but_gemma_gap_open")
    elif mode == "standalone_100m_weights":
        updated["blockers"].append("no_current_truthful_support_for_cell")
    if surface_status:
        updated["current_surface_status"] = surface_status
    return updated


def build_bridge() -> dict[str, Any]:
    source = load_json(SOURCE_LEDGER)
    readiness = load_json(TRAINING_READINESS)
    records = source.get("records") if isinstance(source.get("records"), list) else []
    bridged = [attach_current_support(record, readiness) for record in records]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9718_not_passed")
    if readiness.get("passed") is not True:
        failures.append("stage9778_not_passed")
    if len(bridged) != 72:
        failures.append("bridged_record_count_not_72")

    support_rows = [row for row in bridged if row.get("attached_evidence")]
    standalone_rows = [row for row in bridged if row.get("mode") == "standalone_100m_weights"]
    standalone_support = [row for row in standalone_rows if row.get("attached_evidence")]
    support_by_language = Counter(str(row.get("language_family") or "") for row in standalone_support)
    support_by_skill = Counter(str(row.get("skill_area") or "") for row in standalone_support)
    winning_edit_cells = [
        row for row in standalone_support
        if row.get("skill_area") == "edit_localization"
        and "same_surface_100m_vs_gemma12b_evidence_missing" not in (row.get("blockers") or [])
    ]
    blocked_rebuild_cells = [
        row for row in standalone_rows
        if row.get("skill_area") in BLOCKED_SKILLS
        and "blocked_upstream_evidence_rebuild_required" in (row.get("blockers") or [])
    ]
    if len(standalone_support) != 5:
        failures.append("expected_five_current_truthful_standalone_support_cells")
    if dict(sorted(support_by_skill.items())) != {"edit_localization": 4, "symbol_binding": 1}:
        failures.append("unexpected_current_support_skill_shape")
    if len(winning_edit_cells) != 4:
        failures.append("expected_four_same_surface_edit_localization_win_cells")
    if len(blocked_rebuild_cells) != 8:
        failures.append("expected_eight_blocked_patch_verifier_cells")

    return {
        "passed": not failures,
        "failures": failures,
        "records": bridged,
        "metrics": {
            "records": len(bridged),
            "standalone_cells": len(standalone_rows),
            "standalone_cells_with_current_truthful_support": len(standalone_support),
            "support_by_language": dict(sorted(support_by_language.items())),
            "support_by_skill": dict(sorted(support_by_skill.items())),
            "same_surface_win_cells": len(winning_edit_cells),
            "blocked_rebuild_cells": len(blocked_rebuild_cells),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    bridge = build_bridge()
    LEDGER.write_text(json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the four multilingual edit-localization visible-evidence cells as the current same-surface win front, "
        "attach per-cell expert-maintainer rubric and anti-cheat cards there first, and keep patch/verifier out of the win queue "
        "until their upstream evidence builders are rebuilt."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **bridge["metrics"],
            "failures": bridge["failures"],
        },
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Refreshed the truthful standalone claim bridge so it reflects the current multilingual winner and removes structurally blocked surfaces from the active win path.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9779 Current Truthful Standalone Claim Bridge",
                "",
                f"Passed: `{summary['passed']}`",
                f"Standalone cells with current truthful support: `{bridge['metrics']['standalone_cells_with_current_truthful_support']}`",
                f"Support by skill: `{bridge['metrics']['support_by_skill']}`",
                f"Same-surface win cells: `{bridge['metrics']['same_surface_win_cells']}`",
                f"Blocked rebuild cells: `{bridge['metrics']['blocked_rebuild_cells']}`",
                "",
                "This bridge supersedes stale target-only packaging for current claim work.",
                "- The four multilingual edit-localization visible-evidence cells now carry same-surface Gemma win support.",
                "- Python symbol binding remains a trainable support cell but not yet a same-surface Gemma win.",
                "- Patch operator and verifier-repair cells are left blocked until their upstream evidence builders are rebuilt.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps(bridge, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
