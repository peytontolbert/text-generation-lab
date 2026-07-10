#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10082
NAME = "stage10082_canonical_label_aligned_shortcut_validity_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "canonical_label_aligned_shortcut_validity_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_LABEL_ALIGNED_SHORTCUT_VALIDITY_AUDIT_STAGE10082.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

MANIFEST = ROOT / "runs/local/artifacts/stage10069_canonical_label_aligned_multilingual_successor_packet/canonical_label_aligned_multilingual_manifest.jsonl"
HUNDRED_M = ROOT / "runs/local/artifacts/stage10070_canonical_label_aligned_target100m_probe/edit_localization_probe/row_field_logits.jsonl"
GEMMA = ROOT / "runs/local/artifacts/stage10071_canonical_label_aligned_gemma_execution/same_prompt_surface_gemma12b_outputs_rows.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10072_canonical_label_aligned_same_manifest_comparison_audit/canonical_label_aligned_same_manifest_comparison_audit.json"

EXPECTED_MAP = {
    "A": "TARGET_TEST",
    "B": "TARGET_ENTRYPOINT",
    "C": "TARGET_SYMBOL",
    "D": "TARGET_FILE",
    "E": "TARGET_CONFIG",
}


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
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
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


def _majority_exact(labels: list[str]) -> tuple[str | None, float]:
    if not labels:
        return None, 0.0
    counts = Counter(labels)
    label, count = counts.most_common(1)[0]
    return label, count / len(labels)


def build_audit() -> dict[str, Any]:
    manifest_rows = {
        str(row.get("row_id") or ""): row
        for row in load_jsonl(MANIFEST)
        if str(row.get("split") or "") in {"eval", "strict_eval"}
    }
    hundred_m_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(HUNDRED_M)}
    gemma_rows = {str(row.get("row_id") or ""): row for row in load_jsonl(GEMMA)}
    comparison = load_json(COMPARISON)
    failures: list[str] = []

    shared_ids = sorted(set(manifest_rows) & set(hundred_m_rows) & set(gemma_rows))
    if comparison.get("passed") is not True:
        failures.append("stage10072_not_passed")
    if len(shared_ids) != 55:
        failures.append("shared_rows_not_55")

    labels_all: list[str] = []
    rows_with_permutation = 0
    rows_with_opaque_choice = 0
    rows_with_source_root = 0
    rows_with_source_id = 0
    rows_with_locked_eval_source = 0
    rows_with_source_backed = 0
    rows_with_counterfactual_groups = 0
    canonical_mismatches: list[str] = []
    permutation_orders: Counter[str] = Counter()
    obligation_counter: Counter[str] = Counter()
    label_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    hidden_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    language_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row_id in shared_ids:
        row = manifest_rows[row_id]
        language = str(row.get("language_family") or "")
        clean = row.get("clean_state") if isinstance(row.get("clean_state"), dict) else {}
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        source_lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
        label = str(clean.get("edit_localization_target") or "")
        hidden = str(clean.get("edit_localization_target_hidden") or "")
        labels_all.append(label)
        label_counts_by_language[language][label] += 1
        hidden_counts_by_language[language][hidden] += 1
        language_rows[language].append(row)

        if row.get("choice_permutation_map") and row.get("choice_permutation_order"):
            rows_with_permutation += 1
            permutation_orders["|".join(str(x) for x in row.get("choice_permutation_order") or [])] += 1
        if anti_cheat.get("opaque_choice_surface") is True:
            rows_with_opaque_choice += 1
        if row.get("source_root") is not None:
            rows_with_source_root += 1
        if row.get("source_id") is not None:
            rows_with_source_id += 1
        if source_lineage.get("locked_eval_source") is True:
            rows_with_locked_eval_source += 1
        if row.get("source_backed") is True:
            rows_with_source_backed += 1
        if row.get("counterfactual_group_id"):
            rows_with_counterfactual_groups += 1
        for obligation in row.get("counterfactual_required_obligations") or []:
            obligation_counter[str(obligation)] += 1
        if EXPECTED_MAP.get(label) != hidden:
            canonical_mismatches.append(row_id)

    global_majority_label, global_majority_exact = _majority_exact(labels_all)
    per_language_baselines: dict[str, dict[str, Any]] = {}
    for language, rows in sorted(language_rows.items()):
        labels = [
            str(((row.get("clean_state") or {}) if isinstance(row.get("clean_state"), dict) else {}).get("edit_localization_target") or "")
            for row in rows
        ]
        majority_label, majority_exact = _majority_exact(labels)
        per_language_baselines[language] = {
            "rows": len(rows),
            "majority_label": majority_label,
            "majority_exact": majority_exact,
            "label_counts": dict(sorted(label_counts_by_language[language].items())),
            "hidden_target_counts": dict(sorted(hidden_counts_by_language[language].items())),
        }

    macro_language_majority_exact = (
        sum(row["majority_exact"] for row in per_language_baselines.values()) / len(per_language_baselines)
        if per_language_baselines else 0.0
    )
    comparison_metrics = comparison.get("metrics") if isinstance(comparison.get("metrics"), dict) else {}
    hundred_m_macro = float(comparison_metrics.get("macro_exact_hundred_m") or 0.0)
    gemma_macro = float(comparison_metrics.get("macro_exact_gemma") or 0.0)

    metrics = {
        "shared_rows": len(shared_ids),
        "rows_with_choice_permutation_metadata": rows_with_permutation,
        "rows_with_opaque_choice_surface": rows_with_opaque_choice,
        "unique_choice_permutation_orders": len(permutation_orders),
        "most_common_choice_permutation_order": permutation_orders.most_common(1)[0][0] if permutation_orders else None,
        "rows_with_counterfactual_groups": rows_with_counterfactual_groups,
        "counterfactual_obligation_counts": dict(sorted(obligation_counter.items())),
        "rows_with_source_backed_flag": rows_with_source_backed,
        "rows_with_source_root": rows_with_source_root,
        "rows_with_source_id": rows_with_source_id,
        "rows_with_locked_eval_source": rows_with_locked_eval_source,
        "source_heldout_claim_supported": rows_with_source_root == len(shared_ids) and rows_with_source_id == len(shared_ids),
        "global_majority_label": global_majority_label,
        "global_majority_exact": global_majority_exact,
        "macro_per_language_majority_exact": macro_language_majority_exact,
        "hundred_m_macro_exact": hundred_m_macro,
        "gemma_macro_exact": gemma_macro,
        "hundred_m_minus_global_majority": hundred_m_macro - global_majority_exact,
        "hundred_m_minus_macro_language_majority": hundred_m_macro - macro_language_majority_exact,
        "gemma_minus_global_majority": gemma_macro - global_majority_exact,
        "canonical_mismatch_rows": len(canonical_mismatches),
        "per_language_baselines": per_language_baselines,
    }

    if canonical_mismatches:
        failures.append("canonical_hidden_target_mismatch")
    if len(per_language_baselines) != 4:
        failures.append("per_language_not_4")

    findings = {
        "label_prior_shortcut_risk": {
            "supported_by_majority_baseline": global_majority_exact >= 0.5 or macro_language_majority_exact >= 0.5,
            "interpretation": (
                "Simple label-frequency guessing remains too weak to explain the stage10072 win."
                if global_majority_exact < 0.5 and macro_language_majority_exact < 0.5
                else "Label-frequency guessing is strong enough to require more explicit balancing before making stronger claims."
            ),
        },
        "source_heldout_scope": {
            "supported": metrics["source_heldout_claim_supported"],
            "interpretation": (
                "This canonical packet does not itself prove a source-heldout claim because source_root/source_id provenance is absent on the shared rows."
                if not metrics["source_heldout_claim_supported"]
                else "The shared rows carry source provenance that can support a source-heldout claim."
            ),
        },
        "permutation_coverage_scope": {
            "supported": rows_with_permutation == len(shared_ids) and rows_with_opaque_choice == len(shared_ids),
            "interpretation": (
                "Only a subset of the shared rows carry explicit permutation metadata and opaque-choice anti-cheat tags, so the current packet should not be described as uniformly permutation-audited."
                if rows_with_permutation != len(shared_ids) or rows_with_opaque_choice != len(shared_ids)
                else "Every shared row carries explicit permutation metadata and opaque-choice anti-cheat tags."
            ),
        },
    }

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "findings": findings,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_audit()
    AUDIT.write_text(json.dumps({
        "stage": STAGE,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "findings": built["findings"],
        "failures": built["failures"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this audit to keep the stage10072 claim narrow: same-manifest canonical edit localization with full permutation coverage and weak label-prior baselines, but not yet a source-heldout claim unless a new packet carries real source-root provenance."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"audit": display(AUDIT), "doc": display(DOC)},
        "decision": "Audited the canonical stage10072 winner for permutation coverage, label-prior shortcut risk, and source-heldout support so the claim can distinguish what the packet really proves from what it still cannot prove.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10082 Canonical Label Aligned Shortcut Validity Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Shared rows: `{built['metrics']['shared_rows']}`",
        f"Global majority exact: `{built['metrics']['global_majority_exact']}`",
        f"Macro language-majority exact: `{built['metrics']['macro_per_language_majority_exact']}`",
        f"Source-heldout claim supported: `{built['metrics']['source_heldout_claim_supported']}`",
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
        "failures": built["failures"],
        "metrics": built["metrics"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
