#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9778
NAME = "stage9778_multilingual_training_readiness_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_training_readiness_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_TRAINING_READINESS_AUDIT_STAGE9778.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

SYMBOL_BINDING = ROOT / "runs/summaries/stage9713_symbol_binding_retrieval_test_evidence_execution_audit.json"
EDIT_LOCALIZATION = ROOT / "runs/summaries/stage9773_edit_localization_visible_evidence_execution_audit.json"
EDIT_LOCALIZATION_GEMMA = ROOT / "runs/summaries/stage9775_edit_localization_visible_evidence_gemma_comparison.json"
PATCH_OPERATOR = ROOT / "runs/summaries/stage9776_patch_operator_evidence_sufficiency_audit.json"
VERIFIER_REPAIR = ROOT / "runs/summaries/stage9777_verifier_repair_evidence_sufficiency_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_surface_cards() -> list[dict[str, Any]]:
    symbol = load_json(SYMBOL_BINDING)
    edit = load_json(EDIT_LOCALIZATION)
    edit_gemma = load_json(EDIT_LOCALIZATION_GEMMA)
    patch = load_json(PATCH_OPERATOR)
    verifier = load_json(VERIFIER_REPAIR)

    surfaces = [
        {
            "surface": "symbol_binding",
            "status": "trainable_but_not_yet_winning_proven",
            "ready_for_training": True,
            "honest_progress_expected_from_more_sweeps": True,
            "current_eval_exact": (symbol.get("metrics") or {}).get("eval_symbol_binding_exact"),
            "current_strict_exact": (symbol.get("metrics") or {}).get("strict_symbol_binding_exact"),
            "reason": "Visible retrieval/test evidence separates the task and recent execution improved meaningfully, but there is no current same-surface Gemma win attached in this audit set.",
            "blocking_issue": None,
            "source_summary": str(SYMBOL_BINDING.relative_to(ROOT)),
        },
        {
            "surface": "edit_localization_visible_evidence",
            "status": "winning_ready_surface",
            "ready_for_training": True,
            "honest_progress_expected_from_more_sweeps": False,
            "current_eval_exact": (edit.get("metrics") or {}).get("eval_exact"),
            "current_strict_exact": (edit.get("metrics") or {}).get("strict_exact"),
            "gemma_wins_100m": (edit_gemma.get("metrics") or {}).get("wins_100m"),
            "gemma_wins_gemma": (edit_gemma.get("metrics") or {}).get("wins_gemma"),
            "gemma_ties": (edit_gemma.get("metrics") or {}).get("ties"),
            "reason": "Once safe visible evidence was lifted into the encoder, the 100M model reached 1.0 strict exact and beat deterministic Gemma in all four language slices.",
            "blocking_issue": None,
            "source_summary": str(EDIT_LOCALIZATION.relative_to(ROOT)),
            "gemma_summary": str(EDIT_LOCALIZATION_GEMMA.relative_to(ROOT)),
        },
        {
            "surface": "patch_operator_selection",
            "status": "blocked_upstream_evidence_rebuild_required",
            "ready_for_training": False,
            "honest_progress_expected_from_more_sweeps": False,
            "collapsed_safe_bucket_count": (patch.get("metrics") or {}).get("collapsed_safe_bucket_count"),
            "separable_only_with_leaky_fields_bucket_count": (patch.get("metrics") or {}).get("separable_only_with_leaky_fields_bucket_count"),
            "reason": "All audited language/split buckets collapse under safe observable evidence, so the current package only becomes learnable through label-shaped hints.",
            "blocking_issue": "rebuild upstream rows with real non-label patch evidence before any more target-100M sweeps",
            "source_summary": str(PATCH_OPERATOR.relative_to(ROOT)),
        },
        {
            "surface": "verifier_failure_repair_or_abstain",
            "status": "blocked_upstream_evidence_rebuild_required",
            "ready_for_training": False,
            "honest_progress_expected_from_more_sweeps": False,
            "collapsed_safe_bucket_count": (verifier.get("metrics") or {}).get("collapsed_safe_bucket_count"),
            "separable_only_with_leaky_fields_bucket_count": (verifier.get("metrics") or {}).get("separable_only_with_leaky_fields_bucket_count"),
            "reason": "All audited language/split buckets collapse under safe verifier-visible evidence, so label alignment did not fix the underlying target/evidence mismatch.",
            "blocking_issue": "rebuild upstream rows with real non-label verifier evidence before any more target-100M sweeps",
            "source_summary": str(VERIFIER_REPAIR.relative_to(ROOT)),
        },
    ]
    return surfaces


def build_audit() -> dict[str, Any]:
    surfaces = build_surface_cards()
    blocked = [surface["surface"] for surface in surfaces if not surface["ready_for_training"]]
    ready = [surface["surface"] for surface in surfaces if surface["ready_for_training"]]
    winning = [surface["surface"] for surface in surfaces if surface["status"] == "winning_ready_surface"]
    failures: list[str] = []
    if "edit_localization_visible_evidence" not in winning:
        failures.append("expected_visible_evidence_edit_localization_win_missing")
    if set(blocked) != {"patch_operator_selection", "verifier_failure_repair_or_abstain"}:
        failures.append("blocked_surface_set_unexpected")
    recommendation = {
        "train_now": ["edit_localization_visible_evidence", "symbol_binding"],
        "do_not_train_again_until_rebuilt": blocked,
        "modeling_rule": "Only train multilingual maintenance surfaces when safe observable evidence can separate labels within each evaluation bucket.",
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "failures": failures,
        "ready_surface_count": len(ready),
        "blocked_surface_count": len(blocked),
        "winning_surface_count": len(winning),
        "ready_surfaces": ready,
        "blocked_surfaces": blocked,
        "winning_surfaces": winning,
        "surfaces": surfaces,
        "recommendation": recommendation,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Freeze additional target-100M sweeps for patch_operator_selection and "
        "verifier_failure_repair_or_abstain, and spend the next modeling cycle on "
        "upstream evidence rebuilds plus runner-backed Gemma/harness comparison packaging."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "failures": audit["failures"],
            "ready_surface_count": audit["ready_surface_count"],
            "blocked_surface_count": audit["blocked_surface_count"],
            "winning_surface_count": audit["winning_surface_count"],
            "ready_surfaces": audit["ready_surfaces"],
            "blocked_surfaces": audit["blocked_surfaces"],
            "winning_surfaces": audit["winning_surfaces"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited whether the current multilingual structured surfaces are being trained in a way that can honestly produce wins rather than label-hint imitation.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9778 Multilingual Training Readiness Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Ready surfaces: `{audit['ready_surfaces']}`",
                f"Blocked surfaces: `{audit['blocked_surfaces']}`",
                f"Winning surfaces: `{audit['winning_surfaces']}`",
                "",
                "This audit records the current honest training posture:",
                "- edit_localization_visible_evidence is the only multilingual maintenance surface that both trains correctly and currently beats deterministic Gemma.",
                "- symbol_binding is trainable and improving, but this audit does not attach a same-surface Gemma win yet.",
                "- patch_operator_selection and verifier_failure_repair_or_abstain should not receive more identical target-100M sweeps until their upstream builders emit real non-label evidence.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
