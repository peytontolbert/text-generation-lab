#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8643_verifier_repair_neutral_manifest" / "verifier_repair_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8644_verifier_repair_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8644_verifier_repair_shortcut_baseline.json"
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
    packet = state["verifier_packet"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "patch_context": state["patch_context"],
        "context_key": row["semantic_key"].split(":")[2],
        "verifier_signal": state["verifier_signal"],
        "log_available": str(packet["log_available"]),
        "test_name_visible": str(packet["test_name_visible"]),
        "source_location_visible": str(packet["source_location_visible"]),
        "patch_summary_visible": str(packet["patch_summary_visible"]),
        "runtime_execution_authorized": str(packet["runtime_execution_authorized"]),
        "max_repair_steps": str(budget["max_repair_steps"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
        "runtime_reward_allowed": str(budget["runtime_reward_allowed"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["verifier_repair_action"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["verifier_repair_action"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["verifier_repair_action"] for row in rows]
    features = [
        "language",
        "file_extension",
        "patch_context",
        "context_key",
        "verifier_signal",
        "log_available",
        "test_name_visible",
        "source_location_visible",
        "patch_summary_visible",
        "runtime_execution_authorized",
        "max_repair_steps",
        "decoder_budget_ok",
        "runtime_reward_allowed",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+context_key": grouped_baseline(rows, ["language", "context_key"]),
        "packet_visibility_bits": grouped_baseline(rows, ["log_available", "test_name_visible", "source_location_visible", "patch_summary_visible"]),
        "budget_bits": grouped_baseline(rows, ["max_repair_steps", "decoder_budget_ok", "runtime_reward_allowed"]),
        "verifier_signal+packet_visibility_bits": grouped_baseline(rows, ["verifier_signal", "log_available", "test_name_visible", "source_location_visible", "patch_summary_visible"]),
    }
    proxy_single = {key: value for key, value in single.items() if key != "verifier_signal"}
    proxy_combos = {key: value for key, value in combos.items() if not key.startswith("verifier_signal+")}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "verifier_signal": single["verifier_signal"],
            "verifier_signal+packet_visibility_bits": combos["verifier_signal+packet_visibility_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.12
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
    )
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": 8644,
        "stage_name": "stage8644_verifier_repair_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8644_verifier_repair_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Verifier signal is treated as semantic evidence; non-evidence proxies must remain below ceiling.",
        "next_best_step": "Build label-vocab/hash and telemetry contract cards for structured probe manifests before execution consideration.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
