#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9130_synthetic_route_to_loss_mask_translator_smoke_design import SYNTHETIC_FIXTURES
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.synthetic_route_to_loss_mask_translator import (
        translate_synthetic_fixtures,
        validate_synthetic_loss_masks,
        write_jsonl,
    )
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9130_synthetic_route_to_loss_mask_translator_smoke_design import SYNTHETIC_FIXTURES  # type: ignore
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from synthetic_route_to_loss_mask_translator import (  # type: ignore
        translate_synthetic_fixtures,
        validate_synthetic_loss_masks,
        write_jsonl,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9132
NAME = "stage9132_synthetic_route_to_loss_mask_translator_smoke"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9131 = ROOT / "runs/summaries/stage9131_synthetic_route_to_loss_mask_translator_smoke_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_ROUTE_TO_LOSS_MASK_TRANSLATOR_SMOKE_STAGE9132.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LOSS_MASKS = OUT_DIR / "synthetic_loss_masks.jsonl"
SMOKE = OUT_DIR / "synthetic_route_to_loss_mask_translator_smoke.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_smoke(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9131)
    loss_masks = translate_synthetic_fixtures(SYNTHETIC_FIXTURES)
    validation_failures = validate_synthetic_loss_masks(loss_masks)
    by_route = {card["loss_authority_evidence"]["route"]: card for card in loss_masks}
    checks = {
        "source_stage9131_passed": source.get("passed") is True,
        "synthetic_only_inputs": all((card.get("anti_cheat") or {}).get("synthetic_only") is True for card in loss_masks),
        "all_route_fixtures_present": len(loss_masks) == len(SYNTHETIC_FIXTURES),
        "decoder_ce_only_for_keep_bounded_decoder": [
            card["loss_authority_evidence"]["route"] for card in loss_masks if "decoder_ce" in card["enabled_losses"]
        ] == ["KEEP_BOUNDED_DECODER"],
        "quarantine_fixture_has_no_enabled_losses": by_route["QUARANTINE_LABEL_CONFLICT"]["enabled_losses"] == [],
        "hold_long_output_blocks_decoder_ce": "decoder_ce" not in by_route["HOLD_LONG_OUTPUT"]["enabled_losses"],
        "needs_retrieval_blocks_decoder_ce": "decoder_ce" not in by_route["NEEDS_RETRIEVAL"]["enabled_losses"],
        "denoise_route_blocks_decoder_ce": "decoder_ce" not in by_route["USE_FOR_DENOISE_REPAIR"]["enabled_losses"],
        "all_fixtures_emit_authority_closed": all(not any(card["authority"].values()) for card in loss_masks),
        "all_fixtures_emit_telemetry_required": all(len(card["telemetry_required"]) >= 6 for card in loss_masks),
        "validation_failures_empty": validation_failures == [],
        "registry_frontier_stage9131": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9131,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SYNTHETIC_ROUTE_TO_LOSS_MASK_TRANSLATOR_SMOKE_NO_REAL_DATA",
        "checks": checks,
        "validation_failures": validation_failures,
        "loss_masks": loss_masks,
        "metrics": {
            "synthetic_fixtures": len(SYNTHETIC_FIXTURES),
            "synthetic_loss_masks": len(loss_masks),
            "synthetic_loss_masks_materialized_now": True,
            "real_route_cards_used": 0,
            "real_loss_masks_materialized": 0,
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
        "decision": "Materialized synthetic-only loss-mask cards from synthetic route fixtures. Real route cards, real loss masks, compiler handoff, trainer/model paths, uploads, cleanup, runtime, and training remain closed.",
    }


def validate_smoke(smoke: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in smoke["checks"].items() if value is not True]
    if any((smoke.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9131, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["real_route_cards_used", "real_loss_masks_materialized"]:
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
    if smoke["metrics"].get("synthetic_loss_masks_materialized_now") is not True:
        failures.append("synthetic_loss_masks_not_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    smoke = build_smoke(registry)
    failures = validate_smoke(smoke, registry)
    write_jsonl(LOSS_MASKS, smoke["loss_masks"])
    public_smoke = dict(smoke)
    public_smoke.pop("loss_masks")
    public_smoke["failures"] = failures
    public_smoke["passed"] = not failures
    public_smoke["artifacts"] = {"synthetic_loss_masks": str(LOSS_MASKS.relative_to(ROOT))}
    SMOKE.write_text(json.dumps(public_smoke, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **smoke["metrics"]},
        "artifacts": {
            "smoke": str(SMOKE.relative_to(ROOT)),
            "synthetic_loss_masks": str(LOSS_MASKS.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": smoke["decision"] if not failures else "Synthetic route-to-loss-mask translator smoke failed.",
        "next_best_step": "Audit synthetic-only loss-mask smoke outputs, then design real route-card materialization without trainer execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9132 Synthetic Route-To-Loss-Mask Translator Smoke",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Synthetic loss masks: `{smoke['metrics']['synthetic_loss_masks']}`",
        "",
        "No real route cards, real loss masks, compiler handoff, trainer/model paths, uploads, cleanup, runtime, or training were opened.",
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
