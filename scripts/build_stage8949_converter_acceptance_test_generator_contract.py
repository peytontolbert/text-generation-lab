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
STAGE = 8949
NAME = "stage8949_converter_acceptance_test_generator_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_ACCEPTANCE_TEST_GENERATOR_CONTRACT_STAGE8949.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "converter_acceptance_test_generator_contract.json"
TEST_SPEC_ROWS = OUT_DIR / "converter_acceptance_test_spec_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8948_converter_fixture_only_acceptance_spec.json"
SOURCE_SPEC = ROOT / "runs/local/artifacts/stage8948_converter_fixture_only_acceptance_spec/converter_fixture_only_acceptance_spec.json"

GENERATOR_OUTPUT_FIELDS = [
    "test_spec_id",
    "source_fixture_spec_id",
    "test_name",
    "fixture_type",
    "assertion_contract",
    "forbidden_operations",
    "requires_future_authority_ticket",
    "runnable_now",
]

FORBIDDEN_GENERATOR_OUTPUTS = [
    "python_test_file_written",
    "converter_code_written",
    "checkpoint_path_opened",
    "real_tensor_fixture_embedded",
    "packed_weight_decode_attempted",
    "model_forward_attempted",
    "training_attempted",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def source_acceptance_rows() -> list[dict[str, Any]]:
    spec = load_json(SOURCE_SPEC)
    rows = spec.get("acceptance_spec_rows") or []
    return rows if isinstance(rows, list) else []


def build_test_spec_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        spec_id = str(row.get("spec_id") or "missing_spec_id")
        out.append({
            "test_spec_id": f"test_spec_{spec_id}",
            "source_fixture_spec_id": spec_id,
            "test_name": f"test_contract_{spec_id}",
            "fixture_type": row.get("fixture_type"),
            "assertion_contract": {
                "given": row.get("given"),
                "expect": row.get("expect"),
            },
            "forbidden_operations": list(row.get("forbidden") or []),
            "requires_future_authority_ticket": True,
            "runnable_now": False,
            "writes_test_file_now": False,
            "opens_checkpoint_now": False,
            "reads_real_tensor_now": False,
            "decodes_packed_weight_now": False,
            "runs_model_now": False,
            "trains_now": False,
        })
    return out


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_rows = source_acceptance_rows()
    test_rows = build_test_spec_rows(source_rows)
    checks = {
        "source_stage8948_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "source_fixture_rows_present": len(source_rows) >= 5,
        "test_spec_rows_match_source": len(test_rows) == len(source_rows),
        "generator_output_fields_recorded": len(GENERATOR_OUTPUT_FIELDS) >= 8,
        "forbidden_generator_outputs_recorded": len(FORBIDDEN_GENERATOR_OUTPUTS) >= 7,
        "all_generated_specs_non_runnable": all(row.get("runnable_now") is False for row in test_rows),
        "all_generated_specs_require_future_ticket": all(row.get("requires_future_authority_ticket") is True for row in test_rows),
        "no_generated_test_files": all(row.get("writes_test_file_now") is False for row in test_rows),
        "no_checkpoint_open": all(row.get("opens_checkpoint_now") is False for row in test_rows),
        "no_real_tensor_read": all(row.get("reads_real_tensor_now") is False for row in test_rows),
        "no_packed_decode": all(row.get("decodes_packed_weight_now") is False for row in test_rows),
        "no_model_run": all(row.get("runs_model_now") is False for row in test_rows),
        "no_training": all(row.get("trains_now") is False for row in test_rows),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONVERTER_ACCEPTANCE_TEST_GENERATOR_CONTRACT_ONLY",
        "source_stage": 8948,
        "generator_output_fields": GENERATOR_OUTPUT_FIELDS,
        "forbidden_generator_outputs": FORBIDDEN_GENERATOR_OUTPUTS,
        "checks": checks,
        "metrics": {
            "source_fixture_rows": len(source_rows),
            "test_spec_rows": len(test_rows),
            "python_test_files_written": 0,
            "generated_specs_runnable_now": 0,
            "converter_code_written": False,
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
        "test_spec_rows": test_rows,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Converter acceptance-test generation is recovered only as metadata test-spec rows. No runnable test files, converter code, checkpoint access, tensor reads, packed decode, model execution, runtime, data mining, or training are authorized.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8948, 8949, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "python_test_files_written",
        "generated_specs_runnable_now",
    ]:
        if contract["metrics"].get(key) != 0:
            failures.append(key)
    for key in [
        "converter_code_written",
        "checkpoint_open_authorized",
        "real_tensor_read_authorized",
        "packed_decode_authorized",
        "model_execution_authorized_now",
        "training_authorized",
    ]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    test_rows = contract.pop("test_spec_rows")
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(TEST_SPEC_ROWS, test_rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **contract["metrics"],
        },
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "test_spec_rows": str(TEST_SPEC_ROWS.relative_to(ROOT))},
        "decision": contract["decision"],
        "next_best_step": "Recover converter test-spec promotion gate. It should require an explicit authority ticket before any fixture specs become runnable tests.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8949 Converter Acceptance-Test Generator Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage converts fixture-only acceptance specifications into metadata-only test-spec rows. It writes no runnable test files and does not implement converter code, open checkpoints, read tensors, decode packed weights, run models, train, or mine data.",
        "",
        f"Test spec rows: `{contract['metrics']['test_spec_rows']}`",
        f"Runnable specs now: `{contract['metrics']['generated_specs_runnable_now']}`",
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
    marker = "## Stage8949 Converter Acceptance-Test Generator Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8949 converts fixture-only acceptance specs into metadata-only test-spec rows. It writes no runnable tests and keeps converter implementation, checkpoint access, tensor reads, packed decode, model execution, runtime, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
