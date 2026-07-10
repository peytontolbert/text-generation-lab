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
STAGE = 9726
NAME = "stage9726_multilingual_patch_operator_tiny_package"
SOURCE = ROOT / "runs/local/artifacts/stage9693_locked_guarded_source_backed_multisurface_compiler_refresh/compiled/structured_state.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "multilingual_patch_operator_tiny.jsonl"
AUDIT = OUT_DIR / "multilingual_patch_operator_tiny_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_PATCH_OPERATOR_TINY_PACKAGE_STAGE9726.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
CAPS = {"train": 8, "eval": 4, "strict_eval": 4}
TARGET_LOSS = "patch_operator_ce"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def select_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("expected_enabled_loss") != TARGET_LOSS:
            continue
        lang = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        if lang in LANGS and split in CAPS:
            grouped[lang][split].append(row)
    selected: list[dict[str, Any]] = []
    failures: list[str] = []
    for lang in LANGS:
        for split, cap in CAPS.items():
            bucket = grouped[lang][split]
            if len(bucket) < cap:
                failures.append(f"insufficient_rows:{lang}:{split}")
                continue
            selected.extend(bucket[:cap])
    return selected, failures


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
    selected, failures = select_rows(rows)
    write_jsonl(MANIFEST, selected)
    lang_counts = Counter(str(row.get("language_family") or "") for row in selected)
    split_counts = Counter(f"{row.get('language_family')}::{row.get('split')}" for row in selected)
    if len(selected) != len(LANGS) * sum(CAPS.values()):
        failures.append("selected_row_count_mismatch")
    audit = {
        "passed": not failures,
        "failures": failures,
        "rows": len(selected),
        "language_counts": dict(sorted(lang_counts.items())),
        "language_split_counts": dict(sorted(split_counts.items())),
        "target_loss": TARGET_LOSS,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run Stage9727 target-100M contract-only preflight on the Stage9726 multilingual patch-operator package, then decide whether to execute that multilingual structured probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Materialized a balanced multilingual patch-operator tiny package with current rows from python, rust, c_cpp, and web_js_ts_html.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9726 Multilingual Patch Operator Tiny Package",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Language counts: `{audit['language_counts']}`",
        "",
        "This stage packages a balanced multilingual patch-operator structured surface from current compiled rows: python, rust, c_cpp, and web_js_ts_html.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "rows": audit["rows"], "language_counts": audit["language_counts"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
