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
STAGE = 9165
NAME = "stage9165_trainer_setup_materializer_wrapper_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9164 = ROOT / "runs/summaries/stage9164_trainer_setup_materializer_pre_authorization_audit.json"
MATERIALIZER = ROOT / "scripts/materialize_trainer_setup.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZER_WRAPPER_DESIGN_STAGE9165.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "trainer_setup_materializer_wrapper_design.json"

REQUIRED_WRAPPER_INPUTS = [
    "objective_rows_ref",
    "judge_rows_ref",
    "ranker_rows_ref",
    "route_card_audit_ref",
    "loss_mask_preflight_ref",
    "loss_mask_authority_audit_ref",
    "loss_mask_enforcement_audit_ref",
    "stage9164_materializer_audit_ref",
    "trainer_input_schema_lock_ref",
    "telemetry_artifact_manifest_ref",
]

REQUIRED_WRAPPER_GUARDS = [
    "wrapper_rejects_missing_stage9164_audit",
    "wrapper_rejects_open_authority",
    "wrapper_rejects_materializer_invocation_without_ticket",
    "wrapper_rejects_trainer_input_write_without_ticket",
    "wrapper_rejects_model_input_row_write_without_ticket",
    "wrapper_rejects_model_forward",
    "wrapper_rejects_optimizer_or_backward",
    "wrapper_rejects_arxiv_reads",
    "wrapper_restricts_writes_to_repo_local_artifacts",
    "wrapper_requires_explicit_contract_only_mode",
]

CONTRACT_ONLY_OUTPUTS = [
    "materializer_wrapper_ticket.json",
    "materializer_wrapper_plan.json",
    "materializer_wrapper_blockers.json",
]

BLOCKED_OUTPUTS = [
    "route_cards.jsonl",
    "loss_mask_cards.jsonl",
    "trainer_rows.jsonl",
    "trainer_dry_run_input.json",
    "model_input_rows.jsonl",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "registry_frontier_bad",
    "materializer_missing",
    "missing_wrapper_input",
    "missing_wrapper_guard",
    "missing_contract_only_output",
    "missing_blocked_output",
    "materializer_invoked",
    "trainer_input_materialized",
    "model_input_rows_materialized",
    "model_forward",
    "optimizer_created",
    "backward_called",
    "arxiv_accessed",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9164) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def build_design(registry_card: dict[str, Any] | None = None, materializer_exists: bool | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9164)
    exists = MATERIALIZER.exists() if materializer_exists is None else materializer_exists
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "design_type": "trainer_setup_materializer_wrapper_contract_only_v1",
        "source_stage9164_passed": source.get("passed") is True,
        "registry_frontier_stage9164": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9164,
        "materializer_present": exists,
        "required_wrapper_inputs": list(REQUIRED_WRAPPER_INPUTS),
        "required_wrapper_guards": list(REQUIRED_WRAPPER_GUARDS),
        "contract_only_outputs": list(CONTRACT_ONLY_OUTPUTS),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9164_passed": source.get("passed") is True,
            "registry_frontier_stage9164": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9164,
            "materializer_present": exists,
            "required_wrapper_inputs": len(REQUIRED_WRAPPER_INPUTS),
            "required_wrapper_guards": len(REQUIRED_WRAPPER_GUARDS),
            "contract_only_outputs": len(CONTRACT_ONLY_OUTPUTS),
            "blocked_outputs": len(BLOCKED_OUTPUTS),
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
            "Designed a contract-only wrapper around the recovered trainer setup materializer. "
            "The wrapper may emit only ticket and blocker metadata until a later authorization "
            "stage explicitly permits materialization."
        ),
        "next_best_step": "Audit the contract-only wrapper design; still do not invoke the materializer or emit trainer input.",
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if design.get("source_stage9164_passed") is not True or metrics.get("source_stage9164_passed") is not True:
        failures.append("source_stage9164_not_passed")
    if design.get("registry_frontier_stage9164") is not True or metrics.get("registry_frontier_stage9164") is not True:
        failures.append("registry_frontier_stage9164")
    if design.get("materializer_present") is not True or metrics.get("materializer_present") is not True:
        failures.append("materializer_present")
    for item in REQUIRED_WRAPPER_INPUTS:
        if item not in design.get("required_wrapper_inputs", []):
            failures.append(f"missing_wrapper_input:{item}")
    for item in REQUIRED_WRAPPER_GUARDS:
        if item not in design.get("required_wrapper_guards", []):
            failures.append(f"missing_wrapper_guard:{item}")
    for item in CONTRACT_ONLY_OUTPUTS:
        if item not in design.get("contract_only_outputs", []):
            failures.append(f"missing_contract_only_output:{item}")
    for item in BLOCKED_OUTPUTS:
        if item not in design.get("blocked_outputs", []):
            failures.append(f"missing_blocked_output:{item}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    false_keys = [
        "materializer_invoked_now",
        "trainer_input_materialized_now",
        "model_input_rows_materialized_now",
        "model_forward_attempted",
        "optimizer_created",
        "backward_called",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_accessed",
        "file_content_read",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    cases: dict[str, Any] = {}
    for case in NEGATIVE_CASES:
        design = copy.deepcopy(build_design(registry(), True))
        if case == "source_stage_missing":
            design["source_stage9164_passed"] = False
            design["metrics"]["source_stage9164_passed"] = False
        elif case == "registry_frontier_bad":
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
        cases[case] = {"failures": failures, "rejected": bool(failures)}
    return cases


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design(registry_json)
    failures = validate_design(design)
    negatives = run_negative_cases()
    passed = not failures and all(item["rejected"] for item in negatives.values())
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "design": design,
        "failures": failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **design["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": design["decision"] if passed else "Trainer setup materializer wrapper design failed validation.",
        "next_best_step": design["next_best_step"],
    }
    DESIGN.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **artifact["metrics"], "failures": artifact["failures"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": artifact["decision"],
        "next_best_step": artifact["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9165 Trainer Setup Materializer Wrapper Design",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Designs a contract-only wrapper around the recovered materializer without invoking it.",
                "",
                f"Required wrapper guards: `{artifact['metrics']['required_wrapper_guards']}`",
                f"Negative cases rejected: `{artifact['metrics']['negative_cases_rejected']}/{artifact['metrics']['negative_cases']}`",
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
