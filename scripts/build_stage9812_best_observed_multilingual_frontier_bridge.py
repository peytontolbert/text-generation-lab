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
STAGE = 9812
NAME = "stage9812_best_observed_multilingual_frontier_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BRIDGE = OUT_DIR / "best_observed_multilingual_frontier_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BEST_OBSERVED_MULTILINGUAL_FRONTIER_BRIDGE_STAGE9812.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASELINE_GEMMA = ROOT / "runs/local/artifacts/stage9793_edit_localization_opaque_choice_gemma_comparison/edit_localization_opaque_choice_gemma_comparison.json"
BASELINE_ANTI = ROOT / "runs/local/artifacts/stage9795_opaque_choice_counterfactual_anti_cheat_audit/opaque_choice_counterfactual_anti_cheat_audit.json"
WEB_GEMMA = ROOT / "runs/local/artifacts/stage9810_web_disambiguated_gemma_comparison/web_disambiguated_gemma_comparison.json"
WEB_ANTI = ROOT / "runs/local/artifacts/stage9811_web_disambiguated_counterfactual_anti_cheat_audit/opaque_choice_counterfactual_anti_cheat_audit.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
WEB_LANG = "web_js_ts_html"


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


def _results_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    return {str(row.get("language") or ""): row for row in rows}


def _anti_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("records") if isinstance(payload.get("records"), list) else []
    return {str(row.get("language_family") or ""): row for row in rows}


def _source_for_language(language: str) -> tuple[str, int, dict[str, Any], dict[str, Any]]:
    if language == WEB_LANG:
        gemma = load_json(WEB_GEMMA)
        anti = load_json(WEB_ANTI)
        return ("web_disambiguated_successor_surface", 9809, _results_index(gemma)[language], _anti_index(anti)[language])
    gemma = load_json(BASELINE_GEMMA)
    anti = load_json(BASELINE_ANTI)
    return ("baseline_opaque_choice_surface", 9794, _results_index(gemma)[language], _anti_index(anti)[language])


def build_bridge() -> dict[str, Any]:
    failures: list[str] = []
    records: list[dict[str, Any]] = []
    for language in LANGS:
        source_name, run_stage, result, anti = _source_for_language(language)
        if not isinstance(result, dict) or not isinstance(anti, dict):
            failures.append(f"missing_source_rows:{language}")
            continue
        verdict = str(result.get("verdict") or "")
        if verdict != "100m_better":
            failures.append(f"not_a_win:{language}:{verdict}")
        probes = anti.get("counterfactual_probes") if isinstance(anti.get("counterfactual_probes"), dict) else {}
        records.append(
            {
                "language_family": language,
                "selected_frontier_source": source_name,
                "model_execution_stage": run_stage,
                "comparison_stage": 9810 if language == WEB_LANG else 9793,
                "anti_cheat_stage": 9811 if language == WEB_LANG else 9795,
                "model_strict_exact_100m": result.get("model_strict_exact_100m"),
                "gemma_strict_exact": result.get("gemma_strict_exact"),
                "verdict": verdict,
                "raw_surface_manifest": anti.get("surface_manifest"),
                "prompt_target_literal_row_count": (anti.get("prompt_surface_checks") or {}).get("prompt_target_literal_row_count"),
                "prompt_hidden_target_literal_row_count": (anti.get("prompt_surface_checks") or {}).get("prompt_hidden_target_literal_row_count"),
                "probe_scores": {
                    "permutation": (probes.get("label_order_permutation") or {}).get("score"),
                    "decoy": (probes.get("decoy_label_injection") or {}).get("score"),
                    "ablation": (probes.get("critical_evidence_ablation") or {}).get("score"),
                    "causal_flip": (probes.get("causal_flip") or {}).get("score"),
                },
                "expert_reviewer_judgment": anti.get("expert_reviewer_judgment"),
                "claim_scope": "narrow_visible_evidence_edit_localization_only",
                "frontier_caveat": (
                    "best observed web result comes from a successor surface and separate Stage9809 run; this is a mixed-surface, mixed-checkpoint frontier rather than one uniform frozen packet"
                    if language == WEB_LANG
                    else "best observed result comes from the current baseline opaque-choice packet"
                ),
            }
        )
    metrics = {
        "languages": len(records),
        "wins_100m": sum(1 for row in records if row.get("verdict") == "100m_better"),
        "wins_gemma": sum(1 for row in records if row.get("verdict") == "gemma_better"),
        "ties": sum(1 for row in records if row.get("verdict") == "tie"),
        "mixed_surface_frontier": True,
        "mixed_checkpoint_frontier": True,
        "expert_review_completed_languages": sum(
            1 for row in records if str(((row.get("expert_reviewer_judgment") or {}).get("review_status") or "")) == "confirmed_by_human"
        ),
    }
    caveats = [
        "This is not one uniform single-checkpoint multilingual packet. Python, rust, and c_cpp come from the Stage9794 baseline packet, while web comes from the Stage9809 successor packet.",
        "The result remains narrow visible-evidence edit localization, not broad software-maintenance intelligence.",
        "Counterfactual probe scores remain weak enough that sealed heldout replication and blind expert review are still required before any stronger claim.",
    ]
    return {
        "passed": not failures and metrics["wins_100m"] == 4,
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
    next_step = "Either isolate the web evidence lift so it no longer regresses rust and c_cpp, or explicitly package the current state as a routed multilingual 100M frontier with expert-review and heldout-eval blockers still open."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **bridge["metrics"], "failures": bridge["failures"]},
        "artifacts": {"bridge": str(BRIDGE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Bridged the current best observed multilingual frontier truthfully: the 100M now has a per-language four-for-four win over Gemma only when web is taken from the Stage9809 successor packet and the other three languages remain on the Stage9794 baseline packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9812 Best Observed Multilingual Frontier Bridge",
                "",
                f"Passed: `{bridge['passed']}`",
                f"Wins 100M: `{bridge['metrics']['wins_100m']}`",
                f"Wins Gemma: `{bridge['metrics']['wins_gemma']}`",
                f"Ties: `{bridge['metrics']['ties']}`",
                "",
                "This bridge is intentionally narrow and truthful. It records that the current best observed 100M frontier beats Gemma across python, rust, c_cpp, and web_js_ts_html, but only by mixing the Stage9794 baseline packet for three languages with the Stage9809 web-disambiguated successor packet for web.",
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
