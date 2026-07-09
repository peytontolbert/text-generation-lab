#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9602
NAME = "stage9602_two_phase_in_memory_wrapper_static_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9601_two_phase_trainer_contract_audit.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "two_phase_in_memory_wrapper_static_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TWO_PHASE_IN_MEMORY_WRAPPER_STATIC_AUDIT_STAGE9602.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    trainer = TRAINER.read_text(encoding="utf-8")
    loop = LOOP.read_text(encoding="utf-8")
    checks = {
        "source_stage_passed": source.get("passed") is True,
        "mode_supported": '"two_phase_suffix_denoise_reconnect_probe"' in trainer,
        "phase2_manifest_arg_present": '"--phase2-manifest"' in trainer,
        "phase2_caps_present": '"--phase2-max-train-rows"' in trainer and '"--phase2-max-decoder-tokens"' in trainer,
        "contract_validator_present": "validate_two_phase_suffix_denoise_reconnect_probe" in trainer,
        "execution_dispatch_present": "run_two_phase_suffix_denoise_reconnect_probe" in trainer,
        "loop_function_present": "def run_two_phase_suffix_denoise_reconnect_probe" in loop,
        "runtime_state_return_present": 'return_runtime_state=True' in loop,
        "phase2_model_override_present": "model_override=model" in loop,
        "phase2_tokenizer_override_present": "tokenizer_override=tokenizer" in loop,
        "checkpoint_export_blocked": '"checkpoint_export_allowed_between_phases": False' in loop,
        "decoder_ce_zero_contract": "two-phase suffix/denoise reconnect requires --decoder-ce-weight 0" in trainer,
    }
    failures = [name for name, passed in checks.items() if not passed]
    audit = {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "model_execution_authorized_next": False,
        "nonzero_execution_authorized": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run a tiny authorized two-phase target_100M reconnect probe and audit phase1 exactness plus phase2 generation quality."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Static audit passed for the in-memory two-phase suffix-choice plus residual-denoise trainer wrapper.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9602 Two-Phase In-Memory Wrapper Static Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Failures: `{failures}`",
        "",
        "The trainer now exposes and dispatches an in-memory two-phase reconnect wrapper. Execution remains closed until the next explicit tiny probe stage.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
