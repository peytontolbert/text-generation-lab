#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10059
NAME = "stage10059_hybrid_web_targeted_geometry_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "hybrid_web_targeted_geometry_successor_packet.json"
ROWS = OUT_DIR / "hybrid_web_targeted_geometry_successor_rows.jsonl"
MANIFEST = OUT_DIR / "hybrid_web_targeted_geometry_successor_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HYBRID_WEB_TARGETED_GEOMETRY_SUCCESSOR_PACKET_STAGE10059.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10047_python_symbol_test_source_backed_successor_packet/python_symbol_test_successor_train_manifest.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10058_balanced_fresh_source_multilingual_same_manifest_comparison_audit.json"
STAGE10056_ROWS = ROOT / "runs/local/artifacts/stage10056_balanced_fresh_source_multilingual_geometry_successor_packet/balanced_fresh_source_multilingual_geometry_successor_rows.jsonl"
STAGE10053_ROWS = ROOT / "runs/local/artifacts/stage10053_mixed_fresh_source_multilingual_successor_packet/mixed_fresh_source_multilingual_successor_rows.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"


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
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_readiness():
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", TRAINER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, "assess_multilingual_surface_readiness")


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    source_summary = load_json(SOURCE_SUMMARY)
    geometry_rows = load_jsonl(STAGE10056_ROWS)
    mixed_rows = load_jsonl(STAGE10053_ROWS)
    failures: list[str] = []

    selected_rows = []
    selected_rows.extend([r for r in geometry_rows if r.get('language_family') in {'c_cpp','rust'}])
    selected_rows.extend([r for r in mixed_rows if r.get('language_family') == 'web_js_ts_html'])
    successor_rows = [*base_rows, *selected_rows]
    write_jsonl(ROWS, selected_rows)
    write_jsonl(MANIFEST, successor_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", successor_rows)
    if not readiness or readiness.get("passed") is not True:
        failures.append("hybrid_successor_readiness_failed")

    language_counts = Counter(str(row.get("language_family") or "") for row in successor_rows)
    split_counts = Counter(str(row.get("split") or "") for row in successor_rows)
    selected_language_counts = Counter(str(row.get("language_family") or "") for row in selected_rows)
    selected_counts = Counter(f"{row.get('language_family')}:{(row.get('clean_state') or {}).get('edit_localization_target')}" for row in selected_rows)
    metrics = {
        "base_rows": len(base_rows),
        "successor_rows": len(successor_rows),
        "fresh_source_rows": len(selected_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "fresh_source_language_counts": dict(sorted(selected_language_counts.items())),
        "selected_counts": dict(sorted(selected_counts.items())),
        "readiness_passed": bool(readiness and readiness.get("passed")),
        "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
    }

    if source_summary.get("passed") is not True:
        failures.append("stage10058_not_passed")
    if metrics["fresh_source_rows"] != 21:
        failures.append("fresh_source_rows_not_21")
    if metrics["successor_rows"] != 124:
        failures.append("successor_rows_not_124")
    if split_counts.get("train") != 69:
        failures.append("train_rows_not_69")
    if split_counts.get("eval") != 38:
        failures.append("eval_rows_not_38")
    if split_counts.get("strict_eval") != 17:
        failures.append("strict_rows_not_17")
    if language_counts.get("python") != 27:
        failures.append("python_rows_not_27")
    if language_counts.get("c_cpp") != 38:
        failures.append("c_cpp_rows_not_38")
    if language_counts.get("rust") != 17:
        failures.append("rust_rows_not_17")
    if language_counts.get("web_js_ts_html") != 42:
        failures.append("web_rows_not_42")
    if metrics["selected_counts"] != {
        "c_cpp:A": 1,
        "c_cpp:B": 3,
        "c_cpp:C": 1,
        "c_cpp:D": 1,
        "c_cpp:E": 2,
        "rust:A": 1,
        "rust:B": 1,
        "rust:C": 2,
        "rust:D": 1,
        "rust:E": 1,
        "web_js_ts_html:A": 6,
        "web_js_ts_html:C": 1,
    }:
        failures.append("selected_counts_mismatch")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10047_python_fix": True,
            "keep_c_cpp_and_rust_geometry_from_stage10056": True,
            "revert_web_to_targeted_stage10053_topups": True,
            "no_eval_row_replay": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "stage10056_rows": display(STAGE10056_ROWS),
            "stage10053_rows": display(STAGE10053_ROWS),
            "stage10058_audit": display(Path('runs/local/artifacts/stage10058_balanced_fresh_source_multilingual_same_manifest_comparison_audit/balanced_fresh_source_multilingual_same_manifest_comparison_audit.json')),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = "Run one capped target-100m probe on this hybrid packet to test whether stage10056 rust/cpp recovery can be combined with the stronger stage10053 web behavior without giving back Python."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": built["passed"], "metrics": {**built["metrics"], "failures": built["failures"]}, "artifacts": {"packet": display(PACKET), "rows": display(ROWS), "manifest": display(MANIFEST), "doc": display(DOC)}, "decision": "Materialized a hybrid successor packet that keeps stage10056 geometry repairs for c_cpp/rust but reverts web to the narrower stage10053 targeted A/C topups, while preserving the stage10047 Python fix.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage10059 Hybrid Web Targeted Geometry Successor Packet", "", f"Passed: `{summary['passed']}`", f"Fresh source rows: `{built['metrics']['fresh_source_rows']}`", f"Successor rows: `{built['metrics']['successor_rows']}`", "", summary["decision"], "", f"Next: {next_step}", ""]), encoding="utf-8")
    if summary["passed"]: update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
