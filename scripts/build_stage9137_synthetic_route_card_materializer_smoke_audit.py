#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.route_card_materializer import validate_route_cards
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from route_card_materializer import validate_route_cards  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9137
NAME = "stage9137_synthetic_route_card_materializer_smoke_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9136 = ROOT / "runs/summaries/stage9136_synthetic_route_card_materializer_smoke.json"
SOURCE_ROUTE_CARDS = ROOT / "runs/local/artifacts/stage9136_synthetic_route_card_materializer_smoke/synthetic_route_cards.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_ROUTE_CARD_MATERIALIZER_SMOKE_AUDIT_STAGE9137.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "synthetic_route_card_materializer_smoke_audit.json"

NEGATIVE_MUTATIONS = [
    "open_authority",
    "unknown_route",
    "missing_required_field",
    "missing_anti_cheat",
    "risk_bucket_mismatch",
    "recommended_action_mismatch",
    "bounded_decoder_budget_false",
    "holdout_wrong_bucket",
    "duplicate_row_id",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mutate(cards: list[dict[str, Any]], mutation: str) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(cards)
    first = mutated[0]
    by_route = {card["route"]: card for card in mutated}
    if mutation == "open_authority":
        first["authority"]["runtime_authorized"] = True
    elif mutation == "unknown_route":
        first["route"] = "UNKNOWN"
    elif mutation == "missing_required_field":
        first.pop("loss_mask_ref")
    elif mutation == "missing_anti_cheat":
        first["anti_cheat"].pop("label_leak_checked")
    elif mutation == "risk_bucket_mismatch":
        first["risk_bucket"] = "NEEDS_HUMAN_REVIEW"
    elif mutation == "recommended_action_mismatch":
        first["recommended_action"] = "NEEDS_HUMAN_REVIEW"
    elif mutation == "bounded_decoder_budget_false":
        by_route["KEEP_BOUNDED_DECODER"]["decoder_budget_ok"] = False
    elif mutation == "holdout_wrong_bucket":
        by_route["HOLD_LONG_OUTPUT"]["target_length_bucket"] = "bounded"
    elif mutation == "duplicate_row_id":
        mutated[1]["row_id"] = first["row_id"]
    return mutated


def run_negative_cases(cards: list[dict[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for mutation in NEGATIVE_MUTATIONS:
        failures = validate_route_cards(mutate(cards, mutation))
        results[mutation] = {"failures": failures, "rejected": bool(failures)}
    return results


def build_audit(registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or {"metrics": {"latest_stage": 9136, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source = load_json(SOURCE_9136)
    cards = load_jsonl(SOURCE_ROUTE_CARDS)
    card_failures = validate_route_cards(cards)
    negatives = run_negative_cases(cards)
    route_counts: dict[str, int] = {}
    for card in cards:
        route_counts[card["route"]] = route_counts.get(card["route"], 0) + 1
    checks = {
        "source_stage9136_passed": source.get("passed") is True,
        "synthetic_route_card_file_present": SOURCE_ROUTE_CARDS.exists(),
        "route_card_count": len(cards) == len(ROUTE_ENUM),
        "all_routes_covered": set(route_counts) == set(ROUTE_ENUM),
        "card_failures_empty": card_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "no_real_inputs": all((card.get("provenance") or {}).get("synthetic_only") is True for card in cards),
        "authority_closed": all(not any((card.get("authority") or {}).values()) for card in cards),
        "registry_frontier_stage9136": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9136,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
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
        "route_counts": dict(sorted(route_counts.items())),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "synthetic_route_cards_audited": len(cards),
            "routes_covered": len(route_counts),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
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
        "decision": "Audited synthetic route-card materializer outputs and rejected unsafe mutated cards. Real judge/ranker inputs, real route cards, compiler handoff, trainer/model paths, uploads, cleanup, runtime, and training remain closed.",
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
        "decision": audit["decision"] if audit["passed"] else "Synthetic route-card materializer output audit failed.",
        "next_best_step": "Design real judge/ranker route-card input authorization gate; do not load real data yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9137 Synthetic Route-Card Materializer Smoke Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Synthetic route cards audited: `{audit['metrics']['synthetic_route_cards_audited']}`",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
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
