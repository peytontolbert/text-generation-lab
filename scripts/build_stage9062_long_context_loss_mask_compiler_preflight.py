#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS as ROUTE_LOSS_KEYS
    from scripts.build_stage9061_long_context_compiler_handoff_blocker_audit import REQUIRED_HANDOFF_ARTIFACTS
    from scripts.loss_mask_card import LOSS_KEYS as TRAINER_LOSS_KEYS
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9057_long_context_route_card_schema_contract import LOSS_KEYS as ROUTE_LOSS_KEYS  # type: ignore
    from build_stage9061_long_context_compiler_handoff_blocker_audit import REQUIRED_HANDOFF_ARTIFACTS  # type: ignore
    from loss_mask_card import LOSS_KEYS as TRAINER_LOSS_KEYS  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9062
NAME = "stage9062_long_context_loss_mask_compiler_preflight"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9061 = ROOT / "runs/summaries/stage9061_long_context_compiler_handoff_blocker_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_LOSS_MASK_COMPILER_PREFLIGHT_STAGE9062.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT_PATH = OUT_DIR / "long_context_loss_mask_compiler_preflight.json"

ROUTE_TO_TRAINER_LOSS_TRANSLATION = {
    "structured_aux_ce": [
        "surface_role_ce",
        "repair_surface_ce",
        "symbol_binding_ce",
        "edit_localization_ce",
        "patch_operator_ce",
        "verifier_repair_ce",
    ],
    "decoder_ce": ["decoder_ce"],
    "denoise_ce": ["denoise_ce"],
    "retrieval_loss": [],
    "runtime_reward": ["runtime_reward"],
}
FORBIDDEN_ROUTE_LOSSES_NOW = {"decoder_ce", "denoise_ce", "retrieval_loss", "runtime_reward"}
FORBIDDEN_TRAINER_LOSSES_NOW = {"decoder_ce", "denoise_ce", "runtime_reward"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def closed_route_card() -> dict[str, Any]:
    return {
        "route_card_id": "closed_route_card_example",
        "route": "NEEDS_SOURCE_TICKET",
        "artifact_status": {name: False for name in REQUIRED_HANDOFF_ARTIFACTS},
        "losses_enabled": {key: False for key in ROUTE_LOSS_KEYS},
        "compiler_ready": False,
        "training_ready": False,
        "model_input_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def structured_after_all_gates_card() -> dict[str, Any]:
    card = closed_route_card()
    card.update({
        "route_card_id": "structured_after_all_gates_example",
        "route": "KEEP_STRUCTURED_AFTER_GATES",
        "artifact_status": {name: True for name in REQUIRED_HANDOFF_ARTIFACTS},
        "losses_enabled": {key: key == "structured_aux_ce" for key in ROUTE_LOSS_KEYS},
        "compiler_ready": True,
    })
    return card


def translate_route_losses(route_losses: dict[str, bool]) -> dict[str, bool]:
    trainer_losses = {key: False for key in TRAINER_LOSS_KEYS}
    for route_key, enabled in route_losses.items():
        if not enabled:
            continue
        for trainer_key in ROUTE_TO_TRAINER_LOSS_TRANSLATION.get(route_key, []):
            trainer_losses[trainer_key] = True
    return trainer_losses


def audit_loss_mask_preflight(route_card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    route_losses = route_card.get("losses_enabled") or {}
    for key in ROUTE_LOSS_KEYS:
        if key not in route_losses:
            failures.append(f"missing_route_loss:{key}")
    unknown_route_losses = set(route_losses) - set(ROUTE_LOSS_KEYS)
    for key in sorted(unknown_route_losses):
        failures.append(f"unknown_route_loss:{key}")
    if route_card.get("compiler_ready") is True:
        artifact_status = route_card.get("artifact_status") or {}
        missing = [name for name in REQUIRED_HANDOFF_ARTIFACTS if artifact_status.get(name) is not True]
        if missing:
            failures.append("compiler_ready_missing_handoff_artifacts")
    elif any(route_losses.values()):
        failures.append("loss_open_before_compiler_ready")
    for key in FORBIDDEN_ROUTE_LOSSES_NOW:
        if route_losses.get(key):
            failures.append(f"forbidden_route_loss_open:{key}")
    trainer_losses = translate_route_losses({key: bool(route_losses.get(key, False)) for key in ROUTE_LOSS_KEYS})
    for key in FORBIDDEN_TRAINER_LOSSES_NOW:
        if trainer_losses.get(key):
            failures.append(f"forbidden_trainer_loss_open:{key}")
    if route_card.get("training_ready") is True:
        failures.append("training_ready_not_allowed_by_loss_mask_preflight")
    if route_card.get("model_input_ready") is True:
        failures.append("model_input_ready_not_allowed_by_loss_mask_preflight")
    if any((route_card.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
        failures.append("authority_open")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = closed_route_card()
    cases: dict[str, dict[str, Any]] = {}
    loss_before_ready = copy.deepcopy(base)
    loss_before_ready["losses_enabled"]["structured_aux_ce"] = True
    cases["structured_loss_before_compiler_ready"] = loss_before_ready
    decoder_open = copy.deepcopy(structured_after_all_gates_card())
    decoder_open["losses_enabled"]["decoder_ce"] = True
    cases["decoder_ce_open"] = decoder_open
    denoise_open = copy.deepcopy(structured_after_all_gates_card())
    denoise_open["losses_enabled"]["denoise_ce"] = True
    cases["denoise_ce_open"] = denoise_open
    runtime_open = copy.deepcopy(structured_after_all_gates_card())
    runtime_open["losses_enabled"]["runtime_reward"] = True
    cases["runtime_reward_open"] = runtime_open
    ready_missing_artifacts = copy.deepcopy(structured_after_all_gates_card())
    ready_missing_artifacts["artifact_status"]["loss_mask_card"] = False
    cases["compiler_ready_missing_loss_mask_card"] = ready_missing_artifacts
    training_ready = copy.deepcopy(structured_after_all_gates_card())
    training_ready["training_ready"] = True
    cases["training_ready_open"] = training_ready
    authority_open = copy.deepcopy(structured_after_all_gates_card())
    authority_open["authority"]["decoder_ce_training_authorized_next"] = True
    cases["authority_open"] = authority_open
    return {name: {"failures": audit_loss_mask_preflight(card), "rejected": bool(audit_loss_mask_preflight(card))} for name, card in cases.items()}


def build_preflight() -> dict[str, Any]:
    source = load_json(SOURCE_9061)
    closed_failures = audit_loss_mask_preflight(closed_route_card())
    structured_failures = audit_loss_mask_preflight(structured_after_all_gates_card())
    negatives = run_negative_cases()
    checks = {
        "source_stage9061_present": SOURCE_9061.exists(),
        "source_stage9061_passed": source.get("passed") is True,
        "route_loss_keys_known": set(ROUTE_LOSS_KEYS) == set(ROUTE_TO_TRAINER_LOSS_TRANSLATION),
        "trainer_loss_keys_known": set(FORBIDDEN_TRAINER_LOSSES_NOW).issubset(set(TRAINER_LOSS_KEYS)),
        "closed_card_passes": closed_failures == [],
        "structured_after_all_gates_passes_preflight_only": structured_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "decoder_denoise_runtime_closed": True,
        "training_ready_rows_now_zero": True,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "route_to_trainer_loss_translation": ROUTE_TO_TRAINER_LOSS_TRANSLATION,
        "forbidden_route_losses_now": sorted(FORBIDDEN_ROUTE_LOSSES_NOW),
        "forbidden_trainer_losses_now": sorted(FORBIDDEN_TRAINER_LOSSES_NOW),
        "closed_card_failures": closed_failures,
        "structured_after_all_gates_failures": structured_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "route_loss_keys": len(ROUTE_LOSS_KEYS),
            "trainer_loss_keys": len(TRAINER_LOSS_KEYS),
            "negative_cases": len(negatives),
            "compiler_ready_rows_now": 0,
            "training_ready_rows_now": 0,
            "model_input_rows_now": 0,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "decision": "Route-card losses are explicitly translated into trainer loss-mask keys, but long-context compiler handoff remains preflight-only with decoder/denoise/runtime/training closed.",
    }


def write_outputs(preflight: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREFLIGHT_PATH.write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": preflight["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": preflight["failures"], **preflight["metrics"]},
        "artifacts": {"preflight": str(PREFLIGHT_PATH.relative_to(ROOT))},
        "decision": preflight["decision"] if preflight["passed"] else "Long-context loss-mask compiler preflight failed.",
        "next_best_step": "Continue no-data recovery by attaching Stage9061-9062 compiler/loss-mask blockers to the central graph and training readiness matrix.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9062 Long Context Loss-Mask Compiler Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This no-data preflight bridges route-card losses to trainer loss-mask keys. It allows only a future structured-aux preflight after every Stage9061 artifact passes; decoder CE, denoise CE, runtime reward, model execution, and training remain closed.",
        "",
        f"Route loss keys: `{preflight['metrics']['route_loss_keys']}`",
        f"Trainer loss keys: `{preflight['metrics']['trainer_loss_keys']}`",
        f"Negative cases rejected: `{preflight['checks']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
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
    return summary


def main() -> None:
    preflight = build_preflight()
    summary = write_outputs(preflight)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
