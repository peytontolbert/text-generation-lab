#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage8998_trainer_contract_only_dry_run_contract import (
        FORBIDDEN_OPERATIONS,
        REQUIRED_ASSERTIONS as BASE_DRY_RUN_ASSERTIONS,
        REQUIRED_FLAGS as BASE_DRY_RUN_FLAGS,
        REQUIRED_INPUTS as BASE_DRY_RUN_INPUTS,
        REQUIRED_TELEMETRY_STUBS,
    )
    from scripts.build_stage9065_trainer_dry_run_input_refresh_after_long_context_controls import (
        ADDITIONAL_ASSERTIONS as LONG_CONTEXT_ASSERTIONS,
        REQUIRED_LONG_CONTEXT_INPUTS,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage8998_trainer_contract_only_dry_run_contract import (  # type: ignore
        FORBIDDEN_OPERATIONS,
        REQUIRED_ASSERTIONS as BASE_DRY_RUN_ASSERTIONS,
        REQUIRED_FLAGS as BASE_DRY_RUN_FLAGS,
        REQUIRED_INPUTS as BASE_DRY_RUN_INPUTS,
        REQUIRED_TELEMETRY_STUBS,
    )
    from build_stage9065_trainer_dry_run_input_refresh_after_long_context_controls import (  # type: ignore
        ADDITIONAL_ASSERTIONS as LONG_CONTEXT_ASSERTIONS,
        REQUIRED_LONG_CONTEXT_INPUTS,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9072
NAME = "stage9072_trainer_dry_run_documentation_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_RECOVERED_CONTRACT_STAGE9072.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "trainer_dry_run_documentation_refresh.json"

SOURCE_SUMMARIES = {
    8998: "stage8998_trainer_contract_only_dry_run_contract",
    9003: "stage9003_trainer_contract_dry_run_instance_design",
    9065: "stage9065_trainer_dry_run_input_refresh_after_long_context_controls",
    9066: "stage9066_trainer_dry_run_input_negative_case_audit",
    9067: "stage9067_trainer_dry_run_controls_graph_attachment",
    9071: "stage9071_current_frontier_reconciliation_after_long_context_guards",
}

RECOVERED_INPUTS = list(dict.fromkeys([*BASE_DRY_RUN_INPUTS, *REQUIRED_LONG_CONTEXT_INPUTS]))
RECOVERED_ASSERTIONS = list(dict.fromkeys([*BASE_DRY_RUN_ASSERTIONS, *LONG_CONTEXT_ASSERTIONS]))

DOCUMENTED_HARD_STOPS = [
    "dry_run_stops_before_model_forward",
    "no_model_weights_loaded",
    "no_optimizer_created",
    "no_backward_called",
    "no_dataset_row_body_loaded",
    "no_repository_source_body_loaded",
    "no_long_context_rows_loaded_without_source_ticket",
    "route_to_trainer_loss_translation_blocks_decoder_denoise_runtime",
    "no_final_checkpoint_export_path",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        source = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(source),
            "passed": source.get("passed") is True,
            "next_best_step": source.get("next_best_step"),
            "metrics": source.get("metrics") or {},
        }
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "base_inputs_preserved": set(BASE_DRY_RUN_INPUTS).issubset(set(RECOVERED_INPUTS)),
        "long_context_inputs_preserved": set(REQUIRED_LONG_CONTEXT_INPUTS).issubset(set(RECOVERED_INPUTS)),
        "required_flags_preserved": {"--manifest", "--mode", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe"}.issubset(set(BASE_DRY_RUN_FLAGS)),
        "base_assertions_preserved": set(BASE_DRY_RUN_ASSERTIONS).issubset(set(RECOVERED_ASSERTIONS)),
        "long_context_assertions_preserved": set(LONG_CONTEXT_ASSERTIONS).issubset(set(RECOVERED_ASSERTIONS)),
        "hard_stops_documented": set(DOCUMENTED_HARD_STOPS).issubset(set(RECOVERED_ASSERTIONS)),
        "telemetry_stubs_preserved": len(REQUIRED_TELEMETRY_STUBS) >= 7,
        "forbidden_operations_preserved": len(FORBIDDEN_OPERATIONS) >= 16,
        "stage9071_training_closed": sources["9071"]["metrics"].get("training_ready") is False,
        "stage9071_no_candidate_rows": sources["9071"]["metrics"].get("candidate_rows_materialized") == 0,
        "registry_frontier_stage9071": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9071,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_DRY_RUN_DOCUMENTATION_REFRESH_NO_EXECUTION",
        "source_status": sources,
        "recovered_inputs": RECOVERED_INPUTS,
        "recovered_flags": list(BASE_DRY_RUN_FLAGS),
        "recovered_assertions": RECOVERED_ASSERTIONS,
        "required_telemetry_stubs": list(REQUIRED_TELEMETRY_STUBS),
        "forbidden_operations": list(FORBIDDEN_OPERATIONS),
        "documented_hard_stops": DOCUMENTED_HARD_STOPS,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "recovered_inputs": len(RECOVERED_INPUTS),
            "long_context_inputs": len(REQUIRED_LONG_CONTEXT_INPUTS),
            "recovered_flags": len(BASE_DRY_RUN_FLAGS),
            "recovered_assertions": len(RECOVERED_ASSERTIONS),
            "documented_hard_stops": len(DOCUMENTED_HARD_STOPS),
            "required_telemetry_stubs": len(REQUIRED_TELEMETRY_STUBS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "trainer_invoked": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "candidate_rows_materialized": 0,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recovered trainer dry-run documentation now lists required inputs, flags, assertions, telemetry stubs, hard stops, forbidden operations, and long-context blockers. This stage does not invoke the trainer, load rows, materialize candidates, or authorize training.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9071, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for required in REQUIRED_LONG_CONTEXT_INPUTS:
        if required not in card.get("recovered_inputs", []):
            failures.append(f"missing_long_context_input:{required}")
    for required in DOCUMENTED_HARD_STOPS:
        if required not in card.get("recovered_assertions", []):
            failures.append(f"missing_hard_stop:{required}")
    for key in [
        "trainer_invoked",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "model_weights_loaded",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Trainer dry-run documentation refresh failed.",
        "next_best_step": "Continue no-data recovery with a central graph gap walk against Stage9072, or design a future source/output ticket without reading row bodies.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9072 Trainer Dry-Run Recovered Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This is a no-execution documentation refresh for the recovered trainer dry-run contract. It records the required inputs, flags, hard stops, telemetry stubs, forbidden operations, and long-context blockers that must exist before a future contract-only trainer dry run can even be considered.",
        "",
        "## Required Inputs",
        "",
        *[f"- `{item}`" for item in RECOVERED_INPUTS],
        "",
        "## Required Hard Stops",
        "",
        *[f"- `{item}`" for item in DOCUMENTED_HARD_STOPS],
        "",
        "## Closed Now",
        "",
        "- trainer invocation",
        "- model forward",
        "- row loading",
        "- repository source/body loading",
        "- candidate mining",
        "- decoder CE",
        "- denoise CE",
        "- runtime",
        "- /arxiv compiler IO",
        "- training",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9072 Trainer Dry-Run Recovered Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9072 records the recovered trainer dry-run contract after Stage9071: required locked-manifest inputs, long-context blocker inputs, loss-mask assertions, telemetry stubs, forbidden operations, and hard stops are documented as the current control surface.",
            "",
            "No trainer invocation, model forward, row loading, source/body loading, candidate mining, decoder CE, denoise CE, runtime, /arxiv compiler IO, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
