#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs" / "local" / "artifacts" / "stage8630_intent_to_build_neutral_manifest" / "intent_to_build_neutral_manifest.jsonl"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8631_intent_to_build_shortcut_baseline"
SUMMARY = ROOT / "runs" / "summaries" / "stage8631_intent_to_build_shortcut_baseline.json"

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
    rows: list[dict[str, Any]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def majority_baseline(rows: list[dict[str, Any]]) -> float:
    labels = [row["clean_state"]["build_mode"] for row in rows]
    return max(Counter(labels).values()) / len(labels)


def feature_value(row: dict[str, Any], feature: str) -> str:
    state = row["corrupted_state"]
    repo = state["repo_state"]
    budget = state["budget"]
    mapping = {
        "language": state["language"],
        "file_extension": state["file_extension"],
        "task_key": row["semantic_key"].split(":")[2],
        "import_state": state["import_state"],
        "allowed_repository_visible": str(repo["allowed_repository_visible"]),
        "blocked_dependency_signal": str(repo["blocked_dependency_signal"]),
        "missing_context_signal": str(repo["missing_context_signal"]),
        "can_create_file": str(repo["can_create_file"]),
        "test_required": str(repo["test_required"]),
        "max_files": str(budget["max_files"]),
        "max_patch_hunks": str(budget["max_patch_hunks"]),
        "decoder_budget_ok": str(budget["decoder_budget_ok"]),
    }
    return mapping[feature]


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        table[key][row["clean_state"]["build_mode"]] += 1
    correct = 0
    for row in rows:
        key = tuple(feature_value(row, feature) for feature in features)
        pred = table[key].most_common(1)[0][0]
        correct += int(pred == row["clean_state"]["build_mode"])
    return correct / len(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    labels = [row["clean_state"]["build_mode"] for row in rows]
    features = [
        "language",
        "file_extension",
        "task_key",
        "import_state",
        "allowed_repository_visible",
        "blocked_dependency_signal",
        "missing_context_signal",
        "can_create_file",
        "test_required",
        "max_files",
        "max_patch_hunks",
        "decoder_budget_ok",
    ]
    single = {feature: grouped_baseline(rows, [feature]) for feature in features}
    combos = {
        "language+task_key": grouped_baseline(rows, ["language", "task_key"]),
        "repo_visibility_bits": grouped_baseline(rows, ["allowed_repository_visible", "blocked_dependency_signal", "missing_context_signal", "can_create_file"]),
        "budget_bits": grouped_baseline(rows, ["max_files", "max_patch_hunks", "decoder_budget_ok"]),
        "import_state+repo_visibility_bits": grouped_baseline(rows, ["import_state", "allowed_repository_visible", "blocked_dependency_signal", "missing_context_signal", "can_create_file"]),
    }
    # Import-state is intentionally discriminative evidence for this objective. It must not be a direct label string,
    # but it is allowed to carry semantic polarity. Non-evidence proxies must stay below ceiling.
    proxy_features = {k: v for k, v in single.items() if k != "import_state"}
    proxy_combos = {k: v for k, v in combos.items() if k != "import_state+repo_visibility_bits"}
    card = {
        "rows": len(rows),
        "label_counts": dict(sorted(Counter(labels).items())),
        "majority_baseline": majority_baseline(rows),
        "single_feature_baselines": dict(sorted(single.items())),
        "combo_baselines": dict(sorted(combos.items())),
        "allowed_evidence_baselines": {
            "import_state": single["import_state"],
            "import_state+repo_visibility_bits": combos["import_state+repo_visibility_bits"],
        },
        "proxy_baseline_ceiling": 0.66,
        "max_proxy_single": max(proxy_features.values()),
        "max_proxy_combo": max(proxy_combos.values()),
        "authority": AUTHORITY_CLOSED,
    }
    card["passed"] = (
        card["majority_baseline"] <= 0.21
        and card["max_proxy_single"] <= card["proxy_baseline_ceiling"]
        and card["max_proxy_combo"] <= card["proxy_baseline_ceiling"]
        and set(labels) == {"USE_WHITELIST_IMPORT", "BUILD_ON_TOP", "BUILD_FROM_SCRATCH", "RETRIEVE_MORE", "ABSTAIN_UNSAFE"}
    )
    (OUT_DIR / "shortcut_baseline_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": 8631,
        "stage_name": "stage8631_intent_to_build_shortcut_baseline",
        "passed": card["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": card,
        "artifacts": {
            "audit_card": str((OUT_DIR / "shortcut_baseline_card.json").relative_to(ROOT)),
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8631_intent_to_build_shortcut_baseline.py",
        },
        "decision": "Shortcut audit only. Semantic import_state evidence is allowed; non-evidence proxies must remain below ceiling. No training authority opened.",
        "next_best_step": "If passed, restore edit_localization neutral builder.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
