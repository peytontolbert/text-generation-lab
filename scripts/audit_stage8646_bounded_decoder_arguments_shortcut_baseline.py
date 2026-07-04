#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8645_bounded_decoder_arguments_neutral_manifest" / "bounded_decoder_arguments_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8646_bounded_decoder_arguments_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8646_bounded_decoder_arguments_shortcut_baseline.json"

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
    feats = state["bounded_argument_features"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "context_key": row["semantic_key"].split(":")[2],
        "argument_signal": state["argument_signal"],
        "small_argument_required": str(feats["small_argument_required"]),
        "argument_evidence_visible": str(feats["argument_evidence_visible"]),
        "over_budget_signal": str(feats["over_budget_signal"]),
        "approved_import_policy_visible": str(feats["approved_import_policy_visible"]),
        "path_context_visible": str(feats["path_context_visible"]),
        "symbol_context_visible": str(feats["symbol_context_visible"]),
        "target_length_bucket": budget["target_length_bucket"],
        "max_arg_tokens": str(budget["max_arg_tokens"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["bounded_argument_type"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["bounded_argument_type"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["bounded_argument_type"] for row in rows]
    features = [
        "language",
        "file_extension",
        "context_key",
        "argument_signal",
        "small_argument_required",
        "argument_evidence_visible",
        "over_budget_signal",
        "approved_import_policy_visible",
        "path_context_visible",
        "symbol_context_visible",
        "target_length_bucket",
        "max_arg_tokens",
        "decoder_budget_ok",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+context_key": grouped_baseline(rows, ["language", "context_key"]),
        "arg_visibility_bits": grouped_baseline(rows, ["small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
        "budget_bits": grouped_baseline(rows, ["target_length_bucket", "max_arg_tokens", "decoder_budget_ok"]),
        "argument_signal+arg_visibility_bits": grouped_baseline(rows, ["argument_signal", "small_argument_required", "argument_evidence_visible", "over_budget_signal", "approved_import_policy_visible", "path_context_visible", "symbol_context_visible"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "argument_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "argument_signal+arg_visibility_bits"}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "argument_signal": single["argument_signal"],
            "argument_signal+arg_visibility_bits": combos["argument_signal+arg_visibility_bits"],
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
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8646,
        "stage_name": "stage8646_bounded_decoder_arguments_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8646_bounded_decoder_arguments_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Argument signal is treated as semantic evidence; non-evidence proxies must stay below ceiling. decoder_ce remains closed.",
        "next_best_step": "If passed, restore output_repair_denoise neutral builder.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
