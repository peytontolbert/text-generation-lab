#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10050
NAME = "stage10050_balanced_multilingual_successor_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "balanced_multilingual_successor_packet.json"
ROWS = OUT_DIR / "balanced_multilingual_successor_rows.jsonl"
MANIFEST = OUT_DIR / "balanced_multilingual_successor_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BALANCED_MULTILINGUAL_SUCCESSOR_PACKET_STAGE10050.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASE_MANIFEST = ROOT / "runs/local/artifacts/stage10047_python_symbol_test_source_backed_successor_packet/python_symbol_test_successor_train_manifest.jsonl"
COMPARE_ROWS = ROOT / "runs/local/artifacts/stage10049_python_symbol_test_same_manifest_comparison_audit/python_symbol_test_same_manifest_comparison_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage10049_python_symbol_test_same_manifest_comparison_audit.json"
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
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_readiness():
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", TRAINER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, "assess_multilingual_surface_readiness")


def label_letter(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get("edit_localization") or clean.get("edit_localization_target") or "")


def build_packet() -> dict[str, Any]:
    base_rows = load_jsonl(BASE_MANIFEST)
    compare_rows = load_jsonl(COMPARE_ROWS)
    source_summary = load_json(SOURCE_SUMMARY)
    failures: list[str] = []

    canonical_train: dict[tuple[str, str], dict[str, Any]] = {}
    for row in base_rows:
        if str(row.get("split") or "") != "train":
            continue
        key = (str(row.get("language_family") or ""), label_letter(row))
        canonical_train.setdefault(key, row)

    regression_counts: Counter[tuple[str, str]] = Counter()
    for row in compare_rows:
        if bool(row.get("baseline_hundred_m_correct")) and not bool(row.get("successor_hundred_m_correct")):
            key = (str(row.get("language_family") or ""), str(row.get("expected_label") or ""))
            regression_counts[key] += 1

    anchor_rows: list[dict[str, Any]] = []
    per_anchor_counts: dict[str, int] = {}
    for (language, label), count in sorted(regression_counts.items()):
        source = canonical_train.get((language, label))
        if not isinstance(source, dict):
            failures.append(f"missing_canonical_train:{language}:{label}")
            continue
        per_anchor_counts[f"{language}:{label}"] = count
        for index in range(count):
            cloned = deepcopy(source)
            cloned["row_id"] = f"{source.get('row_id')}::stage10050_anchor_{index + 1}"
            cloned["split"] = "train"
            cloned["stage10050_anchor_language"] = language
            cloned["stage10050_anchor_label"] = label
            cloned["stage10050_anchor_reason"] = "restore_stage10049_baseline_loss"
            cloned["stage10050_anchor_source_row_id"] = source.get("row_id")
            anchor_rows.append(cloned)

    successor_rows = [*base_rows, *anchor_rows]
    write_jsonl(ROWS, anchor_rows)
    write_jsonl(MANIFEST, successor_rows)

    assess_multilingual_surface_readiness = _load_readiness()
    readiness = assess_multilingual_surface_readiness("edit_localization_probe", successor_rows)
    if not readiness or readiness.get("passed") is not True:
        failures.append("balanced_successor_readiness_failed")

    language_counts = Counter(str(row.get("language_family") or "") for row in successor_rows)
    split_counts = Counter(str(row.get("split") or "") for row in successor_rows)
    anchor_language_counts = Counter(str(row.get("language_family") or "") for row in anchor_rows)
    anchor_label_counts = Counter(f"{row.get('language_family')}:{label_letter(row)}" for row in anchor_rows)
    metrics = {
        "base_rows": len(base_rows),
        "successor_rows": len(successor_rows),
        "anchor_rows": len(anchor_rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "anchor_language_counts": dict(sorted(anchor_language_counts.items())),
        "anchor_label_counts": dict(sorted(anchor_label_counts.items())),
        "regression_counts": dict(sorted((f"{k[0]}:{k[1]}", v) for k, v in regression_counts.items())),
        "readiness_passed": bool(readiness and readiness.get("passed")),
        "readiness_failed_buckets": list((readiness or {}).get("failed_buckets") or []),
    }

    if source_summary.get("passed") is not True:
        failures.append("stage10049_not_passed")
    if metrics["anchor_rows"] != sum(regression_counts.values()):
        failures.append("anchor_rows_not_equal_to_regression_rows")
    if split_counts.get("train") != 66:
        failures.append("train_rows_not_66")
    if metrics["successor_rows"] != 121:
        failures.append("successor_rows_not_121")
    if anchor_language_counts.get("web_js_ts_html") != 7:
        failures.append("web_anchor_rows_not_7")
    if anchor_language_counts.get("c_cpp") != 7:
        failures.append("c_cpp_anchor_rows_not_7")
    if anchor_language_counts.get("rust") != 2:
        failures.append("rust_anchor_rows_not_2")
    if anchor_language_counts.get("python") != 2:
        failures.append("python_c_anchor_rows_not_2")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "policy": {
            "preserve_stage10047_python_fix": True,
            "restore_measured_multilingual_regressions_only": True,
            "no_eval_row_replay": True,
            "canonical_train_duplicates_only_for_non_python_anchors": True,
        },
        "inputs": {
            "base_manifest": display(BASE_MANIFEST),
            "comparison_audit": display(SOURCE_SUMMARY),
            "comparison_rows": display(COMPARE_ROWS),
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    write_json(PACKET, built)
    next_step = "Run one capped target-100m probe on this balanced multilingual successor manifest to test whether the Python gain can be retained without giving back c_cpp, rust, and web heldout accuracy."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {
            "packet": display(PACKET),
            "anchor_rows": display(ROWS),
            "manifest": display(MANIFEST),
            "doc": display(DOC),
        },
        "decision": "Materialized a balanced multilingual successor packet that keeps the stage10047 Python intervention while adding only the exact non-Python canonical train anchors needed to restore labels lost in stage10049.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10050 Balanced Multilingual Successor Packet",
                "",
                f"Passed: `{summary['passed']}`",
                f"Successor rows: `{built['metrics']['successor_rows']}`",
                f"Anchor rows: `{built['metrics']['anchor_rows']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
