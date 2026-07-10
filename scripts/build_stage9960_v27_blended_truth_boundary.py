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
STAGE = 9960
NAME = "stage9960_v27_blended_truth_boundary"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BOUNDARY = OUT_DIR / "v27_blended_truth_boundary.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_BLENDED_TRUTH_BOUNDARY_STAGE9960.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

WEIGHTED_MATRIX = ROOT / "runs/local/artifacts/stage9942_weighted_winner_claim_readiness_matrix_refresh/weighted_winner_claim_readiness_matrix_refresh.json"
WEIGHTED_SCOPE = ROOT / "runs/local/artifacts/stage9959_weighted_winner_review_scope_audit/weighted_winner_review_scope_audit.json"
BLENDED_COMPARE = ROOT / "runs/local/artifacts/stage9958_blended_edit_localization_same_manifest_comparison_audit/blended_edit_localization_same_manifest_comparison_audit.json"
BLENDED_HANDOFF = ROOT / "runs/local/artifacts/stage9955_blended_same_manifest_execution_handoff_bundle/blended_same_manifest_execution_handoff_bundle.json"
BLOCKER_LEDGER = ROOT / "runs/local/artifacts/stage9956_v27_current_blocker_ledger/v27_current_blocker_ledger.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def build_boundary() -> dict[str, Any]:
    weighted = load_json(WEIGHTED_MATRIX)
    scope = load_json(WEIGHTED_SCOPE)
    blended = load_json(BLENDED_COMPARE)
    handoff = load_json(BLENDED_HANDOFF)
    ledger = load_json(BLOCKER_LEDGER)
    failures: list[str] = []

    weighted_rows = {
        str(row.get("language_family") or ""): row
        for row in (weighted.get("language_rows") or [])
        if isinstance(row, dict)
    }
    scope_rows = {
        str(row.get("language_family") or ""): row
        for row in (scope.get("language_rows") or [])
        if isinstance(row, dict)
    }
    compare_cells = blended.get("comparison_cells") or {}

    language_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        weighted_row = weighted_rows.get(lang)
        scope_row = scope_rows.get(lang)
        if not isinstance(weighted_row, dict):
            failures.append(f"missing_weighted_row:{lang}")
            continue
        if not isinstance(scope_row, dict):
            failures.append(f"missing_scope_row:{lang}")
            continue
        eval_cell = compare_cells.get(f"{lang}:eval") or {}
        strict_cell = compare_cells.get(f"{lang}:strict_eval") or {}
        language_rows.append({
            "language_family": lang,
            "weighted_same_surface_strict_exact_100m": weighted_row.get("same_surface_strict_exact_100m"),
            "weighted_same_surface_strict_exact_gemma12b": weighted_row.get("same_surface_strict_exact_gemma12b"),
            "weighted_narrow_machine_supported_claim": weighted_row.get("narrow_machine_supported_claim"),
            "weighted_review_packet_stronger": weighted_row.get("narrow_claim_review_packet_stronger"),
            "review_scope_confidently_supported_subskills": scope_row.get("rubric_confidently_supported_count"),
            "review_scope_confidence_tier": scope_row.get("same_surface_confidence_tier"),
            "blended_eval_exact_100m": eval_cell.get("hundred_m_exact"),
            "blended_eval_exact_gemma12b": eval_cell.get("gemma_exact"),
            "blended_eval_verdict": eval_cell.get("verdict"),
            "blended_strict_exact_100m": strict_cell.get("hundred_m_exact"),
            "blended_strict_exact_gemma12b": strict_cell.get("gemma_exact"),
            "blended_strict_verdict": strict_cell.get("verdict"),
            "blended_path_improves_web_gap": (
                lang == "web_js_ts_html"
                and eval_cell.get("verdict") == "100m_better"
            ),
            "recommended_current_use": (
                "keep_weighted_hardened_frontier_for_claims_and_use_targeted_web_refresh_only_as_training_signal"
                if lang != "web_js_ts_html"
                else "treat_as_web_recovery_signal_only_until_a_new_same_manifest_run_produces_a_clean_overall_win"
            ),
        })

    metrics = {
        "weighted_frontier_languages_with_narrow_machine_supported_claim": int((weighted.get("metrics") or {}).get("languages_with_narrow_machine_supported_claim", 0)),
        "weighted_frontier_languages_with_stronger_review_packets": int((weighted.get("metrics") or {}).get("languages_with_stronger_review_packets", 0)),
        "weighted_frontier_weakest_language_family": (weighted.get("metrics") or {}).get("weakest_language_family"),
        "weighted_scope_confident_languages": int((scope.get("metrics") or {}).get("languages_with_confident_machine_supported_applicable_rubric_scope", 0)),
        "blended_comparison_ready_now": bool((blended.get("metrics") or {}).get("comparison_ready_now")),
        "blended_wins_100m": int((blended.get("metrics") or {}).get("wins_100m", 0)),
        "blended_wins_gemma": int((blended.get("metrics") or {}).get("wins_gemma", 0)),
        "blended_ties": int((blended.get("metrics") or {}).get("ties", 0)),
        "blended_overall_beats_gemma": int((blended.get("metrics") or {}).get("wins_100m", 0)) > int((blended.get("metrics") or {}).get("wins_gemma", 0)),
        "handoff_bundle_dual_execution_ready_when_authorized": bool((handoff.get("metrics") or {}).get("dual_execution_ready_when_authorized")),
        "current_blocker_ledger_still_says_packaged": bool((ledger.get("metrics") or {}).get("narrow_blended_path_fully_packaged_locally")),
    }
    if metrics["weighted_frontier_languages_with_narrow_machine_supported_claim"] != 4:
        failures.append("weighted_frontier_languages_with_narrow_machine_supported_claim_not_4")
    if metrics["weighted_frontier_languages_with_stronger_review_packets"] != 4:
        failures.append("weighted_frontier_languages_with_stronger_review_packets_not_4")
    if metrics["weighted_scope_confident_languages"] != 3:
        failures.append("weighted_scope_confident_languages_not_3")
    if metrics["blended_comparison_ready_now"] is not True:
        failures.append("blended_comparison_not_ready_now")
    if metrics["blended_wins_100m"] != 3:
        failures.append("blended_wins_100m_not_3")
    if metrics["blended_wins_gemma"] != 3:
        failures.append("blended_wins_gemma_not_3")
    if metrics["blended_ties"] != 2:
        failures.append("blended_ties_not_2")
    if metrics["blended_overall_beats_gemma"] is not False:
        failures.append("blended_overall_beats_gemma_not_false")
    if metrics["handoff_bundle_dual_execution_ready_when_authorized"] is not True:
        failures.append("handoff_bundle_not_ready")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": language_rows,
        "truth_boundary": {
            "current_claim_frontier": "weighted_hardened_four_language_same_surface_win",
            "current_claim_caveat": "web_js_ts_html remains fragile in maintainer-review confidence even though the weighted hardened packet still records a narrow win.",
            "blended_path_status": "real_same_manifest_outputs_exist_but_do_not_beat_gemma_overall",
            "blended_path_interpretation": "Use the targeted web-refresh/blended path as training and diagnosis evidence, not as the current replacement claim frontier.",
            "next_training_implication": "Keep the targeted web refresh rows in the next edit-localization curriculum, but require a fresh same-manifest rerun to replace the current frontier.",
        },
        "evidence_paths": {
            "weighted_claim_matrix": display(WEIGHTED_MATRIX),
            "weighted_review_scope": display(WEIGHTED_SCOPE),
            "blended_same_manifest_comparison": display(BLENDED_COMPARE),
            "blended_execution_handoff": display(BLENDED_HANDOFF),
            "current_blocker_ledger": display(BLOCKER_LEDGER),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_boundary()
    BOUNDARY.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Keep the weighted hardened four-language frontier as the current truthful claim, use the targeted web-refresh/blended path as the next training input, and only promote that blended path after a fresh same-manifest rerun produces an overall 100M win rather than the current 3-3-2 split."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"boundary": display(BOUNDARY), "doc": display(DOC)},
        "decision": "Refreshed the v2.7 truth boundary by joining the weighted hardened winner claim, the new review-scope audit, and the real blended same-manifest comparison result, which improves web coverage but does not replace the current frontier because it only splits 3 wins / 3 losses / 2 ties against Gemma.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9960 V27 Blended Truth Boundary",
        "",
        f"Passed: `{summary['passed']}`",
        f"Blended wins 100M: `{built['metrics']['blended_wins_100m']}`",
        f"Blended wins Gemma: `{built['metrics']['blended_wins_gemma']}`",
        f"Blended ties: `{built['metrics']['blended_ties']}`",
        f"Weighted scope confident languages: `{built['metrics']['weighted_scope_confident_languages']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
