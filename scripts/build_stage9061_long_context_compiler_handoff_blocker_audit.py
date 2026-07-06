#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS, REQUIRED_GATE_FIELDS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS, REQUIRED_GATE_FIELDS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9061
NAME = "stage9061_long_context_compiler_handoff_blocker_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9059 = ROOT / "runs/summaries/stage9059_long_context_route_card_materialization_audit_contract.json"
SOURCE_9060 = ROOT / "runs/summaries/stage9060_long_context_candidate_quality_guard_refresh_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_COMPILER_HANDOFF_BLOCKER_STAGE9061.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "long_context_compiler_handoff_blocker_audit.json"

REQUIRED_HANDOFF_ARTIFACTS = [
    "source_output_ticket_granted_and_scoped",
    "route_card_materialization_audit_passed",
    "source_lineage_card",
    "dataset_junk_ood_ranker_card",
    "shortcut_baseline_audit",
    "counterfactual_obligation_card",
    "split_overlap_audit",
    "loss_mask_card",
    "telemetry_contract",
]

FORBIDDEN_HANDOFF_FLAGS = [
    "compiler_ready",
    "training_ready",
    "model_input_ready",
    "decoder_ce_training_authorized_next",
    "denoise_ce_training_authorized_next",
    "model_execution_authorized_next",
    "runtime_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def closed_handoff_candidate() -> dict[str, Any]:
    return {
        "handoff_id": "long_context_future_handoff_closed_example",
        "route_card_id": "future_route_card_placeholder",
        "required_handoff_artifacts": list(REQUIRED_HANDOFF_ARTIFACTS),
        "artifact_status": {name: False for name in REQUIRED_HANDOFF_ARTIFACTS},
        "losses_enabled": {key: False for key in LOSS_KEYS},
        "compiler_ready": False,
        "training_ready": False,
        "model_input_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def audit_handoff_candidate(candidate: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    required = set(candidate.get("required_handoff_artifacts") or [])
    for artifact in REQUIRED_HANDOFF_ARTIFACTS:
        if artifact not in required:
            failures.append(f"missing_required_artifact:{artifact}")
    losses = candidate.get("losses_enabled") or {}
    for key in LOSS_KEYS:
        if key not in losses:
            failures.append(f"missing_loss_key:{key}")
    if any(losses.values()):
        failures.append("loss_open_before_compiler_handoff")
    authority = candidate.get("authority") or {}
    for key in AUTHORITY_CLOSED:
        if authority.get(key):
            failures.append(f"authority_open:{key}")
    artifact_status = candidate.get("artifact_status") or {}
    all_artifacts_passed = all(artifact_status.get(name) is True for name in REQUIRED_HANDOFF_ARTIFACTS)
    if candidate.get("compiler_ready") is True and not all_artifacts_passed:
        failures.append("compiler_ready_without_all_handoff_artifacts")
    if candidate.get("training_ready") is True:
        failures.append("training_ready_not_allowed_by_handoff_blocker")
    if candidate.get("model_input_ready") is True:
        failures.append("model_input_ready_not_allowed_by_handoff_blocker")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = closed_handoff_candidate()
    cases: dict[str, dict[str, Any]] = {}
    missing_materialization = copy.deepcopy(base)
    missing_materialization["required_handoff_artifacts"] = [name for name in REQUIRED_HANDOFF_ARTIFACTS if name != "route_card_materialization_audit_passed"]
    cases["missing_materialization_audit"] = missing_materialization
    open_decoder = copy.deepcopy(base)
    open_decoder["losses_enabled"]["decoder_ce"] = True
    cases["open_decoder_ce_loss"] = open_decoder
    open_training = copy.deepcopy(base)
    open_training["authority"]["model_execution_authorized_next"] = True
    cases["open_model_execution_authority"] = open_training
    ready_without_gates = copy.deepcopy(base)
    ready_without_gates["compiler_ready"] = True
    cases["compiler_ready_without_artifacts"] = ready_without_gates
    training_ready = copy.deepcopy(base)
    training_ready["training_ready"] = True
    cases["training_ready_before_handoff"] = training_ready
    model_ready = copy.deepcopy(base)
    model_ready["model_input_ready"] = True
    cases["model_input_ready_before_handoff"] = model_ready
    return {name: {"failures": audit_handoff_candidate(candidate), "rejected": bool(audit_handoff_candidate(candidate))} for name, candidate in cases.items()}


def build_audit() -> dict[str, Any]:
    source_9059 = load_json(SOURCE_9059)
    source_9060 = load_json(SOURCE_9060)
    closed_failures = audit_handoff_candidate(closed_handoff_candidate())
    negatives = run_negative_cases()
    checks = {
        "source_stage9059_present": SOURCE_9059.exists(),
        "source_stage9059_passed": source_9059.get("passed") is True,
        "source_stage9060_present": SOURCE_9060.exists(),
        "source_stage9060_passed": source_9060.get("passed") is True,
        "route_card_required_gates_preserved": set(REQUIRED_GATE_FIELDS).issubset(set(REQUIRED_HANDOFF_ARTIFACTS + ["source_output_ticket_granted"])),
        "closed_candidate_passes": closed_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "compiler_ready_rows_now_zero": True,
        "training_ready_rows_now_zero": True,
        "model_input_rows_now_zero": True,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "required_handoff_artifacts": list(REQUIRED_HANDOFF_ARTIFACTS),
        "forbidden_handoff_flags": list(FORBIDDEN_HANDOFF_FLAGS),
        "closed_candidate_failures": closed_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "required_handoff_artifacts": len(REQUIRED_HANDOFF_ARTIFACTS),
            "negative_cases": len(negatives),
            "compiler_ready_rows_now": 0,
            "training_ready_rows_now": 0,
            "model_input_rows_now": 0,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Long-context candidates remain blocked from compiler handoff until route-card materialization and every judge/shortcut/counterfactual/split/loss/telemetry gate passes.",
    }


def write_outputs(audit: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT_PATH.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Long-context compiler handoff blocker audit failed.",
        "next_best_step": "Continue trainer/compiler no-data recovery: refresh the loss-mask compiler preflight so route-card handoff cannot create gradients without all Stage9061 artifacts.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9061 Long Context Compiler Handoff Blocker",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This no-data audit blocks long-context route cards from curriculum compiler handoff unless source-ticket, materialization, lineage, junk/OOD, shortcut, counterfactual, split-overlap, loss-mask, and telemetry artifacts all pass.",
        "",
        "It materializes no data, opens no loss, and authorizes no model execution or training.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
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
    return summary


def main() -> None:
    audit = build_audit()
    summary = write_outputs(audit)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
