#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9996
NAME = "stage9996_source_heldout_same_manifest_comparison_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ROWS = OUT_DIR / "source_heldout_comparison_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_HELDOUT_SAME_MANIFEST_COMPARISON_AUDIT_STAGE9996.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"
HUNDRED_M = ROOT / "runs/local/artifacts/stage9987_filtered_positive_replay_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA = ROOT / "runs/local/artifacts/stage9990_filtered_same_manifest_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"


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
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def build_audit() -> dict[str, Any]:
    manifest_rows = load_jsonl(MANIFEST)
    hundred_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(HUNDRED_M)}
    gemma_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA)}
    train_sources = {str(row.get("source_row_id") or "") for row in manifest_rows if row.get("split") == "train"}
    comparison_rows: list[dict[str, Any]] = []
    per_language: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "correct_100m": 0, "correct_gemma": 0})
    failures: list[str] = []

    for row in manifest_rows:
        split = str(row.get("split") or "")
        source_row_id = str(row.get("source_row_id") or "")
        if split not in {"eval", "strict_eval"} or source_row_id in train_sources:
            continue
        row_id = str(row.get("row_id") or "")
        hm = hundred_rows.get(row_id)
        gm = gemma_rows.get(row_id)
        if not isinstance(hm, dict):
            failures.append(f"missing_100m:{row_id}")
            continue
        if not isinstance(gm, dict):
            failures.append(f"missing_gemma:{row_id}")
            continue
        language = str(row.get("language_family") or "")
        hm_correct = bool(hm.get("correct"))
        gm_correct = bool(gm.get("correct"))
        comparison_rows.append(
            {
                "row_id": row_id,
                "split": split,
                "language_family": language,
                "source_row_id": source_row_id,
                "counterfactual_role": row.get("counterfactual_role"),
                "hundred_m_correct": hm_correct,
                "hundred_m_pred": hm.get("pred"),
                "gemma_correct": gm_correct,
                "gemma_pred": gm.get("predicted_label"),
                "target": hm.get("target"),
                "task_observation": (row.get("input_state") or {}).get("task_observation"),
                "visible_locality_evidence": (row.get("input_state") or {}).get("visible_locality_evidence"),
            }
        )
        stats = per_language[language]
        stats["rows"] += 1
        stats["correct_100m"] += int(hm_correct)
        stats["correct_gemma"] += int(gm_correct)

    write_jsonl(ROWS, comparison_rows)
    macro_100m = 0.0
    macro_gemma = 0.0
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    per_language_summary: dict[str, Any] = {}
    for language, stats in sorted(per_language.items()):
        rows = int(stats["rows"])
        exact_100m = stats["correct_100m"] / rows if rows else 0.0
        exact_gemma = stats["correct_gemma"] / rows if rows else 0.0
        verdict = "tie"
        if exact_100m > exact_gemma:
            verdict = "100m_better"
            wins_100m += 1
        elif exact_gemma > exact_100m:
            verdict = "gemma_better"
            wins_gemma += 1
        else:
            ties += 1
        macro_100m += exact_100m
        macro_gemma += exact_gemma
        per_language_summary[language] = {
            "rows": rows,
            "exact_100m": exact_100m,
            "exact_gemma": exact_gemma,
            "delta_100m_minus_gemma": exact_100m - exact_gemma,
            "verdict": verdict,
        }

    language_count = len(per_language_summary)
    metrics = {
        "comparison_rows": len(comparison_rows),
        "languages_compared": language_count,
        "macro_exact_100m": (macro_100m / language_count) if language_count else 0.0,
        "macro_exact_gemma": (macro_gemma / language_count) if language_count else 0.0,
        "macro_delta_100m_minus_gemma": ((macro_100m - macro_gemma) / language_count) if language_count else 0.0,
        "micro_exact_100m": (sum(int(row["hundred_m_correct"]) for row in comparison_rows) / len(comparison_rows)) if comparison_rows else 0.0,
        "micro_exact_gemma": (sum(int(row["gemma_correct"]) for row in comparison_rows) / len(comparison_rows)) if comparison_rows else 0.0,
        "wins_100m": wins_100m,
        "wins_gemma": wins_gemma,
        "ties": ties,
        "rows_by_language": dict(sorted(Counter(str(row["language_family"] or "") for row in comparison_rows).items())),
        "rows_by_split": dict(sorted(Counter(str(row["split"] or "") for row in comparison_rows).items())),
        "per_language": per_language_summary,
    }
    if metrics["comparison_rows"] <= 0:
        failures.append("expected_source_heldout_rows")
    return {"passed": not failures, "failures": failures, "metrics": metrics}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    next_step = "Treat this source-heldout comparison as the honest current baseline, then rebuild future eval manifests so Python and c_cpp have more independent heldout roots."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "artifacts": {"rows": display(ROWS), "doc": display(DOC)},
        "decision": "Recomputed the 100M-versus-Gemma comparison on the source-heldout subset that excludes eval rows whose source roots also appear in train.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9996 Source-Heldout Same-Manifest Comparison Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Comparison rows: `{built['metrics']['comparison_rows']}`",
                f"Macro exact 100M: `{built['metrics']['macro_exact_100m']}`",
                f"Macro exact Gemma: `{built['metrics']['macro_exact_gemma']}`",
                f"Wins: `100M {built['metrics']['wins_100m']}`, `Gemma {built['metrics']['wins_gemma']}`, `ties {built['metrics']['ties']}`",
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
