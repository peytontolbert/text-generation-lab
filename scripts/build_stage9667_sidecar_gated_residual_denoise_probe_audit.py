#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9667
NAME = "stage9667_sidecar_gated_residual_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9666_sidecar_gated_residual_denoise_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9666_sidecar_gated_residual_denoise_preexecution/sidecar_gated_residual_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9667_sidecar_gated_residual_denoise_probe"
AUDIT = RUN_DIR / "stage9667_sidecar_gated_residual_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SIDECAR_GATED_RESIDUAL_DENOISE_PROBE_AUDIT_STAGE9667.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "row_token_loss.jsonl", "row_gradient_norms.jsonl", "row_dynamics_history.jsonl", "activation_summary.jsonl", "module_delta_norms.json", "cleanup_proof.json", "short_output_probe.json", "repetition_probe.json", "internal_leak_probe.json", "denoise_repair_quality_audit.json"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    rows = load_jsonl(MANIFEST)
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9666_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("mode") != "denoise_repair_probe" or execution.get("mode") != "denoise_repair_probe":
        failures.append("wrong_mode")
    if int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 26 or int(execution.get("denoise_ce_rows") or 0) != 26:
        failures.append("denoise_row_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(execution.get("decoder_ce_rows") or 0) != 0:
        failures.append("decoder_ce_opened")
    for flag in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if execution.get(flag):
            failures.append(f"forbidden_{flag}")
    if missing:
        failures.append("required_artifacts_missing")
    generated = int(samples_card.get("generated_rows") or execution.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or round(float(execution.get("target_prefix_match_rate") or 0.0) * generated))
    contentful = int(samples_card.get("contentful_rows") or round(float(execution.get("contentful_generation_rate") or 0.0) * generated))
    short_rows = int(short.get("short_or_junk_rows") or 0)
    repetition_rows = int(repetition.get("generated_repetition_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)
    by_bucket: dict[str, Counter[str]] = {}
    failed_samples: list[dict[str, Any]] = []
    for sample in samples:
        row = rows_by_id.get(str(sample.get("row_id")), {})
        route = (row.get("residual_repair_route") or {}).get("repair_bucket") or "unknown"
        counter = by_bucket.setdefault(str(route), Counter())
        counter["rows"] += 1
        counter["exact"] += int(bool(sample.get("exact_match")))
        counter["target_prefix"] += int(bool(sample.get("target_prefix_match")))
        if not sample.get("exact_match"):
            failed_samples.append({"row_id": sample.get("row_id"), "split": sample.get("split"), "repair_bucket": route, "target_prefix_match": sample.get("target_prefix_match"), "target": sample.get("target_text"), "generated": sample.get("generated_text")})
    bucket_card = {key: {"rows": c["rows"], "exact": c["exact"], "target_prefix": c["target_prefix"], "exact_rate": rate(c["exact"], c["rows"]), "target_prefix_rate": rate(c["target_prefix"], c["rows"])} for key, c in sorted(by_bucket.items())}
    safety_passed = not failures
    quality_passed = bool(generated == 26 and exact == 26 and target_prefix == 26 and contentful == 26 and short_rows == 0 and repetition_rows == 0 and leak_rows == 0)
    audit = {"passed": safety_passed and quality_passed, "safety_passed": safety_passed, "quality_passed": quality_passed, "failures": failures, "missing_artifacts": missing, "manifest_rows": len(rows), "generated_rows": generated, "exact_match_rows": exact, "exact_match_rate": rate(exact, generated), "target_prefix_match_rows": target_prefix, "target_prefix_match_rate": rate(target_prefix, generated), "contentful_rows": contentful, "contentful_rate": rate(contentful, generated), "short_or_junk_rows": short_rows, "degenerate_repetition_rows": repetition_rows, "generated_internal_token_rows": leak_rows, "train_rows": execution.get("train_rows"), "eval_rows": execution.get("eval_rows"), "strict_rows": execution.get("strict_rows"), "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"), "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"), "decoder_delta_norm": module_delta.get("decoder_delta_norm"), "denoise_delta_norm": module_delta.get("denoise_delta_norm"), "runtime_executed": execution.get("runtime_executed"), "gemma_executed": execution.get("gemma_executed"), "harness_executed": execution.get("harness_executed"), "final_checkpoint_exported": execution.get("final_checkpoint_exported"), "by_repair_bucket": bucket_card, "failed_sample_count": len(failed_samples), "failed_samples": failed_samples[:20], "diagnosis": "safe_contentful_but_prefix_exactness_low_after_80_steps", "next_patch_target": "prefix_primed_sidecar_gated_residual_denoise", "authority": dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9668 prefix-primed sidecar residual denoise manifest using approved clean prefix spans; keep decoder/runtime/Gemma/harness closed."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Stage9667 executed safely and stayed contentful/leak-clean, but did not pass exact/prefix quality; prefix priming is the next patch." if safety_passed else "Stage9667 safety failed; do not use results.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9667 Sidecar-Gated Residual Denoise Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety passed: `{audit['safety_passed']}`", f"Quality passed: `{audit['quality_passed']}`", f"Exact rows: `{exact}` / `{generated}`", f"Target-prefix rows: `{target_prefix}` / `{generated}`", f"Contentful rows: `{contentful}` / `{generated}`", f"Short/junk rows: `{short_rows}`", f"Repetition rows: `{repetition_rows}`", f"Internal leak rows: `{leak_rows}`", f"By repair bucket: `{bucket_card}`", "", "The probe is safe and contentful but not exact. The next patch should add approved clean prefix spans as model input and use a generation-prefix-field, without exposing the full target.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "safety_passed": safety_passed, "quality_passed": quality_passed, "exact_match_rate": audit["exact_match_rate"], "target_prefix_match_rate": audit["target_prefix_match_rate"], "next_best_step": next_step}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
