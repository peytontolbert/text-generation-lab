#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9134_real_route_card_materialization_design import (
        BLOCKERS,
        REQUIRED_INPUTS,
        REQUIRED_OUTPUTS,
        ROUTE_SOURCE_RULES,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9134_real_route_card_materialization_design import (  # type: ignore
        BLOCKERS,
        REQUIRED_INPUTS,
        REQUIRED_OUTPUTS,
        ROUTE_SOURCE_RULES,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9135
NAME = "stage9135_real_route_card_materialization_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9134 = ROOT / "runs/summaries/stage9134_real_route_card_materialization_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_MATERIALIZATION_DESIGN_AUDIT_STAGE9135.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_route_card_materialization_design_audit.json"

NEGATIVE_CASES = [
    "missing_judge_input",
    "missing_ranker_input",
    "missing_route_cards_output",
    "missing_blocker_shortcut",
    "missing_blocker_authority",
    "missing_keep_bounded_rule",
    "materializes_route_cards",
    "loads_dataset_rows",
    "opens_compiler_handoff",
    "opens_training",
    "opens_decoder_ce",
    "opens_runtime",
    "opens_authority",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9134) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry())
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "missing_judge_input":
            candidate["required_inputs"].remove("judge_rows_jsonl")
        elif name == "missing_ranker_input":
            candidate["required_inputs"].remove("junk_ranker_rows_jsonl")
        elif name == "missing_route_cards_output":
            candidate["required_outputs"].remove("route_cards.jsonl")
        elif name == "missing_blocker_shortcut":
            candidate["blockers"].remove("shortcut_dominance")
        elif name == "missing_blocker_authority":
            candidate["blockers"].remove("authority_open")
        elif name == "missing_keep_bounded_rule":
            candidate["route_source_rules"].pop("KEEP_BOUNDED_DECODER")
        elif name == "materializes_route_cards":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loads_dataset_rows":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "opens_compiler_handoff":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "opens_training":
            candidate["metrics"]["training_authorized"] = True
        elif name == "opens_decoder_ce":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "opens_runtime":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "opens_authority":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate, registry(latest=9999) if name == "bad_registry_frontier" else registry())
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9134)
    design_registry = registry(latest=9133)
    base = build_design(design_registry)
    base_failures = validate_design(base, design_registry)
    negatives = run_negative_cases()
    checks = {
        "source_stage9134_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_inputs_complete": set(REQUIRED_INPUTS).issubset(set(base["required_inputs"])),
        "required_outputs_complete": set(REQUIRED_OUTPUTS).issubset(set(base["required_outputs"])),
        "blockers_complete": set(BLOCKERS).issubset(set(base["blockers"])),
        "route_rules_complete": set(ROUTE_SOURCE_RULES).issubset(set(base["route_source_rules"])),
        "no_route_materialization": base["metrics"]["route_cards_materialized_now"] is False,
        "no_dataset_loading": base["metrics"]["dataset_rows_loaded"] is False,
        "authority_closed": not any(base["authority"].values()),
        "registry_frontier_stage9134": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9134,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(base_failures)
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
            "real_route_cards_used": 0,
            "route_cards_materialized_now": False,
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
        "decision": "Audited real route-card materialization design and rejected missing inputs, missing outputs, missing blockers, route-rule omissions, materialization, dataset loading, compiler handoff, training, decoder CE, runtime, and authority openings.",
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
        "decision": audit["decision"] if audit["passed"] else "Real route-card materialization design audit failed.",
        "next_best_step": "Implement route-card materializer with synthetic fixtures first, then separately authorize real judge/ranker input use.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9135 Real Route-Card Materialization Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
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
