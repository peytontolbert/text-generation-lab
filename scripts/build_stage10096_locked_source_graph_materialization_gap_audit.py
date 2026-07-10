#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10096
NAME = "stage10096_locked_source_graph_materialization_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "locked_source_graph_materialization_gap_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_SOURCE_GRAPH_MATERIALIZATION_GAP_AUDIT_STAGE10096.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOCKED_ROWS = ROOT / "runs/local/artifacts/stage10095_locked_source_realistic_successor_request/locked_source_realistic_successor_rows.jsonl"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10035_real_fresh_heldout_candidate_packet/real_fresh_heldout_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)), "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    locked_rows = load_jsonl(LOCKED_ROWS)
    source_rows = load_jsonl(SOURCE_ROWS)
    source_by_row = {str(row.get("row_id") or ""): row for row in source_rows}
    matched = []
    for row in locked_rows:
        source_row = source_by_row.get(str(row.get("row_id") or ""))
        if source_row:
            matched.append(source_row)
    metrics = {
        "locked_rows": len(locked_rows),
        "matched_source_rows": len(matched),
        "rows_with_source_graph_materialized_false": sum(1 for row in matched if ((row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}).get("source_graph_materialized") is False)),
        "query_kinds": dict(sorted(Counter(str((row.get("query") if isinstance(row.get("query"), dict) else {}).get("query_kind") or "") for row in matched).items())),
        "candidate_family_ids": sorted({str(((row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}).get("candidate_family_id") or "")) for row in matched}),
        "opaque_graph_ids": sorted({str(((row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}).get("opaque_graph_id") or "")) for row in matched}),
        "query_node_ids": sorted({str(((row.get("query") if isinstance(row.get("query"), dict) else {}).get("query_node_id") or "")) for row in matched}),
        "all_query_node_ids_opaque": all(bool((row.get("query") if isinstance(row.get("query"), dict) else {}).get("query_node_id_is_opaque")) for row in matched),
    }
    failures: list[str] = []
    if metrics["locked_rows"] != 18:
        failures.append("locked_rows_not_18")
    if metrics["matched_source_rows"] != 18:
        failures.append("matched_source_rows_not_18")
    if metrics["rows_with_source_graph_materialized_false"] != 18:
        failures.append("source_graph_materialized_false_not_18")
    findings = [
        "Every locked-source bootstrap row still carries source_graph_materialized=false in the source-backed candidate packet.",
        "The query node identifiers and graph identifiers remain opaque row-local handles rather than maintainer-visible or externally joinable IDs.",
        "That means the next missing component is a graph-materialization bridge from the external repo-graph stores to row-level visible evidence, not another evaluation wrapper or comparison run.",
    ]
    next_best_step = "Build a graph-materialization bridge that resolves the locked-source rows from opaque graph/query handles into file paths, trace chains, and snippet spans before attempting a maintainer-grade comparison run."
    return {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "artifacts": {
            "locked_rows": display(LOCKED_ROWS),
            "source_rows": display(SOURCE_ROWS),
        },
        "claim_boundary": {
            "locked_subset_ready_for_real_materialization": False,
            "reason": "The locked subset rows are source-heldout, but their graph evidence is still only present as opaque unmaterialized handles.",
            "graph_materialization_bridge_required": True,
        },
        "metrics": metrics,
        "findings": findings,
        "failures": failures,
        "next_best_step": next_best_step,
    }


def write_doc(packet: dict[str, Any]) -> None:
    metrics = packet['metrics']
    lines = [
        '# Stage10096 Locked Source Graph Materialization Gap Audit',
        '',
        f"Passed: `{packet['passed']}`",
        f"Locked rows: `{metrics['locked_rows']}`",
        f"Matched source rows: `{metrics['matched_source_rows']}`",
        f"Rows with `source_graph_materialized=false`: `{metrics['rows_with_source_graph_materialized_false']}`",
        '',
        'The locked-source subset is honest about heldout provenance, but it is still not enough to build a maintainer-grade packet directly. Every matched row still marks `source_graph_materialized=false`, and the graph/query handles remain opaque.',
        '',
        'Next: build a graph-materialization bridge that resolves those opaque handles into file paths, trace chains, and snippet spans.',
        '',
    ]
    DOC.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    packet = build()
    write_json(PACKET, packet)
    summary = {"stage": STAGE, "stage_name": NAME, "passed": packet['passed'], "artifacts": packet['artifacts'], "metrics": packet['metrics'], "next_best_step": packet['next_best_step']}
    write_json(SUMMARY, summary)
    write_doc(packet)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": packet['passed'], "failures": packet['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
