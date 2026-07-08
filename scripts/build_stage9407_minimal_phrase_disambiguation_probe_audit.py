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
STAGE = 9407
NAME = "stage9407_minimal_phrase_disambiguation_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9406_minimal_phrase_disambiguation_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9407_minimal_phrase_disambiguation_probe"
AUDIT = RUN_DIR / "stage9407_minimal_phrase_disambiguation_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MINIMAL_PHRASE_DISAMBIGUATION_PROBE_AUDIT_STAGE9407.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "row_token_loss.jsonl", "row_gradient_norms.jsonl", "row_dynamics_history.jsonl", "activation_summary.jsonl", "module_delta_norms.json", "cleanup_proof.json", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_target_pair(row: dict) -> bool:
    target = str(row.get("target_text") or "")
    return "expected assertion behavior" in target or "current repair invariant" in target


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
    pair_rows = 0
    pair_exact = 0
    pair_boundary = 0
    for row in rows:
        split = str(row.get("split"))
        by_split[split] += 1
        exact_by_split[split] += int(bool(row.get("exact_match")))
        if split in {"eval", "strict_eval"} and is_target_pair(row):
            pair_rows += 1
            pair_exact += int(bool(row.get("exact_match")))
            pair_boundary += int(bool((row.get("boundary_next_token") or {}).get("match")))
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9406_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if contract.get("loss_counts", {}).get("denoise_ce") != 33 or execution.get("denoise_ce_rows") != 33:
        failures.append("denoise_ce_row_count_mismatch")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    short_rows = int(short.get("short_or_junk_rows") or 0)
    rep_rows = int(rep.get("generated_repetition_rows") or 0)
    unterminated = int(rep.get("unterminated_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)
    safety_gate_passed = not failures
    quality_gate_passed = bool(
        safety_gate_passed
        and pair_rows == 4
        and pair_exact == 4
        and pair_boundary == 4
        and short_rows == rep_rows == unterminated == leak_rows == 0
    )
    audit = {
        "passed": safety_gate_passed and quality_gate_passed,
        "safety_gate_passed": safety_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": int(samples.get("generated_rows") or 0),
        "by_split": dict(sorted(by_split.items())),
        "exact_by_split": dict(sorted(exact_by_split.items())),
        "target_pair_heldout_rows": pair_rows,
        "target_pair_heldout_exact_rows": pair_exact,
        "target_pair_heldout_boundary_rows": pair_boundary,
        "short_or_junk_rows": short_rows,
        "degenerate_repetition_rows": rep_rows,
        "unterminated_rows": unterminated,
        "generated_internal_token_rows": leak_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If no global regression, continue one residual pair at a time from Stage9397 basis." if audit["quality_gate_passed"] else "Inspect Stage9407 target-pair residuals before adding any further support."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited minimal phrase-disambiguation probe; decoder CE remains closed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9407 Minimal Phrase Disambiguation Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety gate passed: `{audit['safety_gate_passed']}`", f"Quality gate passed: `{audit['quality_gate_passed']}`", f"Target-pair heldout exact: `{pair_exact}` / `{pair_rows}`", f"Exact by split: `{audit['exact_by_split']}`", f"Short/junk rows: `{short_rows}`", f"Repetition rows: `{rep_rows}`", f"Unterminated rows: `{unterminated}`", f"Leak rows: `{leak_rows}`", "", "Decoder CE and external authority remain closed.", ""]), encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    reg_rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    reg_rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    reg_rows = sorted(reg_rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = reg_rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(reg_rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"safety": safety_gate_passed, "quality": quality_gate_passed, "target_pair_exact": f"{pair_exact}/{pair_rows}"}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
