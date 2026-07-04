#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8677_source_backed_symbol_binding_shortcut_repair_audit"
SUMMARY = ROOT / "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_audit.json"
DOC = ROOT / "docs/SOURCE_BACKED_SYMBOL_BINDING_SHORTCUT_REPAIR_AUDIT_STAGE8677.md"

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


def leaves(o: Any):
    if isinstance(o, dict):
        for v in o.values():
            yield from leaves(v)
    elif isinstance(o, list):
        for v in o:
            yield from leaves(v)
    else:
        yield o


def stable(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lin = json.loads(LINEAGE.read_text())["records"]
    lin_by_id = {r["source_id"]: r for r in lin}
    locked = {r["source_id"] for r in lin if r.get("locked_eval")}

    failures: list[str] = []
    rows: list[dict] = []
    actions: collections.Counter[str] = collections.Counter()
    splits: collections.Counter[str] = collections.Counter()
    feature_values: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    visible_target_hits: list[dict] = []
    forbidden: list[dict] = []
    missing: list[dict] = []

    for line in MANIFEST.open():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
        clean = row.get("clean_state") or {}
        action = clean.get("binding_action")
        actions[action] += 1
        splits[row.get("split")] += 1

        source_lineage = row.get("source_lineage") or {}
        retrieval_control = row.get("retrieval_control") or {}
        for key in [
            "graph_nodes_source_id",
            "graph_nodes_lineage_hash",
            "graph_spans_source_id",
            "graph_spans_lineage_hash",
        ]:
            if not source_lineage.get(key):
                missing.append({"row_id": row.get("row_id"), "missing": key})
        if source_lineage.get("graph_nodes_source_id") in locked or source_lineage.get("graph_spans_source_id") in locked:
            missing.append({"row_id": row.get("row_id"), "missing": "locked_lineage_used"})
        if source_lineage.get("graph_nodes_source_id") not in lin_by_id or source_lineage.get("graph_spans_source_id") not in lin_by_id:
            missing.append({"row_id": row.get("row_id"), "missing": "unknown_lineage_source_id"})
        for key in ["bm25_top5_recall", "dense_top5_recall", "hybrid_rrf_top5_recall"]:
            if key not in retrieval_control:
                missing.append({"row_id": row.get("row_id"), "missing": "retrieval_control." + key})
        if retrieval_control.get("bm25_top5_recall", 0) < 0.90:
            missing.append({"row_id": row.get("row_id"), "missing": "bm25_recall_floor"})

        visible = {k: row[k] for k in ["graph_input", "query", "source_lineage", "retrieval_control"] if k in row}
        visible_text = stable(visible)
        for value in leaves(clean):
            if isinstance(value, str) and len(value) >= 4 and value in visible_text:
                visible_target_hits.append({"row_id": row.get("row_id"), "target_string": value[:120]})
                break

        for key, value in (row.get("authority") or {}).items():
            if value is True:
                forbidden.append({"row_id": row.get("row_id"), "field": "authority." + key})
        loss = row.get("loss_mask") or {}
        for key in ["decoder_ce", "denoise_ce", "runtime_reward", "symbol_binding_ce", "source_backed_symbol_binding_candidate_ce"]:
            if loss.get(key) is True:
                forbidden.append({"row_id": row.get("row_id"), "field": "loss_mask." + key})

        graph = row.get("graph_input") or {}
        query = row.get("query") or {}
        feature_values["query_kind"][str(graph.get("query_kind"))] += 1
        feature_values["source_file_is_test"][str((query.get("features") or {}).get("source_file_is_test"))] += 1
        for node in graph.get("nodes", []):
            if node.get("node_type") == "file":
                node_features = node.get("features") or {}
                for feature in ["import_count_bucket", "definition_count_bucket", "call_count_bucket", "path_depth_bucket", "is_test"]:
                    feature_values[feature][str(node_features.get(feature))] += 1

    if not rows:
        failures.append("no_rows")
    if missing:
        failures.append(f"missing_required_controls:{len(missing)}")
    if visible_target_hits:
        failures.append(f"visible_target_hits:{len(visible_target_hits)}")
    if forbidden:
        failures.append(f"forbidden_authority_or_loss:{len(forbidden)}")
    if len(set(actions.values())) != 1:
        failures.append("actions_not_balanced")

    shortcut: list[dict] = []
    for feature in feature_values:
        table: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for row in rows:
            action = (row.get("clean_state") or {}).get("binding_action")
            graph = row.get("graph_input") or {}
            query = row.get("query") or {}
            value = None
            if feature == "query_kind":
                value = graph.get("query_kind")
            elif feature == "source_file_is_test":
                value = str((query.get("features") or {}).get("source_file_is_test"))
            else:
                for node in graph.get("nodes", []):
                    if node.get("node_type") == "file":
                        value = str((node.get("features") or {}).get(feature))
                        break
            table[str(value)][action] += 1
        for value, counts in table.items():
            total = sum(counts.values())
            if total >= 10:
                majority = max(counts.values()) / total
                if majority > 0.80:
                    shortcut.append({"feature": feature, "value": value, "majority": majority, "total": total, "dist": dict(counts)})
    if shortcut:
        failures.append(f"shortcut_feature_cells:{len(shortcut)}")

    card = {
        "stage": 8677,
        "stage_name": "stage8677_source_backed_symbol_binding_shortcut_repair_audit",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "rows": len(rows),
            "actions": dict(actions),
            "splits": dict(splits),
            "missing_required_controls": len(missing),
            "visible_target_hits": len(visible_target_hits),
            "forbidden_authority_or_loss": len(forbidden),
            "shortcut_feature_cells": len(shortcut),
            "failures": failures,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "model_execution_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "samples": {
            "missing": missing[:20],
            "visible_target_hits": visible_target_hits[:20],
            "forbidden": forbidden[:20],
            "shortcut": shortcut[:20],
        },
        "decision": "Shortcut-repaired source-backed symbol-binding candidate manifest passes control audit but remains no-authority candidate-only."
        if not failures
        else "Shortcut-repaired source-backed symbol-binding candidate manifest failed control audit; keep blocked.",
        "next_best_step": "If passed, attach Stage8676/8677 to graph and use the manifest as the base for graph/symbol retrieval counterfactual expansion; if failed, mine more counterexamples for listed shortcut cells.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "shortcut_repair_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8677 Source-Backed Symbol Binding Shortcut Repair Audit\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Rows: `{len(rows)}`\n"
        f"- Actions: `{dict(actions)}`\n"
        f"- Missing controls: `{len(missing)}`\n"
        f"- Visible target hits: `{len(visible_target_hits)}`\n"
        f"- Forbidden authority/loss: `{len(forbidden)}`\n"
        f"- Shortcut feature cells: `{len(shortcut)}`\n"
        f"- Failures: `{failures}`\n\n"
        "No training authority opened.\n"
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if card["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
