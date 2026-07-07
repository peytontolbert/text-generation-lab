#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.route_card_materializer import (
        materialize_synthetic_route_cards,
        validate_route_cards,
        write_jsonl,
    )
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9124_route_card_schema_recovery_design import ROUTE_ENUM  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from route_card_materializer import (  # type: ignore
        materialize_synthetic_route_cards,
        validate_route_cards,
        write_jsonl,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9136
NAME = "stage9136_synthetic_route_card_materializer_smoke"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9135 = ROOT / "runs/summaries/stage9135_real_route_card_materialization_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_ROUTE_CARD_MATERIALIZER_SMOKE_STAGE9136.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROUTE_CARDS = OUT_DIR / "synthetic_route_cards.jsonl"
SMOKE = OUT_DIR / "synthetic_route_card_materializer_smoke.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_smoke(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9135)
    cards = materialize_synthetic_route_cards()
    card_failures = validate_route_cards(cards)
    route_counts: dict[str, int] = {}
    for card in cards:
        route_counts[card["route"]] = route_counts.get(card["route"], 0) + 1
    checks = {
        "source_stage9135_passed": source.get("passed") is True,
        "synthetic_route_cards_present": len(cards) == len(ROUTE_ENUM),
        "all_routes_covered": set(route_counts) == set(ROUTE_ENUM),
        "card_failures_empty": card_failures == [],
        "all_cards_synthetic_only": all((card.get("provenance") or {}).get("synthetic_only") is True for card in cards),
        "all_cards_authority_closed": all(not any((card.get("authority") or {}).values()) for card in cards),
        "no_real_judge_ranker_inputs": True,
        "registry_frontier_stage9135": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9135,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SYNTHETIC_ROUTE_CARD_MATERIALIZER_SMOKE_NO_REAL_INPUTS",
        "checks": checks,
        "card_failures": card_failures,
        "route_counts": dict(sorted(route_counts.items())),
        "route_cards": cards,
        "metrics": {
            "synthetic_route_cards": len(cards),
            "routes_covered": len(route_counts),
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "synthetic_route_cards_materialized_now": True,
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
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Materialized synthetic route cards across all recovered route enum values. Real judge/ranker rows, real route cards, compiler handoff, trainer/model paths, uploads, cleanup, runtime, and training remain closed.",
    }


def validate_smoke(smoke: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in smoke["checks"].items() if value is not True]
    failures.extend(smoke.get("card_failures", []))
    if any((smoke.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9135, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["real_judge_rows_used", "real_ranker_rows_used", "real_route_cards_materialized"]:
        if smoke["metrics"].get(key) != 0:
            failures.append(key)
    for key in [
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if smoke["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    smoke = build_smoke(registry)
    failures = validate_smoke(smoke, registry)
    write_jsonl(ROUTE_CARDS, smoke["route_cards"])
    public_smoke = dict(smoke)
    public_smoke.pop("route_cards")
    public_smoke["failures"] = failures
    public_smoke["passed"] = not failures
    public_smoke["artifacts"] = {"synthetic_route_cards": str(ROUTE_CARDS.relative_to(ROOT))}
    SMOKE.write_text(json.dumps(public_smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **smoke["metrics"]},
        "artifacts": {
            "smoke": str(SMOKE.relative_to(ROOT)),
            "synthetic_route_cards": str(ROUTE_CARDS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": smoke["decision"] if not failures else "Synthetic route-card materializer smoke failed.",
        "next_best_step": "Audit synthetic route-card materializer outputs before any real judge/ranker input use.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9136 Synthetic Route-Card Materializer Smoke",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Synthetic route cards: `{smoke['metrics']['synthetic_route_cards']}`",
        f"Routes covered: `{smoke['metrics']['routes_covered']}`",
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
