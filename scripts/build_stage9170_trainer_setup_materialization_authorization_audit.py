#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9169_trainer_setup_materialization_authorization_design import (
        ALLOWABLE_OUTPUTS_IF_AUTHORIZED,
        REQUIRED_AUTHORIZATION_GUARDS,
        REQUIRED_AUTHORIZATION_INPUTS,
        STILL_BLOCKED_OUTPUTS,
        build_design,
        run_negative_cases,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9169_trainer_setup_materialization_authorization_design import (  # type: ignore
        ALLOWABLE_OUTPUTS_IF_AUTHORIZED,
        REQUIRED_AUTHORIZATION_GUARDS,
        REQUIRED_AUTHORIZATION_INPUTS,
        STILL_BLOCKED_OUTPUTS,
        build_design,
        run_negative_cases,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9170
NAME = "stage9170_trainer_setup_materialization_authorization_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9169 = ROOT / "runs/summaries/stage9169_trainer_setup_materialization_authorization_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZATION_AUTHORIZATION_AUDIT_STAGE9170.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_setup_materialization_authorization_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9169) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9169)
    design = build_design(registry(9168))
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "source_stage9169_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_authorization_inputs_complete": set(REQUIRED_AUTHORIZATION_INPUTS).issubset(set(design["required_authorization_inputs"])),
        "required_authorization_guards_complete": set(REQUIRED_AUTHORIZATION_GUARDS).issubset(set(design["required_authorization_guards"])),
        "allowable_outputs_complete": set(ALLOWABLE_OUTPUTS_IF_AUTHORIZED).issubset(set(design["allowable_outputs_if_authorized"])),
        "blocked_outputs_complete": set(STILL_BLOCKED_OUTPUTS).issubset(set(design["still_blocked_outputs"])),
        "trainer_input_still_not_materialized": design["metrics"]["trainer_input_materialized_now"] is False,
        "trainer_still_not_invoked": design["metrics"]["trainer_invoked_now"] is False,
        "model_forward_still_blocked": design["metrics"]["model_forward_attempted"] is False,
        "registry_frontier_stage9169": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9169,
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
            "materialization_authorized_now": False,
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
        "decision": "Audited the materialization authorization design and kept materialization, invocation, and execution closed pending a later explicit instance stage.",
        "next_best_step": "Stop at the authorization-design boundary until a separate materialization instance stage is intentionally opened.",
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
                "# Stage9170 Trainer Setup Materialization Authorization Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Audits the materialization-authorization design without materializing trainer artifacts.",
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
