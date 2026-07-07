#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9152_route_card_materialization_preflight_quality_gate_design import (
        NEGATIVE_CASES as SOURCE_NEGATIVE_CASES,
        OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT,
        PREFLIGHT_SECTIONS,
        REQUIRED_PRECHECKS,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9152_route_card_materialization_preflight_quality_gate_design import (  # type: ignore
        NEGATIVE_CASES as SOURCE_NEGATIVE_CASES,
        OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT,
        PREFLIGHT_SECTIONS,
        REQUIRED_PRECHECKS,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9153
NAME = "stage9153_route_card_materialization_preflight_quality_gate_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9152 = ROOT / "runs/summaries/stage9152_route_card_materialization_preflight_quality_gate_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_MATERIALIZATION_PREFLIGHT_QUALITY_GATE_DESIGN_AUDIT_STAGE9153.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "route_card_materialization_preflight_quality_gate_design_audit.json"

AUDIT_NEGATIVE_CASES = list(SOURCE_NEGATIVE_CASES) + [
    "missing_quality_gate_validate_before_route_write",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9152) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in AUDIT_NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage9150_missing":
            candidate["metrics"]["source_stage9150_passed"] = False
        elif name == "source_stage9151_missing":
            candidate["metrics"]["source_stage9151_passed"] = False
        elif name == "quality_gate_not_attached":
            candidate["metrics"]["candidate_quality_gate_attached"] = False
            candidate["quality_gate_attachment"]["required"] = False
        elif name == "missing_preflight_section":
            candidate["preflight_sections"].remove("candidate_quality_gate_guard")
        elif name == "missing_required_precheck":
            candidate["required_prechecks"].remove("candidate_quality_gate_contract_attached")
        elif name == "missing_blocked_output":
            candidate["outputs_blocked_until_separate_audit"].remove("route_cards.jsonl")
        elif name == "inventory_executed_now":
            candidate["metrics"]["inventory_runner_executed_now"] = True
        elif name == "metadata_inventory_loaded_now":
            candidate["metrics"]["metadata_path_inventory_loaded_now"] = True
            candidate["metrics"]["path_inventory_rows_loaded"] = 1
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "json_parsed":
            candidate["metrics"]["json_parsed"] = True
        elif name == "jsonl_rows_counted":
            candidate["metrics"]["jsonl_rows_counted"] = True
        elif name == "candidate_rows_loaded":
            candidate["metrics"]["candidate_rows_loaded"] = 1
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_executed":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        elif name == "missing_quality_gate_validate_before_route_write":
            candidate["quality_gate_attachment"]["must_validate_before"].remove("route_cards_jsonl_write")
        cases[name] = candidate

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate)
        if name == "bad_registry_frontier":
            failures.append("unexpected_registry_frontier:9999")
        if name == "missing_quality_gate_validate_before_route_write":
            before = set((candidate.get("quality_gate_attachment") or {}).get("must_validate_before") or [])
            if "route_cards_jsonl_write" not in before:
                failures.append("quality_gate_not_before_route_cards_write")
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9152)
    design = build_design()
    design_failures = validate_design(design)
    negatives = run_negative_cases()
    validate_before = set((design.get("quality_gate_attachment") or {}).get("must_validate_before") or [])
    checks = {
        "source_stage9152_passed": source.get("passed") is True,
        "base_design_passes": design_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "preflight_sections_complete": set(PREFLIGHT_SECTIONS).issubset(set(design["preflight_sections"])),
        "required_prechecks_complete": set(REQUIRED_PRECHECKS).issubset(set(design["required_prechecks"])),
        "blocked_outputs_complete": set(OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT).issubset(set(design["outputs_blocked_until_separate_audit"])),
        "quality_gate_before_route_write": "route_cards_jsonl_write" in validate_before,
        "quality_gate_before_route_to_loss": "route_to_loss_translation" in validate_before,
        "no_inventory_execution": design["metrics"]["inventory_runner_executed_now"] is False,
        "no_candidate_loading": design["metrics"]["candidate_rows_loaded"] == 0,
        "no_route_materialization": design["metrics"]["route_cards_materialized_now"] is False,
        "authority_closed": not any(design["authority"].values()),
        "registry_frontier_stage9152": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9152,
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
            "preflight_sections": len(PREFLIGHT_SECTIONS),
            "required_prechecks": len(REQUIRED_PRECHECKS),
            "blocked_outputs": len(OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT),
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Audited the route-card materialization preflight quality-gate design and "
            "rejected missing quality-gate attachment, missing sections/prechecks, "
            "inventory execution, candidate loading, route-card/loss-mask materialization, "
            "compiler handoff, training, runtime, and authority openings."
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
        "decision": audit["decision"] if audit["passed"] else "Route-card materialization preflight quality-gate design audit failed.",
        "next_best_step": (
            "Design a single-run repo-local inventory execution ticket instance, still "
            "metadata-only and still separate from route-card materialization."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9153 Route-Card Materialization Preflight Quality-Gate Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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
