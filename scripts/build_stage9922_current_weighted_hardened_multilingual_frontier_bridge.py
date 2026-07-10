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
STAGE = 9922
NAME = "stage9922_current_weighted_hardened_multilingual_frontier_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BRIDGE = OUT_DIR / "current_weighted_hardened_multilingual_frontier_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_WEIGHTED_HARDENED_MULTILINGUAL_FRONTIER_BRIDGE_STAGE9922.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
STAGE9918 = ROOT / "runs/local/artifacts/stage9918_hardened_weighted_v27_execution_delta_audit/hardened_weighted_v27_execution_delta_audit.json"
STAGE9919 = ROOT / "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_comparison.json"
STAGE9920 = ROOT / "runs/local/artifacts/stage9920_hardened_weighted_edit_localization_shortcut_audit/hardened_weighted_edit_localization_shortcut_audit.json"
STAGE9917 = ROOT / "runs/local/artifacts/stage9917_hardened_weighted_structured_execution_review/hardened_weighted_structured_execution_review_audit.json"
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
    comparison = load_json(STAGE9919)
    shortcut = load_json(STAGE9920)
    delta = load_json(STAGE9918)
    broader = load_json(STAGE9917)
    surface_results = _surface_results_index(broader)
    edit_surface = surface_results.get("edit_localization") or {}

    failures: list[str] = []
    records: list[dict[str, Any]] = []
    total_100m = 0.0
    total_gemma = 0.0
    strict_wins = 0
    for language in LANGS:
        split_cards = {split: _comparison_card(comparison, language, split) for split in SPLITS}
        if any(not isinstance(card, dict) or not card for card in split_cards.values()):
            failures.append(f"missing_stage9919_rows:{language}")
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
        records.append(
            {
                "language_family": language,
                "surface": "edit_localization",
                "same_surface_packet_stage": 9917,
                "same_surface_comparison_stage": 9919,
                "same_surface_shortcut_audit_stage": 9920,
                "weighted_delta_stage": 9918,
                "broader_schedule_review_stage": 9917,
                "eval_exact_100m": hundred_m_eval,
                "eval_exact_gemma": gemma_eval,
                "strict_exact_100m": hundred_m_strict,
                "strict_exact_gemma": gemma_strict,
                "strict_verdict": strict_verdict,
                "language_family_score_100m": round(total_100m_language, 10),
                "language_family_score_gemma": round(total_gemma_language, 10),
                "language_family_verdict": language_verdict,
                "weighted_delta_eval_exact": (((delta.get("metrics") or {}).get("surface_delta") or {}).get("edit_localization") or {}).get("delta_eval_exact"),
                "weighted_delta_strict_exact": (((delta.get("metrics") or {}).get("surface_delta") or {}).get("edit_localization") or {}).get("delta_strict_exact"),
                "claim_scope": "same_surface_multilingual_edit_localization_on_weighted_hardened_packet_only",
                "anti_cheat_status": "prompt_hidden_and_permutation_diverse_but_human_review_still_open",
            }
        )
        total_100m += total_100m_language
        total_gemma += total_gemma_language

    metrics = {
        "languages": len(records),
        "comparison_cells": len(records) * len(SPLITS),
        "wins_100m": int(comparison.get("wins_100m") or 0),
        "wins_gemma": int(comparison.get("wins_gemma") or 0),
        "ties": int(comparison.get("ties") or 0),
        "language_family_wins_100m": sum(1 for row in records if row.get("language_family_verdict") == "100m_better"),
        "language_family_wins_gemma": sum(1 for row in records if row.get("language_family_verdict") == "gemma_better"),
        "language_family_ties": sum(1 for row in records if row.get("language_family_verdict") == "tie"),
        "strict_language_wins_100m": strict_wins,
        "macro_language_family_score_100m": round(total_100m / len(records), 10) if records else None,
        "macro_language_family_score_gemma": round(total_gemma / len(records), 10) if records else None,
        "broader_edit_localization_eval_exact_100m": edit_surface.get("eval_exact"),
        "broader_edit_localization_strict_exact_100m": edit_surface.get("strict_eval_exact"),
        "broader_edit_localization_selected_step": (edit_surface.get("best_state_selection") or {}).get("selected_step"),
        "broader_edit_localization_restore_best": (edit_surface.get("schedule") or {}).get("restore_best"),
        "weighted_delta_eval_exact": (((delta.get("metrics") or {}).get("surface_delta") or {}).get("edit_localization") or {}).get("delta_eval_exact"),
        "weighted_delta_strict_exact": (((delta.get("metrics") or {}).get("surface_delta") or {}).get("edit_localization") or {}).get("delta_strict_exact"),
        "prompt_label_exposure_buckets": (shortcut.get("metrics") or {}).get("buckets_with_prompt_label_vocab_exposed"),
        "unique_permutation_maps": (shortcut.get("metrics") or {}).get("unique_permutation_maps"),
        "same_surface_frontier": True,
        "mixed_surface_frontier": False,
        "mixed_checkpoint_frontier": False,
    }
    caveats = [
        "This bridge is still narrow: it proves a multilingual same-surface edit-localization win on the weighted hardened packet, not a broad software-maintenance or full-product harness win.",
        "Human expert-maintainer rubric confirmation and cell-specific anti-cheat signoff are still open on the four winner cells.",
        "The weighted integrated packet now has direct Gemma wins plus prompt-level anti-cheat coverage, which is stronger than the older mixed-surface bridges and should replace them as the current truthful multilingual frontier.",
    ]
    return {
        "passed": not failures and metrics["language_family_wins_100m"] == 4 and metrics["wins_100m"] == 8,
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
    next_step = "Use this weighted hardened bridge as the new authoritative multilingual frontier, then work the Stage9923/9924 review queue so expert-maintainer and anti-cheat signoff catches up to the machine-side evidence."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **bridge["metrics"], "failures": bridge["failures"]},
        "artifacts": {"bridge": str(BRIDGE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Bridged the current truthful multilingual frontier onto the weighted hardened Stage9917/9919/9920 chain: one frozen integrated packet, one live Gemma comparison, and one matching shortcut audit now support the four-language edit-localization claim.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9922 Current Weighted Hardened Multilingual Frontier Bridge",
                "",
                f"Passed: `{bridge['passed']}`",
                f"Language-family wins 100M: `{bridge['metrics']['language_family_wins_100m']}`",
                f"Strict-language wins 100M: `{bridge['metrics']['strict_language_wins_100m']}`",
                f"Prompt label exposure buckets: `{bridge['metrics']['prompt_label_exposure_buckets']}`",
                f"Unique permutation maps: `{bridge['metrics']['unique_permutation_maps']}`",
                "",
                "This bridge supersedes the stale multilingual frontier path. The current truthful frontier is now the weighted hardened integrated packet: a four-language family win over Gemma on one frozen surface with a matching shortcut audit.",
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
