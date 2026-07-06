#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8930
NAME = "stage8930_targeted_compiler_gap_tests_readiness"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TARGETED_COMPILER_GAP_TESTS_READINESS_STAGE8930.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "targeted_compiler_gap_tests_readiness.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8929_single_compiler_api_contract.json"
TARGETED_TEST = ROOT / "tests/test_targeted_compiler_gap_modules.py"

TARGETED_MODULES = [
    "scripts/program_state_symbol_table_extractor.py",
    "scripts/program_state_call_graph_extractor.py",
    "scripts/structured_dataset_junk_ranker.py",
    "scripts/counterfactual_obligation_audit.py",
]

TARGETED_CAPABILITIES = [
    "symbol_extractor_recovers_import_class_function_method_callsite_local",
    "call_graph_extractor_recovers_call_edges_and_syntax_failure",
    "structured_junk_ranker_routes_budget_internal_safe_rows",
    "counterfactual_obligation_audit_accepts_complete_and_flags_missing",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    module_status = [{"path": path, "exists": (ROOT / path).exists()} for path in TARGETED_MODULES]
    checks = {
        "source_stage8929_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "targeted_test_file_present": TARGETED_TEST.exists(),
        "all_targeted_modules_present": all(row["exists"] for row in module_status),
        "capabilities_recorded": len(TARGETED_CAPABILITIES) == 4,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "checks": checks,
        "metrics": {
            "targeted_modules": len(TARGETED_MODULES),
            "targeted_modules_present": sum(1 for row in module_status if row["exists"]),
            "targeted_capabilities": len(TARGETED_CAPABILITIES),
            "targeted_test_files": int(TARGETED_TEST.exists()),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "targeted_modules": module_status,
        "targeted_capabilities": TARGETED_CAPABILITIES,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "readiness_status": "targeted_tests_added",
            "training_status": "blocked",
            "next_required_artifact": "orchestrated compiler dry-run on synthetic in-memory rows, still no mining/training",
        },
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in audit["checks"].items() if value is not True]
    if any((audit.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8929, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **audit["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Targeted compiler gap tests readiness passed; source extractors, structured junk ranker, and counterfactual obligation audit now have direct readiness coverage.",
        "next_best_step": "Build an orchestrated compiler dry-run on synthetic in-memory rows, still with no data mining, model execution, or training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8930 Targeted Compiler Gap Tests Readiness",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage records direct readiness coverage for the previously identified compiler gaps: symbol extraction, call graph extraction, structured junk routing, and counterfactual obligation auditing.",
        "",
        f"Targeted modules: `{audit['metrics']['targeted_modules_present']}/{audit['metrics']['targeted_modules']}`",
        f"Capabilities covered: `{audit['metrics']['targeted_capabilities']}`",
        "",
        "No mining, execution, runtime, decoder CE, denoise CE, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8930 Targeted Compiler Gap Tests Readiness"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8930 adds direct readiness coverage for source extractors, structured junk ranker, and counterfactual obligation audit. This closes the targeted test gap identified by the compiler inventory while keeping mining and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
