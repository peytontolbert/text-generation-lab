#!/usr/bin/env python3
"""Audit Stage8610 symbol-binding counterfactual patch readiness."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from counterfactual_obligation_audit import audit_rows as audit_counterfactual_rows


REQUIRED_ACTIONS = ("BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "BIND_TEST_TO_SYMBOL", "RETRIEVE_MORE", "ABSTAIN_UNBOUND")
REQUIRED_QUERY_KINDS = ("callsite", "import", "test")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def action(row: dict[str, Any]) -> str:
    return str(row["target"]["binding_action"])


def query_kind(row: dict[str, Any]) -> str:
    return str(row["query"]["query_kind"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="runs/local/artifacts/stage8610_symbol_binding_counterfactual_patch/symbol_binding_counterfactual_patch.jsonl")
    args = parser.parse_args()
    rows = load_jsonl(Path(args.manifest))
    action_counts = Counter(action(row) for row in rows)
    query_counts = Counter(query_kind(row) for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    obligation_counts = Counter(row.get("obligation_type") for row in rows)
    by_query_action: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_action: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_query: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_query_action[query_kind(row)][action(row)] += 1
        by_split_action[row["split"]][action(row)] += 1
        by_split_query[row["split"]][query_kind(row)] += 1

    cf_card = audit_counterfactual_rows(rows)
    row_n = len(rows)
    majority_action_exact = max(action_counts.values(), default=0) / row_n if row_n else 0.0
    query_kind_baseline_exact = 0.0
    if row_n:
        query_kind_baseline_exact = sum(max(counter.values()) for counter in by_query_action.values()) / row_n

    missing_actions = [name for name in REQUIRED_ACTIONS if action_counts.get(name, 0) == 0]
    missing_query_kinds = [name for name in REQUIRED_QUERY_KINDS if query_counts.get(name, 0) == 0]
    missing_split_action_cells = []
    missing_split_query_cells = []
    for split in ("train", "eval", "strict_eval"):
        for name in REQUIRED_ACTIONS:
            if by_split_action[split].get(name, 0) == 0:
                missing_split_action_cells.append(f"{split}:{name}")
        for name in REQUIRED_QUERY_KINDS:
            if by_split_query[split].get(name, 0) == 0:
                missing_split_query_cells.append(f"{split}:{name}")

    model_ready = (
        cf_card["counterfactual_obligations_complete"]
        and not missing_actions
        and not missing_query_kinds
        and not missing_split_action_cells
        and not missing_split_query_cells
        and majority_action_exact < 0.5
        and query_kind_baseline_exact < 0.6
    )
    metrics = {
        "rows": row_n,
        "action_counts": dict(action_counts),
        "query_kind_counts": dict(query_counts),
        "split_counts": dict(split_counts),
        "obligation_counts": dict(obligation_counts),
        "counterfactual_card": cf_card,
        "majority_action_baseline_exact": round(majority_action_exact, 4),
        "query_kind_action_baseline_exact": round(query_kind_baseline_exact, 4),
        "missing_actions": missing_actions,
        "missing_query_kinds": missing_query_kinds,
        "missing_split_action_cells": missing_split_action_cells,
        "missing_split_query_cells": missing_split_query_cells,
        "model_ready": model_ready,
        "model_ready_training_rows": 0,
        "loss_enabled_rows": sum(int(any((row.get("loss_mask") or {}).values())) for row in rows),
        "training_blocked_by_missing_test_bind": "BIND_TEST_TO_SYMBOL" in missing_actions,
        "training_blocked_by_shortcut_baseline": query_kind_baseline_exact >= 0.6,
    }
    passed = cf_card["counterfactual_obligations_complete"] and not model_ready
    summary = {
        "stage": 8611,
        "name": "stage8611_reconstructed_symbol_binding_counterfactual_patch_audit",
        "passed": passed,
        "summary": "Audited Stage8610 symbol-binding counterfactual patch. Counterfactual obligations are complete, but training remains blocked because true BIND_TEST_TO_SYMBOL/test-query coverage is missing and query-kind baseline remains high.",
        "metrics": metrics,
        "gates": {
            "counterfactual_obligations_complete": cf_card["counterfactual_obligations_complete"],
            "model_ready_training_rows": 0,
            "training_blocked_by_missing_test_bind": metrics["training_blocked_by_missing_test_bind"],
            "training_blocked_by_shortcut_baseline": metrics["training_blocked_by_shortcut_baseline"],
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False,
        },
        "next_best_step": "Mine real test-to-symbol binding examples from /arxiv repositories using test name, import, and call evidence, then rebalance query/action cells."
    }
    out = Path("runs/local/artifacts/stage8611_symbol_binding_counterfactual_patch_audit")
    write_json(out / "audit_card.json", metrics)
    write_json(Path("runs/summaries/stage8611_reconstructed_symbol_binding_counterfactual_patch_audit.json"), summary)
    print(json.dumps({"passed": passed, "metrics": metrics}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
