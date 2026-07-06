#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9056
NAME = "stage9056_long_context_synthetic_route_card_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9055 = ROOT / "runs/summaries/stage9055_long_context_synthetic_candidate_quality_audit.json"
AUDIT_9055 = ROOT / "runs/local/artifacts/stage9055_long_context_synthetic_candidate_quality_audit/synthetic_candidate_quality_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_SYNTHETIC_ROUTE_CARD_AUDIT_STAGE9056.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROUTES = OUT_DIR / "synthetic_long_context_route_cards.jsonl"
AUDIT = OUT_DIR / "synthetic_long_context_route_card_audit.json"

REQUIRED_GATES = [
    "source_output_ticket_granted",
    "source_lineage_card",
    "dataset_junk_ood_ranker_card",
    "shortcut_baseline_audit",
    "counterfactual_obligation_card",
    "loss_mask_card",
    "telemetry_contract",
]
LOSS_MASK_CLOSED = {
    "structured_aux_ce": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "retrieval_loss": False,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_route_cards() -> list[dict[str, Any]]:
    audit = load_json(AUDIT_9055)
    candidate_count = int(audit.get("candidate_count", 0))
    repo_paths = list(audit.get("repo_evidence_paths") or [])
    cards = []
    for idx in range(max(candidate_count, 1)):
        cards.append({
            "route_card_id": f"synthetic_long_context_route_{idx + 1:04d}",
            "candidate_id": f"synthetic_long_context_candidate_{idx + 1:04d}",
            "route": "CANDIDATE_REVIEW_ONLY",
            "compiler_ready": False,
            "training_ready": False,
            "model_input_ready": False,
            "repo_evidence_paths": repo_paths,
            "required_gates_before_compiler": list(REQUIRED_GATES),
            "losses_enabled": dict(LOSS_MASK_CLOSED),
            "authority": dict(AUTHORITY_CLOSED),
            "blocked_reason": "synthetic candidate has quality signal only; it lacks real source ticket, judge, shortcut, counterfactual, lineage, loss-mask, and telemetry gates",
        })
    return cards


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9055)
    cards = build_route_cards()
    checks = {
        "source_stage9055_present": SOURCE_9055.exists(),
        "source_stage9055_passed": source.get("passed") is True,
        "route_cards_present": len(cards) > 0,
        "all_review_only": all(card.get("route") == "CANDIDATE_REVIEW_ONLY" for card in cards),
        "compiler_ready_false": all(card.get("compiler_ready") is False for card in cards),
        "training_ready_false": all(card.get("training_ready") is False for card in cards),
        "model_input_ready_false": all(card.get("model_input_ready") is False for card in cards),
        "all_losses_closed": all(not any((card.get("losses_enabled") or {}).values()) for card in cards),
        "all_required_gates_present": all(set(REQUIRED_GATES).issubset(set(card.get("required_gates_before_compiler") or [])) for card in cards),
        "all_authority_closed": all(not any((card.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED) for card in cards),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "route_cards": len(cards),
        "routes": {card["route"]: sum(1 for row in cards if row["route"] == card["route"]) for card in cards},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "route_cards": len(cards),
            "review_only_routes": sum(1 for card in cards if card.get("route") == "CANDIDATE_REVIEW_ONLY"),
            "compiler_ready_rows": sum(1 for card in cards if card.get("compiler_ready") is True),
            "training_ready_rows": sum(1 for card in cards if card.get("training_ready") is True),
            "loss_open_rows": sum(1 for card in cards if any((card.get("losses_enabled") or {}).values())),
            "real_corpus_scan_authorized_now": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "cards": cards,
        "decision": "Synthetic long-context candidates route to review-only cards with all losses and compiler/training readiness closed.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    ROUTES.write_text("".join(json.dumps(card, sort_keys=True) + "\n" for card in audit.pop("cards")), encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "route_cards": str(ROUTES.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Synthetic long-context route-card audit failed.",
        "next_best_step": "Continue no-data compiler recovery or design a metadata-only route-card schema for future granted source tickets. Do not compile/train from synthetic candidates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9056 Long Context Synthetic Route Card Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Synthetic candidates are routed as review-only. They are not compiler-ready, model-input-ready, training-ready, or loss-enabled.",
        "",
        f"Route cards: `{audit['route_cards']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
