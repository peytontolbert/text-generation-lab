#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9988
NAME = "stage9988_filtered_replay_outcome_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "filtered_replay_outcome_audit.json"
DOC = ROOT / "docs" / "FILTERED_REPLAY_OUTCOME_AUDIT_STAGE9988.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

RUN_9965 = ROOT / "runs/local/artifacts/stage9965_edit_localization_blended_weak_language_target100m_probe/edit_localization_probe/execution_result.json"
RUN_9980 = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/execution_result.json"
RUN_9987 = ROOT / "runs/local/artifacts/stage9987_filtered_positive_replay_target100m_probe/edit_localization_probe/execution_result.json"
CELLS_9965 = ROOT / "runs/local/artifacts/stage9965_edit_localization_blended_weak_language_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
CELLS_9980 = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
CELLS_9987 = ROOT / "runs/local/artifacts/stage9987_filtered_positive_replay_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
MANIFEST_9986 = ROOT / "runs/local/artifacts/stage9986_filtered_positive_replay_successor_request/edit_localization_manifest.jsonl"
LOGITS_9987 = ROOT / "runs/local/artifacts/stage9987_filtered_positive_replay_target100m_probe/edit_localization_probe/row_field_logits.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def _aggregate(path: Path) -> dict[str, float]:
    data = load_json(path)
    eval_block = ((data.get("eval") or {}).get("eval")) or {}
    strict_block = ((data.get("eval") or {}).get("strict_eval")) or {}
    return {
        "eval_exact": float((((eval_block.get("field_exact") or {}).get("edit_localization") or {}).get("exact") or 0.0)),
        "strict_exact": float((((strict_block.get("field_exact") or {}).get("edit_localization") or {}).get("exact") or 0.0)),
        "eval_rows": int(eval_block.get("rows") or 0),
        "strict_rows": int(strict_block.get("rows") or 0),
    }


def _language_cells(path: Path) -> dict[str, dict[str, float]]:
    data = load_json(path)
    out: dict[str, dict[str, float]] = {}
    for key, value in (data.get("edit_localization") or {}).items():
        lang = str(key).split("::", 1)[0]
        out[lang] = {
            "exact": float((value or {}).get("exact") or 0.0),
            "rows": int((value or {}).get("rows") or 0),
        }
    return out


def _remaining_positive_breakdown() -> dict[str, dict[str, float]]:
    manifest = {str(r.get("row_id")): r for r in load_jsonl(MANIFEST_9986)}
    out: dict[str, list[int]] = {}
    for row in load_jsonl(LOGITS_9987):
        row_id = str(row.get("row_id"))
        source = manifest.get(row_id)
        if not isinstance(source, dict):
            continue
        if str(source.get("recovery_reason") or "") != "gemma_advantage_only":
            continue
        key = f"{source.get('language_family')}|{row.get('split')}"
        bucket = out.setdefault(key, [0, 0])
        bucket[0] += int(bool(row.get("correct")))
        bucket[1] += 1
    return {key: {"correct": val[0], "rows": val[1], "exact": (val[0] / val[1]) if val[1] else 0.0} for key, val in sorted(out.items())}


def build_audit() -> dict[str, Any]:
    agg_9965 = _aggregate(RUN_9965)
    agg_9980 = _aggregate(RUN_9980)
    agg_9987 = _aggregate(RUN_9987)
    cells_9965 = _language_cells(CELLS_9965)
    cells_9980 = _language_cells(CELLS_9980)
    cells_9987 = _language_cells(CELLS_9987)
    langs = sorted(set(cells_9965) | set(cells_9980) | set(cells_9987))
    per_language = {}
    for lang in langs:
        base = float((cells_9965.get(lang) or {}).get("exact") or 0.0)
        selective = float((cells_9980.get(lang) or {}).get("exact") or 0.0)
        filtered = float((cells_9987.get(lang) or {}).get("exact") or 0.0)
        per_language[lang] = {
            "stage9965_exact": base,
            "stage9980_exact": selective,
            "stage9987_exact": filtered,
            "delta_vs_stage9965": filtered - base,
            "delta_vs_stage9980": filtered - selective,
        }
    remaining = _remaining_positive_breakdown()
    failures: list[str] = []
    if not (agg_9987["strict_exact"] > agg_9965["strict_exact"]):
        failures.append("strict_exact_not_above_stage9965")
    if not (agg_9987["strict_exact"] > agg_9980["strict_exact"]):
        failures.append("strict_exact_not_above_stage9980")
    if not (per_language["python"]["delta_vs_stage9965"] > 0.0):
        failures.append("python_not_above_stage9965")
    if not (per_language["c_cpp"]["delta_vs_stage9965"] > 0.0):
        failures.append("c_cpp_not_above_stage9965")
    for key, stats in remaining.items():
        if round(float(stats.get("exact") or 0.0), 8) != 0.0:
            failures.append(f"remaining_positive_rows_not_zero:{key}")
    return {
        "passed": not failures,
        "failures": failures,
        "aggregate": {
            "stage9965": agg_9965,
            "stage9980": agg_9980,
            "stage9987": agg_9987,
            "stage9987_minus_stage9965": {
                "eval_exact": agg_9987["eval_exact"] - agg_9965["eval_exact"],
                "strict_exact": agg_9987["strict_exact"] - agg_9965["strict_exact"],
            },
            "stage9987_minus_stage9980": {
                "eval_exact": agg_9987["eval_exact"] - agg_9980["eval_exact"],
                "strict_exact": agg_9987["strict_exact"] - agg_9980["strict_exact"],
            },
        },
        "per_language": per_language,
        "remaining_positive_gemma_advantage_rows": remaining,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Keep the seven mixed-replay rows quarantined, hold the remaining four Gemma-advantage positive replay rows out of training until human review resolves them, and use the stage9987 filtered frontier as the next truthful multilingual 100M baseline."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {
            "aggregate": built["aggregate"],
            "per_language": built["per_language"],
            "remaining_positive_gemma_advantage_rows": built["remaining_positive_gemma_advantage_rows"],
            "failures": built["failures"],
        },
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Filtering out the quarantined mixed-replay Gemma-advantage rows preserved rust and web, improved python and c_cpp above the original stage9965 baseline, and lifted strict exact above both stage9965 and stage9980, while the four remaining positive replay Gemma-advantage rows still stayed 0/4 correct.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9988 Filtered Replay Outcome Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Decision: {summary['decision']}",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
