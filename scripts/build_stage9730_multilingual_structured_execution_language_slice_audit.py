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
STAGE = 9730
NAME = "stage9730_multilingual_structured_execution_language_slice_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_structured_execution_language_slice_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_STRUCTURED_EXECUTION_LANGUAGE_SLICE_AUDIT_STAGE9730.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9729_multilingual_structured_execution_support_ledger.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]
SURFACES = {
    "verifier_repair": {
        "manifest": ROOT / "runs/local/artifacts/stage9722_multilingual_verifier_repair_tiny_package/multilingual_verifier_repair_tiny.jsonl",
        "logits": ROOT / "runs/local/artifacts/stage9729_probe_smoke_verifier_repair_exec/row_field_logits.jsonl",
    },
    "edit_localization": {
        "manifest": ROOT / "runs/local/artifacts/stage9724_multilingual_edit_localization_tiny_package/multilingual_edit_localization_tiny.jsonl",
        "logits": ROOT / "runs/local/artifacts/stage9729_probe_smoke_edit_localization_exec/row_field_logits.jsonl",
    },
    "patch_operator": {
        "manifest": ROOT / "runs/local/artifacts/stage9726_multilingual_patch_operator_tiny_package/multilingual_patch_operator_tiny.jsonl",
        "logits": ROOT / "runs/local/artifacts/stage9729_probe_smoke_patch_operator_exec/row_field_logits.jsonl",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def manifest_language_map(path: Path) -> dict[str, str]:
    return {str(row.get("row_id")): str(row.get("language_family") or "unknown") for row in load_jsonl(path)}


def audit_surface(surface: str, manifest: Path, logits_path: Path) -> dict[str, Any]:
    row_to_lang = manifest_language_map(manifest)
    logits = load_jsonl(logits_path)
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    unknown_rows = []
    for row in logits:
        row_id = str(row.get("row_id") or "")
        lang = row_to_lang.get(row_id)
        split = str(row.get("split") or "")
        if lang is None:
            unknown_rows.append(row_id)
            continue
        grouped[lang][split].append(row)
    failures: list[str] = []
    if unknown_rows:
        failures.append("unmapped_row_ids_present")
    slice_metrics: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        lang_metrics: dict[str, Any] = {}
        for split in SPLITS:
            rows = grouped[lang][split]
            if len(rows) != 4:
                failures.append(f"unexpected_rows:{lang}:{split}")
            correct = sum(1 for row in rows if row.get("correct") is True)
            lang_metrics[split] = {
                "rows": len(rows),
                "correct": correct,
                "exact": (correct / len(rows)) if rows else None,
                "high_confidence_wrong_rows": sum(1 for row in rows if row.get("high_confidence_wrong") is True),
            }
        slice_metrics[lang] = lang_metrics
    return {
        "surface": surface,
        "passed": not failures,
        "failures": failures,
        "language_slices": slice_metrics,
        "unknown_row_ids": sorted(set(unknown_rows)),
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    surface_audits = {
        surface: audit_surface(surface, config["manifest"], config["logits"])
        for surface, config in SURFACES.items()
    }
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9729_not_passed")
    for surface, audit in surface_audits.items():
        if not audit["passed"]:
            failures.append(f"surface_language_slice_failed:{surface}")
    status_counts = Counter()
    for audit in surface_audits.values():
        for lang in LANGS:
            for split in SPLITS:
                exact = audit["language_slices"][lang][split]["exact"]
                status_counts[f"{split}::{exact}"] += 1
    return {
        "passed": not failures,
        "failures": failures,
        "surface_audits": surface_audits,
        "metrics": {
            "surfaces": len(surface_audits),
            "languages": len(LANGS),
            "splits": len(SPLITS),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the Stage9730 language-slice exactness map to prioritize repair work or comparison packaging: "
        "verifier_repair is evenly weak across languages, while edit_localization and patch_operator are uniformly failing."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **(audit.get("metrics") or {}),
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Derived per-language exactness slices from the real multilingual target-100M structured executions.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9730 Multilingual Structured Execution Language Slice Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
    ]
    for surface, surface_audit in sorted(audit["surface_audits"].items()):
        lines.append(f"## {surface}")
        for lang in LANGS:
            eval_exact = surface_audit["language_slices"][lang]["eval"]["exact"]
            strict_exact = surface_audit["language_slices"][lang]["strict_eval"]["exact"]
            lines.append(f"- {lang}: eval `{eval_exact}`, strict `{strict_exact}`")
        lines.append("")
    lines.extend([
        "These are language-sliced support metrics from the Stage9729 executions. They are not Gemma comparisons and they are not sufficient for a beat-Gemma claim.",
        "",
        f"Next: {next_step}",
        "",
    ])
    DOC.write_text("\n".join(lines), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": audit["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
