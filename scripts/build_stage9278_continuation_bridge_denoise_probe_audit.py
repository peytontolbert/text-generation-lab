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
STAGE = 9278
NAME = "stage9278_continuation_bridge_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9276_prefix_primed_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9277_continuation_bridge_denoise_manifest/continuation_bridge_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9278_continuation_bridge_denoise_probe/denoise_repair_probe"
AUDIT = RUN_DIR / "stage9278_continuation_bridge_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTINUATION_BRIDGE_DENOISE_PROBE_AUDIT_STAGE9278.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EXPECTED_MANIFEST_SHA = "859c3a5a4f2d76577be62bfd9bff3102fa9562b7b4a9045fa53bf76727b08d56"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bridge_starts() -> dict[str, str]:
    out: dict[str, str] = {}
    for row in load_jsonl(MANIFEST):
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        prefix = str(model_input.get("copy_prefix_span") or "")
        bridge = str(model_input.get("continuation_bridge_span") or "")
        target = str((row.get("target") or {}).get("decoder_text") or "")
        suffix = target[len(prefix):] if target.startswith(prefix) else ""
        idx = suffix.find(bridge) if bridge else -1
        if prefix and bridge and idx >= 0:
            out[str(row.get("row_id"))] = (prefix + suffix[: idx + len(bridge)]).strip()
    return out


def bridge_metrics(samples: dict[str, Any]) -> dict[str, Any]:
    starts = bridge_starts()
    generated = samples.get("samples") if isinstance(samples.get("samples"), list) else []
    checked = 0
    start_rows = 0
    contains_rows = 0
    misses: list[dict[str, str]] = []
    for item in generated:
        if not isinstance(item, dict):
            continue
        row_id = str(item.get("row_id"))
        expected = starts.get(row_id, "")
        if not expected:
            continue
        checked += 1
        text = str(item.get("generated_text") or "")
        if text.startswith(expected):
            start_rows += 1
        if expected in text:
            contains_rows += 1
        else:
            misses.append({"row_id": row_id, "expected_start": expected, "generated_start": text[:100]})
    return {
        "bridge_rows_checked": checked,
        "bridge_start_rows": start_rows,
        "bridge_start_rate": start_rows / checked if checked else 0.0,
        "bridge_contains_rows": contains_rows,
        "bridge_contains_rate": contains_rows / checked if checked else 0.0,
        "bridge_miss_examples": misses[:5],
    }


def audit_run() -> dict[str, Any]:
    previous = load_json(SOURCE_SUMMARY).get("metrics") or {}
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    losses = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    bridge = bridge_metrics(samples)
    failures: list[str] = []
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("manifest_sha256") != EXPECTED_MANIFEST_SHA:
        failures.append("manifest_hash_mismatch")
    if contract.get("generation_prefix_field") != "model_input.copy_prefix_span":
        failures.append("generation_prefix_field_missing")
    if contract.get("loss_counts", {}).get("decoder_ce") != 0 or execution.get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_opened")
    if execution.get("runtime_executed") is not False or execution.get("gemma_executed") is not False or execution.get("harness_executed") is not False:
        failures.append("forbidden_execution_surface_opened")
    if execution.get("final_checkpoint_exported") is not False:
        failures.append("checkpoint_exported")
    if execution.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    start = float(losses[0]["loss"]) if losses else None
    end = float(losses[-1]["loss"]) if losses else None
    contentful = samples.get("contentful_rate")
    prefix_start = samples.get("generation_prefix_start_rate")
    target_prefix = samples.get("target_prefix_match_rate")
    unterminated = repetition.get("unterminated_rate")
    degenerate = repetition.get("degenerate_repetition_rate")
    quality_gate_passed = bool(
        samples.get("generated_rows", 0) > 0
        and prefix_start == 1.0
        and bridge["bridge_start_rate"] == 1.0
        and contentful == 1.0
        and target_prefix and target_prefix > 0.0
        and unterminated == 0.0
        and degenerate == 0.0
        and leak.get("generated_internal_token_rows") == 0
    )
    return {
        "passed": not failures,
        "failures": failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": quality_gate_passed,
        "rows": execution.get("denoise_ce_rows"),
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "max_steps": execution.get("max_steps"),
        "generated_rows": samples.get("generated_rows"),
        "generation_prefix_start_rate": prefix_start,
        "previous_generation_prefix_start_rate": previous.get("generation_prefix_start_rate"),
        **bridge,
        "contentful_generation_rate": contentful,
        "previous_contentful_generation_rate": previous.get("contentful_generation_rate"),
        "unterminated_generation_rate": unterminated,
        "previous_unterminated_generation_rate": previous.get("unterminated_generation_rate"),
        "degenerate_repetition_rate": degenerate,
        "previous_degenerate_repetition_rate": previous.get("degenerate_repetition_rate"),
        "short_or_junk_rate": short.get("short_or_junk_rate"),
        "target_prefix_match_rate": target_prefix,
        "previous_target_prefix_match_rate": previous.get("target_prefix_match_rate"),
        "generated_internal_token_rows": leak.get("generated_internal_token_rows"),
        "train_loss_start": start,
        "train_loss_end": end,
        "train_loss_decreased": start is not None and end is not None and end < start,
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "runtime_executed": execution.get("runtime_executed"),
        "gemma_executed": execution.get("gemma_executed"),
        "harness_executed": execution.get("harness_executed"),
        "final_checkpoint_exported": execution.get("final_checkpoint_exported"),
        "required_artifacts_written": execution.get("required_artifacts_written"),
        "diagnosis": "continuation_bridge_improves_stability_but_bridge_copy_still_fails",
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
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
        "decision": "Continuation bridge evidence improved contentfulness, termination, and repetition, but generated continuations still do not copy the expected bridge span.",
        "next_best_step": "Add decoder-side bridge priming or a shorter next-token bridge objective to separate continuation-copy mechanics from longer semantic generation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage9278 Continuation-Bridge Denoise Probe Audit",
            "",
            "Stage9278 improved stability but did not recover the continuation bridge.",
            "",
            f"Generation prefix start rate: {audit['generation_prefix_start_rate']}",
            f"Bridge start rate: {audit['bridge_start_rate']}",
            f"Contentful rate: {audit['previous_contentful_generation_rate']} -> {audit['contentful_generation_rate']}",
            f"Unterminated rate: {audit['previous_unterminated_generation_rate']} -> {audit['unterminated_generation_rate']}",
            f"Degenerate repetition rate: {audit['previous_degenerate_repetition_rate']} -> {audit['degenerate_repetition_rate']}",
            f"Target prefix match rate: {audit['target_prefix_match_rate']}",
            f"Diagnosis: {audit['diagnosis']}",
            "",
            "Next step: decoder-side bridge priming or shorter next-token bridge objective.",
        ]) + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
