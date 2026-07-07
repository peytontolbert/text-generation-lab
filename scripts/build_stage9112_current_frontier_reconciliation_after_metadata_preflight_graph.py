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
STAGE = 9112
NAME = "stage9112_current_frontier_reconciliation_after_metadata_preflight_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9109 = ROOT / "runs/summaries/stage9109_metadata_only_real_data_availability_preflight_design.json"
SOURCE_9110 = ROOT / "runs/summaries/stage9110_metadata_only_real_data_availability_preflight_audit.json"
SOURCE_9111 = ROOT / "runs/summaries/stage9111_metadata_only_preflight_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_METADATA_PREFLIGHT_GRAPH_STAGE9112.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_metadata_preflight_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9109_metadata_only_real_data_availability_preflight_design",
    "stage9110_metadata_only_preflight_negative_case_audit",
    "stage9111_metadata_only_preflight_graph_attachment",
    "graph_gate_metadata_preflight_blocks_arxiv_access",
    "graph_gate_metadata_preflight_blocks_row_source_reads",
    "graph_gate_metadata_preflight_blocks_arxiv_writes_cleanup",
    "graph_gate_metadata_preflight_requires_source_output_ticket_for_body_reads",
    "graph_gate_metadata_preflight_requires_route_card_ticket_for_compiler_handoff",
]

REMAINING_BLOCKERS = [
    "metadata_only_arxiv_inventory_ticket_missing",
    "real_source_output_ticket_not_instantiated",
    "route_cards_not_materialized",
    "route_to_loss_translation_not_materialized",
    "trainer_contract_only_artifacts_not_materialized",
    "final_pre_execution_audit_missing",
    "one_run_training_ticket_missing",
]

NEXT_SAFE_BRANCHES = [
    "metadata-only real data inventory ticket design without row/source reads",
    "real source/output ticket schema refresh without instantiation",
    "route-card materialization design without compiler handoff",
    "central graph gap walk after metadata preflight reconciliation",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9109 = load_json(SOURCE_9109)
    s9110 = load_json(SOURCE_9110)
    s9111 = load_json(SOURCE_9111)
    checks = {
        "source_stage9109_passed": s9109.get("passed") is True,
        "source_stage9110_passed": s9110.get("passed") is True,
        "source_stage9111_passed": s9111.get("passed") is True,
        "stage9110_negative_cases_rejected": (s9110.get("metrics") or {}).get("negative_cases_rejected") == (s9110.get("metrics") or {}).get("negative_cases"),
        "stage9111_added_graph_nodes": (s9111.get("metrics") or {}).get("added_nodes", 0) >= 7,
        "stage9111_added_graph_edges": (s9111.get("metrics") or {}).get("added_edges", 0) >= 24,
        "stage9111_authority_rows_zero": (s9111.get("metrics") or {}).get("authority_rows") == 0,
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 8,
        "remaining_blockers_recorded": len(REMAINING_BLOCKERS) >= 7,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9111": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9111,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_METADATA_PREFLIGHT_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "remaining_blockers": REMAINING_BLOCKERS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "remaining_blockers": len(REMAINING_BLOCKERS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9111_added_nodes": (s9111.get("metrics") or {}).get("added_nodes", 0),
            "stage9111_added_edges": (s9111.get("metrics") or {}).get("added_edges", 0),
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "model_input_rows_now": 0,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after metadata-only preflight graph attachment. The next real-data step is a future metadata-only inventory ticket; /arxiv access/stat, row reads, source-body reads, writes, mining, compiler handoff, trainer invocation, model forward, decoder CE, denoise CE, runtime, uploads, cleanup, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9111, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("model_input_rows_now") != 0:
        failures.append("model_input_rows_now")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Current frontier reconciliation after metadata preflight graph failed.",
        "next_best_step": "Design a metadata-only real data inventory ticket; do not access /arxiv until that ticket is audited.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9112 Current Frontier After Metadata Preflight Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Metadata-only preflight design, audit, and graph controls are reconciled. Real data inventory is still blocked until a future metadata-only inventory ticket is designed and audited.",
        "",
        "Remaining blockers:",
        "",
        *[f"- {item}" for item in REMAINING_BLOCKERS],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9112 Current Frontier After Metadata Preflight Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9112 reconciles Stage9109-9111 into the active frontier. Metadata-only real-data preflight controls are now graph-visible, but actual `/arxiv` metadata inventory still requires a future audited ticket. Row reads, source-body reads, writes, mining, route-card materialization, route-to-loss translation, compiler handoff, trainer invocation, model forward, decoder CE, denoise CE, runtime, uploads, cleanup, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
