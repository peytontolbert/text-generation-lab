#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8638_patch_operator_neutral_manifest" / "patch_operator_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8639_patch_operator_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8639_patch_operator_shortcut_baseline.json"

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
    scope = state["target_scope_features"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "need_key": row["semantic_key"].split(":")[2],
        "operator_signal": state["operator_signal"],
        "target_kind_hint": scope["target_kind_hint"],
        "has_visible_test": str(scope["has_visible_test"]),
        "has_visible_import_policy": str(scope["has_visible_import_policy"]),
        "has_visible_config": str(scope["has_visible_config"]),
        "bounded_patch_required": str(scope["bounded_patch_required"]),
        "max_hunks": str(budget["max_hunks"]),
        "max_files": str(budget["max_files"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["patch_operator"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        correct += int(table[key].most_common(1)[0][0] == row["clean_state"]["patch_operator"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["patch_operator"] for row in rows]
    features = [
        "language",
        "file_extension",
        "need_key",
        "operator_signal",
        "target_kind_hint",
        "has_visible_test",
        "has_visible_import_policy",
        "has_visible_config",
        "bounded_patch_required",
        "max_hunks",
        "max_files",
        "decoder_budget_ok",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+need_key": grouped_baseline(rows, ["language", "need_key"]),
        "target_scope_bits": grouped_baseline(rows, ["target_kind_hint", "has_visible_test", "has_visible_import_policy", "has_visible_config"]),
        "budget_bits": grouped_baseline(rows, ["max_hunks", "max_files", "decoder_budget_ok"]),
        "operator_signal+target_scope_bits": grouped_baseline(rows, ["operator_signal", "target_kind_hint", "has_visible_test", "has_visible_import_policy", "has_visible_config"]),
    }
    proxy_single = {k: v for k, v in single.items() if k != "operator_signal"}
    proxy_combos = {k: v for k, v in combos.items() if k != "operator_signal+target_scope_bits"}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": max(Counter(labels).values()) / len(labels),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "operator_signal": single["operator_signal"],
            "operator_signal+target_scope_bits": combos["operator_signal+target_scope_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_single.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.09
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
    )
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    summary = {
        "stage": 8639,
        "stage_name": "stage8639_patch_operator_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8639_patch_operator_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Operator signal is treated as semantic evidence; non-evidence proxies must stay below ceiling.",
        "next_best_step": "If passed, restore verifier_repair neutral builder.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
