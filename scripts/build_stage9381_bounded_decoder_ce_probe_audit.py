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
STAGE = 9381
NAME = "stage9381_bounded_decoder_ce_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9380_bounded_decoder_ce_preexecution.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9381_bounded_decoder_ce_probe"
AUDIT = RUN_DIR / "stage9381_bounded_decoder_ce_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_CE_PROBE_AUDIT_STAGE9381.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "row_dynamics_history.jsonl",
    "activation_summary.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "failure_bucket_card.json",
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
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    short_probe = load_json(RUN_DIR / "short_output_probe.json")
    repetition_probe = load_json(RUN_DIR / "repetition_probe.json")
    leak_probe = load_json(RUN_DIR / "internal_leak_probe.json")
    failure_card = load_json(RUN_DIR / "failure_bucket_card.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    loss_steps = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    eval_losses = load_jsonl(RUN_DIR / "eval_loss_by_checkpoint.jsonl")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9380_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("loss_counts", {}).get("decoder_ce") != 64:
        failures.append("decoder_ce_row_count_mismatch")
    if any((contract.get("loss_counts", {}) or {}).get(key, 0) for key in ["denoise_ce", "runtime_reward", "build_mode_ce", "symbol_binding_ce", "patch_operator_ce"]):
        failures.append("forbidden_loss_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if cleanup.get("cleanup_executed") is not False:
        failures.append("unexpected_cleanup_execution")
    if missing:
        failures.append("required_artifacts_missing")

    generated = int(samples.get("generated_rows") or 0)
    exact = int(samples.get("exact_match_rows") or 0)
    contentful = int(samples.get("contentful_rows") or 0)
    prefix = int(samples.get("target_prefix_match_rows") or 0)
    short_rows = int(short_probe.get("short_or_junk_rows") or 0)
    repetition_rows = int(repetition_probe.get("generated_repetition_rows") or 0)
    leak_rows = int(leak_probe.get("generated_internal_token_rows") or 0)
    unterminated_rows = int(samples.get("unterminated_rows") or repetition_probe.get("unterminated_rows") or 0)
    first = float(loss_steps[0]["loss"]) if loss_steps else None
    last = float(loss_steps[-1]["loss"]) if loss_steps else None
    eval_by_split = {row.get("split"): row.get("loss") for row in eval_losses}
    safety_gate_passed = not failures and generated == 16 and leak_rows == 0 and short_rows == 0
    quality_gate_passed = bool(
        safety_gate_passed
        and contentful >= 12
        and prefix >= 8
        and repetition_rows == 0
        and unterminated_rows == 0
        and exact >= 4
    )
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
        "contentful_rows": contentful,
        "contentful_rate": samples.get("contentful_rate"),
        "short_or_junk_rows": short_rows,
        "generated_internal_token_rows": leak_rows,
        "degenerate_repetition_rows": repetition_rows,
        "degenerate_repetition_rate": repetition_probe.get("degenerate_repetition_rate"),
        "unterminated_rows": unterminated_rows,
        "unterminated_rate": samples.get("unterminated_rate"),
        "failure_buckets": failure_card.get("buckets", {}),
        "train_loss_first": first,
        "train_loss_last": last,
        "train_loss_drop": (first - last) if first is not None and last is not None else None,
        "eval_loss": eval_by_split.get("eval") or (execution.get("eval", {}).get("eval", {}) if isinstance(execution.get("eval"), dict) else {}).get("loss"),
        "strict_eval_loss": eval_by_split.get("strict_eval") or (execution.get("eval", {}).get("strict_eval", {}) if isinstance(execution.get("eval"), dict) else {}).get("loss"),
        "diagnosis": "The fresh bounded decoder CE probe executed safely but remains quality-blocked by degenerate repetition and unterminated generation.",
        "next_patch_target": "bounded_decoder_generation_failure_to_denoise_manifest",
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
        "decision": "The bounded decoder CE probe was execution-safe but failed quality gates; do not scale decoder CE yet.",
        "next_best_step": "Build a bounded decoder generation-failure-to-denoise manifest from Stage9381 repetition/unterminated rows; keep decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9381 Bounded Decoder CE Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
                f"Contentful rows: `{audit['contentful_rows']}` / `{audit['generated_rows']}`",
                f"Target-prefix rows: `{audit['target_prefix_match_rows']}` / `{audit['generated_rows']}`",
                f"Repetition rows: `{audit['degenerate_repetition_rows']}`",
                f"Unterminated rows: `{audit['unterminated_rows']}`",
                f"Short/junk rows: `{audit['short_or_junk_rows']}`",
                f"Leak rows: `{audit['generated_internal_token_rows']}`",
                f"Eval loss: `{audit['eval_loss']}`",
                f"Strict eval loss: `{audit['strict_eval_loss']}`",
                "",
                "Decoder CE reopened only for the tiny audited probe. The result is not quality-passing, so the next step returns failures to denoise repair rather than scaling CE.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "contentful_rate", "target_prefix_match_rate", "degenerate_repetition_rate", "unterminated_rate", "generated_internal_token_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
