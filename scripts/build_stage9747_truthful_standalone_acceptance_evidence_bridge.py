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
STAGE = 9747
NAME = "stage9747_truthful_standalone_acceptance_evidence_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "truthful_standalone_acceptance_evidence_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUTHFUL_STANDALONE_ACCEPTANCE_EVIDENCE_BRIDGE_STAGE9747.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SOURCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
SOURCE_ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"

SYMBOL_SUMMARY = ROOT / "runs/summaries/stage9721_symbol_binding_standalone_comparison_package.json"
SYMBOL_PACKETS = ROOT / "runs/local/artifacts/stage9721_symbol_binding_standalone_comparison_package/symbol_binding_standalone_surface_packets.json"

VERIFIER_EXEC_SUMMARY = ROOT / "runs/summaries/stage9729_multilingual_structured_execution_support_ledger.json"
VERIFIER_LANG_AUDIT = ROOT / "runs/local/artifacts/stage9730_multilingual_structured_execution_language_slice_audit/multilingual_structured_execution_language_slice_audit.json"

PATCH_EXEC_SUMMARY = ROOT / "runs/summaries/stage9736_multilingual_patch_operator_label_aligned_execution_audit.json"
PATCH_LANG_AUDIT = ROOT / "runs/local/artifacts/stage9737_patch_operator_label_aligned_language_slice_audit/patch_operator_label_aligned_language_slice_audit.json"

EDIT_EXEC_SUMMARY = ROOT / "runs/summaries/stage9744_multilingual_edit_localization_target_only_execution_audit.json"
EDIT_LANG_AUDIT = ROOT / "runs/local/artifacts/stage9745_edit_localization_target_only_language_slice_audit/edit_localization_target_only_language_slice_audit.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


def load_json(path: Path) -> Any:
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


def _supports_to_missing(required: list[str], evidence: list[dict[str, Any]]) -> list[str]:
    provided = {item for row in evidence for item in row.get("supports", [])}
    return [item for item in required if item not in provided]


def _base_blockers(record: dict[str, Any], missing: list[str]) -> list[str]:
    blockers = [
        "same_surface_100m_vs_gemma12b_evidence_missing",
        "expert_maintainer_rubric_scores_missing",
        "anti_cheat_cards_not_attached_for_specific_cell",
    ]
    blockers.extend(f"missing_required_evidence:{item}" for item in missing)
    if record.get("mode") == "full_product_harness":
        blockers.append("harness_run_not_recorded")
    return blockers


def _symbol_binding_evidence(language: str, required: list[str]) -> list[dict[str, Any]]:
    packets = load_json(SYMBOL_PACKETS)
    packet = packets.get(language) if isinstance(packets, dict) else {}
    if not isinstance(packet, dict):
        return []
    if packet.get("logit_rows", 0) <= 0 or packet.get("slice_exact") is None:
        return []
    return [{
        "kind": "truthful_100m_side_support",
        "stage": 9721,
        "path": str(SYMBOL_SUMMARY.relative_to(ROOT)),
        "supports": [
            "standalone_generation_or_structured_action_outputs",
            "language_slice_scores",
            "telemetry_bundle",
        ],
        "quality_passed": False,
        "details": {
            "language_family": language,
            "surface_rows": packet.get("rows"),
            "logit_rows": packet.get("logit_rows"),
            "eval_exact": packet.get("slice_exact"),
            "strict_exact": packet.get("slice_exact"),
            "available_100m_side_only": True,
        },
        "claim_sufficient": False,
        "why_not_claim_sufficient": [
            "no_same_surface_gemma12b_outputs",
            "no_expert_maintainer_rubric_scores",
            "no_cell_specific_anti_cheat_cards",
            "no_frozen_export_or_checkpoint_hash",
        ],
        "remaining_required_evidence_after_attach": [item for item in required if item not in {
            "standalone_generation_or_structured_action_outputs",
            "language_slice_scores",
            "telemetry_bundle",
        }],
    }]


def _surface_language_slice(audit: dict[str, Any], surface: str, language: str) -> dict[str, Any]:
    if surface == "verifier_repair":
        surface_audits = audit.get("surface_audits") if isinstance(audit.get("surface_audits"), dict) else {}
        surface_card = surface_audits.get(surface) if isinstance(surface_audits.get(surface), dict) else {}
        slices = surface_card.get("language_slices") if isinstance(surface_card.get("language_slices"), dict) else {}
        return slices.get(language) if isinstance(slices.get(language), dict) else {}
    slices = audit.get("language_slices") if isinstance(audit.get("language_slices"), dict) else {}
    return slices.get(language) if isinstance(slices.get(language), dict) else {}


def _surface_support_evidence(
    *,
    language: str,
    required: list[str],
    stage: int,
    summary_path: Path,
    language_audit: dict[str, Any],
    surface: str,
    quality_passed: bool,
) -> list[dict[str, Any]]:
    language_slice = _surface_language_slice(language_audit, surface, language)
    if not language_slice:
        return []
    eval_card = language_slice.get("eval") if isinstance(language_slice.get("eval"), dict) else {}
    strict_card = language_slice.get("strict_eval") if isinstance(language_slice.get("strict_eval"), dict) else {}
    eval_exact = eval_card.get("exact")
    strict_exact = strict_card.get("exact")
    if eval_exact is None or strict_exact is None:
        return []
    return [{
        "kind": "truthful_100m_side_support",
        "stage": stage,
        "path": str(summary_path.relative_to(ROOT)),
        "supports": [
            "standalone_generation_or_structured_action_outputs",
            "language_slice_scores",
            "telemetry_bundle",
        ],
        "quality_passed": quality_passed,
        "details": {
            "language_family": language,
            "surface": surface,
            "eval_exact": eval_exact,
            "strict_exact": strict_exact,
            "eval_rows": eval_card.get("rows"),
            "strict_rows": strict_card.get("rows"),
            "available_100m_side_only": True,
        },
        "claim_sufficient": False,
        "why_not_claim_sufficient": [
            "no_same_surface_gemma12b_outputs",
            "no_expert_maintainer_rubric_scores",
            "no_cell_specific_anti_cheat_cards",
            "no_frozen_export_or_checkpoint_hash",
        ],
        "remaining_required_evidence_after_attach": [item for item in required if item not in {
            "standalone_generation_or_structured_action_outputs",
            "language_slice_scores",
            "telemetry_bundle",
        }],
    }]


def attach_truthful_support(record: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(record)
    required = list(updated.get("required_evidence") or [])
    language = str(updated.get("language_family") or "")
    mode = str(updated.get("mode") or "")
    skill = str(updated.get("skill_area") or "")
    evidence: list[dict[str, Any]] = []
    if mode == "standalone_100m_weights":
        if skill == "symbol_binding":
            evidence = _symbol_binding_evidence(language, required)
        elif skill == "edit_localization":
            evidence = _surface_support_evidence(
                language=language,
                required=required,
                stage=9744,
                summary_path=EDIT_EXEC_SUMMARY,
                language_audit=load_json(EDIT_LANG_AUDIT),
                surface="edit_localization",
                quality_passed=True,
            )
        elif skill == "patch_operator_selection":
            evidence = _surface_support_evidence(
                language=language,
                required=required,
                stage=9736,
                summary_path=PATCH_EXEC_SUMMARY,
                language_audit=load_json(PATCH_LANG_AUDIT),
                surface="patch_operator",
                quality_passed=True,
            )
        elif skill == "verifier_failure_repair_or_abstain":
            evidence = _surface_support_evidence(
                language=language,
                required=required,
                stage=9729,
                summary_path=VERIFIER_EXEC_SUMMARY,
                language_audit=load_json(VERIFIER_LANG_AUDIT),
                surface="verifier_repair",
                quality_passed=True,
            )
    updated["attached_evidence"] = evidence
    updated["missing_required_evidence"] = _supports_to_missing(required, evidence)
    updated["claim_ready"] = False
    updated["claim_status"] = "blocked_missing_final_evidence"
    updated["anti_hacking_gate_passed"] = load_json(SOURCE_ANTI_HACK).get("passed") is True
    updated["blockers"] = _base_blockers(updated, updated["missing_required_evidence"])
    if mode == "standalone_100m_weights":
        if evidence:
            updated["blockers"].append("standalone_100m_side_support_present_but_gemma_gap_open")
        else:
            updated["blockers"].append("no_truthful_100m_side_support_for_cell")
    return updated


def build_bridge() -> dict[str, Any]:
    source = load_json(SOURCE_LEDGER)
    records = source.get("records") if isinstance(source.get("records"), list) else []
    bridged = [attach_truthful_support(record) for record in records]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9718_not_passed")
    if len(bridged) != 72:
        failures.append("bridged_record_count_not_72")
    claim_ready = [row for row in bridged if row.get("claim_ready") is True]
    if claim_ready:
        failures.append("unexpected_claim_ready_cells")
    support_rows = [row for row in bridged if row.get("attached_evidence")]
    standalone_rows = [row for row in bridged if row.get("mode") == "standalone_100m_weights"]
    harness_rows = [row for row in bridged if row.get("mode") == "full_product_harness"]
    standalone_support = [row for row in standalone_rows if row.get("attached_evidence")]
    harness_support = [row for row in harness_rows if row.get("attached_evidence")]
    support_by_language = Counter(str(row.get("language_family") or "") for row in support_rows)
    support_by_skill = Counter(str(row.get("skill_area") or "") for row in support_rows)
    unsupported_symbol_binding_languages = sorted(
        row["language_family"]
        for row in bridged
        if row.get("mode") == "standalone_100m_weights"
        and row.get("skill_area") == "symbol_binding"
        and not row.get("attached_evidence")
    )
    if len(standalone_support) != 13:
        failures.append("expected_thirteen_truthful_standalone_support_cells")
    if harness_support:
        failures.append("unexpected_full_product_harness_support")
    if unsupported_symbol_binding_languages != ["c_cpp", "rust", "web_js_ts_html"]:
        failures.append("unexpected_symbol_binding_language_support_shape")
    return {
        "passed": not failures,
        "failures": failures,
        "records": bridged,
        "metrics": {
            "records": len(bridged),
            "claim_ready_cells": 0,
            "blocked_cells": len(bridged),
            "standalone_cells": len(standalone_rows),
            "full_product_harness_cells": len(harness_rows),
            "standalone_cells_with_truthful_100m_side_support": len(standalone_support),
            "full_product_harness_cells_with_truthful_support": len(harness_support),
            "support_by_language": dict(sorted(support_by_language.items())),
            "support_by_skill": dict(sorted(support_by_skill.items())),
            "unsupported_symbol_binding_languages": unsupported_symbol_binding_languages,
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
        "Use the 13 truthfully supported standalone cells as the highest-leverage same-surface Gemma comparison queue, "
        "while leaving all full-product harness cells blocked until harness execution is explicitly opened and recorded."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **bridge["metrics"]},
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Built a truth-corrected derived acceptance ledger that replaces overstated standalone support with the best real multilingual 100M-side evidence currently available.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9747 Truthful Standalone Acceptance Evidence Bridge",
        "",
        f"Passed: `{summary['passed']}`",
        f"Standalone truthful support cells: `{summary['metrics']['standalone_cells_with_truthful_100m_side_support']}`",
        f"Support by language: `{summary['metrics']['support_by_language']}`",
        f"Support by skill: `{summary['metrics']['support_by_skill']}`",
        f"Unsupported symbol-binding languages: `{summary['metrics']['unsupported_symbol_binding_languages']}`",
        "",
        "This stage corrects the standalone-side acceptance picture: only Python currently has executed symbol-binding support, while edit-localization, patch-operator selection, and verifier-failure repair-or-abstain now have real multilingual standalone support. No cell becomes claim-ready because Gemma, expert-rubric, anti-cheat attachment, frozen export, and harness evidence are still missing.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "standalone_cells_with_truthful_100m_side_support": summary["metrics"]["standalone_cells_with_truthful_100m_side_support"],
        "full_product_harness_cells_with_truthful_support": summary["metrics"]["full_product_harness_cells_with_truthful_support"],
        "unsupported_symbol_binding_languages": summary["metrics"]["unsupported_symbol_binding_languages"],
        "failures": bridge["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if bridge["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
