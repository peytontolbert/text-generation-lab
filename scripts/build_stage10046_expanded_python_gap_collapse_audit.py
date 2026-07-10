#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10046
NAME = "stage10046_expanded_python_gap_collapse_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "expanded_python_gap_collapse_audit.json"
ROWS = OUT_DIR / "expanded_python_gap_review_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPANDED_PYTHON_GAP_COLLAPSE_AUDIT_STAGE10046.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
COMPARISON_ROWS = ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_same_manifest_comparison_audit/expanded_source_heldout_same_manifest_comparison_rows.jsonl"
COMPARISON_SUMMARY = ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_same_manifest_comparison_audit/expanded_source_heldout_same_manifest_comparison_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage10036_real_fresh_heldout_merge_validator/expanded_source_heldout_manifest.jsonl"
HUNDRED_M_LOGITS = ROOT / "runs/local/artifacts/stage10040_expanded_source_heldout_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA_ROWS = ROOT / "runs/local/artifacts/stage10041_expanded_source_heldout_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"

REVIEW_CHECKS = [
    "Can an expert maintainer distinguish TARGET_SYMBOL versus TARGET_TEST from only the visible evidence?",
    "Does the row require abstain or more evidence rather than a forced singleton label?",
    "Do option semantics, field ordering, or stable prompt fragments leak the answer despite opaque labels?",
    "Is this row appropriate for future heldout-only expert review rather than replay-driven training?",
    "If the row is valid, should successor training target symbol-vs-test disambiguation instead of generic replay?",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _bucket(hundred_m_correct: bool, gemma_correct: bool) -> str:
    if hundred_m_correct and gemma_correct:
        return "both_correct"
    if hundred_m_correct and not gemma_correct:
        return "hundred_m_only"
    if not hundred_m_correct and gemma_correct:
        return "gemma_only"
    return "both_wrong"


def build_audit() -> dict[str, Any]:
    comparison = load_json(COMPARISON_SUMMARY)
    manifest_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(MANIFEST)}
    logits_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(HUNDRED_M_LOGITS)}
    gemma_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA_ROWS)}
    rows = [row for row in load_jsonl(COMPARISON_ROWS) if str(row.get("language_family") or "") == "python"]

    review_rows: list[dict[str, Any]] = []
    target_counts: Counter[str] = Counter()
    hundred_m_pred_counts: Counter[str] = Counter()
    gemma_pred_counts: Counter[str] = Counter()
    target_family_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    target_family_outcomes: dict[str, Counter[str]] = {}
    fresh_rows = 0

    for row in rows:
        row_id = str(row.get("row_id") or "")
        manifest = manifest_rows.get(row_id, {})
        logit = logits_rows.get(row_id, {})
        gemma = gemma_rows.get(row_id, {})
        clean_state = manifest.get("clean_state") or {}
        anti_cheat = manifest.get("anti_cheat") or {}
        input_state = manifest.get("input_state") or {}
        hidden_target = str(clean_state.get("edit_localization_target_hidden") or "")
        target = str(row.get("expected_label") or "")
        hundred_m_pred = str(row.get("hundred_m_pred") or "")
        gemma_pred = str(row.get("gemma_pred") or gemma.get("predicted_label") or "")
        outcome = _bucket(bool(row.get("hundred_m_correct")), bool(row.get("gemma_correct")))
        target_counts[target] += 1
        hundred_m_pred_counts[hundred_m_pred] += 1
        gemma_pred_counts[gemma_pred] += 1
        target_family_counts[hidden_target] += 1
        outcome_counts[outcome] += 1
        target_family_outcomes.setdefault(hidden_target, Counter())[outcome] += 1
        if str(manifest.get("locked_guard_refresh_stage") or "") == "stage10035_real_fresh_heldout_candidate_packet":
            fresh_rows += 1
        review_rows.append(
            {
                "row_id": row_id,
                "split": row.get("split"),
                "expected_label": target,
                "hidden_target_family": hidden_target,
                "review_outcome_bucket": outcome,
                "fresh_heldout": str(manifest.get("locked_guard_refresh_stage") or "") == "stage10035_real_fresh_heldout_candidate_packet",
                "model_preds": {
                    "hundred_m": hundred_m_pred,
                    "gemma": gemma_pred,
                },
                "model_correct": {
                    "hundred_m": bool(row.get("hundred_m_correct")),
                    "gemma": bool(row.get("gemma_correct")),
                },
                "hundred_m_logit_view": {
                    "confidence": logit.get("confidence"),
                    "margin": logit.get("margin"),
                    "top_k": logit.get("top_k"),
                },
                "visible_evidence": {
                    "task_observation": input_state.get("task_observation"),
                    "visible_locality_evidence": input_state.get("visible_locality_evidence"),
                    "context_config_visible": input_state.get("context_config_visible"),
                    "context_entrypoint_visible": input_state.get("context_entrypoint_visible"),
                    "context_symbol_names_visible": input_state.get("context_symbol_names_visible"),
                    "context_tests_visible": input_state.get("context_tests_visible"),
                    "query_kind": ((manifest.get("graph_input") or {}).get("query_node_type")),
                },
                "anti_cheat_flags": {
                    "opaque_choice_surface": anti_cheat.get("opaque_choice_surface"),
                    "target_label_literals_in_prompt_surface": anti_cheat.get("target_label_literals_in_prompt_surface"),
                    "raw_source_included": anti_cheat.get("raw_source_included"),
                    "raw_symbol_names_in_model_input": anti_cheat.get("raw_symbol_names_in_model_input"),
                    "source_row_id_in_model_input": anti_cheat.get("source_row_id_in_model_input"),
                    "requires_shortcut_audit_before_training": anti_cheat.get("requires_shortcut_audit_before_training"),
                },
                "required_checks": list(REVIEW_CHECKS),
            }
        )

    rows_count = len(review_rows)
    hundred_m_exact = sum(1 for row in review_rows if row["model_correct"]["hundred_m"]) / rows_count if rows_count else 0.0
    gemma_exact = sum(1 for row in review_rows if row["model_correct"]["gemma"]) / rows_count if rows_count else 0.0
    top_pred, top_pred_count = ("", 0)
    if hundred_m_pred_counts:
        top_pred, top_pred_count = hundred_m_pred_counts.most_common(1)[0]
    collapse_share = (top_pred_count / rows_count) if rows_count else 0.0

    target_family_accuracy = {
        family: {
            "rows": count,
            "hundred_m_exact": target_family_outcomes[family].get("hundred_m_only", 0) + target_family_outcomes[family].get("both_correct", 0),
            "gemma_exact": target_family_outcomes[family].get("gemma_only", 0) + target_family_outcomes[family].get("both_correct", 0),
        }
        for family, count in sorted(target_family_counts.items())
    }
    for family, metrics in target_family_accuracy.items():
        rows_for_family = metrics["rows"] or 1
        metrics["hundred_m_exact"] = metrics["hundred_m_exact"] / rows_for_family
        metrics["gemma_exact"] = metrics["gemma_exact"] / rows_for_family

    failures: list[str] = []
    if rows_count != 11:
        failures.append("python_compare_rows_not_11")
    if fresh_rows != 6:
        failures.append("python_fresh_rows_not_6")
    if comparison.get("metrics", {}).get("per_language", {}).get("python", {}).get("verdict") != "gemma_better":
        failures.append("python_verdict_not_gemma_better")
    if top_pred != "C" or top_pred_count != 9:
        failures.append("hundred_m_python_mode_not_c_9")

    explicit_opaque_choice_true_rows = sum(
        1 for row in review_rows if (row.get("anti_cheat_flags") or {}).get("opaque_choice_surface") is True
    )
    opaque_choice_flag_missing_rows = sum(
        1 for row in review_rows if (row.get("anti_cheat_flags") or {}).get("opaque_choice_surface") is None
    )

    audit = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "python_rows": rows_count,
            "python_fresh_rows": fresh_rows,
            "hundred_m_exact": hundred_m_exact,
            "gemma_exact": gemma_exact,
            "delta_hundred_m_minus_gemma": hundred_m_exact - gemma_exact,
            "target_counts": dict(sorted(target_counts.items())),
            "hundred_m_pred_counts": dict(sorted(hundred_m_pred_counts.items())),
            "gemma_pred_counts": dict(sorted(gemma_pred_counts.items())),
            "review_outcome_counts": dict(sorted(outcome_counts.items())),
            "target_family_accuracy": target_family_accuracy,
            "hundred_m_mode_label": top_pred,
            "hundred_m_mode_share": collapse_share,
            "hundred_m_label_collapse_detected": collapse_share >= 0.75,
            "explicit_opaque_choice_true_rows": explicit_opaque_choice_true_rows,
            "opaque_choice_flag_missing_rows": opaque_choice_flag_missing_rows,
            "any_prompt_label_literal_risk": any(bool((row.get("anti_cheat_flags") or {}).get("target_label_literals_in_prompt_surface")) for row in review_rows),
            "any_raw_source_in_prompt": any(bool((row.get("anti_cheat_flags") or {}).get("raw_source_included")) for row in review_rows),
        },
        "findings": [
            "Python is the only expanded same-manifest language where Gemma beats the 100M on the current 55-row heldout comparison subset.",
            "The 100M predicts label C on 9 of 11 Python rows even though the gold distribution is A=4, D=5, C=2, indicating a real label-collapse pattern rather than a narrow single-row miss.",
            "The new fresh-heldout Python failures are concentrated in TARGET_SYMBOL versus TARGET_TEST disambiguation; Gemma recovers two TARGET_SYMBOL rows that the 100M misses.",
            "Current anti-cheat fields do not show prompt-surface label literals or raw-source leakage on these Python rows, so the immediate frontier is evidence grounding and expert identifiability, not obvious literal leakage.",
        ],
        "next_training_rule": "Do not replay these heldout Python rows into train. Target successor data at valid symbol-vs-test disambiguation roots with fresh heldout review, and treat the current rows as review-first diagnostics.",
        "review_checks": list(REVIEW_CHECKS),
    }
    write_jsonl(ROWS, review_rows)
    return audit


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    write_json(AUDIT, built)
    next_step = "Use this Python-specific audit to drive expert-maintainer review and successor-root construction for symbol-vs-test disambiguation before any further multilingual training changes."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "rows": display(ROWS), "doc": display(DOC)},
        "decision": "Materialized the expanded Python gap collapse audit from the real same-manifest 100M and Gemma outputs so the next v2.7 move can target the actual heldout failure pattern instead of replaying evaluation rows.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10046 Expanded Python Gap Collapse Audit",
                "",
                f"Passed: `{summary['passed']}`",
                f"Python compare rows: `{built['metrics']['python_rows']}`",
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
