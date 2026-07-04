#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8647_output_repair_denoise_neutral_manifest" / "output_repair_denoise_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8648_output_repair_denoise_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8648_output_repair_denoise_shortcut_baseline.json"

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
    bad = state["bad_output_features"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "surface_key": row["semantic_key"].split(":")[2],
        "repair_signal": state["repair_signal"],
        "has_internal_token_shape": str(bad["has_internal_token_shape"]),
        "too_short": str(bad["too_short"]),
        "has_repetition": str(bad["has_repetition"]),
        "surface_mismatch": str(bad["surface_mismatch"]),
        "unsafe_or_unrecoverable": str(bad["unsafe_or_unrecoverable"]),
        "verifier_feedback_visible": str(bad["verifier_feedback_visible"]),
        "structured_state_available": str(bad["structured_state_available"]),
        "max_repair_steps": str(budget["max_repair_steps"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
        "denoise_training_authorized": str(budget["denoise_training_authorized"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["output_repair_action"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["output_repair_action"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["output_repair_action"] for row in rows]
    features = [
        "language",
        "file_extension",
        "surface_key",
        "repair_signal",
        "has_internal_token_shape",
        "too_short",
        "has_repetition",
        "surface_mismatch",
        "unsafe_or_unrecoverable",
        "verifier_feedback_visible",
        "structured_state_available",
        "max_repair_steps",
        "decoder_budget_ok",
        "denoise_training_authorized",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+surface_key": grouped_baseline(rows, ["language", "surface_key"]),
        "bad_output_bits": grouped_baseline(rows, ["has_internal_token_shape", "too_short", "has_repetition", "surface_mismatch", "unsafe_or_unrecoverable"]),
        "context_bits": grouped_baseline(rows, ["verifier_feedback_visible", "structured_state_available"]),
        "budget_bits": grouped_baseline(rows, ["max_repair_steps", "decoder_budget_ok", "denoise_training_authorized"]),
        "repair_signal+context_bits": grouped_baseline(rows, ["repair_signal", "verifier_feedback_visible", "structured_state_available"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "repair_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "repair_signal+context_bits"}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "repair_signal": single["repair_signal"],
            "repair_signal+context_bits": combos["repair_signal+context_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.21
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
    )
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8648,
        "stage_name": "stage8648_output_repair_denoise_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8648_output_repair_denoise_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Repair signal is treated as semantic evidence; non-evidence proxies must stay below ceiling. denoise_ce remains closed.",
        "next_best_step": "Update recovery completion queue status and decide whether to repair repo graph/symbol-binding or prepare aggregate structured curriculum gate.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
