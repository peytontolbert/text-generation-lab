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
STAGE = 9306
NAME = "stage9306_supported_suffix_boundary_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9305_supported_suffix_boundary_probe_preexecution.json"
BASELINE_SUMMARY = ROOT / "runs/summaries/stage9303_causal_mask_boundary_probe_audit.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9306_supported_suffix_boundary_probe"
AUDIT = RUN_DIR / "stage9306_supported_suffix_boundary_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUPPORTED_SUFFIX_BOUNDARY_PROBE_AUDIT_STAGE9306.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "cleanup_proof.json"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _boundary_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [int(row["expected_rank"]) for row in rows if row.get("expected_rank") is not None]
    matches = [row for row in rows if row.get("match")]
    by_split: dict[str, dict[str, Any]] = {}
    for row in rows:
        split = str(row.get("split") or "unknown")
        bucket = by_split.setdefault(split, {"rows": 0, "matches": 0, "ranks": []})
        bucket["rows"] += 1
        bucket["matches"] += int(bool(row.get("match")))
        if row.get("expected_rank") is not None:
            bucket["ranks"].append(int(row["expected_rank"]))
    return {
        "rows": len(rows),
        "matches": len(matches),
        "match_rate": len(matches) / len(rows) if rows else None,
        "mean_expected_rank": sum(ranks) / len(ranks) if ranks else None,
        "min_expected_rank": min(ranks) if ranks else None,
        "max_expected_rank": max(ranks) if ranks else None,
        "split_summary": {
            split: {
                "rows": int(data["rows"]),
                "matches": int(data["matches"]),
                "mean_expected_rank": sum(data["ranks"]) / len(data["ranks"]) if data["ranks"] else None,
                "min_expected_rank": min(data["ranks"]) if data["ranks"] else None,
                "max_expected_rank": max(data["ranks"]) if data["ranks"] else None,
            }
            for split, data in by_split.items()
        },
    }


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE_SUMMARY)
    baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    boundary_rows = load_jsonl(RUN_DIR / "boundary_next_token_logits.jsonl")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9305_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if missing:
        failures.append("required_artifacts_missing")
    boundary = _boundary_summary(boundary_rows)
    train_loss_start = float(losses[0]["loss"]) if losses else None
    train_loss_end = float(losses[-1]["loss"]) if losses else None
    baseline_match_rate = baseline_metrics.get("boundary_match_rate")
    baseline_mean_rank = baseline_metrics.get("boundary_mean_expected_rank")
    rank_improved = baseline_mean_rank is not None and boundary["mean_expected_rank"] is not None and boundary["mean_expected_rank"] < float(baseline_mean_rank)
    match_improved = baseline_match_rate is not None and boundary["match_rate"] is not None and boundary["match_rate"] > float(baseline_match_rate)
    quality_gate_passed = bool(boundary["match_rate"] == 1.0 and samples.get("target_prefix_match_rate") == 1.0)
    return {
        "passed": not failures,
        "failures": failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": quality_gate_passed,
        "boundary_artifact_present": bool(boundary_rows),
        "boundary_rows": boundary["rows"],
        "boundary_match_rows": boundary["matches"],
        "boundary_match_rate": boundary["match_rate"],
        "boundary_mean_expected_rank": boundary["mean_expected_rank"],
        "boundary_min_expected_rank": boundary["min_expected_rank"],
        "boundary_max_expected_rank": boundary["max_expected_rank"],
        "split_boundary_summary": boundary["split_summary"],
        "baseline_boundary_match_rate": baseline_match_rate,
        "baseline_boundary_mean_expected_rank": baseline_mean_rank,
        "boundary_match_rate_improved": match_improved,
        "boundary_mean_rank_improved": rank_improved,
        "generation_prefix_start_rate": samples.get("generation_prefix_start_rate"),
        "target_prefix_match_rate": samples.get("target_prefix_match_rate"),
        "exact_match_rows": samples.get("exact_match_rows"),
        "generated_rows": samples.get("generated_rows"),
        "train_loss_start": train_loss_start,
        "train_loss_end": train_loss_end,
        "train_loss_decreased": train_loss_start is not None and train_loss_end is not None and train_loss_end < train_loss_start,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "missing_artifacts": missing,
        "diagnosis": "supported_suffix_boundary_probe_measures_generation_after_causal_mask_and_suffix_support_patch",
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
    if audit["quality_gate_passed"]:
        decision = "Safety passed and all supported suffix boundary rows generated exactly under the corrected causal mask."
        next_step = "Design the next bounded decoder diagnostic with supported multi-token suffixes; keep decoder CE closed until another explicit preexecution gate authorizes it."
    else:
        decision = "Safety passed or failed as reported; quality did not clear all supported suffix rows."
        next_step = "Inspect row-level boundary logits and add another controlled support/contrast row before widening."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": decision,
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9306 Supported-Suffix Boundary Probe Audit",
                "",
                f"Safety gate passed: `{audit['safety_gate_passed']}`",
                f"Quality gate passed: `{audit['quality_gate_passed']}`",
                f"Boundary match rate: `{audit['boundary_match_rate']}`",
                f"Boundary mean expected rank: `{audit['boundary_mean_expected_rank']}`",
                f"Target prefix match rate: `{audit['target_prefix_match_rate']}`",
                f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
                "",
                "Authority is closed after the audit.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
