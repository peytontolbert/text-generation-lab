#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage8949_converter_acceptance_test_generator_contract import (
        FORBIDDEN_GENERATOR_OUTPUTS,
        GENERATOR_OUTPUT_FIELDS,
        build_test_spec_rows,
        source_acceptance_rows,
        write_jsonl,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage8949_converter_acceptance_test_generator_contract import (  # type: ignore
        FORBIDDEN_GENERATOR_OUTPUTS,
        GENERATOR_OUTPUT_FIELDS,
        build_test_spec_rows,
        source_acceptance_rows,
        write_jsonl,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8952
NAME = "stage8952_registry_independent_acceptance_generator_recovery"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_INDEPENDENT_ACCEPTANCE_GENERATOR_RECOVERY_STAGE8952.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "registry_independent_acceptance_generator_recovery.json"
TEST_SPEC_ROWS = OUT_DIR / "converter_acceptance_test_spec_rows_registry_independent.jsonl"
STABLE_SOURCE_SUMMARY = ROOT / "runs/summaries/stage8948_converter_fixture_only_acceptance_spec.json"
STALE_FRONTIER_STAGES = [8949, 8950, 8951]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def stale_frontier_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in STALE_FRONTIER_STAGES:
        paths = list((ROOT / "runs/summaries").glob(f"stage{stage}_*.json"))
        for path in paths:
            data = load_json(path)
            failures = (data.get("metrics") or {}).get("failures") or []
            rows.append({
                "stage": stage,
                "stage_name": data.get("stage_name"),
                "path": str(path),
                "passed": data.get("passed") is True,
                "failures": failures,
                "frontier_only_failure": failures and all(str(failure).startswith("unexpected_registry_frontier:") for failure in failures),
            })
    return rows


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_rows = source_acceptance_rows()
    test_rows = build_test_spec_rows(source_rows)
    stale_rows = stale_frontier_rows()
    checks = {
        "stable_source_stage8948_passed": load_json(STABLE_SOURCE_SUMMARY).get("passed") is True,
        "source_fixture_rows_present": len(source_rows) >= 5,
        "test_spec_rows_match_source": len(test_rows) == len(source_rows),
        "generator_output_fields_recorded": len(GENERATOR_OUTPUT_FIELDS) >= 8,
        "forbidden_generator_outputs_recorded": len(FORBIDDEN_GENERATOR_OUTPUTS) >= 7,
        "stale_frontier_loop_documented": len(stale_rows) >= 2,
        "stale_failures_are_frontier_only": all(row["frontier_only_failure"] for row in stale_rows if row["failures"]),
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
        "status": "REGISTRY_INDEPENDENT_ACCEPTANCE_GENERATOR_RECOVERY",
        "stable_source_stage": 8948,
        "stale_frontier_rows": stale_rows,
        "generator_output_fields": GENERATOR_OUTPUT_FIELDS,
        "forbidden_generator_outputs": FORBIDDEN_GENERATOR_OUTPUTS,
        "checks": checks,
        "metrics": {
            "source_fixture_rows": len(source_rows),
            "test_spec_rows": len(test_rows),
            "stale_frontier_rows": len(stale_rows),
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
        "decision": "Converter acceptance-test generation is recovered from the stable Stage8948 fixture source without trusting the mutable registry latest pointer. The stage records prior stale-frontier failures as registry hygiene issues and emits only metadata test-spec rows.",
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in ["python_test_files_written", "generated_specs_runnable_now"]:
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
    failures = validate_contract(contract)
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
        "next_best_step": "Recover converter test-spec promotion gate. It must be registry-independent and require an explicit future authority ticket before specs become runnable.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8952 Registry-Independent Acceptance Generator Recovery",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage recovers converter acceptance-test generation from the stable Stage8948 fixture source without relying on the mutable registry latest pointer. It emits metadata-only test-spec rows and records stale-frontier failures as registry hygiene, not execution readiness.",
        "",
        f"Test spec rows: `{contract['metrics']['test_spec_rows']}`",
        f"Stale frontier rows: `{contract['metrics']['stale_frontier_rows']}`",
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
    marker = "## Stage8952 Registry-Independent Acceptance Generator Recovery"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8952 recovers metadata-only converter acceptance-test generation from stable fixture specs without trusting the mutable registry latest pointer. Runtime, checkpoint access, converter execution, model execution, mining, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
