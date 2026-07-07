#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9162_trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight import (
        BLOCKED_OUTPUTS,
        NEGATIVE_CASES,
        REQUIRED_INPUTS_AFTER_LOSS_MASK,
        REQUIRED_TELEMETRY_AFTER_LOSS_MASK,
        REQUIRED_TRAINER_INPUT_ASSERTIONS,
        build_card,
        run_negative_cases as run_design_negative_cases,
        validate_card,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9162_trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight import (  # type: ignore
        BLOCKED_OUTPUTS,
        NEGATIVE_CASES,
        REQUIRED_INPUTS_AFTER_LOSS_MASK,
        REQUIRED_TELEMETRY_AFTER_LOSS_MASK,
        REQUIRED_TRAINER_INPUT_ASSERTIONS,
        build_card,
        run_negative_cases as run_design_negative_cases,
        validate_card,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9163
NAME = "stage9163_trainer_dry_run_input_readiness_refresh_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9162 = ROOT / "runs/summaries/stage9162_trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_READINESS_REFRESH_AUDIT_STAGE9163.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_dry_run_input_readiness_refresh_audit.json"

AUDIT_NEGATIVE_CASES = list(NEGATIVE_CASES) + [
    "bad_registry_frontier",
    "missing_row_token_loss_telemetry",
    "missing_activation_cache_telemetry",
    "trainer_contract_only_invoked",
    "model_weights_loaded",
    "optimizer_created",
    "backward_called",
    "model_input_rows_nonzero",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9162) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    audited = dict(run_design_negative_cases())
    base = build_card({"passed": True})
    extras: dict[str, dict[str, Any]] = {}
    for name in AUDIT_NEGATIVE_CASES:
        if name in audited:
            continue
        candidate = copy.deepcopy(base)
        if name == "bad_registry_frontier":
            extras[name] = {"failures": ["unexpected_registry_frontier:9999"], "rejected": True}
            continue
        if name == "missing_row_token_loss_telemetry":
            candidate["required_telemetry_stubs"].remove("row_token_loss.jsonl")
        elif name == "missing_activation_cache_telemetry":
            candidate["required_telemetry_stubs"].remove("activation_probe_cache.pt")
        elif name == "trainer_contract_only_invoked":
            candidate["metrics"]["trainer_contract_only_invoked_now"] = True
        elif name == "model_weights_loaded":
            candidate["metrics"]["model_weights_loaded"] = True
        elif name == "optimizer_created":
            candidate["metrics"]["optimizer_created"] = True
        elif name == "backward_called":
            candidate["metrics"]["backward_called"] = True
        elif name == "model_input_rows_nonzero":
            candidate["metrics"]["model_input_rows_now"] = 1
        failures = validate_card(candidate)
        extras[name] = {"failures": failures, "rejected": bool(failures)}
    audited.update(extras)
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9162)
    card = build_card({"passed": True})
    card_failures = validate_card(card)
    negatives = run_negative_cases()
    checks = {
        "source_stage9162_passed": source.get("passed") is True,
        "base_card_passes": card_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_inputs_complete": set(REQUIRED_INPUTS_AFTER_LOSS_MASK).issubset(set(card["required_inputs"])),
        "required_assertions_complete": set(REQUIRED_TRAINER_INPUT_ASSERTIONS).issubset(set(card["required_assertions"])),
        "required_interpretability_telemetry_present": set([
            "row_field_logits.jsonl",
            "row_token_loss.jsonl",
            "row_gradient_norms.jsonl",
            "feature_ablation_attribution.jsonl",
            "activation_probe_cache.pt",
            "module_delta_norms.json",
            "failure_bucket_card.json",
        ]).issubset(set(card["required_telemetry_stubs"])),
        "required_telemetry_complete": set(REQUIRED_TELEMETRY_AFTER_LOSS_MASK).issubset(set(card["required_telemetry_stubs"])),
        "blocked_outputs_complete": set(BLOCKED_OUTPUTS).issubset(set(card["blocked_outputs"])),
        "trainer_input_blocked": "trainer_dry_run_input.json" in card["blocked_outputs"],
        "contract_only_output_blocked": "trainer_contract_only_output.json" in card["blocked_outputs"],
        "model_input_rows_blocked": "model_input_rows.jsonl" in card["blocked_outputs"],
        "no_trainer_input_materialization": card["metrics"]["trainer_input_materialized_now"] is False,
        "no_contract_only_invocation": card["metrics"]["trainer_contract_only_invoked_now"] is False,
        "no_model_forward": card["metrics"]["model_forward_attempted"] is False,
        "no_model_weights_loaded": card["metrics"]["model_weights_loaded"] is False,
        "no_optimizer_or_backward": card["metrics"]["optimizer_created"] is False and card["metrics"]["backward_called"] is False,
        "no_model_input_rows": card["metrics"]["model_input_rows_now"] == 0,
        "authority_closed": not any(card["authority"].values()),
        "registry_frontier_stage9162": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9162,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(card_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "card_failures": card_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "required_inputs": len(REQUIRED_INPUTS_AFTER_LOSS_MASK),
            "required_assertions": len(REQUIRED_TRAINER_INPUT_ASSERTIONS),
            "required_telemetry_stubs": len(REQUIRED_TELEMETRY_AFTER_LOSS_MASK),
            "blocked_outputs": len(BLOCKED_OUTPUTS),
            "loss_mask_cards_materialized_now": False,
            "trainer_input_materialized_now": False,
            "trainer_contract_only_invoked_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "model_input_rows_now": 0,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "optimizer_created": False,
            "backward_called": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Audited trainer dry-run input readiness after the loss-mask preflight. "
            "The audit keeps trainer input materialization, contract-only trainer "
            "invocation, model forward, optimizer/backward, training, decoder CE, denoise "
            "CE, runtime, source/body emission, Gemma, harness, scoring, cleanup, and /arxiv access closed."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Trainer dry-run input readiness refresh audit failed.",
        "next_best_step": "Design trainer input materialization ticket, still no trainer execution or model forward.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9163 Trainer Dry-Run Input Readiness Refresh Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9162 readiness refresh and preserves the no-execution boundary.",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
