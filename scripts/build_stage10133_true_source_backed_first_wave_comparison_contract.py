#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10133
NAME = "stage10133_true_source_backed_first_wave_comparison_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "true_source_backed_first_wave_comparison_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_FIRST_WAVE_COMPARISON_CONTRACT_STAGE10133.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ADMITTED = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"
BLOCKED = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json"
SCORING = ROOT / "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract/true_source_backed_first_wave_scoring_contract.json"
SCORING_ROWS = ROOT / "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract/true_source_backed_first_wave_scoring_rows.jsonl"
GOLD_SUPPORT = ROOT / "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support/true_source_backed_first_wave_gold_adjudication_support.json"
READINESS = ROOT / "runs/local/artifacts/stage10132_true_source_backed_first_wave_adjudication_readiness_ledger/true_source_backed_first_wave_adjudication_readiness_ledger.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_contract(
    *,
    admitted_path: Path = ADMITTED,
    blocked_path: Path = BLOCKED,
    scoring_path: Path = SCORING,
    scoring_rows_path: Path = SCORING_ROWS,
    gold_support_path: Path = GOLD_SUPPORT,
    readiness_path: Path = READINESS,
) -> dict[str, Any]:
    admitted = load_json(admitted_path)
    blocked = load_json(blocked_path)
    scoring = load_json(scoring_path)
    scoring_rows = load_jsonl(scoring_rows_path)
    gold_support = load_json(gold_support_path)
    readiness = load_json(readiness_path)

    failures: list[str] = []
    if admitted.get("passed") is not True:
        failures.append("stage10129_admitted_manifest_not_passed")
    if blocked.get("passed") is not True:
        failures.append("stage10129_blocked_manifest_not_passed")
    if scoring.get("passed") is not True:
        failures.append("stage10130_not_passed")
    if gold_support.get("passed") is not True:
        failures.append("stage10131_not_passed")
    if readiness.get("passed") is not True:
        failures.append("stage10132_not_passed")

    readiness_metrics = readiness.get("metrics") or {}
    scoreable_now = int(readiness_metrics.get("bundles_scoreable_now", 0) or 0)
    admitted_bundles = int((scoring.get("metrics") or {}).get("admitted_bundle_count", 0) or 0)
    score_row_count = int((scoring.get("metrics") or {}).get("score_row_count", 0) or 0)
    if admitted_bundles == 0 and score_row_count != 0:
        failures.append("score_rows_present_without_admitted_bundles")
    if admitted_bundles > 0 and score_row_count == 0:
        failures.append("admitted_bundles_without_score_rows")

    contract = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision": (
            "Freeze the future 100M-versus-Gemma maintainer comparison contract now, before any bundle is admitted, so later scoring is not distorted by output-format drift, answer-kind mismatch, or inconsistent normalization."
        ),
        "comparison_ready_now": scoreable_now == 8 and admitted_bundles == 8 and score_row_count == 64 and not failures,
        "claim_boundary": {
            "comparison_requires_all_eight_bundles_admitted": True,
            "comparison_requires_same_bundle_set_for_both_models": True,
            "comparison_requires_root_level_scoring_not_row_only": True,
            "comparison_disallows_prompt_or_parser_retargeting_after_gold_signoff": True,
        },
        "prediction_schema": {
            "bundle_id": "string_matching_admitted_bundle_id",
            "language_family": "string_matching_bundle_language_family",
            "perspective_predictions": [
                {
                    "perspective": "required_exact_bundle_perspective_name",
                    "answer_kind": "one_of_candidate_path|visible_evidence_key|freeform_visible_fact|selected_test|freeform_verifier_outcome|freeform_explanation|freeform_risk|abstain",
                    "answer_value": "string",
                }
            ],
        },
        "normalization_rules": {
            "global": [
                "strip_outer_whitespace",
                "collapse_internal_whitespace_to_single_spaces_for_freeform_kinds",
                "preserve_bundle_and_perspective_identity_exactly",
            ],
            "candidate_path": [
                "trim_whitespace",
                "normalize_path_separators_to_forward_slash",
                "remove_leading_dot_slash",
                "case_sensitive_exact_match_after_path_normalization",
            ],
            "visible_evidence_key": [
                "trim_whitespace",
                "case_sensitive_exact_match_to_prompt_visible_evidence_key",
            ],
            "selected_test": [
                "trim_whitespace",
                "normalize_path_separators_to_forward_slash",
                "remove_leading_dot_slash",
                "case_sensitive_exact_match_after_test_id_normalization",
            ],
            "abstain": [
                "canonicalize_any_of:ABSTAIN|ABSTAIN_INSUFFICIENT_EVIDENCE|INSUFFICIENT_EVIDENCE_TO_DECIDE",
                "normalized_value_is_ABSTAIN_INSUFFICIENT_EVIDENCE",
            ],
            "freeform_visible_fact": [
                "strip_outer_whitespace",
                "collapse_internal_whitespace",
                "exact_match_required_after_normalization_until_human-approved semantic scorer exists",
            ],
            "freeform_verifier_outcome": [
                "strip_outer_whitespace",
                "collapse_internal_whitespace",
                "exact_match_required_after_normalization_until_human-approved semantic scorer exists",
            ],
            "freeform_explanation": [
                "strip_outer_whitespace",
                "collapse_internal_whitespace",
                "exact_match_required_after_normalization_until_human-approved semantic scorer exists",
            ],
            "freeform_risk": [
                "strip_outer_whitespace",
                "collapse_internal_whitespace",
                "exact_match_required_after_normalization_until_human-approved semantic scorer exists",
            ],
        },
        "metrics_contract": {
            "primary_metric": "root_solved_rate",
            "secondary_metrics": [
                "per_perspective_accuracy",
                "per_language_root_solved_rate",
                "per_language_per_perspective_accuracy",
                "abstention_correctness",
                "evidence_citation_correctness",
                "patch_impact_correctness",
                "verifier_outcome_correctness",
            ],
            "root_solved_definition": (
                "A root bundle is solved only if every perspective prediction for that bundle matches its adjudicated gold answer after the allowed normalization for that answer kind."
            ),
            "bundle_count_required_for_first_honest_comparison": 8,
            "score_row_count_required_for_first_honest_comparison": 64,
        },
        "execution_sequence": [
            "rerun_stage10129_after_human_signoff_to_refresh_admitted_bundle_manifest",
            "rerun_stage10130_to_refresh_score_rows_from_the_admitted_manifest",
            "freeze_exact_admitted_bundle_ids_and_score_row_ids_before_any_model_run",
            "run_target_100m_once_on_that_frozen_bundle_set",
            "run_gemma_once_on_that_same_frozen_bundle_set",
            "normalize_predictions_only_by_this_contract",
            "score_root_level_and_per_perspective_metrics_without_prompt retuning",
        ],
        "artifacts": {
            "admitted_manifest": display(admitted_path),
            "blocked_manifest": display(blocked_path),
            "scoring_contract": display(scoring_path),
            "scoring_rows": display(scoring_rows_path),
            "gold_support": display(gold_support_path),
            "readiness_ledger": display(readiness_path),
        },
        "metrics": {
            "admitted_bundle_count": admitted_bundles,
            "blocked_bundle_count": int((blocked.get("row_count", 0) or 0)),
            "score_row_count": score_row_count,
            "bundles_scoreable_now": scoreable_now,
            "comparison_ready_now": scoreable_now == 8 and admitted_bundles == 8 and score_row_count == 64 and not failures,
        },
        "failures": failures,
        "next_best_step": (
            "Complete human signoff on the eight first-wave bundles, rerun Stage10129 and Stage10130, then use this frozen comparison contract for one same-bundle 100M-versus-Gemma maintainer comparison without prompt or parser drift."
        ),
    }
    return contract


def main() -> None:
    contract = build_contract()
    write_json(CONTRACT, contract)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "metrics": contract["metrics"],
        "artifacts": {
            "contract": display(CONTRACT),
            "doc": display(DOC),
        },
        "decision": contract["decision"],
        "next_best_step": contract["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10133 True Source-Backed First-Wave Comparison Contract",
                "",
                f"Passed: `{summary['passed']}`",
                f"Admitted bundles: `{contract['metrics']['admitted_bundle_count']}`",
                f"Score rows: `{contract['metrics']['score_row_count']}`",
                f"Comparison ready now: `{contract['metrics']['comparison_ready_now']}`",
                "",
                summary["decision"],
                "",
                f"Next: {contract['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": contract["passed"], "metrics": contract["metrics"], "failures": contract["failures"]}, indent=2, sort_keys=True))
    if contract["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
