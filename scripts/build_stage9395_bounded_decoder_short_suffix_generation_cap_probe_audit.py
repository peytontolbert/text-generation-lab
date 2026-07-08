#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9395
NAME = "stage9395_bounded_decoder_short_suffix_generation_cap_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9394_bounded_decoder_short_suffix_generation_cap_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9395_bounded_decoder_short_suffix_generation_cap_probe"
AUDIT = RUN_DIR / "stage9395_bounded_decoder_short_suffix_generation_cap_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_SHORT_SUFFIX_GENERATION_CAP_PROBE_AUDIT_STAGE9395.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "row_token_loss.jsonl", "row_gradient_norms.jsonl", "row_dynamics_history.jsonl", "activation_summary.jsonl", "module_delta_norms.json", "cleanup_proof.json", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def update_registry(summary: dict) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit_run() -> dict:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9394_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("max_generation_tokens") != 64:
        failures.append("generation_cap_not_64")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 23 or execution.get("denoise_ce_rows") != 23:
        failures.append("denoise_ce_row_count_mismatch")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    generated = int(samples.get("generated_rows") or 0)
    exact = int(samples.get("exact_match_rows") or 0)
    prefix = int(samples.get("target_prefix_match_rows") or 0)
    boundary = int(samples.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples.get("contentful_rows") or 0)
    short_rows = int(short.get("short_or_junk_rows") or 0)
    repetition_rows = int(repetition.get("generated_repetition_rows") or 0)
    unterminated = int(repetition.get("unterminated_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)
    safety_gate_passed = not failures
    quality_gate_passed = bool(generated == 23 and exact == 23 and prefix == 23 and boundary == 23 and contentful == 23 and short_rows == 0 and repetition_rows == 0 and unterminated == 0 and leak_rows == 0)
    return {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": prefix,
        "target_prefix_match_rate": samples.get("target_prefix_match_rate"),
        "boundary_next_token_match_rows": boundary,
        "boundary_next_token_match_rate": samples.get("boundary_next_token_match_rate"),
        "contentful_rows": contentful,
        "contentful_rate": samples.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "degenerate_repetition_rows": repetition_rows,
        "unterminated_rows": unterminated,
        "generated_internal_token_rows": leak_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_run()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Rejoin target-resolved short-suffix bridge into bounded decoder repair path." if audit["quality_gate_passed"] else "Inspect generation-cap residuals; if train rows still pass but eval fails, add heldout contrastive suffix support before widening."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited the short-suffix generation-cap rerun; decoder CE remains closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9395 Bounded Decoder Short-Suffix Generation-Cap Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety gate passed: `{audit['safety_gate_passed']}`", f"Quality gate passed: `{audit['quality_gate_passed']}`", f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`", f"Target-prefix rows: `{audit['target_prefix_match_rows']}` / `{audit['generated_rows']}`", f"Boundary next-token rows: `{audit['boundary_next_token_match_rows']}` / `{audit['generated_rows']}`", f"Contentful rows: `{audit['contentful_rows']}` / `{audit['generated_rows']}`", f"Unterminated rows: `{audit['unterminated_rows']}`", f"Short/junk rows: `{audit['short_or_junk_rows']}`", f"Leak rows: `{audit['generated_internal_token_rows']}`", "", "Decoder CE and external authority remain closed.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "unterminated_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
