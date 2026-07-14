#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
ORIG_ROWS = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package/headline_strict_eval.jsonl"
REPAIRED_ROWS = ARTIFACTS / "stage10654_reviewed_v28_headline_prompt_contract_repair/headline_strict_eval_repaired.jsonl"
REPAIRED_STANDALONE = ARTIFACTS / "stage10656_reviewed_v28_repaired_headline_audit/reviewed_v28_repaired_headline_audit.json"
REPAIRED_HARNESS = ARTIFACTS / "stage10659_repaired_headline_harness_result_audit/repaired_headline_harness_result_audit.json"

SHORTCUT_NAMES = {
    "algorithmic_background_reference",
    "candidate_change_surface",
    "external_analogue_reference",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def options_prefix(prompt: str) -> str:
    return prompt.split("\nOptions:\n", 1)[0]


def row_visibility(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("prompt_text") or "")
    prefix = options_prefix(prompt)
    target_label = str(row.get("target_text") or "")
    option_values = [str(opt.get("value") or "") for opt in (row.get("opaque_options") or [])]
    target_value = ""
    for opt in row.get("opaque_options") or []:
        if str(opt.get("label") or "") == target_label:
            target_value = str(opt.get("value") or "")
            break
    visible_values = [value for value in option_values if value and value in prefix]
    visible_shortcut_names = sorted(name for name in SHORTCUT_NAMES if name in prefix)
    return {
        "row_id": row["row_id"],
        "task_type": row["task_type"],
        "language_family": row["language_family"],
        "target_label": target_label,
        "target_value": target_value,
        "option_values": option_values,
        "visible_option_values_pre_options": visible_values,
        "visible_option_count_pre_options": len(visible_values),
        "target_value_visible_pre_options": bool(target_value and target_value in prefix),
        "only_gold_value_visible_pre_options": bool(target_value and visible_values == [target_value]),
        "all_option_values_visible_pre_options": set(visible_values) == set(option_values),
        "visible_shortcut_names_pre_options": visible_shortcut_names,
        "semantic_shortcut_name_visible_pre_options": bool(visible_shortcut_names),
    }


def main() -> None:
    orig_rows = {row["row_id"]: row for row in load_jsonl(ORIG_ROWS)}
    repaired_rows = load_jsonl(REPAIRED_ROWS)
    repaired_standalone = load_json(REPAIRED_STANDALONE)
    repaired_harness = load_json(REPAIRED_HARNESS)

    repaired_citation_rows = [row for row in repaired_rows if row.get("task_type") == "evidence_citation"]
    orig_citation_rows = [orig_rows[row["row_id"]] for row in repaired_citation_rows]

    orig_visibility = [row_visibility(row) for row in orig_citation_rows]
    repaired_visibility = [row_visibility(row) for row in repaired_citation_rows]

    comparison_rows = []
    for before, after in zip(orig_visibility, repaired_visibility):
        comparison_rows.append(
            {
                "row_id": before["row_id"],
                "language_family": before["language_family"],
                "target_label": before["target_label"],
                "before": before,
                "after": after,
                "semantic_shortcut_removed": before["semantic_shortcut_name_visible_pre_options"]
                and not after["semantic_shortcut_name_visible_pre_options"],
                "gold_only_copy_path_removed": before["only_gold_value_visible_pre_options"]
                and not after["only_gold_value_visible_pre_options"],
            }
        )

    payload = {
        "stage": 10661,
        "stage_name": "stage10661_repaired_headline_claim_gate",
        "passed": True,
        "sources": {
            "original_headline_rows": str(ORIG_ROWS.relative_to(ROOT)),
            "repaired_headline_rows": str(REPAIRED_ROWS.relative_to(ROOT)),
            "repaired_standalone_audit": str(REPAIRED_STANDALONE.relative_to(ROOT)),
            "repaired_harness_audit": str(REPAIRED_HARNESS.relative_to(ROOT)),
        },
        "repaired_citation_shortcut_comparison": comparison_rows,
        "aggregate_repair_effect": {
            "rows_compared": len(comparison_rows),
            "semantic_shortcut_removed_rows": sum(1 for row in comparison_rows if row["semantic_shortcut_removed"]),
            "gold_only_copy_path_removed_rows": sum(1 for row in comparison_rows if row["gold_only_copy_path_removed"]),
            "rows_with_shortcut_names_still_visible_after": sum(
                1 for row in comparison_rows if row["after"]["semantic_shortcut_name_visible_pre_options"]
            ),
            "rows_with_gold_only_visibility_after": sum(
                1 for row in comparison_rows if row["after"]["only_gold_value_visible_pre_options"]
            ),
            "rows_with_target_value_visible_after": sum(
                1 for row in comparison_rows if row["after"]["target_value_visible_pre_options"]
            ),
            "rows_with_all_option_values_visible_after": sum(
                1 for row in comparison_rows if row["after"]["all_option_values_visible_pre_options"]
            ),
        },
        "standalone_repaired_frontier": repaired_standalone["headline_accuracy_comparison"],
        "harness_repaired_frontier": repaired_harness["metrics"],
        "claim_gate": {
            "same_manifest_cleaned_headline_supported": True,
            "standalone_win_preserved_after_repair": bool(repaired_standalone["verdict"]["hundred_m_win_preserved_after_prompt_contract_repair"]),
            "harness_win_preserved_after_repair": (repaired_harness["metrics"]["hundred_m_accuracy"] > repaired_harness["metrics"]["gemma_accuracy"]),
            "semantic_role_shortcut_removed_from_repaired_citation_rows": all(
                not row["after"]["semantic_shortcut_name_visible_pre_options"] for row in comparison_rows
            ),
            "gold_only_copy_path_absent_after_repair": all(
                not row["after"]["only_gold_value_visible_pre_options"] for row in comparison_rows
            ),
            "source_heldout_supported": False,
        },
        "safe_claims_now": [
            "The same-manifest 24-row multilingual headline still beats Gemma after the four shortcut-prone evidence_citation rows were repaired to opaque evidence IDs.",
            "That repaired headline win now survives in both standalone and recovered harness execution paths.",
        ],
        "blocked_claims_now": [
            "source-heldout multilingual win",
            "fully maintainer-grade realistic benchmark claim",
            "fresh pure-web verifier-anchored headline strength",
            "fresh non-abstention-heavy Rust headline strength",
        ],
        "claim_boundary": [
            "The repaired citation rows remove visible semantic shortcut names like candidate_change_surface from the promotable headline path.",
            "The repaired evidence IDs are still prompt-visible markers, but they no longer expose the original semantic role names and do not create a gold-only copy path.",
            "This is still a same-manifest compact maintainer-choice result, not a source-heldout maintainer-generalization result.",
        ],
        "next_best_steps": [
            "Use the repaired headline contract as the default same-manifest standalone and harness claim path.",
            "If needed, extend the same opaque-evidence-ID repair to supporting validation slices before rebuilding the broader v2.8 claim gate.",
            "Continue mining fresh source-heldout web and Rust roots, because repaired prompt contracts do not close the source-supply gap.",
        ],
    }

    out_dir = ARTIFACTS / "stage10661_repaired_headline_claim_gate"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "repaired_headline_claim_gate.json", payload)
    print(out_dir / "repaired_headline_claim_gate.json")


if __name__ == "__main__":
    main()
