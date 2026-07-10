#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10055
NAME = "stage10055_mixed_fresh_source_multilingual_same_manifest_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "mixed_fresh_source_multilingual_same_manifest_comparison_audit.json"
ROWS = OUT_DIR / "mixed_fresh_source_multilingual_same_manifest_comparison_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MIXED_FRESH_SOURCE_MULTILINGUAL_SAME_MANIFEST_COMPARISON_AUDIT_STAGE10055.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10053_mixed_fresh_source_multilingual_successor_packet/mixed_fresh_source_multilingual_successor_manifest.jsonl"
BASELINE_HUNDRED_M = ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
SUCCESSOR_HUNDRED_M = ROOT / "runs/local/artifacts/stage10054_mixed_fresh_source_multilingual_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA = ROOT / "runs/local/artifacts/stage10041_expanded_source_heldout_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"


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


def _language_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    counts: dict[str, list[int]] = {}
    for row in rows:
        language = str(row.get("language_family") or "")
        bucket = counts.setdefault(language, [0, 0])
        bucket[0] += int(bool(row.get(key)))
        bucket[1] += 1
    metrics = {}
    for language, (correct, total) in sorted(counts.items()):
        metrics[language] = {"exact": correct / total if total else 0.0, "rows": total}
    return metrics


def build_audit() -> dict[str, Any]:
    manifest = {
        str(row.get("row_id") or ""): row
        for row in load_jsonl(MANIFEST)
        if str(row.get("split") or "") in {"eval", "strict_eval"}
    }
    baseline = {str(row.get("row_id") or ""): row for row in load_jsonl(BASELINE_HUNDRED_M)}
    successor = {str(row.get("row_id") or ""): row for row in load_jsonl(SUCCESSOR_HUNDRED_M)}
    gemma = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA)}
    failures: list[str] = []

    shared_ids = sorted(set(manifest) & set(successor) & set(gemma))
    comparisons: list[dict[str, Any]] = []
    for row_id in shared_ids:
        source = manifest[row_id]
        succ = successor[row_id]
        gm = gemma[row_id]
        base = baseline.get(row_id, {})
        comparisons.append(
            {
                "row_id": row_id,
                "language_family": source.get("language_family"),
                "split": source.get("split"),
                "expected_label": succ.get("target"),
                "baseline_hundred_m_pred": base.get("pred"),
                "baseline_hundred_m_correct": bool(base.get("correct")),
                "successor_hundred_m_pred": succ.get("pred"),
                "successor_hundred_m_correct": bool(succ.get("correct")),
                "gemma_pred": gm.get("predicted_label"),
                "gemma_correct": bool(gm.get("correct")),
            }
        )

    successor_by_language = _language_metrics(comparisons, "successor_hundred_m_correct")
    baseline_by_language = _language_metrics(comparisons, "baseline_hundred_m_correct")
    gemma_by_language = _language_metrics(comparisons, "gemma_correct")

    per_language: dict[str, dict[str, Any]] = {}
    wins_100m = wins_gemma = ties = 0
    for language in sorted(successor_by_language):
        succ_exact = successor_by_language[language]["exact"]
        base_exact = baseline_by_language.get(language, {}).get("exact", 0.0)
        gemma_exact = gemma_by_language.get(language, {}).get("exact", 0.0)
        if succ_exact > gemma_exact:
            verdict = "100m_better"
            wins_100m += 1
        elif gemma_exact > succ_exact:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            verdict = "tie"
            ties += 1
        per_language[language] = {
            "baseline_hundred_m_exact": base_exact,
            "successor_hundred_m_exact": succ_exact,
            "gemma_exact": gemma_exact,
            "successor_delta_vs_baseline": succ_exact - base_exact,
            "successor_delta_vs_gemma": succ_exact - gemma_exact,
            "rows": successor_by_language[language]["rows"],
            "verdict": verdict,
        }

    macro_successor = sum(v["successor_hundred_m_exact"] for v in per_language.values()) / len(per_language) if per_language else 0.0
    macro_baseline = sum(v["baseline_hundred_m_exact"] for v in per_language.values()) / len(per_language) if per_language else 0.0
    macro_gemma = sum(v["gemma_exact"] for v in per_language.values()) / len(per_language) if per_language else 0.0

    if len(shared_ids) != len(successor):
        failures.append("shared_ids_not_equal_to_successor_rows")
    if len(shared_ids) != len(gemma):
        failures.append("shared_ids_not_equal_to_gemma_rows")
    if len(shared_ids) != 55:
        failures.append("shared_ids_not_equal_to_55")
    if len(per_language) != 4:
        failures.append("per_language_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "rows_successor_present": len(successor),
            "rows_gemma_present": len(gemma),
            "shared_rows": len(shared_ids),
            "comparison_rows": len(comparisons),
            "macro_exact_successor_100m": macro_successor,
            "macro_exact_baseline_100m": macro_baseline,
            "macro_exact_gemma": macro_gemma,
            "macro_delta_successor_minus_baseline": macro_successor - macro_baseline,
            "macro_delta_successor_minus_gemma": macro_successor - macro_gemma,
            "wins_100m": wins_100m,
            "wins_gemma": wins_gemma,
            "ties": ties,
            "per_language": per_language,
        },
        "rows": comparisons,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps({"stage": STAGE, "name": NAME, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS, built["rows"])
    next_step = "Use this audit to decide whether the mixed fresh-source multilingual successor restores the honest macro frontier while preserving the stage10047 Python gain against Gemma."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the same-manifest comparison audit for the mixed fresh-source multilingual successor run so the resulting 100M outputs can be judged directly against stage10040 and the fixed Gemma comparator.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10055 Mixed Fresh Source Multilingual Same Manifest Comparison Audit",
                "",
                f"Passed: `{summary['passed']}`",
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
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
