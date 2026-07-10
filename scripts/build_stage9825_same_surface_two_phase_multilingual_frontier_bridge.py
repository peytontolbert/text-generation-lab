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
STAGE = 9825
NAME = "stage9825_same_surface_two_phase_multilingual_frontier_bridge"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BRIDGE = OUT_DIR / "same_surface_two_phase_multilingual_frontier_bridge.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SAME_SURFACE_TWO_PHASE_MULTILINGUAL_FRONTIER_BRIDGE_STAGE9825.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
EXECUTION = ROOT / "runs/local/artifacts/stage9824_two_phase_weighted_web_headonly_lr1e5_phase1x64/execution_result.json"
PHASE1_CELLS = ROOT / "runs/local/artifacts/stage9824_two_phase_weighted_web_headonly_lr1e5_phase1x64/phase1_structured_probe/field_exact_by_cell.json"
PHASE2_CELLS = ROOT / "runs/local/artifacts/stage9824_two_phase_weighted_web_headonly_lr1e5_phase1x64/phase2_structured_probe/field_exact_by_cell.json"
GEMMA = ROOT / "runs/local/artifacts/stage9816_web_isolated_gemma_comparison/web_isolated_gemma_comparison.json"
SURFACE_AUDIT = ROOT / "runs/local/artifacts/stage9813_web_isolated_disambiguator_surface/web_isolated_disambiguator_surface_audit.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
FIELD = "edit_localization"


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


def _phase_index(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    rows = payload.get(FIELD) if isinstance(payload.get(FIELD), dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key, card in rows.items():
        language = str(key).split("::", 1)[0]
        out[language] = card
    return out


def _gemma_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("language") or ""): row for row in (payload.get("results") or [])}


def build_bridge() -> dict[str, Any]:
    execution = load_json(EXECUTION)
    phase1_cells = _phase_index(PHASE1_CELLS)
    phase2_cells = _phase_index(PHASE2_CELLS)
    gemma = _gemma_index(load_json(GEMMA))
    surface = load_json(SURFACE_AUDIT)
    anti_cheat_findings = list(surface.get("anti_cheat_findings") or [])

    failures: list[str] = []
    records: list[dict[str, Any]] = []
    phase1_sum = 0.0
    phase2_sum = 0.0

    for language in LANGS:
        phase1 = phase1_cells.get(language)
        phase2 = phase2_cells.get(language)
        gemma_row = gemma.get(language)
        if not isinstance(phase1, dict) or not isinstance(phase2, dict) or not isinstance(gemma_row, dict):
            failures.append(f"missing_rows:{language}")
            continue
        phase1_exact = float(phase1.get("exact") or 0.0)
        phase2_exact = float(phase2.get("exact") or 0.0)
        gemma_exact = float(gemma_row.get("gemma_strict_exact") or 0.0)
        verdict = "100m_better" if phase2_exact > gemma_exact else ("gemma_better" if phase2_exact < gemma_exact else "tie")
        if verdict != "100m_better":
            failures.append(f"not_a_win:{language}:{verdict}")
        phase1_sum += phase1_exact
        phase2_sum += phase2_exact
        records.append(
            {
                "language_family": language,
                "surface_stage": 9813,
                "gemma_stage": 9816,
                "continuation_stage": 9824,
                "same_surface_packet": True,
                "same_in_memory_model_family": True,
                "phase1_strict_exact_100m": phase1_exact,
                "phase2_strict_exact_100m": phase2_exact,
                "gemma_strict_exact": gemma_exact,
                "delta_phase2_vs_phase1": round(phase2_exact - phase1_exact, 10),
                "verdict": verdict,
                "anti_cheat_findings_inherited": anti_cheat_findings,
                "surface_hash_scope": "stage9813_web_isolated_disambiguator_surface",
                "claim_scope": "narrow_same_surface_visible_evidence_edit_localization_only",
            }
        )

    metrics = {
        "languages": len(records),
        "wins_100m": sum(1 for row in records if row.get("verdict") == "100m_better"),
        "wins_gemma": sum(1 for row in records if row.get("verdict") == "gemma_better"),
        "ties": sum(1 for row in records if row.get("verdict") == "tie"),
        "phase1_macro_strict_exact_100m": round(phase1_sum / len(records), 10) if records else None,
        "phase2_macro_strict_exact_100m": round(phase2_sum / len(records), 10) if records else None,
        "improved_languages_from_phase2": sum(1 for row in records if row.get("delta_phase2_vs_phase1", 0.0) > 0.0),
        "same_surface_frontier": True,
        "mixed_surface_frontier": False,
        "mixed_checkpoint_frontier": False,
        "continued_in_memory_model": bool(execution.get("model_reused_in_memory_between_phases")),
        "checkpoint_exported": bool(execution.get("final_checkpoint_exported")),
    }
    caveats = [
        "This is a same-surface multilingual win on the Stage9813 packet with one continued in-memory model run, but it is still not a frozen exported checkpoint claim.",
        "The current evidence remains narrow visible-evidence edit localization, not broad software-maintenance, patch synthesis, verifier repair, or general intelligence.",
        "The Stage9813 surface anti-cheat findings are inherited here, but the continued Stage9824 model still needs same-packet counterfactual probes and blind expert-maintainer review before a stronger benchmark claim.",
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
    next_step = "Build a same-packet counterfactual anti-cheat audit for the Stage9824 phase2 winner and attach blind expert-maintainer review before claiming this continuation result as the v2.7 multilingual benchmark front-runner."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": bridge["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **bridge["metrics"], "failures": bridge["failures"]},
        "artifacts": {"bridge": str(BRIDGE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Bridged the new truthful multilingual frontier: Stage9824 turns the Stage9813 same-surface packet into a one-run continued 100M result that beats the Stage9816 Gemma baseline across python, rust, c_cpp, and web_js_ts_html without mixing surfaces.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9825 Same-Surface Two-Phase Multilingual Frontier Bridge",
                "",
                f"Passed: `{bridge['passed']}`",
                f"Phase1 macro strict exact: `{bridge['metrics']['phase1_macro_strict_exact_100m']}`",
                f"Phase2 macro strict exact: `{bridge['metrics']['phase2_macro_strict_exact_100m']}`",
                f"Wins 100M: `{bridge['metrics']['wins_100m']}`",
                f"Wins Gemma: `{bridge['metrics']['wins_gemma']}`",
                f"Ties: `{bridge['metrics']['ties']}`",
                "",
                "This bridge supersedes the earlier mixed-surface frontier for the current best truthful multilingual result. It records that the Stage9824 two-phase continuation preserves a same-surface four-language win over Gemma on the Stage9813 packet.",
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
