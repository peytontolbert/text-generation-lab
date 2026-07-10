#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10130
NAME = "stage10130_true_source_backed_first_wave_scoring_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "true_source_backed_first_wave_scoring_contract.json"
ROWS = OUT_DIR / "true_source_backed_first_wave_scoring_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_FIRST_WAVE_SCORING_CONTRACT_STAGE10130.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

ADMITTED_MANIFEST = (
    ROOT
    / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"
)
BLOCKED_MANIFEST = (
    ROOT
    / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json"
)

REQUIRED_PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    path.write_text((payload + "\n") if payload else "", encoding="utf-8")


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


def _flatten_rows(bundle: dict[str, Any], gold_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    perspective_rows = list(bundle.get("perspective_rows") or [])
    gold_answers = list(gold_payload.get("perspective_gold_answers") or [])
    gold_by_perspective = {str(answer.get("perspective") or ""): answer for answer in gold_answers}

    seen_perspectives = [str(row.get("perspective") or "") for row in perspective_rows]
    if seen_perspectives != REQUIRED_PERSPECTIVES:
        failures.append(f"bundle_perspective_sequence_mismatch::{bundle.get('bundle_id')}")

    flattened: list[dict[str, Any]] = []
    for row in perspective_rows:
        perspective = str(row.get("perspective") or "")
        prompt_contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        gold = gold_by_perspective.get(perspective)
        if gold is None:
            failures.append(f"missing_gold_for_perspective::{bundle.get('bundle_id')}::{perspective}")
            continue
        if not gold.get("gold_answer_kind"):
            failures.append(f"missing_gold_answer_kind::{bundle.get('bundle_id')}::{perspective}")
        if gold.get("gold_answer_value") in (None, ""):
            failures.append(f"missing_gold_answer_value::{bundle.get('bundle_id')}::{perspective}")
        flattened.append(
            {
                "bundle_id": bundle.get("bundle_id"),
                "repo_id": bundle.get("repo_id"),
                "language_family": bundle.get("language_family"),
                "wave_rank": bundle.get("wave_rank"),
                "priority_score": bundle.get("priority_score"),
                "perspective": perspective,
                "prompt_contract": prompt_contract,
                "candidate_paths": list(prompt_contract.get("candidate_paths") or []),
                "selected_tests": list(prompt_contract.get("selected_tests") or []),
                "visible_evidence_keys": list(prompt_contract.get("visible_evidence_keys") or []),
                "abstention_option_required": bool(prompt_contract.get("abstention_option_required")),
                "maintainer_visible_evidence": bundle.get("maintainer_visible_evidence"),
                "gold_answer_kind": gold.get("gold_answer_kind"),
                "gold_answer_value": gold.get("gold_answer_value"),
                "reviewer_rationale": gold.get("reviewer_rationale"),
                "training_scoring_contract": {
                    "eligible_for_scoring": True,
                    "counts_toward_root_solved": True,
                    "exact_match_required": True,
                    "requires_abstention_support": bool(prompt_contract.get("abstention_option_required"))
                    or str(gold.get("gold_answer_kind")) == "abstain",
                },
            }
        )
    return flattened, failures


def _gold_path(root: Path, bundle: dict[str, Any]) -> Path | None:
    gold_ref = bundle.get("perspective_gold_adjudication")
    if gold_ref:
        return root / str(gold_ref)
    for key in ("rubric_review", "anti_cheat_review"):
        review_ref = bundle.get(key)
        if review_ref:
            return (root / str(review_ref)).parent / "perspective_gold_adjudication.json"
    return None


def build_contract(
    *,
    admitted_manifest_path: Path = ADMITTED_MANIFEST,
    blocked_manifest_path: Path = BLOCKED_MANIFEST,
    root: Path = ROOT,
) -> dict[str, Any]:
    admitted = load_json(admitted_manifest_path)
    blocked = load_json(blocked_manifest_path)
    failures: list[str] = []
    if admitted.get("passed") is not True:
        failures.append("stage10129_admitted_manifest_not_passed")
    if blocked.get("passed") is not True:
        failures.append("stage10129_blocked_manifest_not_passed")

    admitted_rows = list(admitted.get("rows") or [])
    score_rows: list[dict[str, Any]] = []
    score_row_failures: list[str] = []
    gold_kind_counts: Counter[str] = Counter()

    for bundle in admitted_rows:
        gold_path = _gold_path(root, bundle)
        gold_payload = load_json(gold_path) if gold_path else {}
        if not gold_payload:
            score_row_failures.append(f"missing_gold_payload::{bundle.get('bundle_id')}")
            continue
        bundle_rows, bundle_failures = _flatten_rows(bundle, gold_payload)
        score_rows.extend(bundle_rows)
        score_row_failures.extend(bundle_failures)
        gold_kind_counts.update(str(row.get("gold_answer_kind") or "") for row in bundle_rows)

    failures.extend(score_row_failures)

    perspective_counts = Counter(str(row.get("perspective") or "") for row in score_rows)
    language_counts = Counter(str(row.get("language_family") or "") for row in score_rows)
    abstention_rows = sum(1 for row in score_rows if row["training_scoring_contract"]["requires_abstention_support"])
    expected_score_rows = len(admitted_rows) * len(REQUIRED_PERSPECTIVES)
    if admitted_rows and len(score_rows) != expected_score_rows:
        failures.append("score_row_count_mismatch")

    contract = {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifacts": {
            "admitted_manifest": display(admitted_manifest_path),
            "blocked_manifest": display(blocked_manifest_path),
        },
        "decision": (
            "Flatten the admitted first-wave multilingual root bundles into perspective-scoring rows only after completed rubric, anti-cheat, and gold adjudication, "
            "while preserving root-level solved semantics as the primary maintainer-grade metric."
        ),
        "claim_boundary": {
            "row_level_accuracy_is_secondary_to_root_level_coherence": True,
            "no_model_comparison_is_honest_without_admitted_bundles": len(admitted_rows) > 0,
            "scoreable_now": len(admitted_rows) > 0 and not failures,
        },
        "scoring_contract": {
            "unit_of_independence": "root_bundle",
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
                "A bundle is solved only if every admitted perspective row in the bundle is correct under exact adjudicated gold-answer matching, "
                "including abstention rows when insufficient evidence is the honest answer."
            ),
            "bundle_consistency_requirement": (
                "Localization, evidence, alternative elimination, patch impact, verifier outcome, minimal fix, regression risk, and abstention "
                "must all remain mutually consistent for the same root case."
            ),
            "supported_gold_answer_kinds": sorted(kind for kind in gold_kind_counts if kind),
            "required_perspectives": REQUIRED_PERSPECTIVES,
            "model_prediction_schema": {
                "bundle_id": "string",
                "language_family": "string",
                "perspective_predictions": [
                    {
                        "perspective": "one_of_required_perspectives",
                        "answer_kind": "must_match_gold_answer_kind_or_valid_normalized_equivalent",
                        "answer_value": "string_or_structured_value_matching_gold_answer",
                    }
                ],
            },
        },
        "metrics": {
            "admitted_bundle_count": len(admitted_rows),
            "blocked_bundle_count": int(blocked.get("row_count", 0) or 0),
            "score_row_count": len(score_rows),
            "required_perspective_count": len(REQUIRED_PERSPECTIVES),
            "perspective_row_counts": dict(sorted(perspective_counts.items())),
            "language_row_counts": dict(sorted(language_counts.items())),
            "gold_answer_kind_counts": dict(sorted(gold_kind_counts.items())),
            "abstention_required_rows": abstention_rows,
            "scoreable_now": len(admitted_rows) > 0 and not failures,
        },
        "failures": failures,
        "next_best_step": (
            "Complete the Stage10128 first-wave rubric, anti-cheat, and perspective-gold tasks, rerun Stage10129 to admit bundles, "
            "then use these flattened scoring rows for one bounded 100M-versus-Gemma first-wave maintainer comparison."
        ),
    }
    return {"contract": contract, "score_rows": score_rows}


def write_doc(contract: dict[str, Any]) -> None:
    DOC.write_text(
        "\n".join(
            [
                "# Stage10130 True Source-Backed First-Wave Scoring Contract",
                "",
                f"Passed: `{contract['passed']}`",
                f"Admitted bundles: `{contract['metrics']['admitted_bundle_count']}`",
                f"Score rows: `{contract['metrics']['score_row_count']}`",
                "",
                contract["decision"],
                "",
                f"Primary metric: `{contract['scoring_contract']['primary_metric']}`",
                "",
                f"Next: {contract['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    built = build_contract()
    contract = built["contract"]
    write_json(CONTRACT, contract)
    write_jsonl(ROWS, built["score_rows"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "metrics": contract["metrics"],
        "artifacts": {
            "contract": display(CONTRACT),
            "rows": display(ROWS),
            "doc": display(DOC),
        },
        "decision": contract["decision"],
        "next_best_step": contract["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    write_doc(contract)
    if summary["passed"]:
        update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": contract["passed"],
                "metrics": contract["metrics"],
                "failures": contract["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if contract["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
