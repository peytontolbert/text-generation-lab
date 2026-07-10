#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10097
NAME = "stage10097_locked_source_graph_materialization_bridge_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "locked_source_graph_materialization_bridge_request.json"
ROWS = OUT_DIR / "locked_source_graph_materialization_bridge_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_SOURCE_GRAPH_MATERIALIZATION_BRIDGE_REQUEST_STAGE10097.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LOCKED_ROWS = ROOT / "runs/local/artifacts/stage10035_real_fresh_heldout_candidate_packet/real_fresh_heldout_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


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
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding='utf-8')


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = load_jsonl(LOCKED_ROWS)
    rows = [row for row in source_rows if ((row.get('source_lineage') if isinstance(row.get('source_lineage'), dict) else {}).get('locked_eval_source') is True)]
    bridge_rows = []
    for row in rows:
        graph_input = row.get('graph_input') if isinstance(row.get('graph_input'), dict) else {}
        query = row.get('query') if isinstance(row.get('query'), dict) else {}
        bridge_rows.append({
            'row_id': row.get('row_id'),
            'source_row_id': row.get('source_row_id'),
            'language_family': row.get('language_family'),
            'query_kind': query.get('query_kind'),
            'query_node_id': query.get('query_node_id'),
            'query_node_id_is_opaque': query.get('query_node_id_is_opaque'),
            'candidate_family_id': graph_input.get('candidate_family_id'),
            'opaque_graph_id': graph_input.get('opaque_graph_id'),
            'candidate_node_count': graph_input.get('candidate_node_count'),
            'edge_family_count': graph_input.get('edge_family_count'),
            'source_graph_materialized': graph_input.get('source_graph_materialized'),
            'graph_nodes_source_id': ((row.get('source_lineage') if isinstance(row.get('source_lineage'), dict) else {}).get('graph_nodes_source_id')),
            'graph_spans_source_id': ((row.get('source_lineage') if isinstance(row.get('source_lineage'), dict) else {}).get('graph_spans_source_id')),
            'required_materialized_outputs': ['candidate_paths','trace_excerpt','relevant_snippets','failure_text','test_assertion'],
        })
    metrics = {
        'rows': len(bridge_rows),
        'languages': dict(sorted(Counter(str(row.get('language_family') or '') for row in bridge_rows).items())),
        'query_kinds': dict(sorted(Counter(str(row.get('query_kind') or '') for row in bridge_rows).items())),
        'rows_with_opaque_query_ids': sum(1 for row in bridge_rows if row.get('query_node_id_is_opaque') is True),
        'rows_with_unmaterialized_graph': sum(1 for row in bridge_rows if row.get('source_graph_materialized') is False),
    }
    failures: list[str] = []
    if metrics['rows'] != 18:
        failures.append('rows_not_18')
    next_best_step = 'Implement a bridge that joins these opaque query and candidate handles against the external repo graph, emits concrete candidate paths and snippet spans, and then rebuilds the realistic maintainer packet from those outputs.'
    request = {
        'stage': STAGE,
        'name': NAME,
        'passed': not failures,
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'artifacts': {
            'source_rows': display(LOCKED_ROWS),
            'bridge_rows': display(ROWS),
        },
        'intent': 'Enumerate the exact opaque graph/query handles that a bridge must resolve before the locked-source subset can become a real maintainer-visible evidence packet.',
        'claim_boundary': {
            'materialized_packet_ready': False,
            'bridge_spec_ready': True,
        },
        'metrics': metrics,
        'failures': failures,
        'next_best_step': next_best_step,
    }
    return request, bridge_rows


def write_doc(request: dict[str, Any]) -> None:
    lines = [
        '# Stage10097 Locked Source Graph Materialization Bridge Request',
        '',
        f"Passed: `{request['passed']}`",
        f"Rows: `{request['metrics']['rows']}`",
        f"Languages: `{request['metrics']['languages']}`",
        '',
        'This stage does not materialize maintainer evidence yet. It enumerates the opaque query-node and candidate-family handles that must be resolved from the external repo graph before the locked-source subset can become a real failure/trace/snippet packet.',
        '',
        f"Next: {request['next_best_step']}",
        '',
    ]
    DOC.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    request, rows = build()
    write_json(REQUEST, request)
    write_jsonl(ROWS, rows)
    summary = {"stage": STAGE, "stage_name": NAME, "passed": request['passed'], "artifacts": request['artifacts'], "metrics": request['metrics'], "next_best_step": request['next_best_step']}
    write_json(SUMMARY, summary)
    write_doc(request)
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": request['passed'], "failures": request['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
