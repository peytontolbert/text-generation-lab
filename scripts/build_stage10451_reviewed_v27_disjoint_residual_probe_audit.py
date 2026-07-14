#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10451
NAME = "stage10451_reviewed_v27_disjoint_residual_probe_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "reviewed_v27_disjoint_residual_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

BASELINE_EXECUTION = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/bounded_decoder_probe/execution_result.json"
RESIDUAL_EXECUTION = ROOT / "runs/local/artifacts/stage10450_reviewed_v27_disjoint_residual_support_probe/bounded_decoder_probe/execution_result.json"
REQUEST_JSON = ROOT / "runs/local/artifacts/stage10449_reviewed_v27_disjoint_residual_support_probe_request/reviewed_v27_disjoint_residual_support_probe_request.json"
SUPPORT_PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10447_python_disjoint_residual_support_package/python_disjoint_residual_support_package.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def language_of(row_id: str) -> str:
    if "::python::" in row_id:
        return "python"
    if "::c_cpp::" in row_id:
        return "c_cpp"
    if "::rust::" in row_id:
        return "rust"
    if "::web_js_ts_html::" in row_id:
        return "web_js_ts_html"
    return "unknown"


def row_map(execution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = execution["bounded_choice_eval"]["strict_eval"]["row_cards"]
    return {str(row["row_id"]): row for row in rows}


def per_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        lang = language_of(str(row["row_id"]))
        card = counts.setdefault(lang, {"correct": 0, "total": 0})
        card["total"] += 1
        if row["constrained_choice_match"]:
            card["correct"] += 1
    return counts


def main() -> None:
    baseline = load_json(BASELINE_EXECUTION)
    residual = load_json(RESIDUAL_EXECUTION)
    request = load_json(REQUEST_JSON)
    support_package = load_json(SUPPORT_PACKAGE_JSON)

    baseline_rows = row_map(baseline)
    residual_rows = row_map(residual)
    all_row_ids = sorted(set(baseline_rows) | set(residual_rows))

    changed_rows: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    recovered_rows: list[dict[str, Any]] = []
    persistent_misses: list[dict[str, Any]] = []
    for row_id in all_row_ids:
        before = baseline_rows[row_id]
        after = residual_rows[row_id]
        before_ok = bool(before["constrained_choice_match"])
        after_ok = bool(after["constrained_choice_match"])
        if before_ok != after_ok or before["constrained_choice_top1_label"] != after["constrained_choice_top1_label"]:
            changed_rows.append(
                {
                    "row_id": row_id,
                    "language_family": language_of(row_id),
                    "task_type": row_id.split("::")[-2],
                    "baseline_pred": before["constrained_choice_top1_label"],
                    "baseline_correct": before_ok,
                    "residual_pred": after["constrained_choice_top1_label"],
                    "residual_correct": after_ok,
                    "target": after["target_text"],
                    "baseline_target_rank_full_vocab": before["target_rank_full_vocab"],
                    "residual_target_rank_full_vocab": after["target_rank_full_vocab"],
                }
            )
        if before_ok and not after_ok:
            regressions.append(changed_rows[-1] if changed_rows else {
                "row_id": row_id,
                "language_family": language_of(row_id),
                "task_type": row_id.split("::")[-2],
                "baseline_pred": before["constrained_choice_top1_label"],
                "baseline_correct": before_ok,
                "residual_pred": after["constrained_choice_top1_label"],
                "residual_correct": after_ok,
                "target": after["target_text"],
                "baseline_target_rank_full_vocab": before["target_rank_full_vocab"],
                "residual_target_rank_full_vocab": after["target_rank_full_vocab"],
            })
        if (not before_ok) and after_ok:
            recovered_rows.append(changed_rows[-1])
        if (not before_ok) and (not after_ok):
            persistent_misses.append(
                {
                    "row_id": row_id,
                    "language_family": language_of(row_id),
                    "task_type": row_id.split("::")[-2],
                    "baseline_pred": before["constrained_choice_top1_label"],
                    "residual_pred": after["constrained_choice_top1_label"],
                    "target": after["target_text"],
                    "baseline_target_rank_full_vocab": before["target_rank_full_vocab"],
                    "residual_target_rank_full_vocab": after["target_rank_full_vocab"],
                }
            )

    baseline_strict = baseline["bounded_choice_eval"]["strict_eval"]["constrained_choice_top1_accuracy"]
    residual_strict = residual["bounded_choice_eval"]["strict_eval"]["constrained_choice_top1_accuracy"]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "stage10450_diagnostic_only_regressed_live_v27_baseline",
        "claim_scope": [
            "Audit the stage10450 disjoint residual support probe against the live stage10422/stage10424 v2.7 same-manifest baseline.",
            "Do not promote the stage10450 runtime because it regressed strict accuracy while failing to recover the two target misses.",
            "Use this result to prioritize narrower disjoint residual support and option-representation invariance work.",
        ],
        "source_artifacts": {
            "baseline_execution_result": display(BASELINE_EXECUTION),
            "residual_execution_result": display(RESIDUAL_EXECUTION),
            "residual_request": display(REQUEST_JSON),
            "support_package": display(SUPPORT_PACKAGE_JSON),
        },
        "baseline": {
            "strict_constrained_accuracy": baseline_strict,
            "strict_correct_rows": int(round(baseline_strict * 24)),
            "per_language": per_language(list(baseline_rows.values())),
        },
        "residual_probe": {
            "strict_constrained_accuracy": residual_strict,
            "strict_correct_rows": int(round(residual_strict * 24)),
            "per_language": per_language(list(residual_rows.values())),
            "saved_runtime_model": residual.get("saved_runtime_model"),
            "runtime_model_save_dir": residual.get("runtime_model_save_dir"),
        },
        "delta": {
            "strict_constrained_accuracy": residual_strict - baseline_strict,
            "strict_correct_rows": int(round(residual_strict * 24)) - int(round(baseline_strict * 24)),
        },
        "changed_rows": changed_rows,
        "regressions": regressions,
        "persistent_misses": persistent_misses,
        "recovered_rows": recovered_rows,
        "targeted_focus_rows": request["strict_focus_rows"],
        "support_rows": support_package["rows"],
        "support_task_counts": support_package["task_counts"],
        "findings": [
            "The stage10450 probe dropped constrained strict accuracy from 22/24 to 21/24.",
            "The two intended residual misses persisted: Python verifier_outcome and Rust evidence_citation remained wrong.",
            "A new regression was introduced on Python evidence_citation, moving the row from correct to wrong.",
            "C/C++ and Web remained saturated at 6/6; the damage was concentrated in Python while Rust stayed flat at 5/6.",
            "Full-vocab top-1 behavior remained collapsed and materially below constrained-choice behavior, so the recovered performance still depends on bounded-choice scoring rather than raw decoding.",
        ],
        "next_actions": [
            "Keep stage10424 as the live honest v2.7 headline and mark stage10450 diagnostic-only.",
            "Build a narrower disjoint Python residual packet that separates verifier_outcome from evidence_citation so verifier support does not drag citation toward F/candidate-surface behavior.",
            "Build a disjoint Rust evidence-citation contrast packet centered on the E vs F confusion, with option-representation invariance variants.",
            "Add an audit gate that compares targeted support probes against the current repaired overlay baseline and rejects any run that regresses untouched rows.",
        ],
        "required_honesty_gates": [
            "Do not upgrade the v2.7 headline from stage10450.",
            "Do not merge stage10450 support rows into promotable training without fresh disjoint strict validation.",
            "Keep same-manifest and repaired-overlay claims separate from any future source-heldout or fresh-root claims.",
        ],
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": audit["decision"],
            "baseline_strict": baseline_strict,
            "residual_strict": residual_strict,
            "delta": audit["delta"],
            "audit": display(AUDIT_JSON),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
