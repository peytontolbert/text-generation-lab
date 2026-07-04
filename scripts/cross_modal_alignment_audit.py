from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

REQUIRED_MODALITIES = {
    "source_text",
    "cst_ast",
    "symbol_table",
    "import_export_graph",
    "type_signature_map",
    "call_graph",
    "data_flow_graph",
    "control_flow_graph",
}


def _ids(value: Any, keys: tuple[str, ...]) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key in keys:
            v = value.get(key)
            if isinstance(v, str) and v:
                out.add(v)
        for v in value.values():
            out.update(_ids(v, keys))
    elif isinstance(value, list):
        for item in value:
            out.update(_ids(item, keys))
    return out


def _paths(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key in ("path", "file", "file_path", "old_path", "new_path"):
            v = value.get(key)
            if isinstance(v, str) and v:
                out.add(v)
        for v in value.values():
            out.update(_paths(v))
    elif isinstance(value, list):
        for item in value:
            out.update(_paths(item))
    return out


def _source_hashes(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        v = value.get("source_hash")
        if isinstance(v, str) and v:
            out.add(v)
        for child in value.values():
            out.update(_source_hashes(child))
    elif isinstance(value, list):
        for item in value:
            out.update(_source_hashes(item))
    return out


def _edge_endpoints(value: Any) -> tuple[set[str], set[str]]:
    refs: set[str] = set()
    nodes: set[str] = set()
    if isinstance(value, dict):
        for key, val in value.items():
            if key.endswith("_id") and isinstance(val, str):
                nodes.add(val)
        for edge_key in ("edges",):
            edge_list = value.get(edge_key)
            if isinstance(edge_list, list):
                for edge in edge_list:
                    if isinstance(edge, dict):
                        for key in ("src", "dst", "source", "target"):
                            if isinstance(edge.get(key), str):
                                refs.add(edge[key])
        for child in value.values():
            child_refs, child_nodes = _edge_endpoints(child)
            refs.update(child_refs)
            nodes.update(child_nodes)
    elif isinstance(value, list):
        for item in value:
            child_refs, child_nodes = _edge_endpoints(item)
            refs.update(child_refs)
            nodes.update(child_nodes)
    return refs, nodes


def audit_alignment_row(row: dict[str, Any], *, required_modalities: set[str] | None = None) -> dict[str, Any]:
    required_modalities = required_modalities or REQUIRED_MODALITIES
    row_id = str(row.get("row_id") or row.get("id") or "")
    modalities = row.get("modalities") if isinstance(row.get("modalities"), dict) else {}
    present = {key for key, value in modalities.items() if value not in (None, {}, [])}
    missing = sorted(required_modalities - present)
    hashes_by_modality = {name: sorted(_source_hashes(packet)) for name, packet in modalities.items()}
    nonempty_hashes = {tuple(v) for v in hashes_by_modality.values() if v}
    source_hash_mismatch = len(nonempty_hashes) > 1
    paths_by_modality = {name: sorted(_paths(packet)) for name, packet in modalities.items()}
    nonempty_path_sets = [set(v) for v in paths_by_modality.values() if v]
    path_anchor_missing = bool(nonempty_path_sets) and not set.intersection(*nonempty_path_sets)
    refs: set[str] = set()
    nodes: set[str] = set()
    for packet in modalities.values():
        packet_refs, packet_nodes = _edge_endpoints(packet)
        refs.update(packet_refs)
        nodes.update(packet_nodes)
    unresolved_refs = sorted(ref for ref in refs if ref not in nodes and not ref.startswith(("dep_", "call_", "scope_")))[:50]
    failures = []
    if missing:
        failures.append("missing_modalities")
    if source_hash_mismatch:
        failures.append("source_hash_mismatch")
    if path_anchor_missing:
        failures.append("path_anchor_missing")
    if unresolved_refs:
        failures.append("unresolved_edge_refs")
    return {
        "row_id": row_id,
        "passed": not failures,
        "failures": failures,
        "present_modalities": sorted(present),
        "missing_modalities": missing,
        "hashes_by_modality": hashes_by_modality,
        "paths_by_modality": paths_by_modality,
        "unresolved_edge_refs": unresolved_refs,
    }


def audit_alignment_rows(rows: list[dict[str, Any]], *, required_modalities: set[str] | None = None) -> dict[str, Any]:
    row_cards = [audit_alignment_row(row, required_modalities=required_modalities) for row in rows]
    failure_counts: dict[str, int] = collections.Counter(failure for card in row_cards for failure in card["failures"])
    return {
        "passed": all(card["passed"] for card in row_cards),
        "rows": len(rows),
        "passing_rows": sum(1 for card in row_cards if card["passed"]),
        "failing_rows": sum(1 for card in row_cards if not card["passed"]),
        "failure_counts": dict(sorted(failure_counts.items())),
        "row_cards": row_cards,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit cross-modal alignment across program-state modality packets.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = audit_alignment_rows(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
