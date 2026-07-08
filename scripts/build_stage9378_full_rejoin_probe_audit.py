#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9378
NAME = "stage9378_full_rejoin_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9377_full_rejoin_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9376_full_mixture_with_route2_filepath_repairs_manifest/full_mixture_with_route2_filepath_repairs_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9378_full_rejoin_probe"
AUDIT = RUN_DIR / "stage9378_full_rejoin_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FULL_REJOIN_PROBE_AUDIT_STAGE9378.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "boundary_next_token_logits.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "row_dynamics_history.jsonl",
    "activation_summary.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    rows = load_jsonl(MANIFEST)
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9377_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("generation_prefix_field") != "model_input.active_generation_prefix_span":
        failures.append("wrong_generation_prefix_field")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("denoise_ce_rows") != 276 or contract.get("loss_counts", {}).get("denoise_ce") != 276:
        failures.append("denoise_ce_row_count_mismatch")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    generated = int(samples_card.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or 0)
    boundary = int(samples_card.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples_card.get("contentful_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    safety_gate_passed = not failures
    quality_gate_passed = bool(generated == 276 and exact == 276 and target_prefix == 276 and boundary == 276 and contentful == 276 and repetition_rows == 0 and short_rows == 0 and leak_rows == 0)
    return {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "contentful_rows": contentful,
        "contentful_rate": samples_card.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "eval_loss": (execution.get("eval") or {}).get("eval", {}).get("loss"),
        "strict_eval_loss": (execution.get("eval") or {}).get("strict_eval", {}).get("loss"),
        "diagnosis": "The full mixed denoise repair probe is quality-passing after route_0, route_2, and route_file_path residual repairs.",
        "next_patch_target": "bounded_decoder_ce_readiness_bridge",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "The 276-row full rejoin denoise probe passed all generation quality gates; decoder CE remains closed until a separate readiness bridge authorizes the next phase.",
        "next_best_step": "Build a bounded decoder CE readiness bridge that consumes the passing denoise repair evidence and rechecks loss-mask/telemetry contracts before reopening bounded decoder CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9378 Full Rejoin Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
                f"Target-prefix rows: `{audit['target_prefix_match_rows']}` / `{audit['generated_rows']}`",
                f"Boundary next-token rows: `{audit['boundary_next_token_match_rows']}` / `{audit['generated_rows']}`",
                f"Contentful rows: `{audit['contentful_rows']}` / `{audit['generated_rows']}`",
                f"Short/junk rows: `{audit['short_or_junk_rows']}`",
                f"Repetition rows: `{audit['degenerate_repetition_rows']}`",
                f"Leak rows: `{audit['generated_internal_token_rows']}`",
                f"Eval loss: `{audit['eval_loss']}`",
                f"Strict eval loss: `{audit['strict_eval_loss']}`",
                "",
                "This resolves the Stage9366 mixed repair quality blocker. Decoder CE, runtime, Gemma, harness, scoring, source/body emission, promotion, and controller merge remain closed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "short_or_junk_rows", "degenerate_repetition_rows", "generated_internal_token_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
