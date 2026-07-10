#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9735
NAME = "stage9735_multilingual_patch_operator_label_aligned_package"
SOURCE = ROOT / "runs/local/artifacts/stage9693_locked_guarded_source_backed_multisurface_compiler_refresh/compiled/structured_state.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "multilingual_patch_operator_label_aligned.jsonl"
AUDIT = OUT_DIR / "multilingual_patch_operator_label_aligned_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_PATCH_OPERATOR_LABEL_ALIGNED_PACKAGE_STAGE9735.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["train", "eval", "strict_eval"]
TARGET_LOSS = "patch_operator_ce"
LABEL_KEY = "patch_operator"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _label(row: dict[str, Any]) -> str:
    clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
    return str(clean.get(LABEL_KEY) or "")


def select_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    grouped: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    labels = set()
    for row in rows:
        if row.get("expected_enabled_loss") != TARGET_LOSS:
            continue
        lang = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        label = _label(row)
        if lang in LANGS and split in SPLITS and label:
            grouped[lang][split][label].append(row)
            labels.add(label)
    ordered_labels = sorted(labels)
    selected: list[dict[str, Any]] = []
    failures: list[str] = []
    for lang in LANGS:
        for split in SPLITS:
            for label in ordered_labels:
                bucket = grouped[lang][split][label]
                if not bucket:
                    failures.append(f"missing_label:{lang}:{split}:{label}")
                    continue
                selected.append(bucket[0])
    return selected, failures, ordered_labels


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
    rows = load_jsonl(SOURCE)
    selected, failures, labels = select_rows(rows)
    write_jsonl(MANIFEST, selected)
    lang_counts = Counter(str(row.get("language_family") or "") for row in selected)
    split_counts = Counter(str(row.get("split") or "") for row in selected)
    label_counts = Counter(_label(row) for row in selected)
    if len(selected) != len(LANGS) * len(SPLITS) * len(labels):
        failures.append("selected_row_count_mismatch")
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(selected),
        "labels": labels,
        "language_counts": dict(sorted(lang_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9736 target-100M execution on the label-aligned multilingual patch-operator package and compare against the Stage9729 zero-exact baseline."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a label-aligned multilingual patch-operator package so train, eval, and strict-eval share the same target label inventory across all four languages.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9735 Multilingual Patch Operator Label-Aligned Package",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Labels: `{labels}`",
        f"Language counts: `{audit['language_counts']}`",
        f"Split counts: `{audit['split_counts']}`",
        "",
        "This package removes the train/eval label mismatch present in the earlier tiny package by selecting one row for every label in every language and every split.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": audit["rows"], "labels": labels, "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
