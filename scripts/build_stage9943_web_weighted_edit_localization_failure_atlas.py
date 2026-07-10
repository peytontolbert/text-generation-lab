#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9943
NAME = "stage9943_web_weighted_edit_localization_failure_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "web_weighted_edit_localization_failure_atlas.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEB_WEIGHTED_EDIT_LOCALIZATION_FAILURE_ATLAS_STAGE9943.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MODEL_ROWS = ROOT / "runs/local/artifacts/stage9917_hardened_weighted_structured_execution_review/surface_runs/edit_localization/row_field_logits.jsonl"
GEMMA_ROWS = ROOT / "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_rows.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage9919_hardened_weighted_edit_localization_gemma_comparison/hardened_weighted_edit_localization_gemma_comparison.json"

CANDIDATE_RE = re.compile(r"option ([A-D]): ([^|]+)")
RESOLUTION_RE = re.compile(r"state\.visible_locality_resolution=([^|]+)")
WEB_DISAMBIG_RE = re.compile(r"state\.web_surface_disambiguator=([^|]+)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def _parse_prompt(prompt: str) -> dict[str, Any]:
    mapping = {label: semantic.strip() for label, semantic in CANDIDATE_RE.findall(prompt)}
    resolution = RESOLUTION_RE.search(prompt)
    web_disambig = WEB_DISAMBIG_RE.search(prompt)
    return {
        "choice_map": mapping,
        "visible_locality_resolution": resolution.group(1).strip() if resolution else None,
        "web_surface_disambiguator": web_disambig.group(1).strip() if web_disambig else None,
    }


def build_atlas() -> dict[str, Any]:
    model_rows = {
        (str(row.get("row_id")), str(row.get("split"))): row
        for row in load_jsonl(MODEL_ROWS)
        if str(row.get("cell_key", "")).startswith("web_js_ts_html::")
    }
    gemma_rows = [
        row for row in load_jsonl(GEMMA_ROWS)
        if str(row.get("language")) == "web_js_ts_html"
    ]
    comparison = load_json(COMPARISON)
    failures: list[str] = []
    records: list[dict[str, Any]] = []

    for gemma_row in gemma_rows:
        key = (str(gemma_row.get("row_id")), str(gemma_row.get("split")))
        model_row = model_rows.get(key)
        if not isinstance(model_row, dict):
            failures.append(f"missing_model_row:{key[0]}:{key[1]}")
            continue
        parsed = _parse_prompt(str(gemma_row.get("prompt") or ""))
        choice_map = parsed["choice_map"]
        target = str(model_row.get("target") or "")
        pred = str(model_row.get("pred") or "")
        record = {
            "row_id": key[0],
            "split": key[1],
            "target_label": target,
            "target_surface": choice_map.get(target),
            "prediction_label_100m": pred,
            "prediction_surface_100m": choice_map.get(pred),
            "prediction_correct_100m": bool(model_row.get("correct")),
            "confidence_100m": model_row.get("confidence"),
            "margin_100m": model_row.get("margin"),
            "top1_label_100m": model_row.get("top1_label"),
            "top2_label_100m": model_row.get("top2_label"),
            "predicted_label_gemma": gemma_row.get("predicted_label"),
            "prediction_correct_gemma": bool(gemma_row.get("correct")),
            "visible_locality_resolution": parsed["visible_locality_resolution"],
            "web_surface_disambiguator": parsed["web_surface_disambiguator"],
        }
        records.append(record)

    by_target: dict[str, dict[str, Any]] = {}
    for record in records:
        surface = str(record.get("target_surface") or "unknown")
        bucket = by_target.setdefault(surface, {"rows": 0, "correct_100m": 0, "correct_gemma": 0, "wrong_predictions_100m": {}})
        bucket["rows"] += 1
        bucket["correct_100m"] += 1 if record["prediction_correct_100m"] else 0
        bucket["correct_gemma"] += 1 if record["prediction_correct_gemma"] else 0
        if not record["prediction_correct_100m"]:
            pred_surface = str(record.get("prediction_surface_100m") or "unknown")
            bucket["wrong_predictions_100m"][pred_surface] = bucket["wrong_predictions_100m"].get(pred_surface, 0) + 1

    wrong_rows = [row for row in records if not row["prediction_correct_100m"]]
    avg_confidence = sum(float(row["confidence_100m"]) for row in records) / len(records) if records else 0.0
    avg_margin_wrong = sum(float(row["margin_100m"]) for row in wrong_rows) / len(wrong_rows) if wrong_rows else 0.0

    metrics = {
        "web_rows_total": len(records),
        "web_correct_100m": sum(1 for row in records if row["prediction_correct_100m"]),
        "web_correct_gemma": sum(1 for row in records if row["prediction_correct_gemma"]),
        "web_accuracy_100m": sum(1 for row in records if row["prediction_correct_100m"]) / len(records) if records else 0.0,
        "web_accuracy_gemma": sum(1 for row in records if row["prediction_correct_gemma"]) / len(records) if records else 0.0,
        "web_avg_confidence_100m": avg_confidence,
        "web_avg_margin_wrong_100m": avg_margin_wrong,
        "surface_types_with_zero_100m_hits": sorted([surface for surface, bucket in by_target.items() if bucket["correct_100m"] == 0]),
        "surface_types_with_nonzero_100m_hits": sorted([surface for surface, bucket in by_target.items() if bucket["correct_100m"] > 0]),
        "strict_exact_100m": comparison.get("comparisons", {}).get("web_js_ts_html:strict_eval", {}).get("hundred_m_exact"),
    }

    if metrics["web_rows_total"] != 8:
        failures.append("web_rows_total_not_8")
    if metrics["web_correct_100m"] != 2:
        failures.append("web_correct_100m_not_2")
    if metrics["web_correct_gemma"] != 0:
        failures.append("web_correct_gemma_not_0")

    training_actions = [
        {
            "priority": 1,
            "action": "Increase valid web-specific supervision for test-surface versus implementation-surface disambiguation.",
            "why": "The current packet misses every `test_surface` row while symbol-owner rows are the only stable success case.",
        },
        {
            "priority": 2,
            "action": "Add more web rows where entrypoint/startup evidence must beat file-level and symbol-level distractors.",
            "why": "The model misses entrypoint-or-invocation rows and often drifts toward implementation or configuration alternatives with tiny margins.",
        },
        {
            "priority": 3,
            "action": "Treat the web slice as ambiguity-sensitive rather than shortcut-driven and target sharper label separation, not more generic anti-cheat hardening.",
            "why": "Wrong predictions are low-margin and near-uniform rather than high-confidence shortcut collapses.",
        },
    ]

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "by_target_surface": by_target,
        "web_rows": records,
        "training_actions": training_actions,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_atlas()
    ATLAS.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this atlas to build the next valid web_js_ts_html edit-localization refresh around test-surface, entrypoint-surface, and file-responsibility disambiguation instead of adding more generic web rows."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"atlas": display(ATLAS), "doc": display(DOC)},
        "decision": "Materialized a web-specific weighted edit-localization failure atlas that shows the current 100M model only reliably solves symbol-owner rows while missing test-surface, entrypoint, and file-responsibility web cases with low-margin confusion.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9943 Web Weighted Edit Localization Failure Atlas",
        "",
        f"Passed: `{summary['passed']}`",
        f"Web rows total: `{built['metrics']['web_rows_total']}`",
        f"Web accuracy 100M: `{built['metrics']['web_accuracy_100m']}`",
        f"Web accuracy Gemma: `{built['metrics']['web_accuracy_gemma']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
