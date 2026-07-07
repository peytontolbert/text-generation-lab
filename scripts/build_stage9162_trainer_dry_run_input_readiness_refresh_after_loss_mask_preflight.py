#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9072_trainer_dry_run_documentation_refresh import (
        DOCUMENTED_HARD_STOPS,
        RECOVERED_ASSERTIONS,
        RECOVERED_INPUTS,
        REQUIRED_TELEMETRY_STUBS,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9072_trainer_dry_run_documentation_refresh import (  # type: ignore
        DOCUMENTED_HARD_STOPS,
        RECOVERED_ASSERTIONS,
        RECOVERED_INPUTS,
        REQUIRED_TELEMETRY_STUBS,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9162
NAME = "stage9162_trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9161 = ROOT / "runs/summaries/stage9161_loss_mask_materialization_preflight_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_READINESS_REFRESH_AFTER_LOSS_MASK_PREFLIGHT_STAGE9162.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight.json"

REQUIRED_INPUTS_AFTER_LOSS_MASK = list(dict.fromkeys([
    *RECOVERED_INPUTS,
    "loss_mask_cards.jsonl",
    "loss_mask_authority_audit.json",
    "loss_mask_enforcement_audit.json",
    "trainer_dry_run_input_schema_lock.json",
    "telemetry_artifact_manifest.json",
]))

REQUIRED_TRAINER_INPUT_ASSERTIONS = list(dict.fromkeys([
    *RECOVERED_ASSERTIONS,
    "loss_mask_cards_materialized_and_audited_before_trainer_input",
    "trainer_input_rows_are_metadata_only_until_contract_dry_run",
    "trainer_input_materialization_requires_separate_ticket",
    "contract_only_trainer_dry_run_requires_separate_execution_review",
    "no_model_forward_during_input_readiness",
]))

BLOCKED_OUTPUTS = [
    "trainer_dry_run_input.json",
    "trainer_contract_only_output.json",
    "trainer_telemetry_stub_dir",
    "model_input_rows.jsonl",
]

REQUIRED_TELEMETRY_AFTER_LOSS_MASK = list(dict.fromkeys([
    *REQUIRED_TELEMETRY_STUBS,
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_probe_cache.pt",
    "module_delta_norms.json",
    "failure_bucket_card.json",
]))

NEGATIVE_CASES = [
    "source_stage_missing",
    "missing_required_input",
    "missing_required_assertion",
    "missing_hard_stop",
    "missing_telemetry_stub",
    "missing_blocked_output",
    "loss_masks_materialized",
    "trainer_input_materialized",
    "trainer_dry_run_ready",
    "trainer_executed",
    "model_forward",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(source_9161: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9161 = source_9161 if source_9161 is not None else load_json(SOURCE_9161)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "card_type": "trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight_v1",
        "source_stage9161_passed": source_9161.get("passed") is True,
        "required_inputs": list(REQUIRED_INPUTS_AFTER_LOSS_MASK),
        "required_assertions": list(REQUIRED_TRAINER_INPUT_ASSERTIONS),
        "documented_hard_stops": list(DOCUMENTED_HARD_STOPS),
        "required_telemetry_stubs": list(REQUIRED_TELEMETRY_AFTER_LOSS_MASK),
        "blocked_outputs": list(BLOCKED_OUTPUTS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "refresh_only": True,
            "source_stage9161_passed": source_9161.get("passed") is True,
            "required_inputs": len(REQUIRED_INPUTS_AFTER_LOSS_MASK),
            "required_assertions": len(REQUIRED_TRAINER_INPUT_ASSERTIONS),
            "documented_hard_stops": len(DOCUMENTED_HARD_STOPS),
            "required_telemetry_stubs": len(REQUIRED_TELEMETRY_AFTER_LOSS_MASK),
            "blocked_outputs": len(BLOCKED_OUTPUTS),
            "loss_mask_cards_materialized_now": False,
            "trainer_input_materialized_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_contract_only_invoked_now": False,
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
            "Refreshed trainer dry-run input readiness after the audited loss-mask "
            "preflight. This stage does not materialize trainer input, invoke "
            "contract-only trainer mode, run trainer, load model weights, or train."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = card.get("metrics") or {}
    if card.get("source_stage9161_passed") is not True or metrics.get("source_stage9161_passed") is not True:
        failures.append("source_stage9161_not_passed")
    for item in REQUIRED_INPUTS_AFTER_LOSS_MASK:
        if item not in card.get("required_inputs", []):
            failures.append(f"missing_required_input:{item}")
    for item in REQUIRED_TRAINER_INPUT_ASSERTIONS:
        if item not in card.get("required_assertions", []):
            failures.append(f"missing_required_assertion:{item}")
    for item in DOCUMENTED_HARD_STOPS:
        if item not in card.get("documented_hard_stops", []):
            failures.append(f"missing_hard_stop:{item}")
    for item in REQUIRED_TELEMETRY_AFTER_LOSS_MASK:
        if item not in card.get("required_telemetry_stubs", []):
            failures.append(f"missing_telemetry_stub:{item}")
    for item in BLOCKED_OUTPUTS:
        if item not in card.get("blocked_outputs", []):
            failures.append(f"missing_blocked_output:{item}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    false_keys = [
        "loss_mask_cards_materialized_now",
        "trainer_input_materialized_now",
        "trainer_dry_run_ready_now",
        "trainer_contract_only_invoked_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "model_weights_loaded",
        "optimizer_created",
        "backward_called",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_accessed",
        "file_content_read",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "cleanup_authorized_now",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    if metrics.get("model_input_rows_now") != 0:
        failures.append("model_input_rows_now")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_card()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["source_stage9161_passed"] = False
            candidate["metrics"]["source_stage9161_passed"] = False
        elif name == "missing_required_input":
            candidate["required_inputs"].remove("loss_mask_cards.jsonl")
        elif name == "missing_required_assertion":
            candidate["required_assertions"].remove("no_model_forward_during_input_readiness")
        elif name == "missing_hard_stop":
            candidate["documented_hard_stops"].remove("dry_run_stops_before_model_forward")
        elif name == "missing_telemetry_stub":
            candidate["required_telemetry_stubs"].remove("row_field_logits.jsonl")
        elif name == "missing_blocked_output":
            candidate["blocked_outputs"].remove("trainer_dry_run_input.json")
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "trainer_input_materialized":
            candidate["metrics"]["trainer_input_materialized_now"] = True
        elif name == "trainer_dry_run_ready":
            candidate["metrics"]["trainer_dry_run_ready_now"] = True
        elif name == "trainer_executed":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "model_forward":
            candidate["metrics"]["model_forward_attempted"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_card(candidate), "rejected": bool(validate_card(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    card = build_card()
    failures = validate_card(card)
    negatives = run_negative_cases()
    checks = {
        "card_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "trainer_input_blocked": "trainer_dry_run_input.json" in card["blocked_outputs"],
        "contract_only_output_blocked": "trainer_contract_only_output.json" in card["blocked_outputs"],
        "authority_closed": not any(card["authority"].values()),
    }
    all_failures = [key for key, value in checks.items() if value is not True]
    all_failures.extend(failures)
    passed = not all_failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": all_failures,
        "card": card,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **card["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": card["decision"] if passed else "Trainer dry-run input readiness refresh failed validation.",
        "next_best_step": "Audit trainer dry-run input readiness refresh; still do not materialize trainer input or execute trainer.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    CARD.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9162 Trainer Dry-Run Input Readiness Refresh After Loss-Mask Preflight",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Refreshes trainer dry-run input readiness without materializing trainer input or executing trainer.",
        "",
        f"Required inputs: `{summary['metrics']['required_inputs']}`",
        f"Required assertions: `{summary['metrics']['required_assertions']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": public_summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": public_summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = public_summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": public_summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    raise SystemExit(0 if public_summary["passed"] else 1)


if __name__ == "__main__":
    main()
