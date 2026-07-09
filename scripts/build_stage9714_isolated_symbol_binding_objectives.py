#!/usr/bin/env python3
from __future__ import annotations

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
STAGE = 9714
NAME = "stage9714_isolated_symbol_binding_objectives"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9713_symbol_binding_retrieval_test_evidence_execution_audit.json"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9711_symbol_binding_retrieval_test_evidence_repair/symbol_binding_retrieval_test_evidence.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TEST_BINARY = OUT_DIR / "symbol_binding_test_coverage_binary.jsonl"
RETRIEVE_GATE = OUT_DIR / "symbol_binding_retrieve_gate_ternary.jsonl"
AUDIT = OUT_DIR / "isolated_symbol_binding_objectives_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ISOLATED_SYMBOL_BINDING_OBJECTIVES_STAGE9714.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("binding_action") or clean.get("symbol_binding") or "")


def qkind(row: dict[str, Any]) -> str:
    query = row.get("query") if isinstance(row.get("query"), dict) else {}
    graph = row.get("graph_input") if isinstance(row.get("graph_input"), dict) else {}
    return str(query.get("query_kind") or graph.get("query_kind") or "unknown")


def set_label(row: dict[str, Any], new_label: str, objective: str) -> dict[str, Any]:
    out = deepcopy(row)
    out.setdefault("clean_state", {})["binding_action"] = new_label
    out["row_id"] = f"{row.get('row_id')}__stage9714_{objective}"
    out["semantic_key"] = f"{out.get('split')}:{objective}:{new_label}:{qkind(row)}"
    out["source_skill_area"] = f"symbol_binding_{objective}"
    out.setdefault("stage9714_isolated_objective", {})["objective"] = objective
    out["stage9714_isolated_objective"]["source_binding_action"] = label(row)
    out.setdefault("anti_cheat", {})["stage9714_target_label_in_model_input"] = False
    return out


def test_binary_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if qkind(row) != "test":
            continue
        source_label = label(row)
        if source_label == "BIND_TEST_TO_SYMBOL":
            rows.append(set_label(row, "TEST_BINDS_VISIBLE_SYMBOL", "test_coverage_binary"))
        elif source_label == "RETRIEVE_MORE":
            rows.append(set_label(row, "TEST_NEEDS_RETRIEVAL", "test_coverage_binary"))
    return rows


def retrieve_gate_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in source_rows:
        source_label = label(row)
        if source_label == "RETRIEVE_MORE":
            new_label = "RETRIEVE_MORE"
        elif source_label == "ABSTAIN_UNBOUND":
            new_label = "ABSTAIN_UNBOUND"
        else:
            new_label = "BIND_AVAILABLE"
        rows.append(set_label(row, new_label, "retrieve_gate_ternary"))
    return rows


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("split") or "unknown") for row in rows))


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(label(row) for row in rows))


def split_label_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get("split") or "unknown")][label(row)] += 1
    return {split: dict(counts) for split, counts in sorted(grouped.items())}


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


def grouped_baseline(rows: list[dict[str, Any]], feature_fn) -> float:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(feature_fn(row))][label(row)] += 1
    return round(sum(max(counter.values()) for counter in grouped.values()) / len(rows), 6) if rows else 0.0


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
    test_rows = test_binary_rows(source_rows)
    gate_rows = retrieve_gate_rows(source_rows)
    write_jsonl(TEST_BINARY, test_rows)
    write_jsonl(RETRIEVE_GATE, gate_rows)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9713_not_passed")
    if len(test_rows) != 32:
        failures.append(f"test_binary_row_count_not_32:{len(test_rows)}")
    if len(gate_rows) != 92:
        failures.append(f"retrieve_gate_row_count_not_92:{len(gate_rows)}")
    for name, rows in {"test_binary": test_rows, "retrieve_gate": gate_rows}.items():
        if count_enabled_losses(rows) != Counter({"symbol_binding_ce": len(rows)}):
            failures.append(f"{name}_unexpected_losses:{dict(count_enabled_losses(rows))}")
        if authority_violations(rows):
            failures.append(f"{name}_authority_violations:{authority_violations(rows)[:3]}")
    audit = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "manifests": {"test_binary": str(TEST_BINARY.relative_to(ROOT)), "retrieve_gate": str(RETRIEVE_GATE.relative_to(ROOT))},
        "test_binary": {"rows": len(test_rows), "split_counts": split_counts(test_rows), "label_counts": label_counts(test_rows), "split_label_counts": split_label_counts(test_rows), "query_kind_baseline": grouped_baseline(test_rows, qkind)},
        "retrieve_gate": {"rows": len(gate_rows), "split_counts": split_counts(gate_rows), "label_counts": label_counts(gate_rows), "split_label_counts": split_label_counts(gate_rows), "query_kind_baseline": grouped_baseline(gate_rows, qkind)},
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run contract-only preflight for one isolated Stage9714 objective at a time, starting with test_coverage_binary; do not rejoin five-way symbol binding until isolated exactness passes."
    summary = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "quality_passed": False,
        "promotion_ready": False,
        "created_at_unix": int(time.time()),
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "test_binary_manifest": str(TEST_BINARY.relative_to(ROOT)), "retrieve_gate_manifest": str(RETRIEVE_GATE.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "metrics": {"test_binary_rows": len(test_rows), "retrieve_gate_rows": len(gate_rows), "test_binary_label_counts": label_counts(test_rows), "retrieve_gate_label_counts": label_counts(gate_rows)},
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": next_step,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9714 Isolated Symbol-Binding Objectives",
                "",
                "Stage9714 splits the two unsolved Stage9713 transitions out of the mixed five-way symbol-binding objective.",
                "",
                "## Manifests",
                "",
                "- `symbol_binding_test_coverage_binary.jsonl`: test query rows only, TEST_BINDS_VISIBLE_SYMBOL vs TEST_NEEDS_RETRIEVAL.",
                "- `symbol_binding_retrieve_gate_ternary.jsonl`: all rows collapsed to BIND_AVAILABLE, RETRIEVE_MORE, or ABSTAIN_UNBOUND.",
                "",
                "## Result",
                "",
                f"- Passed: `{not failures}`",
                f"- Test binary rows: `{len(test_rows)}`",
                f"- Retrieve gate rows: `{len(gate_rows)}`",
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
