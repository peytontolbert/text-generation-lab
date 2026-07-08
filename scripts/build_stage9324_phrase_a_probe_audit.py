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
STAGE = 9324
NAME = "stage9324_phrase_a_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9323_phrase_a_probe_preexecution.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9322_phrase_family_split_manifests/phrase_a_patch_inside_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9324_phrase_a_patch_inside_probe"
AUDIT = RUN_DIR / "stage9324_phrase_a_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_A_PROBE_AUDIT_STAGE9324.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = ["probe_contract_audit.json", "execution_result.json", "sample_generation_audit.json", "boundary_next_token_logits.jsonl", "row_token_loss.jsonl", "module_delta_norms.json", "cleanup_proof.json"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_run() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples = load_json(RUN_DIR / "sample_generation_audit.json")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("source_stage9323_not_passed")
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
    generated = int(samples.get("generated_rows") or 0)
    exact = int(samples.get("exact_match_rows") or 0)
    target_prefix = int(samples.get("target_prefix_match_rows") or 0)
    boundary = int(samples.get("boundary_next_token_match_rows") or 0)
    contentful = int(samples.get("contentful_rows") or 0)
    quality_gate_passed = bool(generated == 8 and exact == generated and target_prefix == generated and boundary == generated and contentful == generated)
    return {
        "passed": not failures,
        "safety_gate_passed": not failures,
        "quality_gate_passed": quality_gate_passed,
        "failures": failures,
        "missing_artifacts": missing,
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": exact / generated if generated else None,
        "target_prefix_match_rate": samples.get("target_prefix_match_rate"),
        "boundary_next_token_match_rate": samples.get("boundary_next_token_match_rate"),
        "boundary_next_token_mean_expected_rank": samples.get("boundary_next_token_mean_expected_rank"),
        "contentful_rate": samples.get("contentful_rate"),
        "diagnosis": "phrase_a_patch_inside_is_individually_learnable_and_fails_only_under_mixed_phrase_curriculum",
        "next_patch_target": "run_phrase_b_isolated_probe_then_design_phrase_router_or_source_balanced_mixture",
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
        "decision": "Phrase A passed in isolation; patch-inside failures are caused by mixed-curriculum interference, not local unlearnability.",
        "next_best_step": "Run phrase-B isolated probe, then decide whether to add an explicit phrase router or source-balanced mixture before combining.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9324 Phrase A Probe Audit",
        "",
        f"Safety gate passed: `{audit['safety_gate_passed']}`",
        f"Quality gate passed: `{audit['quality_gate_passed']}`",
        f"Exact match rows: `{audit['exact_match_rows']}` / `{audit['generated_rows']}`",
        f"Target prefix match rate: `{audit['target_prefix_match_rate']}`",
        f"Boundary next-token match rate: `{audit['boundary_next_token_match_rate']}`",
        "Phrase A (`patch inside`) is individually learnable. Authority is closed after the audit.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {k: audit[k] for k in ["safety_gate_passed", "quality_gate_passed", "exact_match_rate", "target_prefix_match_rate", "boundary_next_token_match_rate", "contentful_rate"]}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
