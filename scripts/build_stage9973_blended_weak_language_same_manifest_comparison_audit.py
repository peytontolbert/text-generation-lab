#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9973
NAME = "stage9973_blended_weak_language_same_manifest_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "blended_weak_language_same_manifest_comparison_audit.json"
ROWS = OUT_DIR / "blended_weak_language_same_manifest_comparison_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_SAME_MANIFEST_COMPARISON_AUDIT_STAGE9973.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ACCEPT_100M = ROOT / "runs/local/artifacts/stage9972_blended_weak_language_output_acceptance_audit/blended_weak_language_output_acceptance_audit.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9968_blended_weak_language_same_manifest_handoff_bundle/blended_weak_language_same_manifest_handoff_bundle.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ("eval", "strict_eval")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def future_paths() -> tuple[Path, Path]:
    accept = load_json(ACCEPT_100M)
    handoff = load_json(HANDOFF)
    future_100m_dir = ROOT / str((accept.get("future_run") or {}).get("future_output_dir") or "")
    handoff_bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    gemma_output = ROOT / str(((handoff_bundle.get("gemma_execution") or {}).get("future_output_stub")) or "")
    gemma_rows = gemma_output.with_name(gemma_output.stem + "_rows.jsonl") if gemma_output.name else Path()
    return future_100m_dir / "row_field_logits.jsonl", gemma_rows


def language_from_text(text: str) -> str:
    lowered = str(text or "").lower()
    for lang in LANGS:
        if f"language={lang}" in lowered or lang in lowered:
            return lang
    if "javascript" in lowered or "typescript" in lowered or "html" in lowered or "web" in lowered:
        return "web_js_ts_html"
    if "c_cpp" in lowered or "::c_" in lowered or "::cpp" in lowered or "c++" in lowered:
        return "c_cpp"
    return "unknown"


def language_from_rows(row_100m: dict[str, Any], gemma_row: dict[str, Any]) -> str:
    candidates = [
        gemma_row.get("prompt"),
        row_100m.get("cell_key"),
        row_100m.get("row_id"),
    ]
    for value in candidates:
        inferred = language_from_text(str(value or ""))
        if inferred in LANGS:
            return inferred
    return "unknown"


def build_comparison_rows(rows_100m: list[dict[str, Any]], gemma_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gemma_index = {str(row.get("row_id") or ""): row for row in gemma_rows}
    combined: list[dict[str, Any]] = []
    for row in rows_100m:
        row_id = str(row.get("row_id") or "")
        gemma = gemma_index.get(row_id, {})
        split = str(row.get("split") or gemma.get("split") or "")
        combined.append({
            "row_id": row_id,
            "language_family": language_from_rows(row, gemma),
            "split": split,
            "expected_label": str(gemma.get("expected_label") or row.get("target") or ""),
            "hundred_m_pred": str(row.get("pred") or ""),
            "gemma_pred": str(gemma.get("predicted_label") or ""),
            "hundred_m_correct": bool(row.get("correct")),
            "gemma_correct": bool(gemma.get("correct")),
        })
    return combined


def bucket_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lang = str(row.get("language_family") or "")
        split = str(row.get("split") or "")
        if lang in LANGS and split in SPLITS:
            grouped[(lang, split)].append(row)
    buckets = {}
    for lang in LANGS:
        for split in SPLITS:
            bucket = grouped.get((lang, split), [])
            hundred_m_correct = sum(int(row["hundred_m_correct"]) for row in bucket)
            gemma_correct = sum(int(row["gemma_correct"]) for row in bucket)
            total = len(bucket)
            verdict = "tie"
            if total:
                hm = hundred_m_correct / total
                gm = gemma_correct / total
                verdict = "100m_better" if hm > gm else "gemma_better" if hm < gm else "tie"
            buckets[f"{lang}:{split}"] = {
                "hundred_m_correct": hundred_m_correct,
                "gemma_correct": gemma_correct,
                "rows": total,
                "hundred_m_exact": (hundred_m_correct / total) if total else None,
                "gemma_exact": (gemma_correct / total) if total else None,
                "verdict": verdict,
            }
    return buckets


def build_audit() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    accept = load_json(ACCEPT_100M)
    handoff = load_json(HANDOFF)
    failures: list[str] = []
    pending: list[str] = []

    if accept.get("passed") is not True:
        failures.append("stage9972_not_passed")
    if (accept.get("metrics") or {}).get("acceptance_ready") is not True:
        failures.append("stage9965_output_acceptance_not_ready")
    if handoff.get("passed") is not True:
        failures.append("stage9968_not_passed")

    rows_100m_path, gemma_rows_path = future_paths()
    rows_100m_exists = rows_100m_path.exists()
    gemma_rows_exists = gemma_rows_path.exists()
    if not rows_100m_exists:
        pending.append("stage9965_row_field_logits_missing")
    if not gemma_rows_exists:
        pending.append("stage9971_gemma_rows_missing")

    rows_100m = load_jsonl(rows_100m_path) if rows_100m_exists else []
    gemma_rows = load_jsonl(gemma_rows_path) if gemma_rows_exists else []
    comparisons = {}
    combined_rows: list[dict[str, Any]] = []
    if rows_100m_exists and gemma_rows_exists:
        combined_rows = build_comparison_rows(rows_100m, gemma_rows)
        comparisons = bucket_metrics(combined_rows)

    metrics = {
        "comparison_ready_now": rows_100m_exists and gemma_rows_exists,
        "rows_100m_present": len(rows_100m),
        "rows_gemma_present": len(gemma_rows),
        "pending_conditions": pending,
        "comparison_cells": len(comparisons),
        "wins_100m": sum(1 for row in comparisons.values() if row.get("verdict") == "100m_better"),
        "wins_gemma": sum(1 for row in comparisons.values() if row.get("verdict") == "gemma_better"),
        "ties": sum(1 for row in comparisons.values() if row.get("verdict") == "tie"),
        "macro_exact_100m": (
            sum(float(row.get("hundred_m_exact") or 0.0) for row in comparisons.values()) / len(comparisons)
            if comparisons else None
        ),
        "macro_exact_gemma": (
            sum(float(row.get("gemma_exact") or 0.0) for row in comparisons.values()) / len(comparisons)
            if comparisons else None
        ),
    }
    if metrics["rows_100m_present"] != 80:
        failures.append("rows_100m_present_not_80")
    if metrics["rows_gemma_present"] != 80:
        failures.append("rows_gemma_present_not_80")
    return ({
        "passed": not failures,
        "failures": failures,
        "pending_conditions": pending,
        "metrics": metrics,
        "comparison_cells": comparisons,
        "future_artifacts": {
            "hundred_m_rows": display(rows_100m_path),
            "gemma_rows": display(gemma_rows_path),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }, combined_rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit, rows = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, rows)
    next_step = "Use this real same-manifest weak-language comparison to decide whether the stage9965 recovery path should replace the current frontier, then attach these verdicts back into the stage9969-stage9970 review packets and workbook."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": display(AUDIT), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the actual weak-language same-manifest comparison audit on real Stage9965 and Stage9971 outputs, so the 100M-versus-Gemma verdict is now measured rather than inferred.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9973 Blended Weak-Language Same-Manifest Comparison Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Comparison ready now: `{audit['metrics']['comparison_ready_now']}`",
        f"100M rows present: `{audit['metrics']['rows_100m_present']}`",
        f"Gemma rows present: `{audit['metrics']['rows_gemma_present']}`",
        f"100M wins: `{audit['metrics']['wins_100m']}`",
        f"Gemma wins: `{audit['metrics']['wins_gemma']}`",
        f"Ties: `{audit['metrics']['ties']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": audit["metrics"],
        "failures": audit["failures"],
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
