#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9128_loss_mask_card_schema_recovery_design import (
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_TELEMETRY,
    )
    from scripts.build_stage9130_synthetic_route_to_loss_mask_translator_smoke_design import (
        SYNTHETIC_FIXTURES,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9128_loss_mask_card_schema_recovery_design import (  # type: ignore
        REQUIRED_DISABLED_BY_DEFAULT,
        REQUIRED_TELEMETRY,
    )
    from build_stage9130_synthetic_route_to_loss_mask_translator_smoke_design import (  # type: ignore
        SYNTHETIC_FIXTURES,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROUTE_TO_ENABLED_LOSSES = {
    "KEEP_STRUCTURED": [
        "surface_role_ce",
        "repair_surface_ce",
        "action_ce",
        "evidence_state_ce",
        "budget_gate_ce",
        "decode_gate_ce",
    ],
    "KEEP_BOUNDED_DECODER": ["decoder_ce"],
    "HOLD_LONG_OUTPUT": ["long_output_holdout_supervision"],
    "USE_FOR_DENOISE_REPAIR": ["denoise_ce"],
    "USE_AS_NEGATIVE": ["abstain_ce", "suppress_decode_ce"],
    "NEEDS_RETRIEVAL": ["retrieve_more_ce", "decode_block_ce"],
    "QUARANTINE_LABEL_CONFLICT": [],
    "DROP_DUPLICATE": [],
    "NEEDS_HUMAN_REVIEW": [],
}


def _bool(value: Any) -> bool:
    return value is True


def translate_synthetic_fixture(fixture: dict[str, Any], *, created_by_stage: int = 9132) -> dict[str, Any]:
    route = str(fixture["route"])
    expected_losses = list(ROUTE_TO_ENABLED_LOSSES.get(route, []))
    decoder_budget_ok = _bool(fixture.get("decoder_budget_ok"))
    decode_allowed = _bool(fixture.get("decode_allowed"))
    repair_route = _bool(fixture.get("repair_route"))
    decoder_ce_allowed = route == "KEEP_BOUNDED_DECODER" and decoder_budget_ok and decode_allowed
    denoise_ce_allowed = route == "USE_FOR_DENOISE_REPAIR" and repair_route

    enabled_losses: list[str] = []
    forbidden_loss_reasons: dict[str, str] = {}
    for loss in expected_losses:
        if loss == "decoder_ce" and not decoder_ce_allowed:
            forbidden_loss_reasons[loss] = "decoder_ce_requires_keep_bounded_decoder_budget_and_decode"
            continue
        if loss == "denoise_ce" and not denoise_ce_allowed:
            forbidden_loss_reasons[loss] = "denoise_ce_requires_repair_route"
            continue
        enabled_losses.append(loss)

    disabled_losses = set(REQUIRED_DISABLED_BY_DEFAULT)
    disabled_losses.update(fixture.get("expected_disabled_losses", []))
    disabled_losses.update(loss for loss in ROUTE_TO_ENABLED_LOSSES["KEEP_STRUCTURED"] if loss not in enabled_losses)
    disabled_losses.update(["abstain_ce", "suppress_decode_ce", "retrieve_more_ce", "decode_block_ce", "long_output_holdout_supervision"])
    for loss in enabled_losses:
        disabled_losses.discard(loss)

    loss_weights = {loss: 1.0 for loss in enabled_losses}
    target_token_len = int(fixture.get("target_token_len", 0))
    target_length_bucket = "synthetic_unknown"
    if target_token_len > 4096:
        target_length_bucket = "long_holdout"
    elif target_token_len > 0:
        target_length_bucket = "bounded"

    return {
        "row_id": fixture["fixture_id"],
        "route_card_ref": f"synthetic://stage9130/{fixture['fixture_id']}",
        "enabled_losses": enabled_losses,
        "disabled_losses": sorted(disabled_losses),
        "loss_weights": loss_weights,
        "decoder_ce_allowed": decoder_ce_allowed,
        "denoise_ce_allowed": denoise_ce_allowed,
        "structured_aux_allowed": route == "KEEP_STRUCTURED",
        "runtime_reward_allowed": False,
        "authority": dict(AUTHORITY_CLOSED),
        "decoder_budget_ok": decoder_budget_ok,
        "decode_allowed": decode_allowed,
        "target_token_len": target_token_len,
        "target_length_bucket": target_length_bucket,
        "loss_authority_evidence": {
            "route": route,
            "synthetic_only": True,
            "decoder_budget_ok": decoder_budget_ok,
            "decode_allowed": decode_allowed,
            "repair_route": repair_route,
            "runtime_closed": True,
        },
        "forbidden_loss_reasons": forbidden_loss_reasons,
        "telemetry_required": list(REQUIRED_TELEMETRY),
        "anti_cheat": {
            "synthetic_only": True,
            "real_route_card_used": False,
            "real_dataset_row_used": False,
            "target_not_in_input": True,
            "authority_closed": True,
        },
        "created_by_stage": created_by_stage,
        "schema_version": "loss_mask_card_v1_synthetic_smoke",
    }


def translate_synthetic_fixtures(fixtures: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return [translate_synthetic_fixture(fixture) for fixture in (fixtures or SYNTHETIC_FIXTURES)]


def validate_synthetic_loss_masks(loss_masks: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if len(loss_masks) != len(SYNTHETIC_FIXTURES):
        failures.append("synthetic_loss_mask_count_mismatch")
    for card in loss_masks:
        row_id = str(card.get("row_id", ""))
        route = str((card.get("loss_authority_evidence") or {}).get("route", ""))
        enabled = set(card.get("enabled_losses", []))
        if any((card.get("authority") or {}).values()):
            failures.append(f"{row_id}:authority_open")
        if not (card.get("anti_cheat") or {}).get("synthetic_only"):
            failures.append(f"{row_id}:not_synthetic_only")
        if card.get("runtime_reward_allowed") is not False:
            failures.append(f"{row_id}:runtime_reward_allowed")
        if "decoder_ce" in enabled and route != "KEEP_BOUNDED_DECODER":
            failures.append(f"{row_id}:decoder_ce_route_violation")
        if "denoise_ce" in enabled and route != "USE_FOR_DENOISE_REPAIR":
            failures.append(f"{row_id}:denoise_ce_route_violation")
        if route == "QUARANTINE_LABEL_CONFLICT" and enabled:
            failures.append(f"{row_id}:quarantine_has_enabled_losses")
        if route == "HOLD_LONG_OUTPUT" and "decoder_ce" in enabled:
            failures.append(f"{row_id}:hold_long_output_decoder_ce")
        if route == "NEEDS_RETRIEVAL" and "decoder_ce" in enabled:
            failures.append(f"{row_id}:needs_retrieval_decoder_ce")
        for telemetry in REQUIRED_TELEMETRY:
            if telemetry not in card.get("telemetry_required", []):
                failures.append(f"{row_id}:missing_telemetry:{telemetry}")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
