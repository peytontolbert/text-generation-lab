#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9026
NAME = "stage9026_row_sample_judge_reason_code_taxonomy_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9023_SUMMARY = ROOT / "runs/summaries/stage9023_row_sample_judge_diagnostics_contract.json"
SOURCE_9023_CONTRACT = ROOT / "runs/local/artifacts/stage9023_row_sample_judge_diagnostics_contract/row_sample_judge_diagnostics_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROW_SAMPLE_JUDGE_REASON_CODE_TAXONOMY_CONTRACT_STAGE9026.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "row_sample_judge_reason_code_taxonomy_contract.json"

REASON_CODE_TAXONOMY = {
    "locked_eval_overlap": {"severity": "critical", "compiler_action": "reject", "training_action": "block_all_losses"},
    "target_leakage": {"severity": "critical", "compiler_action": "reject", "training_action": "block_all_losses"},
    "shortcut_proxy": {"severity": "high", "compiler_action": "quarantine", "training_action": "block_until_counterfactual"},
    "near_duplicate_cluster": {"severity": "medium", "compiler_action": "dedupe_or_downsample", "training_action": "allow_only_if_split_safe"},
    "junk_or_ood": {"severity": "medium", "compiler_action": "reject_or_review", "training_action": "route_to_abstain_or_ood_only"},
    "missing_source_provenance": {"severity": "high", "compiler_action": "quarantine", "training_action": "block_until_provenance"},
    "incomplete_gate_status": {"severity": "high", "compiler_action": "reject", "training_action": "block_all_losses"},
    "unsafe_loss_mask": {"severity": "critical", "compiler_action": "reject", "training_action": "block_all_losses"},
    "requires_row_body_text": {"severity": "critical", "compiler_action": "reject", "training_action": "block_all_losses"},
    "requires_source_body_text": {"severity": "critical", "compiler_action": "reject", "training_action": "block_all_losses"},
}

COMPILER_ACTIONS = [
    "accept_pending_manifest_compile",
    "reject",
    "quarantine",
    "dedupe_or_downsample",
    "reject_or_review",
    "route_to_abstain_or_ood_only",
]

TRAINING_ACTIONS = [
    "allow_structured_aux_only",
    "block_all_losses",
    "block_until_counterfactual",
    "allow_only_if_split_safe",
    "route_to_abstain_or_ood_only",
    "block_until_provenance",
]

FORBIDDEN_OPERATIONS = [
    "RUN_ROW_SAMPLE_JUDGE_NOW",
    "READ_ROW_BODY_TEXT",
    "READ_REPOSITORY_SOURCE_BODY",
    "MATERIALIZE_JUDGE_OUTPUTS_NOW",
    "MATERIALIZE_MANIFEST_NOW",
    "RUN_TRAINER_DRY_RUN_NOW",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
    "RUN_GEMMA",
    "WRITE_TO_ARXIV",
    "AUTHORIZE_DECODER_CE",
    "AUTHORIZE_DENOISE_CE",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    s9023 = load_json(SOURCE_9023_SUMMARY)
    c9023 = load_json(SOURCE_9023_CONTRACT)
    source_codes = set(c9023.get("reject_reason_codes") or [])
    taxonomy_codes = set(REASON_CODE_TAXONOMY)
    critical_codes = [code for code, spec in REASON_CODE_TAXONOMY.items() if spec["severity"] == "critical"]
    checks = {
        "source_stage9023_present": SOURCE_9023_SUMMARY.exists() and SOURCE_9023_CONTRACT.exists(),
        "source_stage9023_passed": s9023.get("passed") is True,
        "source_reason_codes_covered": source_codes.issubset(taxonomy_codes) and bool(source_codes),
        "taxonomy_has_no_extra_unknown_training_actions": all(spec["training_action"] in TRAINING_ACTIONS for spec in REASON_CODE_TAXONOMY.values()),
        "taxonomy_has_no_extra_unknown_compiler_actions": all(spec["compiler_action"] in COMPILER_ACTIONS for spec in REASON_CODE_TAXONOMY.values()),
        "critical_codes_block_all_losses": all(REASON_CODE_TAXONOMY[code]["training_action"] == "block_all_losses" for code in critical_codes),
        "body_text_codes_are_critical": REASON_CODE_TAXONOMY["requires_row_body_text"]["severity"] == "critical" and REASON_CODE_TAXONOMY["requires_source_body_text"]["severity"] == "critical",
        "leakage_codes_are_critical": REASON_CODE_TAXONOMY["locked_eval_overlap"]["severity"] == "critical" and REASON_CODE_TAXONOMY["target_leakage"]["severity"] == "critical",
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 13,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROW_SAMPLE_JUDGE_REASON_CODE_TAXONOMY_CONTRACT_NO_EXECUTION",
        "reason_code_taxonomy": REASON_CODE_TAXONOMY,
        "compiler_actions": COMPILER_ACTIONS,
        "training_actions": TRAINING_ACTIONS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "reason_codes": len(REASON_CODE_TAXONOMY),
            "critical_reason_codes": len(critical_codes),
            "compiler_actions": len(COMPILER_ACTIONS),
            "training_actions": len(TRAINING_ACTIONS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "taxonomy_contract_only": True,
            "judge_executed_now": False,
            "judge_outputs_materialized_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "manifest_compile_authorized_now": False,
            "manifest_materialized_now": False,
            "trainer_dry_run_execution_authorized_now": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "gemma_execution_attempted": False,
            "harness_scoring_attempted": False,
            "arxiv_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Future judge reject reasons must compile into deterministic compiler/training actions before any manifest compilation. This stage defines taxonomy only and performs no execution.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    taxonomy = card.get("reason_code_taxonomy") or {}
    for code in ["locked_eval_overlap", "target_leakage", "unsafe_loss_mask", "requires_row_body_text", "requires_source_body_text"]:
        spec = taxonomy.get(code) or {}
        if spec.get("severity") != "critical" or spec.get("training_action") != "block_all_losses":
            failures.append(f"critical_code_not_blocking:{code}")
    for key in [
        "judge_executed_now",
        "judge_outputs_materialized_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "manifest_compile_authorized_now",
        "manifest_materialized_now",
        "trainer_dry_run_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "gemma_execution_attempted",
        "harness_scoring_attempted",
        "arxiv_write_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Use this taxonomy when future judge outputs are materialized; then audit compiler handoff. Keep judge execution, manifest compile, and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9026 Row-Sample Judge Reason Code Taxonomy Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines how future row-sample judge reject reasons compile into deterministic compiler and training actions. It does not run the judge, read row/source bodies, materialize outputs, compile a manifest, run trainer dry-run, train, mine, or write `/arxiv`.",
        "",
        f"Reason codes: `{summary['metrics']['reason_codes']}`",
        f"Critical reason codes: `{summary['metrics']['critical_reason_codes']}`",
        f"Judge executed now: `{summary['metrics']['judge_executed_now']}`",
        f"Training authorized: `{summary['metrics']['training_authorized']}`",
        "",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
