#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9128_loss_mask_card_schema_recovery_design import (
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_LOSS_MASK_FIELDS,
        REQUIRED_TELEMETRY,
        build_schema,
        validate_schema,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9128_loss_mask_card_schema_recovery_design import (  # type: ignore
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_LOSS_MASK_FIELDS,
        REQUIRED_TELEMETRY,
        build_schema,
        validate_schema,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9129
NAME = "stage9129_loss_mask_card_schema_recovery_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9128 = ROOT / "runs/summaries/stage9128_loss_mask_card_schema_recovery_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOSS_MASK_CARD_SCHEMA_RECOVERY_AUDIT_STAGE9129.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "loss_mask_card_schema_recovery_audit.json"

REJECT_METRICS = [
    "loss_mask_cards_materialized_now",
    "route_cards_materialized_now",
    "route_to_loss_translation_ready_now",
    "compiler_handoff_ready_now",
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "trainer_executed_now",
    "model_forward_attempted",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized_flag",
    "network_upload_performed",
    "cleanup_authorized_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9127) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_schema(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in REJECT_METRICS:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_field = copy.deepcopy(base)
    missing_field["required_loss_mask_fields"].remove("loss_authority_evidence")
    cases["missing_loss_authority_evidence"] = missing_field

    missing_disabled = copy.deepcopy(base)
    missing_disabled["required_disabled_by_default"].remove("runtime_reward")
    cases["missing_runtime_reward_disabled_default"] = missing_disabled

    missing_telemetry = copy.deepcopy(base)
    missing_telemetry["required_telemetry"].remove("loss_mask_enforcement_audit")
    cases["missing_loss_mask_enforcement_telemetry"] = missing_telemetry

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_schema(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9128)
    base = build_schema(registry())
    base_failures = validate_schema(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9128_present": SOURCE_9128.exists(),
        "source_stage9128_passed": source.get("passed") is True,
        "base_schema_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_loss_mask_fields_recorded": len(REQUIRED_LOSS_MASK_FIELDS) >= 20,
        "required_disabled_by_default_recorded": len(REQUIRED_DISABLED_BY_DEFAULT) >= 6,
        "required_telemetry_recorded": len(REQUIRED_TELEMETRY) >= 6,
        "no_loss_mask_materialization": base["metrics"]["loss_mask_cards_materialized_now"] is False,
        "authority_closed": not any(base["authority"].values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "required_loss_mask_fields": len(REQUIRED_LOSS_MASK_FIELDS),
            "required_disabled_by_default": len(REQUIRED_DISABLED_BY_DEFAULT),
            "required_telemetry": len(REQUIRED_TELEMETRY),
            "loss_mask_cards_materialized_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
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
        "decision": "Loss-mask card schema recovery audit rejects missing authority fields, missing disabled-default losses, missing telemetry, loss-mask materialization, compiler handoff, trainer/model paths, training, runtime, upload, cleanup, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9128, STAGE}:
        audit["failures"].append(f"unexpected_registry_frontier:{latest}")
        audit["passed"] = False
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Loss-mask card schema recovery audit failed.",
        "next_best_step": "Design synthetic route-card to loss-mask translator smoke; do not use real data yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9129 Loss-Mask Card Schema Recovery Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {**(registry_json.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
