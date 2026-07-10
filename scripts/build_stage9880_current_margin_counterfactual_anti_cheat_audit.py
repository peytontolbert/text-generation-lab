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
STAGE = 9880
NAME = "stage9880_current_margin_counterfactual_anti_cheat_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_counterfactual_anti_cheat_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_COUNTERFACTUAL_ANTI_CHEAT_AUDIT_STAGE9880.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
FRONTIER = ROOT / "runs/local/artifacts/stage9878_current_margin_multilingual_frontier_bridge/current_margin_multilingual_frontier_bridge.json"
PACKETS = ROOT / "runs/local/artifacts/stage9879_current_margin_multilingual_winner_review_packets/current_margin_multilingual_winner_review_packet_manifest.json"
GLOBAL_GATE = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


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


def build_audit() -> dict[str, Any]:
    frontier = load_json(FRONTIER)
    packets = load_json(PACKETS)
    gate = load_json(GLOBAL_GATE)
    frontier_rows = frontier.get("records") if isinstance(frontier.get("records"), list) else []
    packet_rows = packets.get("rows") if isinstance(packets.get("rows"), list) else []
    packet_index = {str(row.get("language_family") or ""): row for row in packet_rows}

    failures: list[str] = []
    records: list[dict[str, Any]] = []
    for language in LANGS:
        frontier_row = next((row for row in frontier_rows if str(row.get("language_family") or "") == language), None)
        packet_row = packet_index.get(language)
        if not isinstance(frontier_row, dict):
            failures.append(f"missing_frontier_row:{language}")
            continue
        if not isinstance(packet_row, dict):
            failures.append(f"missing_packet_row:{language}")
            continue
        review_paths = packet_row.get("review_packet_paths") if isinstance(packet_row.get("review_packet_paths"), dict) else {}
        anti_draft_path = ROOT / str(review_paths.get("anti_cheat_recommendation_draft") or "")
        anti_card_path = ROOT / str(review_paths.get("anti_cheat_cards") or "")
        anti_draft = load_json(anti_draft_path) if anti_draft_path.exists() else {}
        anti_card = load_json(anti_card_path) if anti_card_path.exists() else {}
        judgments = anti_draft.get("recommended_challenge_judgments") if isinstance(anti_draft.get("recommended_challenge_judgments"), list) else []
        label_proxy = next((j for j in judgments if str(j.get("challenge_family") or "") == "label_proxy_shortcuts"), None)
        fairness = next((j for j in judgments if str(j.get("challenge_family") or "") == "cross_model_surface_fairness"), None)
        hidden_reference = next((j for j in judgments if str(j.get("challenge_family") or "") == "hidden_reference_materialization"), None)
        metadata_shortcuts = next((j for j in judgments if str(j.get("challenge_family") or "") == "metadata_and_graph_shortcuts"), None)
        records.append(
            {
                "language_family": language,
                "claim_scope": frontier_row.get("claim_scope"),
                "same_surface_comparison_stage": frontier_row.get("same_surface_comparison_stage"),
                "same_surface_packet_stage": frontier_row.get("same_surface_packet_stage"),
                "strict_exact_100m": frontier_row.get("strict_exact_100m"),
                "strict_exact_gemma": frontier_row.get("strict_exact_gemma"),
                "strict_verdict": frontier_row.get("strict_verdict"),
                "language_family_verdict": frontier_row.get("language_family_verdict"),
                "harder_counterfactual_strict_exact_100m": frontier_row.get("harder_counterfactual_strict_exact_100m"),
                "harder_counterfactual_strict_exact_gemma": frontier_row.get("harder_counterfactual_strict_exact_gemma"),
                "harder_counterfactual_strict_verdict": frontier_row.get("harder_counterfactual_strict_verdict"),
                "abstention_counterfactual_strict_exact_100m": frontier_row.get("abstention_counterfactual_strict_exact_100m"),
                "abstention_counterfactual_strict_exact_gemma": frontier_row.get("abstention_counterfactual_strict_exact_gemma"),
                "abstention_counterfactual_strict_verdict": frontier_row.get("abstention_counterfactual_strict_verdict"),
                "label_proxy_shortcut_risk": {
                    "recommended_pass": None if not isinstance(label_proxy, dict) else label_proxy.get("recommended_pass"),
                    "confidence": None if not isinstance(label_proxy, dict) else label_proxy.get("confidence"),
                },
                "cross_model_surface_fairness": {
                    "recommended_pass": None if not isinstance(fairness, dict) else fairness.get("recommended_pass"),
                    "confidence": None if not isinstance(fairness, dict) else fairness.get("confidence"),
                },
                "hidden_reference_materialization": {
                    "recommended_pass": None if not isinstance(hidden_reference, dict) else hidden_reference.get("recommended_pass"),
                    "confidence": None if not isinstance(hidden_reference, dict) else hidden_reference.get("confidence"),
                },
                "metadata_and_graph_shortcuts": {
                    "recommended_pass": None if not isinstance(metadata_shortcuts, dict) else metadata_shortcuts.get("recommended_pass"),
                    "confidence": None if not isinstance(metadata_shortcuts, dict) else metadata_shortcuts.get("confidence"),
                },
                "global_stage9717_gate_passed": gate.get("passed") is True,
                "cell_specific_anti_cheat_status": anti_card.get("status"),
                "cell_specific_anti_cheat_path": str(anti_card_path.relative_to(ROOT)) if anti_card_path.exists() else None,
                "cell_specific_recommendation_path": str(anti_draft_path.relative_to(ROOT)) if anti_draft_path.exists() else None,
                "anti_cheat_conclusion": (
                    "fair_same_surface_comparison_but_shortcut_resistance_not_yet_proven"
                    if isinstance(label_proxy, dict) and label_proxy.get("recommended_pass") is False
                    else "review_incomplete"
                ),
            }
        )

    metrics = {
        "validated_cells": len(records),
        "global_stage9717_gate_passed": gate.get("passed") is True,
        "language_family_wins_100m": sum(1 for row in records if row.get("language_family_verdict") == "100m_better"),
        "strict_language_wins_100m": sum(1 for row in records if row.get("strict_verdict") == "100m_better"),
        "strict_language_ties": sum(1 for row in records if row.get("strict_verdict") == "tie"),
        "cells_with_label_proxy_shortcut_risk": sum(1 for row in records if (row.get("label_proxy_shortcut_risk") or {}).get("recommended_pass") is False),
        "cells_with_cross_model_fairness_support": sum(1 for row in records if (row.get("cross_model_surface_fairness") or {}).get("recommended_pass") is True),
        "cells_with_hidden_reference_clearance": sum(1 for row in records if (row.get("hidden_reference_materialization") or {}).get("recommended_pass") is True),
        "cells_with_metadata_shortcut_clearance": sum(1 for row in records if (row.get("metadata_and_graph_shortcuts") or {}).get("recommended_pass") is True),
        "cells_where_harder_counterfactual_keeps_100m_edge": sum(1 for row in records if (row.get("harder_counterfactual_strict_verdict") == "100m_win")),
        "cells_where_harder_counterfactual_erases_or_reverses_edge": sum(1 for row in records if (row.get("harder_counterfactual_strict_verdict") in {"tie", "gemma_win"})),
        "cells_where_abstention_counterfactual_favors_100m": sum(1 for row in records if (row.get("abstention_counterfactual_strict_verdict") == "100m_win")),
    }

    if metrics["validated_cells"] != 4:
        failures.append("validated_cells_not_4")
    if metrics["cells_with_label_proxy_shortcut_risk"] != 4:
        failures.append("label_proxy_shortcut_risk_count_mismatch")
    if metrics["cells_with_cross_model_fairness_support"] != 4:
        failures.append("cross_model_fairness_support_count_mismatch")

    caveats = [
        "This audit is current to the Stage9878 same-surface multilingual frontier and Stage9879 review packets, not the older Stage9826 continuation packet.",
        "The comparison is fair at the same-surface level, but all four cells still carry unresolved label-proxy shortcut risk.",
        "Harder counterfactuals preserve a 100M strict edge in only one language family, so robustness remains materially incomplete.",
        "Abstention counterfactuals improve the story in three of four language families, which supports explicit abstention labeling for ambiguous rows.",
    ]

    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": metrics,
        "caveats": caveats,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Strengthen same-packet shortcut probes on the Stage9867/9878 frontier, especially for python, c_cpp, and web where harder counterfactuals erase or reverse the strict edge."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Packaged the current Stage9878 multilingual frontier into direct anti-cheat cards that combine same-surface fairness evidence from Stage9878 with the active Stage9879 review packets and the later harder/abstention counterfactual outcomes.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9880 Current Margin Counterfactual Anti-Cheat Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Validated cells: `{audit['metrics']['validated_cells']}`",
                f"Language-family wins 100M: `{audit['metrics']['language_family_wins_100m']}`",
                f"Strict-language wins 100M: `{audit['metrics']['strict_language_wins_100m']}`",
                f"Strict-language ties: `{audit['metrics']['strict_language_ties']}`",
                f"Cells with label-proxy shortcut risk: `{audit['metrics']['cells_with_label_proxy_shortcut_risk']}`",
                f"Cells with same-surface fairness support: `{audit['metrics']['cells_with_cross_model_fairness_support']}`",
                f"Harder counterfactuals preserving 100M edge: `{audit['metrics']['cells_where_harder_counterfactual_keeps_100m_edge']}`",
                "",
                "This stage supersedes the old Stage9826 anti-cheat packaging for the current truthful multilingual margin frontier.",
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
    print(json.dumps({"stage": STAGE, "passed": summary['passed'], "metrics": audit['metrics'], "failures": audit['failures']}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
