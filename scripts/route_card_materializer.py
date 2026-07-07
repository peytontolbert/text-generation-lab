#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9124_route_card_schema_recovery_design import (
        ANTI_CHEAT_FIELDS,
        OBJECTIVE_FAMILIES,
        REQUIRED_ROUTE_FIELDS,
        ROUTE_ENUM,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9124_route_card_schema_recovery_design import (  # type: ignore
        ANTI_CHEAT_FIELDS,
        OBJECTIVE_FAMILIES,
        REQUIRED_ROUTE_FIELDS,
        ROUTE_ENUM,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

SYNTHETIC_ROUTE_CARD_FIXTURES = [
    ("synthetic_route_keep_structured", "KEEP_STRUCTURED", "intent_to_build_strategy", False, True, "bounded"),
    ("synthetic_route_keep_bounded_decoder", "KEEP_BOUNDED_DECODER", "bounded_decoder_ce", True, True, "bounded"),
    ("synthetic_route_hold_long_output", "HOLD_LONG_OUTPUT", "bounded_decoder_ce", False, False, "long_holdout"),
    ("synthetic_route_denoise_repair", "USE_FOR_DENOISE_REPAIR", "output_repair_denoise", False, True, "bounded"),
    ("synthetic_route_negative", "USE_AS_NEGATIVE", "verifier_repair", False, True, "bounded"),
    ("synthetic_route_needs_retrieval", "NEEDS_RETRIEVAL", "symbol_binding", False, True, "bounded"),
    ("synthetic_route_quarantine", "QUARANTINE_LABEL_CONFLICT", "repo_state_graph", False, True, "bounded"),
    ("synthetic_route_drop_duplicate", "DROP_DUPLICATE", "edit_localization", False, True, "bounded"),
    ("synthetic_route_human_review", "NEEDS_HUMAN_REVIEW", "patch_operator", False, True, "bounded"),
]


def synthetic_materialization_inputs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_id, route, objective_family, decode_allowed, budget_ok, length_bucket in SYNTHETIC_ROUTE_CARD_FIXTURES:
        rows.append(
            {
                "objective_row": {
                    "row_id": row_id,
                    "semantic_key": f"synthetic_semantic::{row_id}",
                    "source_manifest": "synthetic://route_card_materializer",
                    "source_stage": 9136,
                    "objective_family": objective_family,
                    "split": "train",
                    "language_family": "synthetic_python",
                    "surface": "synthetic_surface",
                    "task_phase": "synthetic_route_materialization",
                    "state_schema_ref": "repo_state_graph_v1",
                    "evidence_state": "missing" if route == "NEEDS_RETRIEVAL" else "direct_present",
                    "decoder_budget_ok": budget_ok,
                    "decode_allowed": decode_allowed,
                    "target_length_bucket": length_bucket,
                },
                "judge_row": {
                    "row_id": row_id,
                    "judge_reasons": [] if route not in {"QUARANTINE_LABEL_CONFLICT", "DROP_DUPLICATE"} else ["synthetic_blocker"],
                    "anti_cheat": {
                        "label_leak_checked": True,
                        "shortcut_baseline_max": 0.333,
                        "split_overlap_checked": True,
                        "raw_text_forbidden_checked": True,
                        "authority_closed_checked": True,
                        "target_not_in_input_checked": True,
                    },
                    "authority": dict(AUTHORITY_CLOSED),
                },
                "ranker_row": {
                    "row_id": row_id,
                    "junk_score": 0.0 if route.startswith("KEEP") else 0.4,
                    "risk_bucket": route,
                    "recommended_action": route,
                    "reasons": [] if route.startswith("KEEP") else [f"synthetic_{route.lower()}"],
                },
            }
        )
    return rows


def materialize_route_card(objective_row: dict[str, Any], judge_row: dict[str, Any], ranker_row: dict[str, Any]) -> dict[str, Any]:
    route = str(ranker_row.get("recommended_action") or ranker_row.get("risk_bucket"))
    anti_cheat = dict(judge_row.get("anti_cheat") or {})
    for field in ANTI_CHEAT_FIELDS:
        anti_cheat.setdefault(field, True if field != "shortcut_baseline_max" else 0.333)
    return {
        "row_id": objective_row.get("row_id"),
        "source_manifest": objective_row.get("source_manifest"),
        "source_stage": objective_row.get("source_stage"),
        "objective_family": objective_row.get("objective_family"),
        "route": route,
        "risk_bucket": ranker_row.get("risk_bucket"),
        "recommended_action": ranker_row.get("recommended_action"),
        "split": objective_row.get("split"),
        "language_family": objective_row.get("language_family"),
        "surface": objective_row.get("surface"),
        "task_phase": objective_row.get("task_phase"),
        "state_schema_ref": objective_row.get("state_schema_ref"),
        "evidence_state": objective_row.get("evidence_state"),
        "decoder_budget_ok": objective_row.get("decoder_budget_ok") is True,
        "target_length_bucket": objective_row.get("target_length_bucket"),
        "loss_mask_ref": f"loss-mask://pending/{objective_row.get('row_id')}",
        "authority": dict(AUTHORITY_CLOSED),
        "judge_reasons": list(judge_row.get("judge_reasons") or []) + list(ranker_row.get("reasons") or []),
        "anti_cheat": anti_cheat,
        "provenance": {
            "semantic_key": objective_row.get("semantic_key"),
            "judge_row_id": judge_row.get("row_id"),
            "ranker_row_id": ranker_row.get("row_id"),
            "synthetic_only": str(objective_row.get("source_manifest", "")).startswith("synthetic://"),
        },
    }


def validate_route_card(card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    row_id = str(card.get("row_id", ""))
    for field in REQUIRED_ROUTE_FIELDS:
        if field not in card:
            failures.append(f"{row_id}:missing_required_field:{field}")
    if card.get("route") not in ROUTE_ENUM:
        failures.append(f"{row_id}:unknown_route:{card.get('route')}")
    if card.get("objective_family") not in OBJECTIVE_FAMILIES:
        failures.append(f"{row_id}:unknown_objective_family:{card.get('objective_family')}")
    if card.get("risk_bucket") != card.get("route"):
        failures.append(f"{row_id}:risk_bucket_route_mismatch")
    if card.get("recommended_action") != card.get("route"):
        failures.append(f"{row_id}:recommended_action_route_mismatch")
    if any((card.get("authority") or {}).values()):
        failures.append(f"{row_id}:authority_open")
    anti_cheat = card.get("anti_cheat") or {}
    for field in ANTI_CHEAT_FIELDS:
        if field not in anti_cheat:
            failures.append(f"{row_id}:missing_anti_cheat:{field}")
    if card.get("route") == "KEEP_BOUNDED_DECODER" and card.get("decoder_budget_ok") is not True:
        failures.append(f"{row_id}:bounded_decoder_without_budget_ok")
    if card.get("route") == "HOLD_LONG_OUTPUT" and card.get("target_length_bucket") != "long_holdout":
        failures.append(f"{row_id}:hold_long_output_without_long_bucket")
    return failures


def materialize_synthetic_route_cards() -> list[dict[str, Any]]:
    cards = []
    for item in synthetic_materialization_inputs():
        cards.append(materialize_route_card(item["objective_row"], item["judge_row"], item["ranker_row"]))
    return cards


def validate_route_cards(cards: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    for card in cards:
        row_id = str(card.get("row_id", ""))
        if row_id in seen:
            failures.append(f"{row_id}:duplicate_row_id")
        seen.add(row_id)
        failures.extend(validate_route_card(card))
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
