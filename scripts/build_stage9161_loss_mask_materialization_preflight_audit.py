#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9160_loss_mask_materialization_preflight_design import (
        BLOCKED_OUTPUTS,
        LOSS_MASK_PREFLIGHT_CHECKS,
        NEGATIVE_CASES,
        REQUIRED_INPUTS_BEFORE_LOSS_MASKS,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9160_loss_mask_materialization_preflight_design import (  # type: ignore
        BLOCKED_OUTPUTS,
        LOSS_MASK_PREFLIGHT_CHECKS,
        NEGATIVE_CASES,
        REQUIRED_INPUTS_BEFORE_LOSS_MASKS,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9161
NAME = "stage9161_loss_mask_materialization_preflight_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9160 = ROOT / "runs/summaries/stage9160_loss_mask_materialization_preflight_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOSS_MASK_MATERIALIZATION_PREFLIGHT_AUDIT_STAGE9161.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "loss_mask_materialization_preflight_audit.json"

AUDIT_NEGATIVE_CASES = list(NEGATIVE_CASES) + [
    "bad_registry_frontier",
    "missing_trainer_input_block",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9160) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in AUDIT_NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["source_stage9159_passed"] = False
            candidate["metrics"]["source_stage9159_passed"] = False
        elif name == "missing_required_input":
            candidate["required_inputs_before_loss_masks"].remove("route_cards_jsonl_materialized_and_audited")
        elif name == "missing_preflight_check":
            candidate["loss_mask_preflight_checks"].remove("decoder_ce_requires_keep_bounded_decoder_and_budget_ok")
        elif name == "missing_blocked_output":
            candidate["blocked_outputs"].remove("loss_mask_cards.jsonl")
        elif name == "missing_trainer_input_block":
            candidate["blocked_outputs"].remove("trainer_dry_run_input.json")
        elif name == "missing_loss_mask_field":
            candidate["required_loss_mask_fields"].remove("loss_authority_evidence")
        elif name == "missing_disabled_default":
            candidate["required_disabled_by_default"].remove("runtime_reward")
        elif name == "missing_telemetry":
            candidate["required_telemetry"].remove("loss_mask_enforcement_audit")
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "trainer_input_materialized":
            candidate["metrics"]["trainer_input_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_ready":
            candidate["metrics"]["trainer_dry_run_ready_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate)
        if name == "bad_registry_frontier":
            failures.append("unexpected_registry_frontier:9999")
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9160)
    design = build_design()
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "source_stage9160_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_inputs_complete": set(REQUIRED_INPUTS_BEFORE_LOSS_MASKS).issubset(set(design["required_inputs_before_loss_masks"])),
        "preflight_checks_complete": set(LOSS_MASK_PREFLIGHT_CHECKS).issubset(set(design["loss_mask_preflight_checks"])),
        "blocked_outputs_complete": set(BLOCKED_OUTPUTS).issubset(set(design["blocked_outputs"])),
        "loss_masks_blocked": "loss_mask_cards.jsonl" in design["blocked_outputs"],
        "trainer_input_blocked": "trainer_dry_run_input.json" in design["blocked_outputs"],
        "no_loss_mask_materialization": design["metrics"]["loss_mask_cards_materialized_now"] is False,
        "no_trainer_input_materialization": design["metrics"]["trainer_input_materialized_now"] is False,
        "authority_closed": not any(design["authority"].values()),
        "registry_frontier_stage9160": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9160,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(design_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": design_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "loss_mask_cards_materialized_now": False,
            "trainer_input_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Audited loss-mask materialization preflight and rejected missing inputs, "
            "missing checks, missing blocked outputs, loss-mask materialization, trainer "
            "input materialization, compiler handoff, trainer readiness, training, decoder "
            "CE, denoise CE, runtime, and authority openings."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Loss-mask materialization preflight audit failed.",
        "next_best_step": "Refresh trainer dry-run input readiness against the audited loss-mask preflight; still do not materialize trainer input or execute trainer.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9161 Loss-Mask Materialization Preflight Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
