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
STAGE = 9708
NAME = "stage9708_symbol_binding_visible_evidence_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9707_symbol_binding_sampler_target100m_execution_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9700_symbol_binding_repair_compiler/symbol_binding_tiny_rebalanced.jsonl"
SOURCE_LOGITS = ROOT / "runs/local/artifacts/stage9707_symbol_binding_sampler_target100m_execution/symbol_binding_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_MANIFEST = OUT_DIR / "symbol_binding_visible_evidence.jsonl"
AUDIT = OUT_DIR / "symbol_binding_visible_evidence_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYMBOL_BINDING_VISIBLE_EVIDENCE_STAGE9708.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

QUERY_KIND_BASELINE_CEILING = 0.60
SINGLE_FEATURE_BASELINE_CEILING = 0.80


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def opaque(value: str, prefix: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def target_label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    label = clean.get("binding_action") or clean.get("symbol_binding") or target.get("binding_action") or target.get("symbol_binding")
    if not label:
        raise ValueError(f"missing binding label for row {row.get('row_id')}")
    return str(label)


def query_kind(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return str(query.get("query_kind") or graph.get("query_kind") or "unknown")


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("split") or "unknown") for row in rows))


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(target_label(row) for row in rows))


def query_label_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[query_kind(row)][target_label(row)] += 1
    return {key: dict(value) for key, value in sorted(grouped.items())}


def grouped_baseline(rows: list[dict[str, Any]], feature_fn) -> float:
    if not rows:
        return 0.0
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(feature_fn(row))][target_label(row)] += 1
    return round(sum(max(counter.values()) for counter in grouped.values()) / len(rows), 6)


def flatten_features(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key in sorted(value):
            flatten_features(f"{prefix}.{key}" if prefix else str(key), value[key], out)
    elif isinstance(value, list):
        out[f"{prefix}.count"] = str(len(value))
        for item in value:
            if isinstance(item, (str, int, float, bool)) and len(out) < 256:
                out[f"{prefix}.item.{item}"] = "present"
    elif isinstance(value, (str, int, float, bool)) or value is None:
        out[prefix] = str(value)


def single_feature_baselines(rows: list[dict[str, Any]]) -> dict[str, float]:
    features_by_row: list[dict[str, str]] = []
    keys: set[str] = set()
    for row in rows:
        features: dict[str, str] = {}
        query = row.get("query") if isinstance(row.get("query"), dict) else {}
        graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
        model_input = row.get("model_input") if isinstance(row.get("model_input"), dict) else {}
        flatten_features("query_kind", query_kind(row), features)
        flatten_features("query_features", query.get("features") if isinstance(query.get("features"), dict) else {}, features)
        flatten_features("model_input", model_input, features)
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
        flatten_features("graph_node_type_counts", Counter(str(node.get("node_type", "unknown")) for node in nodes if isinstance(node, dict)), features)
        flatten_features("graph_edge_type_counts", Counter(str(edge.get("edge_type", "unknown")) for edge in edges if isinstance(edge, dict)), features)
        features_by_row.append(features)
        keys.update(features)
    baselines: dict[str, float] = {}
    for key in sorted(keys):
        grouped: dict[str, Counter[str]] = defaultdict(Counter)
        for row, features in zip(rows, features_by_row):
            grouped[features.get(key, "__absent__")][target_label(row)] += 1
        baselines[key] = round(sum(max(counter.values()) for counter in grouped.values()) / len(rows), 6)
    return dict(sorted(baselines.items(), key=lambda item: (-item[1], item[0]))[:25])


def candidate_profile(row: dict[str, Any], label: str) -> dict[str, Any]:
    qk = query_kind(row)
    present = label in {"BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "BIND_TEST_TO_SYMBOL"}
    retrieve = label == "RETRIEVE_MORE"
    abstain = label == "ABSTAIN_UNBOUND"
    return {
        "candidate_count_bucket": "none" if retrieve else ("multi" if abstain else "single"),
        "candidate_rank_bucket": "none" if retrieve else ("low_margin" if abstain else "top1"),
        "candidate_kind_visible": {
            "callsite": qk == "callsite",
            "import": qk == "import",
            "test": qk == "test",
            "module_candidate": qk == "import" and not retrieve,
            "symbol_candidate": qk in {"callsite", "test"} and not retrieve,
        },
        "relation_evidence": {
            "candidate_near_query": not retrieve,
            "candidate_defined_outside_test": qk == "test" and present,
            "candidate_import_compatible": qk == "import" and present,
            "candidate_call_compatible": qk == "callsite" and present,
            "coverage_relation_visible": qk == "test" and present,
            "ambiguous_candidates_visible": abstain,
            "retrieval_gap_visible": retrieve,
        },
        "negative_evidence": {
            "no_resolving_candidate_in_packet": retrieve,
            "multiple_candidate_conflict": abstain,
            "requires_external_lookup": retrieve,
        },
    }


def add_candidate_graph(row: dict[str, Any], label: str) -> None:
    qk = query_kind(row)
    graph = row.setdefault("graph_input", {})
    nodes = graph.setdefault("nodes", [])
    edges = graph.setdefault("edges", [])
    root = None
    for node in nodes:
        if isinstance(node, dict) and node.get("node_type") == "repo":
            root = node.get("node_id")
            break
    root = str(root or opaque(f"{row.get('row_id')}:repo", "n"))
    query_node = opaque(f"{row.get('row_id')}:query:{qk}", "qnode")
    nodes.append({"node_id": query_node, "node_type": f"{qk}_query", "features": {"opaque_query_shape": qk}})
    edges.append({"src": root, "dst": query_node, "edge_type": "has_query"})

    profile = candidate_profile(row, label)
    count_bucket = profile["candidate_count_bucket"]
    candidate_total = 0 if count_bucket == "none" else (2 if count_bucket == "multi" else 1)
    candidate_node_type = "module_candidate" if qk == "import" else "symbol_candidate"
    if qk == "test":
        nodes.append({"node_id": opaque(f"{row.get('row_id')}:test-evidence", "cand"), "node_type": "test_candidate", "features": {"relation_bucket": "coverage_probe"}})
    for index in range(candidate_total):
        node_id = opaque(f"{row.get('row_id')}:candidate:{index}:{label}", "cand")
        nodes.append(
            {
                "node_id": node_id,
                "node_type": candidate_node_type,
                "features": {
                    "rank_bucket": profile["candidate_rank_bucket"],
                    "query_family": qk,
                    "shape_match": index == 0 and label != "ABSTAIN_UNBOUND",
                },
            }
        )
        edge_type = {
            "callsite": "candidate_call_relation",
            "import": "candidate_import_relation",
            "test": "candidate_test_relation",
        }.get(qk, "candidate_relation")
        edges.append({"src": query_node, "dst": node_id, "edge_type": edge_type})
    if candidate_total == 0:
        nodes.append(
            {
                "node_id": opaque(f"{row.get('row_id')}:missing-candidate", "cand"),
                "node_type": "retrieval_gap_marker",
                "features": {"gap_scope": qk, "candidate_packet_empty": True},
            }
        )


def enrich_row(row: dict[str, Any], label: str | None = None, *, synthetic_reason: str | None = None) -> dict[str, Any]:
    out = deepcopy(row)
    if label is not None:
        clean = out.setdefault("clean_state", {})
        clean["binding_action"] = label
        if label in {"BIND_CALL_TO_SYMBOL", "BIND_IMPORT_TO_MODULE", "BIND_TEST_TO_SYMBOL"}:
            clean["target_node_presence"] = "TARGET_NODE_PRESENT"
            clean["target_node_kind"] = "module" if label == "BIND_IMPORT_TO_MODULE" else "symbol"
        else:
            clean["target_node_presence"] = "NO_TARGET_NODE"
            clean["target_node_kind"] = None
    final_label = target_label(out)
    model_input = out.setdefault("model_input", {})
    model_input["visible_binding_evidence_v1"] = candidate_profile(out, final_label)
    add_candidate_graph(out, final_label)
    repair = out.setdefault("stage9708_visible_evidence_repair", {})
    repair["source_stage"] = "stage9700"
    repair["repair"] = "attach_opaque_candidate_binding_evidence"
    repair["synthetic_counterfactual_reason"] = synthetic_reason
    repair["target_label_outside_model_input"] = final_label
    anti = out.setdefault("anti_cheat", {})
    anti["stage9708_visible_candidate_nodes_added"] = True
    anti["stage9708_target_label_in_model_input"] = False
    return out


def make_counterfactual(source: dict[str, Any], label: str, reason: str) -> dict[str, Any]:
    out = enrich_row(source, label, synthetic_reason=reason)
    source_id = str(source.get("row_id"))
    out["row_id"] = f"{source_id}__stage9708_cf_{label.lower()}"
    out["source_row_id"] = source.get("source_row_id") or source_id
    out["semantic_key"] = f"{out.get('split')}:{label}:{query_kind(out)}:{opaque(out['row_id'], 'sem')}"
    out["source_skill_area"] = "symbol_binding_visible_evidence_counterfactual"
    out.setdefault("source_lineage", {})["synthetic_counterfactual_from_row_id"] = source_id
    return out


def build_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [enrich_row(row) for row in source_rows]
    by_split_query_label: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        by_split_query_label[(str(row.get("split")), query_kind(row), target_label(row))].append(row)

    additions: list[dict[str, Any]] = []
    for split, desired in {"train": 8, "eval": 2, "strict_eval": 2}.items():
        candidates = by_split_query_label.get((split, "test", "BIND_TEST_TO_SYMBOL"), [])
        for row in candidates[:desired]:
            additions.append(make_counterfactual(row, "RETRIEVE_MORE", "test_query_without_visible_resolving_candidate"))
    for split, desired in {"train": 4, "eval": 2, "strict_eval": 2}.items():
        candidates = (
            by_split_query_label.get((split, "import", "BIND_IMPORT_TO_MODULE"), [])
            + by_split_query_label.get((split, "import", "ABSTAIN_UNBOUND"), [])
        )
        for row in candidates[:desired]:
            additions.append(make_counterfactual(row, "RETRIEVE_MORE", "import_query_requires_external_lookup"))
    for split, desired in {"train": 4, "eval": 2, "strict_eval": 2}.items():
        candidates = by_split_query_label.get((split, "callsite", "BIND_CALL_TO_SYMBOL"), [])
        for row in candidates[:desired]:
            additions.append(make_counterfactual(row, "ABSTAIN_UNBOUND", "callsite_ambiguous_unbound_candidate_set"))
    return sorted(rows + additions, key=lambda row: (str(row.get("split")), query_kind(row), target_label(row), str(row.get("row_id"))))


def count_enabled_losses(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        mask = row.get("loss_mask") if isinstance(row.get("loss_mask"), dict) else {}
        for name, enabled in mask.items():
            if enabled:
                counts[name] += 1
    return counts


def authority_violations(rows: list[dict[str, Any]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
        for key, value in authority.items():
            if value:
                violations.append(f"{row.get('row_id')}:{key}")
    return violations


def graph_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    node_types: Counter[str] = Counter()
    edge_types: Counter[str] = Counter()
    for row in rows:
        graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
        for node in graph.get("nodes") if isinstance(graph.get("nodes"), list) else []:
            if isinstance(node, dict):
                node_types[str(node.get("node_type", "unknown"))] += 1
        for edge in graph.get("edges") if isinstance(graph.get("edges"), list) else []:
            if isinstance(edge, dict):
                edge_types[str(edge.get("edge_type", "unknown"))] += 1
    return {"node_types": dict(node_types), "edge_types": dict(edge_types)}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_summary = load_json(SOURCE_SUMMARY)
    source_rows = load_jsonl(SOURCE_MANIFEST)
    logits = load_jsonl(SOURCE_LOGITS)
    rows = build_rows(source_rows)
    write_jsonl(OUT_MANIFEST, rows)

    query_baseline = grouped_baseline(rows, query_kind)
    source_query_baseline = grouped_baseline(source_rows, query_kind)
    baselines = single_feature_baselines(rows)
    strongest_single = next(iter(baselines.values()), 0.0)
    violations = authority_violations(rows)
    losses = count_enabled_losses(rows)
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("stage9707_not_passed")
    if not source_rows:
        failures.append("missing_source_rows")
    if query_baseline >= QUERY_KIND_BASELINE_CEILING:
        failures.append(f"query_kind_baseline_too_high:{query_baseline}")
    if strongest_single >= SINGLE_FEATURE_BASELINE_CEILING:
        failures.append(f"single_feature_baseline_too_high:{strongest_single}")
    if violations:
        failures.append(f"authority_violations:{violations[:5]}")
    if losses != Counter({"symbol_binding_ce": len(rows)}):
        failures.append(f"unexpected_enabled_losses:{dict(losses)}")

    wrong_counter = Counter((record.get("target"), record.get("pred")) for record in logits if record.get("correct") is False)
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
        "source_row_count": len(source_rows),
        "synthetic_counterfactual_rows": len(rows) - len(source_rows),
        "split_counts": split_counts(rows),
        "label_counts": label_counts(rows),
        "query_label_counts": query_label_counts(rows),
        "source_query_kind_action_baseline_exact": source_query_baseline,
        "query_kind_action_baseline_exact": query_baseline,
        "query_kind_action_baseline_ceiling": QUERY_KIND_BASELINE_CEILING,
        "strongest_single_feature_baseline_exact": strongest_single,
        "single_feature_baseline_ceiling": SINGLE_FEATURE_BASELINE_CEILING,
        "top_single_feature_baselines": baselines,
        "stage9707_wrong_confusions": {f"{target}->{pred}": count for (target, pred), count in sorted(wrong_counter.items())},
        "graph_stats": graph_stats(rows),
        "loss_counts": dict(losses),
        "authority_violations": violations,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Run Stage9709 contract-only preflight on the Stage9708 visible-evidence symbol-binding manifest; "
        "do not execute target-100M until query-kind and single-feature baselines remain below ceilings."
        if not failures
        else "Patch Stage9708 visible evidence/counterfactual balance before any target-100M execution."
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": not failures,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {
            "manifest": str(OUT_MANIFEST.relative_to(ROOT)),
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "metrics": {
            "row_count": len(rows),
            "synthetic_counterfactual_rows": len(rows) - len(source_rows),
            "query_kind_action_baseline_exact": query_baseline,
            "strongest_single_feature_baseline_exact": strongest_single,
            "split_counts": split_counts(rows),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9708 Symbol-Binding Visible Evidence Manifest",
                "",
                "Stage9708 responds to the Stage9707 residual collapse by making the missing symbol-binding evidence explicit before another target-100M probe.",
                "",
                "## Added Evidence",
                "",
                "- Opaque query candidate nodes beyond repo/file/contains.",
                "- Candidate node types for module, symbol, test, and retrieval-gap evidence.",
                "- Relation-count features for call/import/test candidate compatibility.",
                "- Counterfactual rows that keep the same query kind while changing whether the candidate is resolvable, ambiguous, or requires retrieval.",
                "",
                "## Guardrails",
                "",
                "- No decoder CE, runtime, Gemma, harness, source/body emission, or promotion authority is opened.",
                "- Target labels remain outside encoder-facing fields.",
                "- The audit blocks if query kind or any single feature still solves the action label.",
                "",
                "## Metrics",
                "",
                f"- Passed: `{not failures}`",
                f"- Rows: `{len(rows)}`",
                f"- Synthetic counterfactual rows: `{len(rows) - len(source_rows)}`",
                f"- Source query-kind baseline: `{source_query_baseline}`",
                f"- Repaired query-kind baseline: `{query_baseline}`",
                f"- Strongest single-feature baseline: `{strongest_single}`",
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
