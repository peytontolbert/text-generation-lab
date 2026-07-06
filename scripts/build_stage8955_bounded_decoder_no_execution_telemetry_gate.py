#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.native_probe_interpretability_artifact_contract import BOUNDED_JSON_KEYS, BOUNDED_JSONL_KEYS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from native_probe_interpretability_artifact_contract import BOUNDED_JSON_KEYS, BOUNDED_JSONL_KEYS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8955
NAME = "stage8955_bounded_decoder_no_execution_telemetry_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_NO_EXECUTION_TELEMETRY_GATE_STAGE8955.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "bounded_decoder_no_execution_telemetry_gate.json"
SOURCE_STAGE = ROOT / "runs/summaries/stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh.json"
TELEMETRY_MODULE = ROOT / "scripts/native_probe_interpretability_artifact_contract.py"
TELEMETRY_TEST = ROOT / "tests/test_native_probe_interpretability_artifact_contract.py"

MANDATORY_FAILURE_MODES = [
    "missing_artifact",
    "empty_jsonl_artifact",
    "missing_required_keys",
    "row_token_loss_without_per_position_loss",
    "json_artifact_not_object",
    "invalid_json",
    "invalid_jsonl",
]

GATED_BEFORE_EXECUTION = [
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "row_dynamics_history.jsonl",
    "module_delta_norms.json",
    "internal_token_logit_summary.json",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_gate(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_STAGE)
    module_text = TELEMETRY_MODULE.read_text(encoding="utf-8") if TELEMETRY_MODULE.exists() else ""
    test_text = TELEMETRY_TEST.read_text(encoding="utf-8") if TELEMETRY_TEST.exists() else ""
    required_jsonl = sorted(BOUNDED_JSONL_KEYS)
    required_json = sorted(BOUNDED_JSON_KEYS)
    all_required = set(required_jsonl) | set(required_json)
    checks = {
        "source_stage8954_passed": source.get("passed") is True,
        "telemetry_module_exists": TELEMETRY_MODULE.exists(),
        "telemetry_test_exists": TELEMETRY_TEST.exists(),
        "bounded_jsonl_artifacts_recorded": len(required_jsonl) >= 6,
        "bounded_json_artifacts_recorded": len(required_json) >= 9,
        "gated_before_execution_artifacts_covered": set(GATED_BEFORE_EXECUTION).issubset(all_required),
        "row_token_loss_requires_positions": "row_token_loss.jsonl positions must contain per-position loss" in module_text,
        "jsonl_empty_failure_present": "empty jsonl artifact" in module_text,
        "missing_artifact_failure_present": "missing artifact" in module_text,
        "native_test_covers_bounded_token_positions": "test_bounded_artifact_contract_requires_real_token_positions" in test_text,
        "mandatory_failure_modes_recorded": len(MANDATORY_FAILURE_MODES) >= 7,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8954": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8954,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BOUNDED_DECODER_TELEMETRY_GATE_NO_EXECUTION",
        "source_stage": 8954,
        "required_bounded_jsonl_artifacts": {name: sorted(keys) for name, keys in BOUNDED_JSONL_KEYS.items()},
        "required_bounded_json_artifacts": {name: sorted(keys) for name, keys in BOUNDED_JSON_KEYS.items()},
        "gated_before_execution": GATED_BEFORE_EXECUTION,
        "mandatory_failure_modes": MANDATORY_FAILURE_MODES,
        "checks": checks,
        "metrics": {
            "required_bounded_jsonl_artifacts": len(required_jsonl),
            "required_bounded_json_artifacts": len(required_json),
            "gated_before_execution_artifacts": len(GATED_BEFORE_EXECUTION),
            "mandatory_failure_modes": len(MANDATORY_FAILURE_MODES),
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Bounded decoder CE cannot receive an execution ticket unless telemetry artifact gates are present and future probe outputs are non-empty/schema-complete. This stage records the no-execution telemetry gate only; it does not run a probe, model, converter, runtime, mining, decoder CE, denoise CE, or training.",
    }


def validate_gate(gate: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in gate["checks"].items() if value is not True]
    if any((gate.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8954, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized"]:
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
        "next_best_step": "Recover the explicit one-run authorization review schema for a future tiny bounded decoder CE probe; keep execution and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8955 Bounded Decoder No-Execution Telemetry Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records the telemetry artifacts that must exist and be non-empty/schema-complete before any future tiny bounded decoder CE execution ticket can be considered.",
        "",
        f"Required JSONL artifacts: `{gate['metrics']['required_bounded_jsonl_artifacts']}`",
        f"Required JSON artifacts: `{gate['metrics']['required_bounded_json_artifacts']}`",
        f"Actual execution authorized next: `{gate['metrics']['actual_execution_authorized_next']}`",
        "",
        "No model execution, converter execution, runtime, mining, decoder CE, denoise CE, checkpoint export, or training is authorized.",
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
    marker = "## Stage8955 Bounded Decoder No-Execution Telemetry Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8955 records mandatory bounded decoder CE telemetry gates. Future probe outputs must include non-empty/schema-complete token loss, gradient, activation, dynamics, EOS/length, leak, repetition, sample, module-delta, cleanup, and failure-bucket artifacts before any execution result can be trusted.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
