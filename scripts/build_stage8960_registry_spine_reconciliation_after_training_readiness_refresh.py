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
STAGE = 8960
NAME = "stage8960_registry_spine_reconciliation_after_training_readiness_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_TRAINING_READINESS_REFRESH_STAGE8960.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "registry_spine_reconciliation_after_training_readiness_refresh.json"

SOURCE_SUMMARIES = {
    8953: "stage8953_training_readiness_matrix_refresh_after_converter_contracts",
    8954: "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh",
    8955: "stage8955_bounded_decoder_no_execution_telemetry_gate",
    8956: "stage8956_bounded_decoder_future_one_run_authorization_schema",
    8957: "stage8957_no_mining_compiler_readiness_refresh_after_decoder_gates",
    8958: "stage8958_real_manifest_audit_only_route_card_readiness",
    8959: "stage8959_training_readiness_blocker_matrix_refresh",
}

GRAPH_ATTACHMENTS = [
    {
        "node_id": "control:converter_contract_chain",
        "kind": "control_gate",
        "status": "no_execution_recovered",
        "evidence_stage": 8953,
    },
    {
        "node_id": "objective:bounded_decoder_ce",
        "kind": "objective_gate",
        "status": "trainer_loss_mask_telemetry_recovered_but_execution_closed",
        "evidence_stages": [8954, 8955, 8956],
    },
    {
        "node_id": "support_module:no_mining_curriculum_compiler",
        "kind": "compiler",
        "status": "synthetic_and_audit_only_recovered",
        "evidence_stage": 8957,
    },
    {
        "node_id": "support_module:real_manifest_route_cards",
        "kind": "compiler_gate",
        "status": "explicit_repo_local_manifest_audit_only_recovered",
        "evidence_stage": 8958,
    },
    {
        "node_id": "training:readiness_blocker_matrix",
        "kind": "readiness_gate",
        "status": "training_hard_blocked",
        "evidence_stage": 8959,
    },
]

CURRENT_BLOCKED_AUTHORITY = [
    "model_execution",
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime",
    "source_body_emission",
    "gemma",
    "harness",
    "scoring",
    "controller_merge",
    "promotion",
    "data_mining",
    "arxiv_compiler_io",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "next_best_step": summary.get("next_best_step"),
            "metrics": summary.get("metrics") or {},
        }
    stage8959_metrics = sources["8959"]["metrics"]
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "graph_attachments_recorded": len(GRAPH_ATTACHMENTS) >= 5,
        "blocked_authority_recorded": len(CURRENT_BLOCKED_AUTHORITY) >= 12,
        "stage8959_training_ready_false": stage8959_metrics.get("training_ready") is False,
        "stage8959_training_blockers_present": int(stage8959_metrics.get("training_blockers", 0) or 0) >= 8,
        "stage8959_ready_no_execution_components_present": int(stage8959_metrics.get("ready_no_execution_components", 0) or 0) >= 16,
        "registry_frontier_stage8959": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8959,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_SPINE_RECONCILED_AFTER_TRAINING_READINESS_REFRESH",
        "source_status": sources,
        "graph_attachments": GRAPH_ATTACHMENTS,
        "current_blocked_authority": CURRENT_BLOCKED_AUTHORITY,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "graph_attachments": len(GRAPH_ATTACHMENTS),
            "blocked_authority_count": len(CURRENT_BLOCKED_AUTHORITY),
            "ready_no_execution_components": int(stage8959_metrics.get("ready_no_execution_components", 0) or 0),
            "training_blockers": int(stage8959_metrics.get("training_blockers", 0) or 0),
            "training_ready": False,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Registry/spine reconciliation after Stage8959 is current: the recovered pipeline has no-execution contracts for converter, bounded decoder CE, telemetry, compiler, manifest route cards, and blocker matrix. Training remains hard-blocked.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8959, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["training_ready", "actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
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
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Choose deliberately: continue no-execution recovery, audit existing repo-local manifests, or explicitly request a future one-run bounded probe ticket. Do not train or mine directly.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8960 Registry/Spine Reconciliation After Training Readiness Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage reconciles the current no-execution recovery chain into the central research spine.",
        "",
        f"Graph attachments: `{card['metrics']['graph_attachments']}`",
        f"No-execution ready components: `{card['metrics']['ready_no_execution_components']}`",
        f"Training blockers: `{card['metrics']['training_blockers']}`",
        f"Training ready: `{card['metrics']['training_ready']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
        "",
    ]), encoding="utf-8")
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8960 Registry/Spine Reconciliation After Training Readiness Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8960 reconciles Stage8953-8959 into the central research spine: converter contracts, bounded decoder trainer/loss-mask readiness, telemetry gates, inactive one-run schema, no-mining compiler readiness, real-manifest audit-only route cards, and training blocker matrix are current.",
            "",
            "Training remains hard-blocked. No model execution, mining, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
