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
STAGE = 9075
NAME = "stage9075_current_frontier_reconciliation_after_trainer_docs_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9071 = ROOT / "runs/summaries/stage9071_current_frontier_reconciliation_after_long_context_guards.json"
SOURCE_9072 = ROOT / "runs/summaries/stage9072_trainer_dry_run_documentation_refresh.json"
SOURCE_9073 = ROOT / "runs/summaries/stage9073_central_graph_gap_walk_after_trainer_docs.json"
SOURCE_9074 = ROOT / "runs/summaries/stage9074_trainer_docs_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_TRAINER_DOCS_GRAPH_STAGE9075.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_trainer_docs_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9071_current_frontier_reconciled_after_long_context_guards",
    "stage9072_trainer_dry_run_documentation_contract",
    "stage9073_stage9072_graph_gap_identified",
    "stage9074_trainer_docs_contract_attached_to_graph",
    "compound_only_long_context_candidate_mode",
]

NEXT_SAFE_BRANCHES = [
    "future source/output ticket design without row-body reads",
    "no-data route-card materialization audit instance design",
    "trainer dry-run input completeness checklist refresh",
    "central graph gap walk for source-ticket and route-card blockers",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9071 = load_json(SOURCE_9071)
    s9072 = load_json(SOURCE_9072)
    s9073 = load_json(SOURCE_9073)
    s9074 = load_json(SOURCE_9074)
    checks = {
        "source_stage9071_passed": s9071.get("passed") is True,
        "source_stage9072_passed": s9072.get("passed") is True,
        "source_stage9073_passed": s9073.get("passed") is True,
        "source_stage9074_passed": s9074.get("passed") is True,
        "stage9074_added_graph_nodes": (s9074.get("metrics") or {}).get("added_nodes", 0) >= 7,
        "stage9074_added_graph_edges": (s9074.get("metrics") or {}).get("added_edges", 0) >= 13,
        "stage9074_training_closed": (s9074.get("metrics") or {}).get("training_ready") is False,
        "stage9074_trainer_not_invoked": (s9074.get("metrics") or {}).get("trainer_invoked") is False,
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 5,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9074": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9074,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_TRAINER_DOCS_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9074_added_nodes": (s9074.get("metrics") or {}).get("added_nodes", 0),
            "stage9074_added_edges": (s9074.get("metrics") or {}).get("added_edges", 0),
            "trainer_invoked": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "candidate_rows_materialized": 0,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after attaching recovered trainer documentation controls to the graph. The control plane is clearer, but real source/output tickets, route-card materialization, trainer dry run, model forward, decoder CE, denoise CE, runtime, mining, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9074, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "trainer_invoked",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after trainer docs graph attachment failed.",
        "next_best_step": "Design a future source/output ticket without row-body reads, or perform a no-data route-card materialization audit instance design.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9075 Current Frontier After Trainer Docs Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9074. The trainer documentation contract is now represented in the central graph, but all execution and data paths remain closed.",
        "",
        f"Stage9074 added nodes: `{card['metrics']['stage9074_added_nodes']}`",
        f"Stage9074 added edges: `{card['metrics']['stage9074_added_edges']}`",
        "",
        "Next safe branches:",
        "",
        *[f"- {branch}" for branch in NEXT_SAFE_BRANCHES],
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
    marker = "## Stage9075 Current Frontier After Trainer Docs Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9075 reconciles the current frontier after Stage9074. Trainer dry-run documentation controls are now attached to the graph; the next safe branches remain future source/output ticket design or route-card audit design.",
            "",
            "Trainer execution, row loading, candidate mining, model forward, decoder CE, denoise CE, runtime, /arxiv compiler IO, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
