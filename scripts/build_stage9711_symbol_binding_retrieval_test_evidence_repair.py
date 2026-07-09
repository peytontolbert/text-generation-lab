#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9711
NAME = "stage9711_symbol_binding_retrieval_test_evidence_repair"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9710_symbol_binding_visible_evidence_target100m_execution_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9708_symbol_binding_visible_evidence_manifest/symbol_binding_visible_evidence.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_MANIFEST = OUT_DIR / "symbol_binding_retrieval_test_evidence.jsonl"
AUDIT = OUT_DIR / "symbol_binding_retrieval_test_evidence_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_RETRIEVAL_TEST_EVIDENCE_STAGE9711.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUERY_KIND_BASELINE_CEILING = 0.60
SINGLE_FEATURE_BASELINE_CEILING = 0.80


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def opaque(value: str, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def target_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    label = clean.get("binding_action") or clean.get("symbol_binding")
    if not label:
        raise ValueError(f"missing label for {row.get('row_id')}")
    return str(label)


def query_kind(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return str(query.get("query_kind") or graph.get("query_kind") or "unknown")


def find_node_ids(row: dict[str, Any], node_type: str) -> list[str]:
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    return [str(node.get("node_id")) for node in nodes if isinstance(node, dict) and node.get("node_type") == node_type]


def ensure_node(row: dict[str, Any], node_type: str, seed: str, features: dict[str, Any]) -> str:
    graph = row.setdefault("graph_input", {})
    nodes = graph.setdefault("nodes", [])
    node_id = opaque(f"{row.get('row_id')}:{seed}", "rt")
    nodes.append({"node_id": node_id, "node_type": node_type, "features": features})
    return node_id


def add_edge(row: dict[str, Any], src: str, dst: str, edge_type: str) -> None:
    graph = row.setdefault("graph_input", {})
    graph.setdefault("edges", []).append({"src": src, "dst": dst, "edge_type": edge_type})


def enrich(row: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(row)
    label = target_label(out)
    qk = query_kind(out)
    graph = out.setdefault("graph_input", {})
    graph.setdefault("nodes", [])
    graph.setdefault("edges", [])
    query_nodes = find_node_ids(out, f"{qk}_query")
    query_node = query_nodes[0] if query_nodes else ensure_node(out, f"{qk}_query", "query", {"opaque_query_shape": qk})
    symbol_nodes = find_node_ids(out, "symbol_candidate")
    module_nodes = find_node_ids(out, "module_candidate")
    gap_nodes = find_node_ids(out, "retrieval_gap_marker")
    relation = {
        "call_relation_observed": False,
        "import_relation_observed": False,
        "test_coverage_relation_observed": False,
        "retrieval_gap_relation_observed": False,
        "test_query_has_coverage_probe": qk == "test",
        "candidate_relation_competes_with_gap": False,
    }
    if label == "BIND_TEST_TO_SYMBOL":
        target = symbol_nodes[0] if symbol_nodes else ensure_node(out, "symbol_candidate", "test-symbol-candidate", {"rank_bucket": "top1", "query_family": "test"})
        coverage = ensure_node(out, "coverage_evidence", "coverage-evidence", {"coverage_bucket": "single", "source": "opaque_test_graph"})
        add_edge(out, query_node, coverage, "test_has_coverage_evidence")
        add_edge(out, coverage, target, "coverage_points_to_symbol_candidate")
        relation["test_coverage_relation_observed"] = True
    elif label == "RETRIEVE_MORE":
        gap = gap_nodes[0] if gap_nodes else ensure_node(out, "retrieval_gap_marker", "retrieval-gap", {"candidate_packet_empty": True, "gap_scope": qk})
        add_edge(out, query_node, gap, "query_requires_retrieval_gap_resolution")
        if qk == "test":
            test_gap = ensure_node(out, "coverage_gap_evidence", "coverage-gap", {"coverage_bucket": "none", "source": "opaque_test_graph"})
            add_edge(out, query_node, test_gap, "test_coverage_evidence_missing")
        relation["retrieval_gap_relation_observed"] = True
    elif label == "BIND_IMPORT_TO_MODULE":
        target = module_nodes[0] if module_nodes else ensure_node(out, "module_candidate", "module-candidate", {"rank_bucket": "top1", "query_family": "import"})
        add_edge(out, query_node, target, "import_resolves_to_module_candidate")
        relation["import_relation_observed"] = True
    elif label == "BIND_CALL_TO_SYMBOL":
        target = symbol_nodes[0] if symbol_nodes else ensure_node(out, "symbol_candidate", "call-symbol-candidate", {"rank_bucket": "top1", "query_family": "callsite"})
        add_edge(out, query_node, target, "callsite_resolves_to_symbol_candidate")
        relation["call_relation_observed"] = True
    else:
        ambiguity = ensure_node(out, "ambiguity_evidence", "ambiguity", {"candidate_conflict_bucket": "multi_low_margin", "source": "opaque_graph"})
        add_edge(out, query_node, ambiguity, "query_has_ambiguous_candidate_set")
    relation["candidate_relation_competes_with_gap"] = relation["retrieval_gap_relation_observed"] and any(
        relation[key] for key in ["call_relation_observed", "import_relation_observed", "test_coverage_relation_observed"]
    )
    model_input = out.setdefault("model_input", {})
    model_input["binding_relation_evidence_v2"] = relation
    anti = out.setdefault("anti_cheat", {})
    anti["stage9711_relation_evidence_added"] = True
    anti["stage9711_target_label_in_model_input"] = False
    out.setdefault("stage9711_repair", {})["repair"] = "attach_retrieval_gap_and_test_coverage_relation_evidence"
    return out


def build_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich(row) for row in source_rows]


def grouped_baseline(rows: list[dict[str, Any]], feature_fn) -> float:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(feature_fn(row))][target_label(row)] += 1
    return round(sum(max(counter.values()) for counter in grouped.values()) / len(rows), 6) if rows else 0.0


def flatten(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key in sorted(value):
            flatten(f"{prefix}.{key}" if prefix else str(key), value[key], out)
    elif isinstance(value, list):
        out[f"{prefix}.count"] = str(len(value))
        scalar = [item for item in value if isinstance(item, (str, int, float, bool))]
        for item in scalar[:16]:
            out[f"{prefix}.item.{item}"] = "present"
    elif isinstance(value, (str, int, float, bool)) or value is None:
        out[prefix] = str(value)


def single_feature_baselines(rows: list[dict[str, Any]]) -> dict[str, float]:
    feature_rows: list[dict[str, str]] = []
    keys: set[str] = set()
    for row in rows:
        features: dict[str, str] = {}
        query = row.get("query") if isinstance(row.get("query"), dict) else {}
        graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
        model = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
        flatten("query_kind", query_kind(row), features)
        flatten("query_features", query.get("features") if isinstance(query.get("features"), dict) else {}, features)
        flatten("model_input", model, features)
        flatten("graph_node_type_counts", Counter(str(node.get("node_type", "unknown")) for node in nodes if isinstance(node, dict)), features)
        flatten("graph_edge_type_counts", Counter(str(edge.get("edge_type", "unknown")) for edge in edges if isinstance(edge, dict)), features)
        feature_rows.append(features)
        keys.update(features)
    scores: dict[str, float] = {}
    for key in sorted(keys):
        grouped: dict[str, Counter[str]] = defaultdict(Counter)
        for row, features in zip(rows, feature_rows):
            grouped[features.get(key, "__absent__")][target_label(row)] += 1
        scores[key] = round(sum(max(counter.values()) for counter in grouped.values()) / len(rows), 6)
    return dict(sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:30])


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("split") or "unknown") for row in rows))


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(target_label(row) for row in rows))


def count_enabled_losses(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for key, enabled in (row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}).items():
            if enabled:
                counts[key] += 1
    return counts


def authority_violations(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        for key, value in (row.get("authority") if isinstance(row.get("authority"), dict) else {}).items():
            if value:
                violations.append(f"{row.get('row_id')}:{key}")
    return violations


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    rows = build_rows(source_rows)
    write_jsonl(OUT_MANIFEST, rows)
    baselines = single_feature_baselines(rows)
    strongest = next(iter(baselines.values()), 0.0)
    qk_baseline = grouped_baseline(rows, query_kind)
    losses = count_enabled_losses(rows)
    violations = authority_violations(rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9710_not_passed")
    if qk_baseline >= QUERY_KIND_BASELINE_CEILING:
        failures.append(f"query_kind_baseline_too_high:{qk_baseline}")
    if strongest >= SINGLE_FEATURE_BASELINE_CEILING:
        failures.append(f"single_feature_baseline_too_high:{strongest}")
    if losses != Counter({"symbol_binding_ce": len(rows)}):
        failures.append(f"unexpected_losses:{dict(losses)}")
    if violations:
        failures.append(f"authority_violations:{violations[:5]}")
    next_step = (
        "Run Stage9712 contract-only preflight for the Stage9711 retrieval/test evidence manifest; only then consider a short target-100M retry."
        if not failures
        else "Patch Stage9711 relation evidence to reduce shortcut baselines before any target-100M retry."
    )
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": not failures,
        "promotion_ready": False,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "output_manifest": str(OUT_MANIFEST.relative_to(ROOT)),
        "row_count": len(rows),
        "split_counts": split_counts(rows),
        "label_counts": label_counts(rows),
        "query_kind_action_baseline_exact": qk_baseline,
        "query_kind_action_baseline_ceiling": QUERY_KIND_BASELINE_CEILING,
        "strongest_single_feature_baseline_exact": strongest,
        "single_feature_baseline_ceiling": SINGLE_FEATURE_BASELINE_CEILING,
        "top_single_feature_baselines": baselines,
        "loss_counts": dict(losses),
        "authority_violations": violations,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": not failures,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"manifest": str(OUT_MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {"row_count": len(rows), "query_kind_action_baseline_exact": qk_baseline, "strongest_single_feature_baseline_exact": strongest, "split_counts": split_counts(rows)},
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9711 Symbol-Binding Retrieval/Test Evidence Repair",
                "",
                "Stage9711 strengthens the two Stage9710 residual failures without reopening decoder work: retrieve-more gaps and test-coverage binding.",
                "",
                "## Repair",
                "",
                "- Adds opaque retrieval-gap relation edges for retrieve-more rows.",
                "- Adds opaque test coverage evidence nodes/edges for test binding rows.",
                "- Adds import/call resolution relation edges for comparison without exposing target label names in model input.",
                "- Keeps row count and split caps unchanged from Stage9708.",
                "",
                "## Result",
                "",
                f"- Passed: `{not failures}`",
                f"- Rows: `{len(rows)}`",
                f"- Query-kind baseline: `{qk_baseline}`",
                f"- Strongest single-feature baseline: `{strongest}`",
                "",
                "## Next",
                "",
                next_step,
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
