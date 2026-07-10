#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10094
NAME = "stage10094_realistic_source_materialization_recoverability_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "realistic_source_materialization_recoverability_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REALISTIC_SOURCE_MATERIALIZATION_RECOVERABILITY_AUDIT_STAGE10094.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUEST_ROWS = ROOT / "runs/local/artifacts/stage10093_canonical_source_heldout_realistic_source_backed_successor_request/canonical_source_heldout_realistic_source_backed_successor_rows.jsonl"
LINEAGE = ROOT / "runs/local/artifacts/stage8663_source_inventory_lineage_registry/source_lineage_registry.jsonl"


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


def normalize_root(source_row_id: str) -> str:
    match = re.search(r"(stage8765_row_[0-9a-f]+)", source_row_id)
    return match.group(1) if match else source_row_id


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)), "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> dict[str, Any]:
    rows = load_jsonl(REQUEST_ROWS)
    lineage_rows = load_jsonl(LINEAGE)
    lineage_map = {str(row.get("source_id") or ""): row for row in lineage_rows}
    normalized_roots = [normalize_root(str(row.get("source_row_id") or "")) for row in rows]
    graph_nodes_ids = sorted({str(row.get("graph_nodes_source_id") or "") for row in rows if row.get("graph_nodes_source_id")})
    graph_spans_ids = sorted({str(row.get("graph_spans_source_id") or "") for row in rows if row.get("graph_spans_source_id")})
    graph_nodes_paths = {sid: (lineage_map.get(sid) or {}).get("path") for sid in graph_nodes_ids}
    graph_spans_paths = {sid: (lineage_map.get(sid) or {}).get("path") for sid in graph_spans_ids}
    metrics = {
        "request_rows": len(rows),
        "unique_request_source_row_ids": len({str(row.get("source_row_id") or "") for row in rows}),
        "unique_normalized_stage8765_roots": len(set(normalized_roots)),
        "locked_eval_source_rows": sum(1 for row in rows if row.get("locked_eval_source") is True),
        "locked_eval_source_languages": dict(sorted(Counter(str(row.get("language_family") or "") for row in rows if row.get("locked_eval_source") is True).items())),
        "non_locked_rows": sum(1 for row in rows if row.get("locked_eval_source") is not True),
        "compare_subset_split_counts": dict(sorted(Counter(str(row.get("compare_subset_split") or "") for row in rows).items())),
        "graph_nodes_source_ids": graph_nodes_ids,
        "graph_spans_source_ids": graph_spans_ids,
        "graph_nodes_source_paths": graph_nodes_paths,
        "graph_spans_source_paths": graph_spans_paths,
        "graph_sources_resolve_to_external_arxiv": all(str(path).startswith('/arxiv/') for path in list(graph_nodes_paths.values()) + list(graph_spans_paths.values()) if path),
    }
    failures: list[str] = []
    if metrics["request_rows"] != 55:
        failures.append("request_rows_not_55")
    if metrics["locked_eval_source_rows"] != 18:
        failures.append("locked_eval_source_rows_not_18")
    if metrics["unique_normalized_stage8765_roots"] >= metrics["request_rows"]:
        failures.append("expected_replay_wrapper_collapse_missing")
    findings = [
        "Only a minority of the 55 realistic successor request rows are already marked locked_eval_source, so the current comparison bank is not yet a uniformly source-heldout maintainer packet.",
        "The shared graph node and span lineage IDs resolve to external /arxiv/TOLBERT_BRAIN repo-graph files rather than a local materialized cache in this workspace.",
        "The request rows collapse from 55 wrapper row IDs to 32 underlying stage8765 roots, which means real source-backed evidence construction must either recover those primitive roots or deliberately rebuild a fresh locked-source successor.",
    ]
    next_best_step = "Build a source-materialization gate that either resolves the external repo-graph files into local evidence for the 32 underlying roots, or narrows the next maintainer-grade successor to the 18 already-locked heldout rows."
    return {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "artifacts": {
            "request_rows": display(REQUEST_ROWS),
            "lineage_registry": display(LINEAGE),
        },
        "claim_boundary": {
            "full_55_row_source_backed_materialization_ready_now": False,
            "reason": "Only 18 rows are already locked_eval_source and the shared repo-graph payloads resolve to external /arxiv files rather than local materialized evidence.",
            "locked_subset_materialization_candidate": True,
        },
        "metrics": metrics,
        "findings": findings,
        "failures": failures,
        "next_best_step": next_best_step,
    }


def write_doc(packet: dict[str, Any]) -> None:
    metrics = packet['metrics']
    lines = [
        '# Stage10094 Realistic Source Materialization Recoverability Audit',
        '',
        f"Passed: `{packet['passed']}`",
        f"Request rows: `{metrics['request_rows']}`",
        f"Locked eval source rows: `{metrics['locked_eval_source_rows']}`",
        f"Unique normalized stage8765 roots: `{metrics['unique_normalized_stage8765_roots']}`",
        '',
        'The requested realistic successor cannot honestly be called fully source-backed yet. Only 18 of the 55 compare-subset rows are already locked eval sources, and the shared repo-graph node/span lineage points to external `/arxiv/TOLBERT_BRAIN` files rather than a local materialized cache in this workspace.',
        '',
        'Next: either materialize those repo-graph sources locally for the underlying 32 stage8765 roots, or narrow the next maintainer-grade successor to the 18 already locked-source rows until more real heldout roots are available.',
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
