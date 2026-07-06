#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9045
NAME = "stage9045_mining_training_gap_status_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GAP_DOC = ROOT / "docs/MINING_AND_TRAINING_RECOVERY_GAP_STATUS.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MINING_TRAINING_GAP_STATUS_REFRESH_STAGE9045.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "mining_training_gap_status_refresh.json"

RECOVERED_CONTROL_COMPONENTS = [
    "stage_registry",
    "authority_flags",
    "safe_cleanup",
    "loss_mask_card",
    "dataset_judge_ranker",
    "curriculum_compiler",
    "shortcut_counterfactual_audit",
    "gate_status_contract",
    "telemetry_contract",
    "semantic_intent_surface_contract",
    "domain_twin_operator_bridge",
    "long_context_transition_pipeline",
]
RECOVERED_OBJECTIVE_FAMILIES = [
    "intent_to_build_strategy_contract",
    "repo_state_graph_v1_contract",
    "symbol_binding_candidates",
    "edit_localization_candidates",
    "patch_operator_candidates",
    "verifier_repair_candidates",
    "bounded_decoder_arguments_contract",
    "bounded_decoder_ce_candidate_contract",
    "output_repair_denoise_controls",
    "verified_transition_record_v1",
]
REMAINING_BEFORE_BROAD_MINING = [
    "active_source_ticket_for_arxiv_or_repository_library_reads",
    "metadata_only_domain_graph_manifest_design",
    "repo_twin_memory_manifest_design",
    "paper_twin_memory_manifest_design",
    "semantic_presentation_user_intent_shortcut_audit_for_real_rows",
    "operator_detail_metadata_patch_validation_stage9040",
    "source_body_ticket_for_any_source_backed_row_materialization",
    "row_body_ticket_for_any_dataset_record_read",
    "compiler_route_card_for_each_real_manifest",
    "full_gate_status_materialization_for_real_rows",
    "training_authorization_review_after_manifest_audits",
]
BLOCKED_NOW = [
    "broad_arxiv_mining",
    "repository_library_scan",
    "dataset_row_body_read",
    "repository_source_body_read",
    "train_100m_model",
    "run_native_probe",
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime_execution",
    "gemma_or_harness_scoring",
    "hf_upload",
    "write_arxiv",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_doc() -> str:
    lines = [
        "# Mining And Training Recovery Gap Status",
        "",
        "Current frontier: `Stage9045`.",
        "",
        "## Direct Answer",
        "",
        "Broad mining and training are still closed. The control plane, compiler scaffolds, semantic/user-intent contract, domain/twin/operator bridge, and long-context pipeline guards are recovered enough to design future real-manifest tickets, but not enough to scan `/arxiv` or train.",
        "",
        "## Recovered Control Components",
        "",
        *[f"- `{item}`" for item in RECOVERED_CONTROL_COMPONENTS],
        "",
        "## Recovered Objective Families Or Contracts",
        "",
        *[f"- `{item}`" for item in RECOVERED_OBJECTIVE_FAMILIES],
        "",
        "## Still Required Before Broad Mining",
        "",
        *[f"- `{item}`" for item in REMAINING_BEFORE_BROAD_MINING],
        "",
        "## Blocked Now",
        "",
        *[f"- `{item}`" for item in BLOCKED_NOW],
        "",
        "## Current Safe Work",
        "",
        "Safe work remains contract-only, synthetic-fixture, or repo-local audit-only. Future real-row work must start with explicit active source tickets, then route-card/schema/header audits, then judge/ranker/shortcut/counterfactual/loss-mask audits before any model gradients.",
        "",
        "## Rule",
        "",
        "No `/arxiv` row or repository body reaches a compiler or model until it has an explicit route card, authority card, source/row-body ticket, gate status, loss mask, shortcut audit, duplicate check, budget/evidence status, and telemetry contract.",
        "",
    ]
    return "\n".join(lines)


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "registry_frontier_at_least_9044": int((registry.get("metrics") or {}).get("latest_stage", 0)) >= 9044,
        "recovered_control_components_recorded": len(RECOVERED_CONTROL_COMPONENTS) >= 12,
        "objective_families_recorded": len(RECOVERED_OBJECTIVE_FAMILIES) >= 10,
        "remaining_blockers_recorded": len(REMAINING_BEFORE_BROAD_MINING) >= 11,
        "blocked_now_recorded": len(BLOCKED_NOW) >= 12,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "MINING_TRAINING_GAP_STATUS_REFRESH_NO_EXECUTION",
        "recovered_control_components": RECOVERED_CONTROL_COMPONENTS,
        "recovered_objective_families": RECOVERED_OBJECTIVE_FAMILIES,
        "remaining_before_broad_mining": REMAINING_BEFORE_BROAD_MINING,
        "blocked_now": BLOCKED_NOW,
        "checks": checks,
        "metrics": {
            "recovered_control_components": len(RECOVERED_CONTROL_COMPONENTS),
            "recovered_objective_families": len(RECOVERED_OBJECTIVE_FAMILIES),
            "remaining_before_broad_mining": len(REMAINING_BEFORE_BROAD_MINING),
            "blocked_now": len(BLOCKED_NOW),
            "status_refresh_only": True,
            "broad_mining_authorized": False,
            "repository_library_scan_authorized_now": False,
            "arxiv_scan_authorized_now": False,
            "dataset_row_body_read_authorized_now": False,
            "repository_source_body_read_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "hf_upload_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Refresh the mining/training gap status to the current recovery frontier while keeping mining, training, execution, /arxiv IO, HF upload, and body reads closed.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "broad_mining_authorized",
        "repository_library_scan_authorized_now",
        "arxiv_scan_authorized_now",
        "dataset_row_body_read_authorized_now",
        "repository_source_body_read_authorized_now",
        "training_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "hf_upload_authorized_now",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    GAP_DOC.write_text(build_doc(), encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"gap_status_refresh": str(CARD.relative_to(ROOT)), "gap_doc": str(GAP_DOC.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Design metadata-only DomainGraph/Twin manifests or operator-detail metadata patches; do not start broad mining/training until explicit source, route-card, judge, shortcut, loss-mask, and telemetry gates pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9045 Mining/Training Gap Status Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage refreshes `docs/MINING_AND_TRAINING_RECOVERY_GAP_STATUS.md` to the current recovery frontier.",
        "No mining, training, model execution, body reads, `/arxiv` writes, or Hugging Face uploads are authorized.",
        "",
        f"Recovered control components: `{summary['metrics']['recovered_control_components']}`",
        f"Remaining blockers before broad mining: `{summary['metrics']['remaining_before_broad_mining']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
