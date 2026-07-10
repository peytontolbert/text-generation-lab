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
STAGE = 9878
NAME = "stage9878_current_margin_multilingual_frontier_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BRIDGE = OUT_DIR / "current_margin_multilingual_frontier_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_MULTILINGUAL_FRONTIER_BRIDGE_STAGE9878.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
STAGE9873 = ROOT / "runs/local/artifacts/stage9873_edit_localization_field_attention_margin_gemma_comparison/edit_localization_field_attention_margin_gemma_comparison.json"
STAGE9877 = ROOT / "runs/local/artifacts/stage9877_margin_objective_schedule_aware_structured_review/margin_objective_schedule_aware_structured_review_audit.json"
STAGE9846 = ROOT / "runs/local/artifacts/stage9846_restored_counterfactual_per_language_gemma_comparison/restored_counterfactual_per_language_gemma_comparison.json"
STAGE9852 = ROOT / "runs/local/artifacts/stage9852_abstention_counterfactual_gemma_comparison/abstention_counterfactual_gemma_comparison.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]


def load_json(path: Path) -> Any:
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


def _comparison_card(payload: dict[str, Any], language: str, split: str) -> dict[str, Any]:
    return (payload.get("comparisons") or {}).get(f"{language}:{split}") or {}


def _surface_results_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("surface_results") if isinstance(payload.get("surface_results"), list) else []
    return {str(row.get("surface") or ""): row for row in rows}


def build_bridge() -> dict[str, Any]:
    current = load_json(STAGE9873)
    broader = load_json(STAGE9877)
    harder_counterfactual = load_json(STAGE9846)
    abstention_counterfactual = load_json(STAGE9852)
    surface_results = _surface_results_index(broader)
    edit_surface = surface_results.get("edit_localization") or {}

    failures: list[str] = []
    records: list[dict[str, Any]] = []
    total_100m = 0.0
    total_gemma = 0.0
    strict_wins = 0
    strict_ties = 0
    for language in LANGS:
        split_cards = {split: _comparison_card(current, language, split) for split in SPLITS}
        if any(not isinstance(card, dict) or not card for card in split_cards.values()):
            failures.append(f"missing_stage9873_rows:{language}")
            continue
        eval_card = split_cards["eval"]
        strict_card = split_cards["strict_eval"]
        hundred_m_eval = float(eval_card.get("hundred_m_exact") or 0.0)
        gemma_eval = float(eval_card.get("gemma_exact") or 0.0)
        hundred_m_strict = float(strict_card.get("hundred_m_exact") or 0.0)
        gemma_strict = float(strict_card.get("gemma_exact") or 0.0)
        total_100m_language = hundred_m_eval + hundred_m_strict
        total_gemma_language = gemma_eval + gemma_strict
        language_verdict = "100m_better" if total_100m_language > total_gemma_language else ("gemma_better" if total_100m_language < total_gemma_language else "tie")
        if language_verdict != "100m_better":
            failures.append(f"language_not_a_win:{language}:{language_verdict}")
        strict_verdict = str(strict_card.get("verdict") or "")
        if strict_verdict == "100m_better":
            strict_wins += 1
        elif strict_verdict == "tie":
            strict_ties += 1
        harder_strict = _comparison_card(harder_counterfactual, language, "strict_eval")
        abstention_strict = _comparison_card(abstention_counterfactual, language, "strict_eval")
        records.append(
            {
                "language_family": language,
                "surface": "edit_localization",
                "same_surface_packet_stage": 9867,
                "same_surface_comparison_stage": 9873,
                "broader_schedule_review_stage": 9877,
                "counterfactual_regression_stage": 9846,
                "abstention_counterfactual_stage": 9852,
                "eval_exact_100m": hundred_m_eval,
                "eval_exact_gemma": gemma_eval,
                "strict_exact_100m": hundred_m_strict,
                "strict_exact_gemma": gemma_strict,
                "strict_verdict": strict_verdict,
                "language_family_score_100m": round(total_100m_language, 10),
                "language_family_score_gemma": round(total_gemma_language, 10),
                "language_family_verdict": language_verdict,
                "harder_counterfactual_strict_exact_100m": harder_strict.get("hundred_m_exact"),
                "harder_counterfactual_strict_exact_gemma": harder_strict.get("gemma_exact"),
                "harder_counterfactual_strict_verdict": harder_strict.get("verdict"),
                "abstention_counterfactual_strict_exact_100m": abstention_strict.get("hundred_m_exact"),
                "abstention_counterfactual_strict_exact_gemma": abstention_strict.get("gemma_exact"),
                "abstention_counterfactual_strict_verdict": abstention_strict.get("verdict"),
                "claim_scope": "same_surface_multilingual_edit_localization_on_stage9867_packet_only",
                "anti_cheat_status": "provisional_counterfactual_margin_present_but_not_decisive",
            }
        )
        total_100m += total_100m_language
        total_gemma += total_gemma_language

    metrics = {
        "languages": len(records),
        "comparison_cells": len(records) * len(SPLITS),
        "wins_100m": int(current.get("wins_100m") or 0),
        "wins_gemma": int(current.get("wins_gemma") or 0),
        "ties": int(current.get("ties") or 0),
        "language_family_wins_100m": sum(1 for row in records if row.get("language_family_verdict") == "100m_better"),
        "language_family_wins_gemma": sum(1 for row in records if row.get("language_family_verdict") == "gemma_better"),
        "language_family_ties": sum(1 for row in records if row.get("language_family_verdict") == "tie"),
        "strict_language_wins_100m": strict_wins,
        "strict_language_ties": strict_ties,
        "macro_language_family_score_100m": round(total_100m / len(records), 10) if records else None,
        "macro_language_family_score_gemma": round(total_gemma / len(records), 10) if records else None,
        "broader_edit_localization_eval_exact_100m": edit_surface.get("eval_exact"),
        "broader_edit_localization_strict_exact_100m": edit_surface.get("strict_eval_exact"),
        "broader_edit_localization_selected_step": (edit_surface.get("best_state_selection") or {}).get("selected_step"),
        "broader_edit_localization_restore_best": (edit_surface.get("schedule") or {}).get("restore_best"),
        "harder_counterfactual_macro_strict_delta": (harder_counterfactual.get("macro_delta_by_split") or {}).get("strict_eval"),
        "harder_counterfactual_wins_100m": int(harder_counterfactual.get("wins_100m") or 0),
        "harder_counterfactual_wins_gemma": int(harder_counterfactual.get("wins_gemma") or 0),
        "harder_counterfactual_ties": int(harder_counterfactual.get("ties") or 0),
        "abstention_counterfactual_macro_strict_delta": (abstention_counterfactual.get("macro_delta_by_split") or {}).get("strict_eval"),
        "abstention_counterfactual_wins_100m": int(abstention_counterfactual.get("wins_100m") or 0),
        "abstention_counterfactual_wins_gemma": int(abstention_counterfactual.get("wins_gemma") or 0),
        "abstention_counterfactual_ties": int(abstention_counterfactual.get("ties") or 0),
        "same_surface_frontier": True,
        "mixed_surface_frontier": False,
        "mixed_checkpoint_frontier": False,
    }
    caveats = [
        "This bridge records the current strongest same-surface multilingual edit-localization result on the Stage9867 packet: the 100M model beats Gemma across all four language families when eval and strict-eval are both counted, but python remains only a strict-eval tie.",
        "Harder restored counterfactuals in Stage9846 erase most of the margin, so this is not yet a robust anti-cheat or general-maintainer win.",
        "Stage9852 shows that explicit abstention improves the counterfactual story, which supports keeping ambiguous rows out of forced-singleton win claims.",
        "Stage9877 preserves the improved edit-localization path inside the broader v2.7 mix, but symbol binding still trails and patch/verifier remain guardrails rather than leaderboard differentiators.",
    ]
    return {
        "passed": not failures and metrics["language_family_wins_100m"] == 4,
        "failures": failures,
        "metrics": metrics,
        "records": records,
        "caveats": caveats,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    bridge = build_bridge()
    BRIDGE.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "name": NAME,
                "passed": bridge["passed"],
                "metrics": bridge["metrics"],
                "records": bridge["records"],
                "caveats": bridge["caveats"],
                "authority": dict(AUTHORITY_CLOSED),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    next_step = "Refresh the multilingual winner review packets and standalone ledger to point at this Stage9873/9877 frontier, then add stronger same-packet anti-cheat probes before treating the 4-language win as robust expert-maintainer evidence."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **bridge["metrics"], "failures": bridge["failures"]},
        "artifacts": {"bridge": str(BRIDGE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Bridged the current truthful multilingual frontier onto the Stage9873 margin-objective same-surface comparison and the Stage9877 broader schedule-aware review, while carrying forward the Stage9846 and Stage9852 counterfactual caveats.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9878 Current Margin Multilingual Frontier Bridge",
                "",
                f"Passed: `{bridge['passed']}`",
                f"Language-family wins 100M: `{bridge['metrics']['language_family_wins_100m']}`",
                f"Strict-language wins 100M: `{bridge['metrics']['strict_language_wins_100m']}`",
                f"Strict-language ties: `{bridge['metrics']['strict_language_ties']}`",
                f"Harder counterfactual strict delta: `{bridge['metrics']['harder_counterfactual_macro_strict_delta']}`",
                f"Abstention counterfactual strict delta: `{bridge['metrics']['abstention_counterfactual_macro_strict_delta']}`",
                "",
                "This bridge supersedes the stale multilingual frontier path for the current best truthful same-surface edit-localization result. It records a four-language family win over Gemma on the Stage9867 packet while preserving the stronger counterfactual caveats from later audits.",
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if bridge["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": bridge["passed"], "metrics": bridge["metrics"], "failures": bridge["failures"]}, indent=2, sort_keys=True))
    if bridge["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
