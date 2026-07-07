#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9171_trainer_setup_materialization_instance_design import (
        ALLOWABLE_MATERIALIZATION_OUTPUTS,
        REQUIRED_INSTANCE_CHECKS,
        REQUIRED_INSTANCE_REFS,
        STILL_BLOCKED_AFTER_INSTANCE,
        build_design,
        run_negative_cases,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9171_trainer_setup_materialization_instance_design import (  # type: ignore
        ALLOWABLE_MATERIALIZATION_OUTPUTS,
        REQUIRED_INSTANCE_CHECKS,
        REQUIRED_INSTANCE_REFS,
        STILL_BLOCKED_AFTER_INSTANCE,
        build_design,
        run_negative_cases,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9172
NAME = "stage9172_trainer_setup_materialization_instance_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9171 = ROOT / "runs/summaries/stage9171_trainer_setup_materialization_instance_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZATION_INSTANCE_AUDIT_STAGE9172.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_setup_materialization_instance_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9171) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9171)
    design = build_design(registry(9170))
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "source_stage9171_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_instance_refs_complete": set(REQUIRED_INSTANCE_REFS).issubset(set(design["required_instance_refs"])),
        "required_instance_checks_complete": set(REQUIRED_INSTANCE_CHECKS).issubset(set(design["required_instance_checks"])),
        "allowable_outputs_complete": set(ALLOWABLE_MATERIALIZATION_OUTPUTS).issubset(set(design["allowable_materialization_outputs"])),
        "blocked_outputs_complete": set(STILL_BLOCKED_AFTER_INSTANCE).issubset(set(design["still_blocked_after_instance"])),
        "trainer_input_not_materialized": design["metrics"]["trainer_input_materialized_now"] is False,
        "trainer_not_invoked": design["metrics"]["trainer_invoked_now"] is False,
        "model_forward_blocked": design["metrics"]["model_forward_attempted"] is False,
        "registry_frontier_stage9171": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9171,
        "authority_closed": not any(design["authority"].values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(design_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "materialization_emitted_now": False,
            "trainer_input_materialized_now": False,
            "trainer_invoked_now": False,
            "model_forward_attempted": False,
            "optimizer_created": False,
            "backward_called": False,
            "arxiv_accessed": False,
            "repository_source_bodies_loaded": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "decision": "Audited the materialization instance design and kept emission, invocation, and execution closed.",
        "next_best_step": "Stop at the materialization-instance boundary until a deliberate emit-only stage is intentionally opened.",
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
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9172 Trainer Setup Materialization Instance Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Audits the materialization instance design without emitting outputs.",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
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
