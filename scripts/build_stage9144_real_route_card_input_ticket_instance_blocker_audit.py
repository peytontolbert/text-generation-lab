#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9144
NAME = "stage9144_real_route_card_input_ticket_instance_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9143 = ROOT / "runs/summaries/stage9143_real_route_card_input_ticket_instance_schema_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_TICKET_INSTANCE_BLOCKER_AUDIT_STAGE9144.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_route_card_input_ticket_instance_blocker_audit.json"

REQUIRED_BLOCKERS = [
    "explicit_user_approval_for_ticket_instance_missing",
    "objective_rows_path_missing",
    "judge_rows_path_missing",
    "junk_ranker_rows_path_missing",
    "shortcut_baseline_card_path_missing",
    "counterfactual_obligation_card_path_missing",
    "source_lineage_card_path_missing",
    "max_rows_not_selected",
    "output_dir_not_selected",
]

FORBIDDEN_UNTIL_UNBLOCKED = [
    "ticket_instance_materialized",
    "real_input_authorized_now",
    "dataset_rows_loaded",
    "route_cards_materialized_now",
    "route_to_loss_translation_ready_now",
    "loss_mask_cards_materialized_now",
    "compiler_handoff_ready_now",
    "trainer_executed_now",
    "model_forward_attempted",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized_flag",
    "cleanup_authorized_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_blocker(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9143)
    checks = {
        "source_stage9143_passed": source.get("passed") is True,
        "required_blockers_recorded": len(REQUIRED_BLOCKERS) >= 9,
        "forbidden_until_unblocked_recorded": len(FORBIDDEN_UNTIL_UNBLOCKED) >= 14,
        "registry_frontier_stage9143": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9143,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TICKET_INSTANCE_BLOCKED_NO_CONCRETE_INPUT_PATHS",
        "required_blockers": list(REQUIRED_BLOCKERS),
        "forbidden_until_unblocked": list(FORBIDDEN_UNTIL_UNBLOCKED),
        "unblock_requirements": {
            "explicit_user_approval": "required before any ticket instance is created",
            "concrete_repo_local_paths": [
                "objective_rows_path",
                "judge_rows_path",
                "junk_ranker_rows_path",
                "shortcut_baseline_card_path",
                "counterfactual_obligation_card_path",
                "source_lineage_card_path",
            ],
            "arxiv_policy": "/arxiv remains blocked unless separately authorized",
            "output_policy": "output_dir must remain repo-local under runs/local/artifacts",
        },
        "checks": checks,
        "metrics": {
            "required_blockers": len(REQUIRED_BLOCKERS),
            "forbidden_until_unblocked": len(FORBIDDEN_UNTIL_UNBLOCKED),
            "ticket_instance_blocked": True,
            "ticket_instance_materialized": False,
            "approved_for_preflight_only": False,
            "approved_for_route_card_materialization": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Blocked bounded real route-card input ticket instance creation because explicit approval and concrete repo-local artifact paths are not present. No real input, route-card materialization, loss-mask materialization, compiler handoff, training, runtime, cleanup, or model execution was opened.",
    }


def validate_blocker(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9143, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for blocker in REQUIRED_BLOCKERS:
        if blocker not in card.get("required_blockers", []):
            failures.append(f"missing_blocker:{blocker}")
    for item in FORBIDDEN_UNTIL_UNBLOCKED:
        if item not in card.get("forbidden_until_unblocked", []):
            failures.append(f"missing_forbidden_until_unblocked:{item}")
    if card["metrics"].get("ticket_instance_blocked") is not True:
        failures.append("ticket_instance_not_blocked")
    for key in FORBIDDEN_UNTIL_UNBLOCKED:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    registry = {"metrics": {"latest_stage": 9143, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    base = build_blocker(registry)
    cases: dict[str, dict[str, Any]] = {}
    for name in [
        "missing_explicit_approval_blocker",
        "missing_objective_path_blocker",
        "ticket_instance_unblocked",
        "ticket_instance_materialized",
        "real_input_authorized_now",
        "dataset_rows_loaded",
        "route_cards_materialized_now",
        "training_authorized",
        "runtime_authorized_flag",
        "authority_open",
        "bad_registry_frontier",
    ]:
        candidate = copy.deepcopy(base)
        if name == "missing_explicit_approval_blocker":
            candidate["required_blockers"].remove("explicit_user_approval_for_ticket_instance_missing")
        elif name == "missing_objective_path_blocker":
            candidate["required_blockers"].remove("objective_rows_path_missing")
        elif name == "ticket_instance_unblocked":
            candidate["metrics"]["ticket_instance_blocked"] = False
        elif name in FORBIDDEN_UNTIL_UNBLOCKED:
            candidate["metrics"][name] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        audit_registry = {"metrics": {"latest_stage": 9999 if name == "bad_registry_frontier" else 9143, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
        failures = validate_blocker(candidate, audit_registry)
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    blocker = build_blocker(registry)
    failures = validate_blocker(blocker, registry)
    negatives = run_negative_cases()
    if not all(item["rejected"] for item in negatives.values()):
        failures.append("negative_cases_not_rejected")
    blocker["negative_cases"] = negatives
    blocker["metrics"]["negative_cases"] = len(negatives)
    blocker["metrics"]["negative_cases_rejected"] = sum(1 for item in negatives.values() if item["rejected"])
    blocker["failures"] = failures
    blocker["passed"] = not failures
    AUDIT.write_text(json.dumps(blocker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": blocker["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **blocker["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": blocker["decision"] if blocker["passed"] else "Real route-card input ticket instance blocker audit failed.",
        "next_best_step": "Wait for explicit user approval and concrete repo-local artifact paths before creating a bounded real input preflight ticket instance.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9144 Real Route-Card Input Ticket Instance Blocker Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Ticket instance creation is blocked until explicit approval and concrete repo-local artifact paths exist.",
        "",
        f"Next: {summary['next_best_step']}",
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
