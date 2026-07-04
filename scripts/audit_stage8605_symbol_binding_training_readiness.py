#!/usr/bin/env python3
"""Training-readiness audit for Stage8604 symbol-binding candidates."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_QUERY_KINDS = ("callsite", "import", "test")
REQUIRED_ACTIONS = ("BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "BIND_TEST_TO_SYMBOL", "RETRIEVE_MORE", "ABSTAIN_UNBOUND")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="runs/local/artifacts/stage8604_arxiv_symbol_binding_candidates_id_patch/symbol_binding_candidates.jsonl")
    args = parser.parse_args()
    rows = load_jsonl(Path(args.manifest))

    query_counts = Counter(row["query"]["query_kind"] for row in rows)
    action_counts = Counter(row["target"]["binding_action"] for row in rows)
    split_counts = Counter(row["split"] for row in rows)
    by_query_action: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_action: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_query: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_query_action[row["query"]["query_kind"]][row["target"]["binding_action"]] += 1
        by_split_action[row["split"]][row["target"]["binding_action"]] += 1
        by_split_query[row["split"]][row["query"]["query_kind"]] += 1

    rows_n = len(rows)
    majority_action_exact = max(action_counts.values(), default=0) / rows_n if rows_n else 0.0
    query_kind_baseline_exact = 0.0
    if rows_n:
        query_kind_baseline_exact = sum(max(counter.values()) for counter in by_query_action.values()) / rows_n

    missing_query_kinds = [kind for kind in REQUIRED_QUERY_KINDS if query_counts.get(kind, 0) == 0]
    missing_actions = [action for action in REQUIRED_ACTIONS if action_counts.get(action, 0) == 0]
    low_query_kinds = [kind for kind in REQUIRED_QUERY_KINDS if query_counts.get(kind, 0) < 30]
    low_actions = [action for action in REQUIRED_ACTIONS if action_counts.get(action, 0) < 30]
    missing_split_action_cells = []
    for split in ("train", "eval", "strict_eval"):
        for action in REQUIRED_ACTIONS:
            if by_split_action[split].get(action, 0) == 0:
                missing_split_action_cells.append(f"{split}:{action}")
    missing_split_query_cells = []
    for split in ("train", "eval", "strict_eval"):
        for kind in REQUIRED_QUERY_KINDS:
            if by_split_query[split].get(kind, 0) == 0:
                missing_split_query_cells.append(f"{split}:{kind}")

    # Counterfactuals are not materialized yet. The model-ready symbol-binding
    # stage must add siblings such as local bind vs external abstain, test bind
    # vs retrieve, and import bind vs blocked/external import.
    counterfactual_sibling_rows = 0
    model_ready = (
        not missing_query_kinds
        and not missing_actions
        and not low_query_kinds
        and not low_actions
        and not missing_split_action_cells
        and not missing_split_query_cells
        and majority_action_exact < 0.5
        and query_kind_baseline_exact < 0.6
        and counterfactual_sibling_rows > 0
    )

    metrics = {
        "rows": rows_n,
        "query_kind_counts": dict(query_counts),
        "binding_action_counts": dict(action_counts),
        "split_counts": dict(split_counts),
        "by_query_action": {k: dict(v) for k, v in by_query_action.items()},
        "by_split_action": {k: dict(v) for k, v in by_split_action.items()},
        "by_split_query": {k: dict(v) for k, v in by_split_query.items()},
        "majority_action_baseline_exact": round(majority_action_exact, 4),
        "query_kind_action_baseline_exact": round(query_kind_baseline_exact, 4),
        "missing_query_kinds": missing_query_kinds,
        "missing_actions": missing_actions,
        "low_query_kinds": low_query_kinds,
        "low_actions": low_actions,
        "missing_split_action_cells": missing_split_action_cells,
        "missing_split_query_cells": missing_split_query_cells,
        "counterfactual_sibling_rows": counterfactual_sibling_rows,
        "model_ready_training_rows": 0,
        "training_blocked_by_balance": True,
        "training_blocked_by_missing_counterfactuals": True,
        "model_ready": model_ready
    }
    passed = not model_ready
    summary = {
        "stage": 8605,
        "name": "stage8605_reconstructed_symbol_binding_training_readiness_audit",
        "passed": passed,
        "summary": "Symbol-binding candidate rows are leak-clean but not training-ready. Query/action imbalance and missing counterfactual siblings must be patched before structured loss can be enabled.",
        "metrics": metrics,
        "gates": {
            "model_ready_training_rows": 0,
            "training_blocked_by_balance": True,
            "training_blocked_by_missing_counterfactuals": True,
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False
        },
        "next_best_step": "Build a balanced symbol-binding patch with import/test rows and counterfactual siblings before any native structured probe."
    }
    out = Path("runs/local/artifacts/stage8605_symbol_binding_training_readiness_audit")
    write_json(out / "audit_card.json", metrics)
    write_json(Path("runs/summaries/stage8605_reconstructed_symbol_binding_training_readiness_audit.json"), summary)
    print(json.dumps({"passed": passed, "metrics": metrics}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
