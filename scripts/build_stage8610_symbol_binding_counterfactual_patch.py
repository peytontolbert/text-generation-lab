#!/usr/bin/env python3
"""Build balanced counterfactual symbol-binding patch rows from Stage8604."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


OBLIGATIONS = (
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED_OR_RETRIEVE",
    "CONTRASTIVE_BOUNDARY_SIBLING",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(*parts: str, n: int = 16) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:n]


def split_for(group_id: str) -> str:
    bucket = int(stable_hash(group_id, n=8), 16) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "strict_eval"


def action(row: dict[str, Any]) -> str:
    return str(row["target"]["binding_action"])


def query_kind(row: dict[str, Any]) -> str:
    return str(row["query"]["query_kind"])


def neutralize_ids(row: dict[str, Any], group_id: str, index: int, obligation: str) -> dict[str, Any]:
    out = copy.deepcopy(row)
    out["row_id"] = f"stage8610_row_{stable_hash(group_id, str(index), obligation, n=12)}"
    out["counterfactual_group_id"] = group_id
    out["obligation_type"] = obligation
    out["split"] = split_for(group_id)
    out["loss_mask"] = {
        "symbol_binding_ce": False,
        "decoder_ce": False,
        "denoise_ce": False,
        "runtime_reward": False,
    }
    out.setdefault("anti_cheat", {})["counterfactual_patch_row"] = True
    return out


def as_retrieve_control(row: dict[str, Any], group_id: str, index: int) -> dict[str, Any]:
    out = neutralize_ids(row, group_id, index, "EVIDENCE_REMOVED_OR_RETRIEVE")
    out["query"] = copy.deepcopy(out["query"])
    out["query"]["features"] = copy.deepcopy(out["query"].get("features", {}))
    out["query"]["features"]["evidence_removed"] = True
    out["graph_input"] = copy.deepcopy(out["graph_input"])
    out["graph_input"]["nodes"] = [
        node for node in out["graph_input"].get("nodes", []) if node.get("node_type") == "repo"
    ]
    out["graph_input"]["edges"] = []
    out["target"] = {
        "binding_action": "RETRIEVE_MORE",
        "target_node_id": None,
        "target_node_kind": None,
    }
    return out


def as_contrastive(row: dict[str, Any], sibling: dict[str, Any], group_id: str, index: int) -> dict[str, Any]:
    out = neutralize_ids(sibling, group_id, index, "CONTRASTIVE_BOUNDARY_SIBLING")
    out["query"] = copy.deepcopy(out["query"])
    out["query"]["features"] = copy.deepcopy(out["query"].get("features", {}))
    out["query"]["features"]["contrastive_sibling"] = True
    out["query"]["features"]["same_query_kind_as_positive"] = query_kind(row) == query_kind(sibling)
    return out


def select_rows(rows: list[dict[str, Any]], per_action: int) -> dict[str, list[dict[str, Any]]]:
    by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_action[action(row)].append(row)
    return {key: value[:per_action] for key, value in by_action.items()}


def build_groups(rows: list[dict[str, Any]], per_action: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = select_rows(rows, per_action)
    output: list[dict[str, Any]] = []
    actions = sorted(selected)
    sibling_pool = {key: list(value) for key, value in selected.items()}
    true_test_bind_available = len(selected.get("BIND_TEST_TO_SYMBOL", []))

    group_index = 0
    for action_name in actions:
        if action_name == "RETRIEVE_MORE":
            continue
        for row in selected[action_name]:
            group_id = f"cf_{stable_hash(row['row_id'], action_name)}"
            output.append(neutralize_ids(row, group_id, 0, "POSITIVE_ORIGINAL"))
            output.append(as_retrieve_control(row, group_id, 1))
            contrastive_source = None
            # Prefer same query kind with a different action.
            for candidate_action in actions:
                if candidate_action == action_name:
                    continue
                for candidate in sibling_pool[candidate_action]:
                    if query_kind(candidate) == query_kind(row):
                        contrastive_source = candidate
                        break
                if contrastive_source:
                    break
            if contrastive_source is None:
                for candidate_action in actions:
                    if candidate_action != action_name and sibling_pool[candidate_action]:
                        contrastive_source = sibling_pool[candidate_action][0]
                        break
            if contrastive_source is None:
                continue
            output.append(as_contrastive(row, contrastive_source, group_id, 2))
            group_index += 1

    # Add pure retrieve groups from candidate rows that were originally retrieve.
    for row in selected.get("RETRIEVE_MORE", [])[:per_action]:
        group_id = f"cf_{stable_hash(row['row_id'], 'retrieve')}"
        bind_sibling = None
        for candidate_action in ("BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "ABSTAIN_UNBOUND"):
            for candidate in sibling_pool.get(candidate_action, []):
                if query_kind(candidate) == query_kind(row):
                    bind_sibling = candidate
                    break
            if bind_sibling:
                break
        if not bind_sibling:
            continue
        output.append(neutralize_ids(row, group_id, 0, "POSITIVE_ORIGINAL"))
        output.append(as_retrieve_control(row, group_id, 1))
        output.append(as_contrastive(row, bind_sibling, group_id, 2))

    card = {
        "source_rows": len(rows),
        "output_rows": len(output),
        "selected_source_action_counts": {k: len(v) for k, v in selected.items()},
        "true_test_bind_available": true_test_bind_available,
        "groups": len({row["counterfactual_group_id"] for row in output}),
        "obligation_counts": dict(Counter(row["obligation_type"] for row in output)),
        "action_counts": dict(Counter(action(row) for row in output)),
        "query_kind_counts": dict(Counter(query_kind(row) for row in output)),
        "split_counts": dict(Counter(row["split"] for row in output)),
        "model_ready_training_rows": 0,
        "loss_enabled_rows": 0,
    }
    return output, card


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="runs/local/artifacts/stage8604_arxiv_symbol_binding_candidates_id_patch/symbol_binding_candidates.jsonl")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8610_symbol_binding_counterfactual_patch")
    parser.add_argument("--per-action", type=int, default=24)
    args = parser.parse_args()
    rows = load_jsonl(Path(args.input))
    output, card = build_groups(rows, args.per_action)
    out = Path(args.output_dir)
    write_jsonl(out / "symbol_binding_counterfactual_patch.jsonl", output)
    write_json(out / "cell_card.json", card)
    passed = (
        card["output_rows"] > 0
        and card["groups"] > 0
        and card["loss_enabled_rows"] == 0
        and card["obligation_counts"].get("POSITIVE_ORIGINAL", 0) == card["groups"]
        and card["obligation_counts"].get("EVIDENCE_REMOVED_OR_RETRIEVE", 0) == card["groups"]
        and card["obligation_counts"].get("CONTRASTIVE_BOUNDARY_SIBLING", 0) == card["groups"]
    )
    summary = {
        "stage": 8610,
        "name": "stage8610_reconstructed_symbol_binding_counterfactual_patch",
        "passed": passed,
        "summary": "Built a closed-authority symbol-binding counterfactual patch manifest from Stage8604 candidates. Rows materialize positive, retrieve/evidence-removed, and contrastive sibling obligations but keep training loss disabled pending shortcut/readiness audits.",
        "metrics": card,
        "artifacts": {
            "manifest": str(out / "symbol_binding_counterfactual_patch.jsonl"),
            "cell_card": str(out / "cell_card.json"),
        },
        "gates": {
            "model_ready_training_rows": 0,
            "loss_enabled_rows": card["loss_enabled_rows"],
            "true_test_bind_available": card["true_test_bind_available"],
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
            "promotion_ready": False,
        },
        "next_best_step": "Audit counterfactual completeness and shortcut baselines; then patch true BIND_TEST_TO_SYMBOL coverage before enabling symbol_binding_ce."
    }
    write_json(Path("runs/summaries/stage8610_reconstructed_symbol_binding_counterfactual_patch.json"), summary)
    print(json.dumps({"passed": passed, "metrics": card}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
