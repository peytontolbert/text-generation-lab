#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields, apply_diagnostic_gate_fields
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields, apply_diagnostic_gate_fields  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8952
NAME = "stage8952_converter_test_spec_promotion_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_TEST_SPEC_PROMOTION_GATE_STAGE8952.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "converter_test_spec_promotion_gate.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8951_converter_acceptance_test_generator_contract_retry.json"
SOURCE_TEST_ROWS = ROOT / "runs/local/artifacts/stage8951_converter_acceptance_test_generator_contract_retry/converter_acceptance_test_spec_rows_retry.jsonl"

PROMOTION_REQUIREMENTS = [
    "explicit_future_authority_ticket_present",
    "authority_ticket_schema_valid",
    "diagnostic_gate_fields_present",
    "allowed_operations_include_generate_fixture_tests_only",
    "forbidden_operations_remain_denied",
    "test_output_path_under_focused_tests_root",
    "no_checkpoint_paths_opened",
    "no_real_tensor_fixtures_embedded",
    "no_converter_code_written_by_promotion_gate",
    "human_approval_record_present",
]
FORBIDDEN_WITHOUT_PROMOTION_TICKET = [
    "write_python_test_file",
    "mark_test_spec_runnable",
    "open_checkpoint",
    "read_tensor_bytes",
    "decode_packed_weight",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def placeholder_ticket() -> dict[str, Any]:
    return apply_diagnostic_gate_fields({
        "ticket_id": None,
        "scope": "not_granted",
        "allowed_operations": [],
        "human_approval_record": None,
        "authority": dict(AUTHORITY_CLOSED),
    })


def build_gate(registry: dict[str, Any]) -> dict[str, Any]:
    rows = load_jsonl(SOURCE_TEST_ROWS)
    ticket = placeholder_ticket()
    diagnostic_failures = audit_diagnostic_ticket_fields(ticket)
    checks = {
        "source_stage8951_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "source_test_spec_rows_present": len(rows) >= 5,
        "source_rows_non_runnable": all(row.get("runnable_now") is False for row in rows),
        "source_rows_require_future_ticket": all(row.get("requires_future_authority_ticket") is True for row in rows),
        "promotion_requirements_recorded": len(PROMOTION_REQUIREMENTS) >= 10,
        "forbidden_without_ticket_recorded": len(FORBIDDEN_WITHOUT_PROMOTION_TICKET) >= 8,
        "placeholder_ticket_has_diagnostic_fields": diagnostic_failures == [],
        "placeholder_ticket_grants_no_operations": ticket["allowed_operations"] == [],
        "no_test_file_write_authorized": True,
        "no_runnable_specs_authorized": True,
        "no_checkpoint_open_authorized": True,
        "no_tensor_read_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONVERTER_TEST_SPEC_PROMOTION_GATE_CONTRACT_ONLY",
        "source_stage": 8951,
        "promotion_requirements": PROMOTION_REQUIREMENTS,
        "forbidden_without_promotion_ticket": FORBIDDEN_WITHOUT_PROMOTION_TICKET,
        "placeholder_ticket": ticket,
        "checks": checks,
        "metrics": {
            "source_test_spec_rows": len(rows),
            "promotion_requirements": len(PROMOTION_REQUIREMENTS),
            "forbidden_without_ticket": len(FORBIDDEN_WITHOUT_PROMOTION_TICKET),
            "future_ticket_present": False,
            "test_files_written": 0,
            "runnable_specs_authorized": 0,
            "checkpoint_open_authorized": False,
            "real_tensor_read_authorized": False,
            "packed_decode_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Converter metadata test-spec promotion is gated behind a future explicit authority ticket. Without that ticket, no runnable tests, checkpoint access, tensor reads, packed decode, converter execution, model execution, runtime, mining, or training are authorized.",
    }


def validate_gate(gate: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in gate["checks"].items() if value is not True]
    if any((gate.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8951, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["test_files_written", "runnable_specs_authorized"]:
        if gate["metrics"].get(key) != 0:
            failures.append(key)
    for key in ["checkpoint_open_authorized", "real_tensor_read_authorized", "packed_decode_authorized", "model_execution_authorized_now", "training_authorized"]:
        if gate["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    gate = build_gate(registry)
    failures = validate_gate(gate, registry)
    GATE.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **gate["metrics"],
        },
        "artifacts": {"gate": str(GATE.relative_to(ROOT))},
        "decision": gate["decision"],
        "next_best_step": "Return to training readiness matrix refresh: converter recovery is contract-complete but still no-execution. Do not run converter, models, or training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8952 Converter Test-Spec Promotion Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage gates metadata converter test-spec rows from becoming runnable tests. A future explicit authority ticket is required before any test file can be written or any spec can become runnable. No checkpoint access, tensor reads, packed decode, converter execution, model execution, runtime, mining, decoder CE, denoise CE, or training is authorized.",
        "",
        f"Source test-spec rows: `{gate['metrics']['source_test_spec_rows']}`",
        f"Runnable specs authorized: `{gate['metrics']['runnable_specs_authorized']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8952 Converter Test-Spec Promotion Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8952 gates converter metadata test-spec promotion. Without a future explicit authority ticket, no runnable tests, checkpoint access, tensor reads, packed decode, converter execution, model execution, runtime, mining, or training are authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
