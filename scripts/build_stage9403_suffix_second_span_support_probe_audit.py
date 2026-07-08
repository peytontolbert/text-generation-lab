#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9403
NAME = "stage9403_suffix_second_span_support_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9402_suffix_second_span_support_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9403_suffix_second_span_support_probe"
AUDIT = RUN_DIR / "stage9403_suffix_second_span_support_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_SECOND_SPAN_SUPPORT_PROBE_AUDIT_STAGE9403.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "row_token_loss.jsonl", "row_gradient_norms.jsonl", "row_dynamics_history.jsonl", "activation_summary.jsonl", "module_delta_norms.json", "cleanup_proof.json", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    rep = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    rows = samples.get("samples") if isinstance(samples.get("samples"), list) else []
    by_split = Counter()
    exact_by_split = Counter()
    prefix_by_split = Counter()
    boundary_by_split = Counter()
    for row in rows:
        split = str(row.get("split"))
        by_split[split] += 1
        exact_by_split[split] += int(bool(row.get("exact_match")))
        prefix_by_split[split] += int(bool(row.get("target_prefix_match")))
        boundary_by_split[split] += int(bool((row.get("boundary_next_token") or {}).get("match")))
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9402_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 43 or execution.get("denoise_ce_rows") != 43:
        failures.append("denoise_ce_row_count_mismatch")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    generated = int(samples.get("generated_rows") or 0)
    short_rows = int(short.get("short_or_junk_rows") or 0)
    rep_rows = int(rep.get("generated_repetition_rows") or 0)
    unterminated = int(rep.get("unterminated_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)
    heldout_rows = by_split["eval"] + by_split["strict_eval"]
    heldout_exact = exact_by_split["eval"] + exact_by_split["strict_eval"]
    heldout_prefix = prefix_by_split["eval"] + prefix_by_split["strict_eval"]
    heldout_boundary = boundary_by_split["eval"] + boundary_by_split["strict_eval"]
    safety_gate_passed = not failures
    quality_gate_passed = bool(
        generated == 43
        and exact_by_split["train"] == by_split["train"] == 27
        and heldout_exact == heldout_rows == 16
        and heldout_prefix == heldout_rows
        and heldout_boundary == heldout_rows
        and short_rows == rep_rows == unterminated == leak_rows == 0
    )
    audit = {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": generated,
        "by_split": dict(sorted(by_split.items())),
        "exact_by_split": dict(sorted(exact_by_split.items())),
        "prefix_by_split": dict(sorted(prefix_by_split.items())),
        "boundary_by_split": dict(sorted(boundary_by_split.items())),
        "heldout_rows": heldout_rows,
        "heldout_exact_rows": heldout_exact,
        "heldout_prefix_rows": heldout_prefix,
        "heldout_boundary_rows": heldout_boundary,
        "short_or_junk_rows": short_rows,
        "degenerate_repetition_rows": rep_rows,
        "unterminated_rows": unterminated,
        "generated_internal_token_rows": leak_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Rejoin second-span suffix support into bounded decoder repair path." if audit["quality_gate_passed"] else "Inspect Stage9403 residuals and decide whether the support rows caused interference or still lack exact suffix coverage."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited second-span suffix support probe; decoder CE remains closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9403 Suffix Second-Span Support Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety gate passed: `{audit['safety_gate_passed']}`", f"Quality gate passed: `{audit['quality_gate_passed']}`", f"Exact by split: `{audit['exact_by_split']}`", f"Heldout exact rows: `{heldout_exact}` / `{heldout_rows}`", f"Boundary by split: `{audit['boundary_by_split']}`", f"Short/junk rows: `{short_rows}`", f"Repetition rows: `{rep_rows}`", f"Unterminated rows: `{unterminated}`", f"Leak rows: `{leak_rows}`", "", "Decoder CE and external authority remain closed.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"safety": safety_gate_passed, "quality": quality_gate_passed, "heldout_exact": f"{heldout_exact}/{heldout_rows}"}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
