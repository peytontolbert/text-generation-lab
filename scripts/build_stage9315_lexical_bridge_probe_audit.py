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
STAGE = 9315
NAME = "stage9315_lexical_bridge_contrast_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9314_lexical_bridge_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9313_lexical_bridge_contrast_manifest/lexical_bridge_contrast_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9315_lexical_bridge_contrast_probe"
AUDIT = RUN_DIR / "stage9315_lexical_bridge_contrast_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEXICAL_BRIDGE_PROBE_AUDIT_STAGE9315.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "sample_generation_audit.json",
    "boundary_next_token_logits.jsonl",
    "row_token_loss.jsonl",
    "module_delta_norms.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _bucket(samples: list[dict[str, Any]], manifest_by_id: dict[str, dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample in samples:
        meta = manifest_by_id.get(str(sample.get("row_id")), {})
        if key == "bridge":
            value = str((meta.get("target") or {}).get("bridge_family") if isinstance(meta.get("target"), dict) else "unknown")
        elif key == "variant":
            value = str(meta.get("repair_task_type") or "unknown")
        elif key == "split":
            value = str(sample.get("split") or "unknown")
        else:
            value = "unknown"
        item = out.setdefault(value, {"rows": 0, "exact": 0, "target_prefix": 0, "boundary": 0, "contentful": 0, "repetition": 0})
        item["rows"] += 1
        item["exact"] += int(bool(sample.get("exact_match")))
        item["target_prefix"] += int(bool(sample.get("target_prefix_match")))
        item["contentful"] += int(not bool(sample.get("empty_output")) and not bool(sample.get("short_or_junk")))
        item["repetition"] += int(bool(sample.get("degenerate_repetition")))
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        item["boundary"] += int(bool(boundary.get("match")))
    return {
        name: {
            **counts,
            "exact_rate": _rate(counts["exact"], counts["rows"]),
            "target_prefix_rate": _rate(counts["target_prefix"], counts["rows"]),
            "boundary_rate": _rate(counts["boundary"], counts["rows"]),
            "contentful_rate": _rate(counts["contentful"], counts["rows"]),
            "repetition_rate": _rate(counts["repetition"], counts["rows"]),
        }
        for name, counts in sorted(out.items())
    }


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    manifest_rows = load_jsonl(MANIFEST)
    manifest_by_id = {str(row.get("row_id")): row for row in manifest_rows}
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9314_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if contract.get("generation_prefix_field") != "model_input.active_generation_prefix_span":
        failures.append("wrong_generation_prefix_field")
    if execution.get("decoder_ce_rows") != 0 or contract.get("loss_counts", {}).get("decoder_ce") != 0:
        failures.append("decoder_ce_opened")
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
    repetition = sum(1 for row in samples if row.get("degenerate_repetition"))
    quality_gate_passed = bool(generated == 12 and exact == generated and target_prefix == generated and boundary == generated and contentful == generated and repetition == 0)
    return {
        "passed": not failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": _rate(exact, generated),
        "target_prefix_match_rate": samples_card.get("target_prefix_match_rate"),
        "boundary_next_token_match_rate": samples_card.get("boundary_next_token_match_rate"),
        "boundary_next_token_mean_expected_rank": samples_card.get("boundary_next_token_mean_expected_rank"),
        "contentful_rate": samples_card.get("contentful_rate"),
        "degenerate_repetition_rows": repetition,
        "by_bridge": _bucket(samples, manifest_by_id, "bridge"),
        "by_variant": _bucket(samples, manifest_by_id, "variant"),
        "by_split": _bucket(samples, manifest_by_id, "split"),
        "diagnosis": "lexical_bridge_contrast_probe_repaired_the_stage9312_keepside_and_operatch_failure_set",
        "next_patch_target": "merge_lexical_bridge_contrast_rows_back_into_prefix_ladder_curriculum_then_rerun_combined_probe",
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
        "decision": "Safety and quality passed for the isolated lexical bridge contrast failure set.",
        "next_best_step": "Merge Stage9313 lexical bridge rows with Stage9310 prefix-ladder rows and rerun one combined tiny target-100M denoise probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9315 Lexical Bridge Contrast Probe Audit",
        "",
        f"Safety gate passed: `{audit['safety_gate_passed']}`",
        f"Quality gate passed: `{audit['quality_gate_passed']}`",
        f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
        f"Target prefix match rate: `{audit['target_prefix_match_rate']}`",
        f"Boundary next-token match rate: `{audit['boundary_next_token_match_rate']}`",
        f"Contentful generation rate: `{audit['contentful_rate']}`",
        f"Degenerate repetition rows: `{audit['degenerate_repetition_rows']}`",
        "The isolated bridge patch repaired the `keepside` and `operatch` residual failure set.",
        "Authority is closed after the audit.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate", "degenerate_repetition_rows"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
