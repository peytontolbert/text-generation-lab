#!/usr/bin/env python3
from __future__ import annotations

import collections
import hashlib
import json
import time
from pathlib import Path

from gate_status_contract import default_gate_status

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
RETRIEVAL = ROOT / "runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest"
OUT = OUT_DIR / "source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries/stage8676_source_backed_symbol_binding_shortcut_repair_manifest.json"
DOC = ROOT / "docs/SOURCE_BACKED_SYMBOL_BINDING_SHORTCUT_REPAIR_MANIFEST_STAGE8676.md"

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
LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "symbol_binding_ce": False,
    "source_backed_symbol_binding_candidate_ce": False,
}
ACTIONS = [
    "RETRIEVE_MORE",
    "BIND_CALL_TO_SYMBOL",
    "BIND_TEST_TO_SYMBOL",
    "ABSTAIN_UNBOUND",
    "BIND_IMPORT_TO_MODULE",
]


def opaque(s: str, prefix: str = "o") -> str:
    return prefix + "_" + hashlib.sha256(s.encode()).hexdigest()[:16]


def round_robin_splits(rows: list[dict], n: int) -> list[dict]:
    by_split: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        by_split[row.get("split") or "unknown"].append(row)
    selected: list[dict] = []
    order = ["train", "eval", "strict_eval", "unknown"]
    while len(selected) < n and any(by_split.values()):
        progressed = False
        for split in order:
            if by_split.get(split):
                selected.append(by_split[split].pop(0))
                progressed = True
                if len(selected) == n:
                    break
        if not progressed:
            break
    return selected


def make_row(raw: dict, nodes_lin: dict, spans_lin: dict, retrieval: dict) -> dict:
    old_id = raw.get("row_id", "")
    graph = raw.get("graph_input") or {}
    query = raw.get("query") or {}
    target = raw.get("target") or {}
    old_src = raw.get("source_ref") or {}
    action = target.get("binding_action")
    clean = {
        "binding_action": action,
        "target_node_kind": target.get("target_node_kind"),
        "target_node_presence": "TARGET_NODE_PRESENT" if target.get("target_node_id") is not None else "NO_TARGET_NODE",
    }
    return {
        "row_id": "stage8676_" + opaque(old_id, "row"),
        "source_row_id": old_id,
        "split": raw.get("split"),
        "objective_family": "source_backed_symbol_binding",
        "source_stage": "stage8676_from_stage8618_shortcut_repair",
        "semantic_key": f"{raw.get('split')}:{action}:{graph.get('query_kind')}:{query.get('query_node_id')}",
        "authority": AUTHORITY_CLOSED,
        "loss_mask": LOSS_MASK,
        "gate_status": default_gate_status(
            source_inventory_lineage=True,
            source_provenance=True,
            golden_locked_eval_suite=True,
        ),
        "source_lineage": {
            "graph_nodes_source_id": nodes_lin["source_id"],
            "graph_nodes_lineage_hash": nodes_lin["lineage_hash"],
            "graph_spans_source_id": spans_lin["source_id"],
            "graph_spans_lineage_hash": spans_lin["lineage_hash"],
            "old_source_ref_path": old_src.get("path"),
            "old_source_ref_in_model_input": False,
            "locked_eval_source": False,
            "train_eligible_lineage": True,
        },
        "retrieval_control": {
            "retrieval_required": True,
            "retrieval_baseline_stage": "stage8671_dense_hybrid_retrieval_baseline",
            "bm25_top5_recall": retrieval["metrics"]["bm25_top5"],
            "dense_top5_recall": retrieval["metrics"]["dense_top5"],
            "hybrid_rrf_top5_recall": retrieval["metrics"]["hybrid_rrf_top5"],
            "metadata_only_disallowed": True,
            "evidence_removed_disallowed": True,
        },
        "graph_input": graph,
        "query": query,
        "clean_state": clean,
        "anti_cheat": {
            "raw_source_included": False,
            "raw_symbol_names_in_model_input": False,
            "target_label_in_id": False,
            "target_node_id_in_model_input": False,
            "requires_shortcut_audit_before_training": True,
            "requires_retrieval_card_before_training": True,
            "stage8675_shortcut_repair": "downcap_test_binding_until_query_kind_test_majority_at_or_below_0_80",
        },
        "route": "CANDIDATE_NEEDS_AUDIT",
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lineage = json.loads(LINEAGE.read_text())["records"]
    lin_by_path = {r["path"]: r for r in lineage}
    nodes_lin = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl"]
    spans_lin = lin_by_path["/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl"]
    retrieval = json.loads(RETRIEVAL.read_text())

    buckets: dict[str, list[dict]] = collections.defaultdict(list)
    retrieve_test: list[dict] = []
    retrieve_other: list[dict] = []
    for line in SRC.open():
        if not line.strip():
            continue
        row = json.loads(line)
        action = (row.get("target") or {}).get("binding_action")
        query_kind = (row.get("graph_input") or {}).get("query_kind")
        if action == "RETRIEVE_MORE":
            (retrieve_test if query_kind == "test" else retrieve_other).append(row)
        elif action in ACTIONS:
            buckets[action].append(row)

    # Stage8675 showed query_kind=test was the only blocking shortcut.
    # There are only four RETRIEVE_MORE/test counterexamples in the source pool,
    # so 16 BIND_TEST rows is the largest balanced action cap that keeps
    # BIND_TEST at exactly 16/(16+4)=0.80, which passes the strict >0.80 gate.
    cap = 16
    selected_raw: list[dict] = []
    selected_raw.extend(round_robin_splits(retrieve_test, len(retrieve_test)))
    selected_raw.extend(round_robin_splits(retrieve_other, cap - len(retrieve_test)))
    for action in ACTIONS:
        if action == "RETRIEVE_MORE":
            continue
        selected_raw.extend(round_robin_splits(buckets[action], cap))

    rows = [make_row(row, nodes_lin, spans_lin, retrieval) for row in selected_raw]
    counts = collections.Counter((r["clean_state"] or {}).get("binding_action") for r in rows)
    splits = collections.Counter(r.get("split") for r in rows)
    query_counts = collections.Counter((r.get("graph_input") or {}).get("query_kind") for r in rows)
    test_dist = collections.Counter(
        (r["clean_state"] or {}).get("binding_action")
        for r in rows
        if (r.get("graph_input") or {}).get("query_kind") == "test"
    )

    with OUT.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    passed = bool(rows) and all(counts.get(action) == cap for action in ACTIONS) and max(test_dist.values()) / sum(test_dist.values()) <= 0.80
    card = {
        "stage": 8676,
        "stage_name": "stage8676_source_backed_symbol_binding_shortcut_repair_manifest",
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "rows": len(rows),
            "actions": dict(counts),
            "cap_per_action": cap,
            "splits": dict(splits),
            "query_kind_counts": dict(query_counts),
            "query_kind_test_action_dist": dict(test_dist),
            "query_kind_test_majority": max(test_dist.values()) / sum(test_dist.values()) if test_dist else None,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "model_execution_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "artifacts": {
            "manifest": str(OUT.relative_to(ROOT)),
            "source_manifest": str(SRC.relative_to(ROOT)),
            "lineage_registry": str(LINEAGE.relative_to(ROOT)),
            "retrieval_baseline": str(RETRIEVAL.relative_to(ROOT)),
        },
        "decision": "Built a no-authority shortcut-repaired source-backed symbol-binding candidate manifest by down-capping test binding rows and preserving all four available test counterexamples.",
        "next_best_step": "Run Stage8677 audit. If it passes, attach Stage8676/8677 to the central graph; if it fails, mine more test-query counterexamples before any training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "shortcut_repair_manifest_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8676 Source-Backed Symbol Binding Shortcut Repair Manifest\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Rows: `{len(rows)}`\n"
        f"- Cap per action: `{cap}`\n"
        f"- Actions: `{dict(counts)}`\n"
        f"- Query-kind counts: `{dict(query_counts)}`\n"
        f"- Query-kind=test action dist: `{dict(test_dist)}`\n\n"
        "No training authority opened.\n"
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
