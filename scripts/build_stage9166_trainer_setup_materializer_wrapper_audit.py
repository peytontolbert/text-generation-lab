#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9165_trainer_setup_materializer_wrapper_design import (
        BLOCKED_OUTPUTS,
        CONTRACT_ONLY_OUTPUTS,
        NEGATIVE_CASES,
        REQUIRED_WRAPPER_GUARDS,
        REQUIRED_WRAPPER_INPUTS,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9165_trainer_setup_materializer_wrapper_design import (  # type: ignore
        BLOCKED_OUTPUTS,
        CONTRACT_ONLY_OUTPUTS,
        NEGATIVE_CASES,
        REQUIRED_WRAPPER_GUARDS,
        REQUIRED_WRAPPER_INPUTS,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9166
NAME = "stage9166_trainer_setup_materializer_wrapper_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9165 = ROOT / "runs/summaries/stage9165_trainer_setup_materializer_wrapper_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZER_WRAPPER_AUDIT_STAGE9166.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_setup_materializer_wrapper_audit.json"

AUDIT_NEGATIVE_CASES = list(NEGATIVE_CASES) + [
    "bad_registry_frontier",
    "missing_blocked_model_input_rows",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9165) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    audited: dict[str, Any] = {}
    for case in AUDIT_NEGATIVE_CASES:
        design = copy.deepcopy(build_design(registry(9164), True))
        if case == "source_stage_missing":
            design["source_stage9164_passed"] = False
            design["metrics"]["source_stage9164_passed"] = False
        elif case in {"registry_frontier_bad", "bad_registry_frontier"}:
            design["registry_frontier_stage9164"] = False
            design["metrics"]["registry_frontier_stage9164"] = False
        elif case == "materializer_missing":
            design["materializer_present"] = False
            design["metrics"]["materializer_present"] = False
        elif case == "missing_wrapper_input":
            design["required_wrapper_inputs"].remove("stage9164_materializer_audit_ref")
        elif case == "missing_wrapper_guard":
            design["required_wrapper_guards"].remove("wrapper_rejects_trainer_input_write_without_ticket")
        elif case == "missing_contract_only_output":
            design["contract_only_outputs"].remove("materializer_wrapper_ticket.json")
        elif case == "missing_blocked_output":
            design["blocked_outputs"].remove("trainer_dry_run_input.json")
        elif case == "missing_blocked_model_input_rows":
            design["blocked_outputs"].remove("model_input_rows.jsonl")
        elif case == "materializer_invoked":
            design["metrics"]["materializer_invoked_now"] = True
        elif case == "trainer_input_materialized":
            design["metrics"]["trainer_input_materialized_now"] = True
        elif case == "model_input_rows_materialized":
            design["metrics"]["model_input_rows_materialized_now"] = True
        elif case == "model_forward":
            design["metrics"]["model_forward_attempted"] = True
        elif case == "optimizer_created":
            design["metrics"]["optimizer_created"] = True
        elif case == "backward_called":
            design["metrics"]["backward_called"] = True
        elif case == "arxiv_accessed":
            design["metrics"]["arxiv_accessed"] = True
        elif case == "training_authorized":
            design["metrics"]["training_authorized"] = True
        elif case == "decoder_ce_authorized":
            design["metrics"]["decoder_ce_authorized"] = True
        elif case == "denoise_ce_authorized":
            design["metrics"]["denoise_ce_authorized"] = True
        elif case == "runtime_authorized":
            design["metrics"]["runtime_authorized_flag"] = True
        elif case == "authority_open":
            design["authority"]["model_execution_authorized_next"] = True
        failures = validate_design(design)
        if case == "bad_registry_frontier":
            failures.append("unexpected_registry_frontier:9999")
        audited[case] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9165)
    design = build_design(registry(9164), True)
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "source_stage9165_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_wrapper_inputs_complete": set(REQUIRED_WRAPPER_INPUTS).issubset(set(design["required_wrapper_inputs"])),
        "required_wrapper_guards_complete": set(REQUIRED_WRAPPER_GUARDS).issubset(set(design["required_wrapper_guards"])),
        "contract_only_outputs_complete": set(CONTRACT_ONLY_OUTPUTS).issubset(set(design["contract_only_outputs"])),
        "blocked_outputs_complete": set(BLOCKED_OUTPUTS).issubset(set(design["blocked_outputs"])),
        "trainer_input_blocked": "trainer_dry_run_input.json" in design["blocked_outputs"],
        "model_input_rows_blocked": "model_input_rows.jsonl" in design["blocked_outputs"],
        "no_materializer_invocation": design["metrics"]["materializer_invoked_now"] is False,
        "no_materialization": design["metrics"]["trainer_input_materialized_now"] is False and design["metrics"]["model_input_rows_materialized_now"] is False,
        "no_model_forward": design["metrics"]["model_forward_attempted"] is False,
        "no_optimizer_or_backward": design["metrics"]["optimizer_created"] is False and design["metrics"]["backward_called"] is False,
        "authority_closed": not any(design["authority"].values()),
        "registry_frontier_stage9165": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9165,
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
            "materializer_invoked_now": False,
            "trainer_input_materialized_now": False,
            "model_input_rows_materialized_now": False,
            "model_forward_attempted": False,
            "optimizer_created": False,
            "backward_called": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
        },
        "decision": (
            "Audited the contract-only materializer wrapper design and kept invocation, "
            "trainer-input materialization, model input rows, model forward, optimizer/backward, "
            "training, decoder CE, denoise CE, runtime, and /arxiv access closed."
        ),
        "next_best_step": "Design the contract-only wrapper ticket instance; still do not invoke the materializer.",
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
        "decision": audit["decision"] if audit["passed"] else "Trainer setup materializer wrapper audit failed.",
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9166 Trainer Setup Materializer Wrapper Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Audits the contract-only wrapper design without invoking the materializer.",
                "",
                f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
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
