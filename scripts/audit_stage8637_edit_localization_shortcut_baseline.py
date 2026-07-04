#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8636_edit_localization_neutral_manifest" / "edit_localization_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8637_edit_localization_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8637_edit_localization_shortcut_baseline.json"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def read_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def feature_value(row: dict[str, Any], feature: str) -> str:
    state = row["corrupted_state"]
    graph = state["graph_packet"]
    bits = state["neutral_context_bits"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "task_key": row["semantic_key"].split(":")[2],
        "locality_signal": state["locality_signal"],
        "query_node_type": graph["query_node_type"],
        "edge_family_count": str(graph["edge_family_count"]),
        "candidate_node_count": str(graph["candidate_node_count"]),
        "opaque_graph_id": graph["opaque_graph_id"],
        "tests_visible": str(bits["tests_visible"]),
        "config_visible": str(bits["config_visible"]),
        "entrypoint_visible": str(bits["entrypoint_visible"]),
        "symbol_names_visible": str(bits["symbol_names_visible"]),
        "max_files": str(state["budget"]["max_files"]),
        "max_symbols": str(state["budget"]["max_symbols"]),
        "decoder_budget_ok": str(state["budget"]["decoder_budget_ok"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["edit_localization_target"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        pred = table[key].most_common(1)[0][0]
        correct += int(pred == row["clean_state"]["edit_localization_target"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["edit_localization_target"] for row in rows]
    features = [
        "language",
        "file_extension",
        "task_key",
        "locality_signal",
        "query_node_type",
        "edge_family_count",
        "candidate_node_count",
        "opaque_graph_id",
        "tests_visible",
        "config_visible",
        "entrypoint_visible",
        "symbol_names_visible",
        "max_files",
        "max_symbols",
        "decoder_budget_ok",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+task_key": grouped_baseline(rows, ["language", "task_key"]),
        "graph_shape": grouped_baseline(rows, ["query_node_type", "edge_family_count", "candidate_node_count"]),
        "neutral_context_bits": grouped_baseline(rows, ["tests_visible", "config_visible", "entrypoint_visible", "symbol_names_visible"]),
        "budget_bits": grouped_baseline(rows, ["max_files", "max_symbols", "decoder_budget_ok"]),
        "locality_signal+graph_shape": grouped_baseline(rows, ["locality_signal", "query_node_type", "edge_family_count", "candidate_node_count"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "locality_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "locality_signal+graph_shape"}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "locality_signal": single["locality_signal"],
            "locality_signal+graph_shape": combos["locality_signal+graph_shape"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.15
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
    )
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": 8637,
        "stage_name": "stage8637_edit_localization_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8637_edit_localization_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Locality signal is treated as semantic evidence; graph/context/budget proxies must stay below ceiling.",
        "next_best_step": "If passed, restore patch_operator neutral builder.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
