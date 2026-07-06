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
STAGE = 9028
NAME = "stage9028_operator_inventory_recovery_bridge_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MISSING_STAGE1239 = ROOT / "runs/summaries/stage1239_operator_spec_pack.json"
SOURCE_8718_SUMMARY = ROOT / "runs/summaries/stage8718_operator_codelength_interface_readiness.json"
SOURCE_8718_INVENTORY = ROOT / "runs/local/artifacts/stage8718_operator_codelength_interface_readiness/operator_inventory.json"
SOURCE_8719_SUMMARY = ROOT / "runs/summaries/stage8719_operator_codelength_interface_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OPERATOR_INVENTORY_RECOVERY_BRIDGE_AUDIT_STAGE9028.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "operator_inventory_recovery_bridge_audit.json"

REQUIRED_RECOVERED_CATEGORIES = [
    "instruction_intent",
    "software_grounding",
    "relationship_graph",
    "retrieval_context",
    "planning",
    "synthesis_transform",
    "validation",
    "debug_repair",
    "governance",
    "probabilistic_compression",
    "candidate_search",
    "memory_learning",
    "semantic_verification",
    "environment_tooling",
    "version_control_collaboration",
]

REQUIRED_GAP_OPERATORS = [
    "CHOICE_PROBABILITY_ESTIMATOR",
    "TARGET_CODELENGTH_SCORER",
    "COMPRESSION_GAIN_TRACKER",
    "CANDIDATE_ENUMERATOR",
    "CANDIDATE_EQUIVALENCE_CHECKER",
    "REPO_FACT_STORE",
    "SEMANTIC_EQUIVALENCE_CHECKER",
    "DEPENDENCY_RESOLVER",
    "DIRTY_WORKTREE_AUDITOR",
    "HANDOFF_SUMMARY_BUILDER",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    s8718 = load_json(SOURCE_8718_SUMMARY)
    inv = load_json(SOURCE_8718_INVENTORY)
    s8719 = load_json(SOURCE_8719_SUMMARY)
    categories = set((inv.get("categories") or {}).keys())
    operators = {row.get("operator_id") for row in inv.get("operators", []) if isinstance(row, dict)}
    missing_categories = [cat for cat in REQUIRED_RECOVERED_CATEGORIES if cat not in categories]
    missing_operators = [op for op in REQUIRED_GAP_OPERATORS if op not in operators]
    checks = {
        "stage1239_missing_recorded": not MISSING_STAGE1239.exists(),
        "source_stage8718_present": SOURCE_8718_SUMMARY.exists() and SOURCE_8718_INVENTORY.exists(),
        "source_stage8718_passed": s8718.get("passed") is True,
        "source_stage8719_present": SOURCE_8719_SUMMARY.exists(),
        "source_stage8719_passed": s8719.get("passed") is True,
        "operator_count_gte_83": int(inv.get("operator_count", 0)) >= 83,
        "all_required_categories_present": not missing_categories,
        "all_gap_operators_present": not missing_operators,
        "authority_counts_zero": not any(
            ((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0)
            for key in AUTHORITY_CLOSED
        ),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "OPERATOR_INVENTORY_RECOVERY_BRIDGE_AUDIT_NO_EXECUTION",
        "missing_stage1239_path": str(MISSING_STAGE1239.relative_to(ROOT)),
        "replacement_sources": {
            "stage8718_summary": str(SOURCE_8718_SUMMARY.relative_to(ROOT)),
            "stage8718_inventory": str(SOURCE_8718_INVENTORY.relative_to(ROOT)),
            "stage8719_graph_attachment": str(SOURCE_8719_SUMMARY.relative_to(ROOT)),
        },
        "required_recovered_categories": REQUIRED_RECOVERED_CATEGORIES,
        "required_gap_operators": REQUIRED_GAP_OPERATORS,
        "missing_categories": missing_categories,
        "missing_operators": missing_operators,
        "checks": checks,
        "metrics": {
            "stage1239_present": MISSING_STAGE1239.exists(),
            "replacement_operator_count": int(inv.get("operator_count", 0)),
            "replacement_category_count": len(categories),
            "required_categories": len(REQUIRED_RECOVERED_CATEGORIES),
            "missing_categories": len(missing_categories),
            "required_gap_operators": len(REQUIRED_GAP_OPERATORS),
            "missing_gap_operators": len(missing_operators),
            "model_execution_attempted": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "scoring_authorized_next": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Stage1239 is absent in the rebuilt workspace, but Stage8718/8719 recover the operator inventory and codelength interface with the previously missing gap categories. No execution or training authority is opened.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "model_execution_attempted",
        "training_authorized",
        "data_mining_authorized",
        "runtime_authorized_flag",
        "scoring_authorized_next",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Use Stage8718/8719 as the durable operator/codelength replacement for missing Stage1239; keep data mining and training closed until judge-output gates exist.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9028 Operator Inventory Recovery Bridge Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This audit records that the old Stage1239 operator pack is absent, and Stage8718/8719 are the recovered replacement for operator inventory plus codelength/probability interfaces.",
                "",
                f"Replacement operator count: `{summary['metrics']['replacement_operator_count']}`",
                f"Replacement category count: `{summary['metrics']['replacement_category_count']}`",
                f"Missing gap operators: `{summary['metrics']['missing_gap_operators']}`",
                f"Training authorized: `{summary['metrics']['training_authorized']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
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
