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
STAGE = 9167
NAME = "stage9167_trainer_setup_materializer_wrapper_ticket_instance_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9166 = ROOT / "runs/summaries/stage9166_trainer_setup_materializer_wrapper_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZER_WRAPPER_TICKET_INSTANCE_DESIGN_STAGE9167.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "trainer_setup_materializer_wrapper_ticket_instance_design.json"

REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "source_stage9166_audit_ref",
    "objective_rows_ref",
    "judge_rows_ref",
    "ranker_rows_ref",
    "route_card_audit_ref",
    "loss_mask_authority_audit_ref",
    "loss_mask_enforcement_audit_ref",
    "telemetry_artifact_manifest_ref",
    "wrapper_mode",
    "output_dir_ref",
]

REQUIRED_INSTANCE_GUARDS = [
    "ticket_instance_requires_stage9166_passed",
    "ticket_instance_requires_contract_only_wrapper_mode",
    "ticket_instance_forbids_materializer_invocation",
    "ticket_instance_forbids_trainer_input_materialization",
    "ticket_instance_forbids_model_input_row_materialization",
    "ticket_instance_forbids_model_forward",
    "ticket_instance_forbids_optimizer_or_backward",
    "ticket_instance_forbids_arxiv_reads",
]

CONTRACT_ONLY_EMITTABLE = [
    "materializer_wrapper_ticket.json",
    "materializer_wrapper_plan.json",
    "materializer_wrapper_blockers.json",
    "materializer_wrapper_instance_card.json",
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
    "missing_ticket_field",
    "missing_instance_guard",
    "missing_emittable_output",
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


def registry(latest: int = 9166) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def build_design(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9166)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "design_type": "trainer_setup_materializer_wrapper_ticket_instance_v1",
        "source_stage9166_passed": source.get("passed") is True,
        "registry_frontier_stage9166": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9166,
        "required_ticket_fields": list(REQUIRED_TICKET_FIELDS),
        "required_instance_guards": list(REQUIRED_INSTANCE_GUARDS),
        "contract_only_emittable_outputs": list(CONTRACT_ONLY_EMITTABLE),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9166_passed": source.get("passed") is True,
            "registry_frontier_stage9166": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9166,
            "required_ticket_fields": len(REQUIRED_TICKET_FIELDS),
            "required_instance_guards": len(REQUIRED_INSTANCE_GUARDS),
            "contract_only_emittable_outputs": len(CONTRACT_ONLY_EMITTABLE),
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
            "Designed the contract-only materializer wrapper ticket instance. The instance may "
            "describe refs, blockers, and wrapper mode, but it may not invoke the materializer or "
            "emit trainer-input artifacts."
        ),
        "next_best_step": "Audit the wrapper ticket instance design; still do not invoke the materializer.",
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if design.get("source_stage9166_passed") is not True or metrics.get("source_stage9166_passed") is not True:
        failures.append("source_stage9166_not_passed")
    if design.get("registry_frontier_stage9166") is not True or metrics.get("registry_frontier_stage9166") is not True:
        failures.append("registry_frontier_stage9166")
    for item in REQUIRED_TICKET_FIELDS:
        if item not in design.get("required_ticket_fields", []):
            failures.append(f"missing_ticket_field:{item}")
    for item in REQUIRED_INSTANCE_GUARDS:
        if item not in design.get("required_instance_guards", []):
            failures.append(f"missing_instance_guard:{item}")
    for item in CONTRACT_ONLY_EMITTABLE:
        if item not in design.get("contract_only_emittable_outputs", []):
            failures.append(f"missing_emittable_output:{item}")
    for item in BLOCKED_OUTPUTS:
        if item not in design.get("blocked_outputs", []):
            failures.append(f"missing_blocked_output:{item}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
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
    ]:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    negatives: dict[str, Any] = {}
    for case in NEGATIVE_CASES:
        design = copy.deepcopy(build_design(registry()))
        if case == "source_stage_missing":
            design["source_stage9166_passed"] = False
            design["metrics"]["source_stage9166_passed"] = False
        elif case == "registry_frontier_bad":
            design["registry_frontier_stage9166"] = False
            design["metrics"]["registry_frontier_stage9166"] = False
        elif case == "missing_ticket_field":
            design["required_ticket_fields"].remove("source_stage9166_audit_ref")
        elif case == "missing_instance_guard":
            design["required_instance_guards"].remove("ticket_instance_forbids_trainer_input_materialization")
        elif case == "missing_emittable_output":
            design["contract_only_emittable_outputs"].remove("materializer_wrapper_ticket.json")
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
        negatives[case] = {"failures": validate_design(design), "rejected": bool(validate_design(design))}
    return negatives


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
        "decision": design["decision"] if passed else "Wrapper ticket instance design failed validation.",
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
                "# Stage9167 Trainer Setup Materializer Wrapper Ticket Instance Design",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Designs the contract-only wrapper ticket instance without invoking the materializer.",
                "",
                f"Required ticket fields: `{artifact['metrics']['required_ticket_fields']}`",
                f"Negative cases rejected: `{artifact['metrics']['negative_cases_rejected']}/{artifact['metrics']['negative_cases']}`",
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
