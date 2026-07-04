#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/local/artifacts/stage8676_source_backed_symbol_binding_shortcut_repair_manifest/source_backed_symbol_binding_shortcut_repair_manifest.jsonl"
LINEAGE = ROOT / "configs/software_maintainer/source_inventory_lineage_registry_stage8663.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit"
SUMMARY = ROOT / "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit.json"
DOC = ROOT / "docs/SOURCE_BACKED_SYMBOL_BINDING_SHORTCUT_REPAIR_MANIFEST_AUDIT_STAGE8677.md"

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


def leaves(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from leaves(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from leaves(value)
    else:
        yield obj


def stable(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lineage = json.loads(LINEAGE.read_text())["records"]
    lineage_by_id = {row["source_id"]: row for row in lineage}
    locked = {row["source_id"] for row in lineage if row.get("locked_eval")}

    rows = []
    actions = collections.Counter()
    splits = collections.Counter()
    missing = []
    visible_target_hits = []
    forbidden = []
    feature_tables: dict[str, dict[str, collections.Counter]] = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))

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
        for key in ["graph_nodes_source_id", "graph_nodes_lineage_hash", "graph_spans_source_id", "graph_spans_lineage_hash"]:
            if not source_lineage.get(key):
                missing.append({"row_id": row.get("row_id"), "missing": key})
        if source_lineage.get("graph_nodes_source_id") in locked or source_lineage.get("graph_spans_source_id") in locked:
            missing.append({"row_id": row.get("row_id"), "missing": "locked_lineage_used"})
        if source_lineage.get("graph_nodes_source_id") not in lineage_by_id or source_lineage.get("graph_spans_source_id") not in lineage_by_id:
            missing.append({"row_id": row.get("row_id"), "missing": "unknown_lineage_source_id"})
        for key in ["bm25_top5_recall", "dense_top5_recall", "hybrid_rrf_top5_recall"]:
            if key not in retrieval_control:
                missing.append({"row_id": row.get("row_id"), "missing": "retrieval_control." + key})
        if retrieval_control.get("bm25_top5_recall", 0.0) < 0.90:
            missing.append({"row_id": row.get("row_id"), "missing": "bm25_recall_floor"})

        visible = {key: row[key] for key in ["graph_input", "query", "source_lineage", "retrieval_control"] if key in row}
        visible_blob = stable(visible)
        for value in leaves(clean):
            if isinstance(value, str) and len(value) >= 4 and value in visible_blob:
                visible_target_hits.append({"row_id": row.get("row_id"), "target_string": value[:120]})
                break

        for key, value in (row.get("authority") or {}).items():
            if value is True:
                forbidden.append({"row_id": row.get("row_id"), "field": "authority." + key})
        for key, value in (row.get("loss_mask") or {}).items():
            if value is True:
                forbidden.append({"row_id": row.get("row_id"), "field": "loss_mask." + key})

        graph = row.get("graph_input") or {}
        query = row.get("query") or {}
        feature_tables["query_kind"][str(graph.get("query_kind"))][action] += 1
        feature_tables["source_file_is_test"][str((query.get("features") or {}).get("source_file_is_test"))][action] += 1
        for node in graph.get("nodes", []):
            if node.get("node_type") != "file":
                continue
            features = node.get("features") or {}
            for feature in ["import_count_bucket", "definition_count_bucket", "call_count_bucket", "path_depth_bucket", "is_test"]:
                feature_tables[feature][str(features.get(feature))][action] += 1
            break

    shortcut = []
    for feature, table in feature_tables.items():
        for value, dist in table.items():
            total = sum(dist.values())
            if total >= 10:
                majority = max(dist.values()) / total
                if majority > 0.80:
                    shortcut.append({
                        "feature": feature,
                        "value": value,
                        "majority": majority,
                        "total": total,
                        "dist": dict(dist),
                    })

    failures = []
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
    if shortcut:
        failures.append(f"shortcut_feature_cells:{len(shortcut)}")

    card = {
        "stage": 8677,
        "stage_name": "stage8677_source_backed_symbol_binding_shortcut_repair_manifest_audit",
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
        "decision": "Shortcut-repaired source-backed symbol-binding manifest passes control audit but remains no-authority candidate-only." if not failures else "Shortcut-repaired source-backed symbol-binding manifest failed control audit; keep blocked.",
        "next_best_step": "Attach Stage8676/8677 to the central graph and then run unified junk/OOD plus cluster/slice audits before any training." if not failures else "Repair listed failures before graph attachment or training.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    (OUT_DIR / "shortcut_repair_manifest_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8677 Source-Backed Symbol Binding Shortcut Repair Manifest Audit\n\n"
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
