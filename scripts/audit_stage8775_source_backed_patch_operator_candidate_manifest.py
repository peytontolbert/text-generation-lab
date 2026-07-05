#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from contamination_leakage_detector import detect_card
from dataset_junk_ood_ranker_v1 import rank_row_v1
from gate_status_contract import gate_status_card
from schema_drift_detector import audit_rows
from source_backed_patch_operator_builder import AUTHORITY_CLOSED, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8775
NAME = "stage8775_source_backed_patch_operator_candidate_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8774_source_backed_patch_operator_candidate_manifest/source_backed_patch_operator_candidate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_PATCH_OPERATOR_CANDIDATE_AUDIT_STAGE8775.md"
SCHEMA = {
    "required_fields": ["row_id", "split", "objective_family", "route", "authority", "loss_mask", "gate_status", "source_lineage", "graph_input", "query", "corrupted_state", "clean_state", "anti_cheat"],
    "optional_fields": ["source_backed", "source_stage", "source_row_ref", "semantic_key"],
    "typed_fields": {"row_id": "str", "split": "str", "objective_family": "str", "route": "str", "authority": "dict", "loss_mask": "dict", "gate_status": "dict", "source_lineage": "dict", "graph_input": "dict", "query": "dict", "corrupted_state": "dict", "clean_state": "dict", "anti_cheat": "dict"},
    "forbidden_fields": ["decoder_text", "raw_source", "raw_source_body", "patch_body", "target_node_id", "target_file_path"],
    "allow_unknown_fields": False,
}


def feature_value(row: dict[str, Any], feature: str) -> str:
    state = row.get("corrupted_state") or {}; graph = row.get("graph_input") or {}; scope = state.get("target_scope_features") or {}; budget = state.get("budget") or {}
    mapping = {"language": state.get("language"), "file_extension": state.get("file_extension"), "operator_signal": state.get("operator_signal"), "target_kind_hint": scope.get("target_kind_hint"), "has_visible_test": scope.get("has_visible_test"), "has_visible_import_policy": scope.get("has_visible_import_policy"), "has_visible_config": scope.get("has_visible_config"), "bounded_patch_required": scope.get("bounded_patch_required"), "max_hunks": budget.get("max_hunks"), "max_files": budget.get("max_files"), "decoder_budget_ok": budget.get("decoder_budget_ok"), "candidate_node_count": graph.get("candidate_node_count"), "edge_family_count": graph.get("edge_family_count")}
    return str(mapping[feature])


def grouped_baseline(rows: list[dict[str, Any]], features: list[str]) -> float:
    table: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[tuple(feature_value(row, f) for f in features)][row["clean_state"]["patch_operator"]] += 1
    return sum(int(table[tuple(feature_value(row, f) for f in features)].most_common(1)[0][0] == row["clean_state"]["patch_operator"]) for row in rows) / len(rows) if rows else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(MANIFEST)
    contamination = detect_card(rows)
    schema = audit_rows(rows, SCHEMA)
    junk_records = [rank_row_v1(row) for row in rows]
    junk_routes = Counter(record["route"] for record in junk_records)
    gate_card = gate_status_card(rows)
    labels = Counter(row["clean_state"]["patch_operator"] for row in rows)
    features = ["language", "file_extension", "target_kind_hint", "has_visible_test", "has_visible_import_policy", "has_visible_config", "bounded_patch_required", "max_hunks", "max_files", "decoder_budget_ok", "candidate_node_count", "edge_family_count"]
    single = {f: grouped_baseline(rows, [f]) for f in features}
    combos = {"target_scope_bits": grouped_baseline(rows, ["target_kind_hint", "has_visible_test", "has_visible_import_policy", "has_visible_config"]), "graph_shape": grouped_baseline(rows, ["candidate_node_count", "edge_family_count"]), "operator_signal+target_scope_bits": grouped_baseline(rows, ["operator_signal", "target_kind_hint", "has_visible_test", "has_visible_import_policy", "has_visible_config"])}
    failures: list[str] = []
    if contamination["blocked_rows"]: failures.append("contamination blocked rows present")
    if schema["metrics"]["blocked_rows"]: failures.append("schema blocked rows present")
    if gate_card["complete_gate_status_rows"] != len(rows): failures.append("incomplete gate_status rows")
    if any(any((row.get("authority") or {}).values()) for row in rows): failures.append("authority rows present")
    if any(any((row.get("loss_mask") or {}).values()) for row in rows): failures.append("training losses present in candidate rows")
    if labels and len(set(labels.values())) != 1: failures.append("operator labels are not balanced")
    if max(single.values()) > 0.66: failures.append("single proxy baseline above ceiling")
    if max(v for k, v in combos.items() if k != "operator_signal+target_scope_bits") > 0.66: failures.append("combo proxy baseline above ceiling")
    (OUT_DIR / "contamination_card.json").write_text(json.dumps(contamination, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "schema_card.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "junk_routes.json").write_text(json.dumps({"route_counts": dict(junk_routes)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "rows": len(rows), "operator_counts": dict(sorted(labels.items())), "contamination_blocked_rows": contamination["blocked_rows"], "contamination_review_rows": contamination["review_rows"], "schema_blocked_rows": schema["metrics"]["blocked_rows"], "schema_review_rows": schema["metrics"]["review_rows"], "junk_route_counts": dict(junk_routes), "gate_status_complete_rows": gate_card["complete_gate_status_rows"], "max_single_proxy_baseline": max(single.values()) if single else 0.0, "max_combo_proxy_baseline": max(v for k, v in combos.items() if k != "operator_signal+target_scope_bits") if combos else 0.0, "semantic_evidence_baseline": combos["operator_signal+target_scope_bits"], "failures": failures}, "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "contamination_card": str((OUT_DIR / "contamination_card.json").relative_to(ROOT)), "schema_card": str((OUT_DIR / "schema_card.json").relative_to(ROOT)), "junk_routes": str((OUT_DIR / "junk_routes.json").relative_to(ROOT))}, "decision": "Source-backed patch-operator candidate audit passed for leakage/schema/proxy basics, but rows remain candidate-only until remaining recovered gates are materialized into compiler-ready gate_status." if not failures else "Source-backed patch-operator candidate audit failed.", "next_best_step": "Materialize compiler-ready source-backed patch-operator rows only after cluster/drift/junk/golden gate cards are explicit, then recover source-backed verifier-repair builder.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8775 Source-Backed Patch Operator Candidate Audit", "", f"Passed: `{card['passed']}`", "", f"Rows: `{len(rows)}`", f"Contamination blocked rows: `{contamination['blocked_rows']}`", f"Schema blocked rows: `{schema['metrics']['blocked_rows']}`", f"Max single proxy baseline: `{card['metrics']['max_single_proxy_baseline']}`", "", "Rows remain candidate-only. Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
