#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9981
NAME = "stage9981_selective_replay_outcome_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "selective_replay_outcome_audit.json"
DOC = ROOT / "docs" / "SELECTIVE_REPLAY_OUTCOME_AUDIT_STAGE9981.md"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BASELINE = ROOT / "runs/local/artifacts/stage9965_edit_localization_blended_weak_language_target100m_probe/edit_localization_probe/execution_result.json"
BROAD = ROOT / "runs/local/artifacts/stage9977_real_loss_successor_target100m_probe/edit_localization_probe/execution_result.json"
SELECTIVE = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/execution_result.json"
BASELINE_CELLS = ROOT / "runs/local/artifacts/stage9965_edit_localization_blended_weak_language_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
BROAD_CELLS = ROOT / "runs/local/artifacts/stage9977_real_loss_successor_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
SELECTIVE_CELLS = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/field_exact_by_cell.json"
SELECTIVE_MANIFEST = ROOT / "runs/local/artifacts/stage9979_selective_gemma_advantage_successor_request/edit_localization_manifest.jsonl"
SELECTIVE_LOGITS = ROOT / "runs/local/artifacts/stage9980_selective_gemma_advantage_target100m_probe/edit_localization_probe/row_field_logits.jsonl"


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


def _aggregate_metrics(path: Path) -> dict[str, float]:
    data = load_json(path)
    eval_block = (((data.get("eval") or {}).get("eval")) or {})
    strict_block = (((data.get("eval") or {}).get("strict_eval")) or {})
    return {
        "eval_exact": float((((eval_block.get("field_exact") or {}).get("edit_localization") or {}).get("exact") or 0.0)),
        "strict_exact": float((((strict_block.get("field_exact") or {}).get("edit_localization") or {}).get("exact") or 0.0)),
        "eval_rows": int(eval_block.get("rows") or 0),
        "strict_rows": int(strict_block.get("rows") or 0),
    }


def _language_cells(path: Path) -> dict[str, dict[str, float]]:
    data = load_json(path)
    cells = ((data.get("edit_localization") or {}) if isinstance(data, dict) else {})
    out: dict[str, dict[str, float]] = {}
    for key, value in cells.items():
        language = str(key).split("::", 1)[0]
        out[language] = {
            "exact": float((value or {}).get("exact") or 0.0),
            "rows": int((value or {}).get("rows") or 0),
            "correct": int((value or {}).get("correct") or 0),
        }
    return out


def _recovery_breakdown() -> dict[str, dict[str, float]]:
    manifest_rows = {str(row.get("row_id")): row for row in load_jsonl(SELECTIVE_MANIFEST)}
    counts: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in load_jsonl(SELECTIVE_LOGITS):
        row_id = str(row.get("row_id"))
        manifest = manifest_rows.get(row_id)
        if not isinstance(manifest, dict):
            continue
        key = (
            str(manifest.get("language_family") or ""),
            str(manifest.get("recovery_reason") or "anchor"),
            str(row.get("split") or ""),
        )
        counts[key][0] += int(bool(row.get("correct")))
        counts[key][1] += 1
    return {
        f"{language}|{reason}|{split}": {
            "correct": correct,
            "rows": rows,
            "exact": (correct / rows) if rows else 0.0,
        }
        for (language, reason, split), (correct, rows) in sorted(counts.items())
    }


def build_audit() -> dict[str, Any]:
    baseline = _aggregate_metrics(BASELINE)
    broad = _aggregate_metrics(BROAD)
    selective = _aggregate_metrics(SELECTIVE)
    baseline_cells = _language_cells(BASELINE_CELLS)
    broad_cells = _language_cells(BROAD_CELLS)
    selective_cells = _language_cells(SELECTIVE_CELLS)
    recovery = _recovery_breakdown()
    languages = sorted(set(baseline_cells) | set(broad_cells) | set(selective_cells))
    per_language = {}
    for language in languages:
        base_exact = float((baseline_cells.get(language) or {}).get("exact") or 0.0)
        broad_exact = float((broad_cells.get(language) or {}).get("exact") or 0.0)
        selective_exact = float((selective_cells.get(language) or {}).get("exact") or 0.0)
        per_language[language] = {
            "baseline_exact": base_exact,
            "broad_replay_exact": broad_exact,
            "selective_replay_exact": selective_exact,
            "delta_vs_baseline": selective_exact - base_exact,
            "delta_vs_broad_replay": selective_exact - broad_exact,
            "rows": int((selective_cells.get(language) or {}).get("rows") or 0),
        }
    failures: list[str] = []
    if not (selective["eval_exact"] > broad["eval_exact"]):
        failures.append("selective_eval_not_above_broad")
    if not (selective["strict_exact"] > broad["strict_exact"]):
        failures.append("selective_strict_not_above_broad")
    if not (selective["eval_exact"] < baseline["eval_exact"]):
        failures.append("selective_eval_not_below_baseline")
    if not (selective["strict_exact"] < baseline["strict_exact"]):
        failures.append("selective_strict_not_below_baseline")
    for required_zero_key in (
        "python|gemma_advantage_only|eval",
        "python|gemma_advantage_only|strict_eval",
        "c_cpp|gemma_advantage_only|eval",
        "c_cpp|gemma_advantage_only|strict_eval",
    ):
        if round(float((recovery.get(required_zero_key) or {}).get("exact") or 0.0), 8) != 0.0:
            failures.append(f"expected_zero_recovery_exact:{required_zero_key}")
    passed = not failures
    return {
        "passed": passed,
        "failures": failures,
        "aggregate": {
            "baseline": baseline,
            "broad_replay": broad,
            "selective_replay": selective,
            "selective_minus_broad": {
                "eval_exact": selective["eval_exact"] - broad["eval_exact"],
                "strict_exact": selective["strict_exact"] - broad["strict_exact"],
            },
            "selective_minus_baseline": {
                "eval_exact": selective["eval_exact"] - baseline["eval_exact"],
                "strict_exact": selective["strict_exact"] - baseline["strict_exact"],
            },
        },
        "per_language": per_language,
        "recovery_row_breakdown": recovery,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Stop treating the 11 Gemma-advantage rows as ordinary positive replay data; route them into expert-maintainer "
        "and anti-cheat review, keep the web and rust anchors intact, and only consider new training after the review packet "
        "decides whether the python and c_cpp rows are identifiable expert-maintainer tasks or invalid/eval-hack candidates."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "metrics": {
            "aggregate": audit["aggregate"],
            "per_language": audit["per_language"],
            "recovery_row_breakdown": audit["recovery_row_breakdown"],
            "failures": audit["failures"],
        },
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": (
            "Selective replay recovered part of the broad-replay regression without restoring the original stage9965 baseline, "
            "and none of the 11 Gemma-advantage review rows became correct under the replayed stage9980 run."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9981 Selective Replay Outcome Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Decision: {summary['decision']}",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
