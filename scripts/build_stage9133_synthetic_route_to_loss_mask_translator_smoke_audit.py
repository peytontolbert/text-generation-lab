#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9128_loss_mask_card_schema_recovery_design import REQUIRED_LOSS_MASK_FIELDS
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.synthetic_route_to_loss_mask_translator import validate_synthetic_loss_masks
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9128_loss_mask_card_schema_recovery_design import REQUIRED_LOSS_MASK_FIELDS  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from synthetic_route_to_loss_mask_translator import validate_synthetic_loss_masks  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9133
NAME = "stage9133_synthetic_route_to_loss_mask_translator_smoke_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9132 = ROOT / "runs/summaries/stage9132_synthetic_route_to_loss_mask_translator_smoke.json"
SOURCE_LOSS_MASKS = ROOT / "runs/local/artifacts/stage9132_synthetic_route_to_loss_mask_translator_smoke/synthetic_loss_masks.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_ROUTE_TO_LOSS_MASK_TRANSLATOR_SMOKE_AUDIT_STAGE9133.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "synthetic_route_to_loss_mask_translator_smoke_audit.json"

NEGATIVE_MUTATIONS = [
    "open_authority",
    "structured_decoder_ce",
    "quarantine_enabled_loss",
    "holdout_decoder_ce",
    "needs_retrieval_decoder_ce",
    "denoise_decoder_ce",
    "missing_required_field",
    "missing_telemetry",
    "real_route_card_used",
    "runtime_reward_allowed",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_cards(cards: list[dict[str, Any]]) -> list[str]:
    failures = validate_synthetic_loss_masks(cards)
    seen = set()
    for card in cards:
        row_id = str(card.get("row_id", ""))
        if row_id in seen:
            failures.append(f"{row_id}:duplicate_row_id")
        seen.add(row_id)
        for field in REQUIRED_LOSS_MASK_FIELDS:
            if field not in card:
                failures.append(f"{row_id}:missing_required_field:{field}")
        if not str(card.get("route_card_ref", "")).startswith("synthetic://"):
            failures.append(f"{row_id}:non_synthetic_route_card_ref")
        if (card.get("anti_cheat") or {}).get("real_route_card_used") is not False:
            failures.append(f"{row_id}:real_route_card_used")
        if (card.get("anti_cheat") or {}).get("real_dataset_row_used") is not False:
            failures.append(f"{row_id}:real_dataset_row_used")
        if card.get("schema_version") != "loss_mask_card_v1_synthetic_smoke":
            failures.append(f"{row_id}:wrong_schema_version")
    return failures


def mutate(cards: list[dict[str, Any]], mutation: str) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(cards)
    first = mutated[0]
    by_route = {card["loss_authority_evidence"]["route"]: card for card in mutated}
    if mutation == "open_authority":
        first["authority"]["model_execution_authorized_next"] = True
    elif mutation == "structured_decoder_ce":
        by_route["KEEP_STRUCTURED"]["enabled_losses"].append("decoder_ce")
    elif mutation == "quarantine_enabled_loss":
        by_route["QUARANTINE_LABEL_CONFLICT"]["enabled_losses"].append("action_ce")
    elif mutation == "holdout_decoder_ce":
        by_route["HOLD_LONG_OUTPUT"]["enabled_losses"].append("decoder_ce")
    elif mutation == "needs_retrieval_decoder_ce":
        by_route["NEEDS_RETRIEVAL"]["enabled_losses"].append("decoder_ce")
    elif mutation == "denoise_decoder_ce":
        by_route["USE_FOR_DENOISE_REPAIR"]["enabled_losses"].append("decoder_ce")
    elif mutation == "missing_required_field":
        first.pop("loss_weights")
    elif mutation == "missing_telemetry":
        first["telemetry_required"] = []
    elif mutation == "real_route_card_used":
        first["anti_cheat"]["real_route_card_used"] = True
    elif mutation == "runtime_reward_allowed":
        first["runtime_reward_allowed"] = True
    return mutated


def run_negative_cases(cards: list[dict[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for mutation in NEGATIVE_MUTATIONS:
        failures = audit_cards(mutate(cards, mutation))
        results[mutation] = {"failures": failures, "rejected": bool(failures)}
    return results


def build_audit(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or {"metrics": {"latest_stage": 9132, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source = load_json(SOURCE_9132)
    cards = load_jsonl(SOURCE_LOSS_MASKS)
    card_failures = audit_cards(cards)
    negatives = run_negative_cases(cards)
    checks = {
        "source_stage9132_passed": source.get("passed") is True,
        "synthetic_loss_mask_file_present": SOURCE_LOSS_MASKS.exists(),
        "synthetic_loss_mask_count": len(cards) == 6,
        "card_failures_empty": card_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "registry_frontier_stage9132": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9132,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "no_real_route_cards": all((card.get("anti_cheat") or {}).get("real_route_card_used") is False for card in cards),
        "no_real_dataset_rows": all((card.get("anti_cheat") or {}).get("real_dataset_row_used") is False for card in cards),
        "authority_closed": all(not any((card.get("authority") or {}).values()) for card in cards),
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
            "synthetic_loss_masks_audited": len(cards),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "real_route_cards_used": 0,
            "real_loss_masks_materialized": 0,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Audited synthetic loss-mask smoke outputs and rejected unsafe mutated cards. Real route cards, real loss masks, compiler handoff, trainer/model paths, uploads, cleanup, runtime, and training remain closed.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Synthetic loss-mask smoke output audit failed.",
        "next_best_step": "Design real route-card materialization from judge/ranker outputs without trainer execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9133 Synthetic Route-To-Loss-Mask Translator Smoke Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Synthetic loss masks audited: `{audit['metrics']['synthetic_loss_masks_audited']}`",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
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
