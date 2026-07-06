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
STAGE = 8965
NAME = "stage8965_registry_spine_reconciliation_after_focused_manifest_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_FOCUSED_MANIFEST_AUDIT_STAGE8965.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "registry_spine_reconciliation_after_focused_manifest_audit.json"

SOURCE_SUMMARIES = {
    8961: "stage8961_repo_local_manifest_inventory_no_mining",
    8962: "stage8962_focused_manifest_audit_only_compiler_refresh",
    8963: "stage8963_focused_manifest_patch_queue_interpretation",
    8964: "stage8964_focused_manifest_counterbalance_design_no_mining",
}

SPINE_STATUS = [
    {
        "node_id": "manifest:stage8937_tiny_explicit_manifest",
        "status": "audit_only_compiler_path_passed",
        "evidence_stage": 8962,
        "trainable_now": False,
    },
    {
        "node_id": "issue:focused_manifest_combo_shortcut",
        "status": "blocked_trainability",
        "evidence_stage": 8963,
        "trainable_now": False,
    },
    {
        "node_id": "design:focused_manifest_counterbalance_templates",
        "status": "design_only_non_trainable",
        "evidence_stage": 8964,
        "trainable_now": False,
    },
]

NEXT_BRANCH_OPTIONS = [
    {
        "branch": "continue_no_execution_recovery",
        "allowed_now": True,
        "description": "Continue contracts, audits, and docs without mining/training.",
    },
    {
        "branch": "repo_local_manifest_audit_only",
        "allowed_now": True,
        "description": "Audit explicit repo-local manifests only; do not recurse or mine.",
    },
    {
        "branch": "future_one_run_bounded_probe_ticket",
        "allowed_now": False,
        "description": "Requires explicit user one-run authorization and fresh pre-execution audit.",
    },
    {
        "branch": "counterbalance_row_materialization",
        "allowed_now": False,
        "description": "Requires separate row-source/audit gate; current templates are not trainable.",
    },
    {
        "branch": "data_mining_or_arxiv_walk",
        "allowed_now": False,
        "description": "Still closed.",
    },
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
            "metrics": summary.get("metrics") or {},
        }
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "spine_status_recorded": len(SPINE_STATUS) >= 3,
        "all_focused_manifest_status_non_trainable": all(row["trainable_now"] is False for row in SPINE_STATUS),
        "next_branch_options_recorded": len(NEXT_BRANCH_OPTIONS) >= 5,
        "only_no_execution_branches_allowed": all(row["allowed_now"] is (row["branch"] in {"continue_no_execution_recovery", "repo_local_manifest_audit_only"}) for row in NEXT_BRANCH_OPTIONS),
        "counterbalance_templates_non_trainable": sources["8964"]["metrics"].get("trainable_rows") == 0,
        "focused_manifest_not_trainable": sources["8963"]["metrics"].get("manifest_trainable_now") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8964": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8964,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "RECONCILED_FOCUSED_MANIFEST_AUDIT_BRANCH",
        "source_status": sources,
        "spine_status": SPINE_STATUS,
        "next_branch_options": NEXT_BRANCH_OPTIONS,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "spine_status_nodes": len(SPINE_STATUS),
            "next_branch_options": len(NEXT_BRANCH_OPTIONS),
            "allowed_now_branches": sum(1 for row in NEXT_BRANCH_OPTIONS if row["allowed_now"]),
            "focused_manifest_trainable_now": False,
            "counterbalance_templates_trainable_now": False,
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
        "decision": "Focused manifest audit branch is reconciled: audit plumbing works, but combo shortcuts block trainability and counterbalance rows are design-only. Continue only no-execution work unless an explicit future authorization is requested.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8964, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["focused_manifest_trainable_now", "counterbalance_templates_trainable_now", "actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
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
        "next_best_step": "Continue no-execution recovery or stop and commit/push the recovery branch. Do not mine or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8965 Registry/Spine Reconciliation After Focused Manifest Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "The focused manifest audit branch is reconciled into the spine. Audit-only compiler plumbing works, but trainability is blocked by combo shortcuts.",
        "",
        f"Allowed-now branches: `{card['metrics']['allowed_now_branches']}`",
        f"Focused manifest trainable now: `{card['metrics']['focused_manifest_trainable_now']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
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
    marker = "## Stage8965 Registry/Spine Reconciliation After Focused Manifest Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8965 reconciles the focused manifest audit branch. The compiler audit path is working, but the focused manifest remains non-trainable because combo-feature shortcuts solve the target exactly. Counterbalance rows are templates only.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
