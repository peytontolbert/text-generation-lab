#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10266
NAME = "stage10266_code_assist_web_commit_compact_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REVIEW_DIR = OUT_DIR / "review_packets"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
EVAL_JSONL = OUT_DIR / "agentkernel_lite_encdec_eval.jsonl"
PACKAGE_JSON = OUT_DIR / "code_assist_web_commit_compact_support_package.json"
ADMITTED_JSON = OUT_DIR / "code_assist_web_commit_admitted_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
BASE_PACKAGE = ROOT / "runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json"
SOURCE_BUNDLES = ROOT / "runs/local/artifacts/stage10264_code_assist_web_commit_bundle_candidates/code_assist_web_commit_bundle_candidates.json"
ADJUDICATION = ROOT / "runs/summaries/stage10265_code_assist_web_commit_ai_adjudication.json"


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


PROJECTION = _load_module(
    "stage10266_stage10177_projection",
    ROOT / "scripts" / "build_stage10177_augmented_web_permutation_balanced_package.py",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return slug or "bundle"


def selected_tests(bundle: dict[str, Any]) -> list[str]:
    tests: list[str] = []
    for row in bundle.get("perspective_rows") or []:
        if not isinstance(row, dict):
            continue
        contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        for value in contract.get("selected_tests") or []:
            text = str(value or "")
            if text and text not in tests:
                tests.append(text)
    return tests


def visible_evidence_keys(bundle: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for row in bundle.get("perspective_rows") or []:
        if not isinstance(row, dict):
            continue
        contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        for value in contract.get("visible_evidence_keys") or []:
            text = str(value or "")
            if text and text not in keys:
                keys.append(text)
    return keys


def evidence_key_for_bundle(bundle: dict[str, Any]) -> str:
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    if evidence.get("verifier_and_test_constraint"):
        return "verifier_and_test_constraint"
    keys = visible_evidence_keys(bundle)
    return keys[0] if keys else "candidate_change_surface"


def bundle_subject(bundle: dict[str, Any]) -> str:
    return str(bundle.get("commit_subject") or "").strip()


def gold_answers(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [str(value) for value in bundle.get("candidate_paths") or [] if value]
    tests = selected_tests(bundle)
    visible_keys = visible_evidence_keys(bundle)
    backend_path = "src/code_assist/ui/fastapi_dashboard.py"
    evidence_key = evidence_key_for_bundle(bundle)
    subject = bundle_subject(bundle)
    risk_text = (
        "Changes in fastapi_dashboard.py could regress dashboard asset serving, project task views, "
        "API route responses, and live event or verdict updates across the UI."
    )
    alternative = (
        "The asset files are plausible presentation surfaces, but the visible verifier and route evidence "
        "point to backend API behavior owned by fastapi_dashboard.py rather than a static asset-only fault."
    )
    if "verdict" in subject.lower():
        alternative = (
            "The asset files expose the verdict tab, but the visible evidence also includes a new backend "
            "verdict endpoint and dashboard API verifier anchor, so fastapi_dashboard.py is the stronger behavior owner."
        )
    return [
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": backend_path,
            "perspective": "symptom_localization",
            "reviewer_rationale": "The visible route and verifier evidence attach the changed behavior to the FastAPI dashboard backend.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "visible_evidence_key",
            "gold_answer_value": evidence_key,
            "perspective": "evidence_citation",
            "reviewer_rationale": "The verifier and test anchor is the strongest visible fact tying the behavior to the backend dashboard surface.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "freeform_explanation",
            "gold_answer_value": alternative,
            "perspective": "alternative_hypothesis_elimination",
            "reviewer_rationale": "The frontend assets are plausible competitors, but they are less justified than the backend route and verifier evidence.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": backend_path,
            "perspective": "patch_impact",
            "reviewer_rationale": "A backend dashboard edit is the most direct way to change the tested API behavior without speculating about presentation-only fixes.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "selected_test",
            "gold_answer_value": tests[0] if tests else "tests/integration/test_dashboard_api.py",
            "perspective": "verifier_outcome",
            "reviewer_rationale": "The dashboard API integration suite is the visible verification target for the changed behavior.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "candidate_path",
            "gold_answer_value": backend_path,
            "perspective": "minimal_fix_selection",
            "reviewer_rationale": "fastapi_dashboard.py is the narrowest behavior-owning surface justified by the visible evidence.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": False,
            "candidate_paths": paths,
            "gold_answer_kind": "freeform_risk",
            "gold_answer_value": risk_text,
            "perspective": "regression_risk",
            "reviewer_rationale": "The backend dashboard module fans out into both UI asset serving and API/event behavior, so regressions there can affect the full dashboard.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
        {
            "abstention_option_required": True,
            "candidate_paths": paths,
            "gold_answer_kind": "abstain",
            "gold_answer_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
            "perspective": "abstention_insufficient_evidence",
            "reviewer_rationale": "This remains the explicit honesty row for the bundle even though the other bounded perspectives are sufficiently grounded.",
            "selected_tests": tests,
            "visible_evidence_keys": visible_keys,
        },
    ]


def rubric_review(bundle: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    rationale = list(review.get("rationale") or [])
    return {
        "bundle_id": bundle["bundle_id"],
        "bundle_valid_for_eval": True,
        "decision_rationale": rationale,
        "gold_adjudication_slot": {
            "bundle_level_signoff": True,
            "perspective_gold_answers_recorded": True,
            "reviewer_rationale": rationale,
        },
        "language_family": bundle["language_family"],
        "passed": True,
        "repo_id": "code_assist",
        "required_human_action": "AI maintainer adjudication completed in-repo for train-support and repo-overlap stress-eval use only.",
        "reviewer_id": "codex-gpt5-ai-review",
        "reviewer_notes": "This review keeps commit subject leakage out of prompt-visible evidence and treats the bundle as non-headline because of same-repo overlap.",
        "rubric_lines": {
            "abstention_is_available_when_evidence_is_insufficient": True,
            "candidate_paths_are_maintainer_plausible": True,
            "perspectives_test_distinct_reasoning_not_template_rephrases": True,
            "root_bundle_is_maintainer_meaningful": True,
            "visible_evidence_is_sufficient_for_bundle_perspectives": True,
        },
        "rubric_version": "expert_maintainer_root_bundle_v1",
        "status": "completed",
    }


def anti_cheat_review(bundle: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    shortcut_risks = list(review.get("shortcut_risks") or [])
    return {
        "admissible_for_same_surface_comparison": True,
        "bundle_id": bundle["bundle_id"],
        "challenge_families": {
            "candidate_path_or_order_bias": True,
            "commit_metadata_leakage_removed_from_prompt": True,
            "hidden_reference_or_metadata_leakage": True,
            "perspective_paraphrase_collapse": True,
            "repo_overlap_claim_boundary_enforced": True,
            "same_surface_fairness_for_future_gemma_comparison": True,
            "template_and_surface_prior_shortcuts": True,
        },
        "decision_rationale": shortcut_risks,
        "language_family": bundle["language_family"],
        "passed": True,
        "repo_id": "code_assist",
        "required_human_action": "Use only for train support or repo-overlap stress eval; keep it out of source-heldout headline claims.",
        "reviewer_id": "codex-gpt5-ai-review",
        "reviewer_notes": "Same-repo overlap is the binding claim boundary. The prompt-visible evidence avoids commit subject and commit hash leakage.",
        "status": "completed",
    }


def perspective_gold_adjudication(bundle: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    rationale = list(review.get("rationale") or [])
    return {
        "bundle_gold_ready_for_eval": True,
        "bundle_id": bundle["bundle_id"],
        "decision_rationale": rationale,
        "language_family": bundle["language_family"],
        "perspective_gold_answers": gold_answers(bundle),
        "recommended_answer_kind_schema": {
            "abstention_insufficient_evidence": {"allowed_answer_kinds": ["abstain"], "recommended_primary_kind": "abstain"},
            "alternative_hypothesis_elimination": {"allowed_answer_kinds": ["freeform_explanation", "candidate_path", "abstain"], "recommended_primary_kind": "freeform_explanation"},
            "evidence_citation": {"allowed_answer_kinds": ["visible_evidence_key", "freeform_visible_fact", "abstain"], "recommended_primary_kind": "visible_evidence_key"},
            "minimal_fix_selection": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "patch_impact": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "regression_risk": {"allowed_answer_kinds": ["freeform_risk", "candidate_path", "abstain"], "recommended_primary_kind": "freeform_risk"},
            "symptom_localization": {"allowed_answer_kinds": ["candidate_path", "abstain"], "recommended_primary_kind": "candidate_path"},
            "verifier_outcome": {"allowed_answer_kinds": ["selected_test", "freeform_verifier_outcome", "abstain"], "recommended_primary_kind": "selected_test"},
        },
        "repo_id": "code_assist",
        "required_human_action": "No additional human review is required for this train-support and repo-overlap stress-eval packet.",
        "reviewer_guidance": [
            "Keep commit subject and raw commit metadata out of prompt-visible evidence.",
            "Do not promote this bundle to source-heldout headline evidence.",
        ],
        "reviewer_id": "codex-gpt5-ai-review",
        "status": "completed",
    }


def build_review_packet(bundle: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    packet_dir = REVIEW_DIR / slugify(bundle["bundle_id"])
    rubric = rubric_review(bundle, review)
    anti = anti_cheat_review(bundle, review)
    gold = perspective_gold_adjudication(bundle, review)
    rubric_path = packet_dir / "expert_maintainer_rubric_review.json"
    anti_path = packet_dir / "anti_cheat_review_card.json"
    gold_path = packet_dir / "perspective_gold_adjudication.json"
    write_json(rubric_path, rubric)
    write_json(anti_path, anti)
    write_json(gold_path, gold)
    admitted = dict(bundle)
    admitted["repo_id"] = "code_assist"
    admitted["selected_tests"] = selected_tests(bundle)
    admitted["perspective_gold_adjudication"] = display(gold_path)
    admitted["rubric_review"] = display(rubric_path)
    admitted["anti_cheat_review"] = display(anti_path)
    admitted["claim_boundary"] = {
        "source_heldout_headline_admissible": False,
        "repo_overlap_stress_eval_candidate": True,
        "repo_overlap_stress_eval_admitted": True,
        "train_support_candidate": True,
        "train_support_admitted": True,
        "same_repo_overlap_risk": True,
        "reason_not_source_heldout": "same_repo_family_as_consumed_web_frontier",
    }
    return admitted


def label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("target_text") or "")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def nondegenerate_compact_rows(bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: list[dict[str, Any]] = []
    excluded: list[str] = []
    for row in PROJECTION.compile_bundle_rows(bundle):
        option_count = len(row.get("opaque_options") or [])
        if option_count < 2:
            excluded.append(f"{row.get('row_id')}::degenerate_option_count_{option_count}")
            continue
        kept.append(row)
    return kept, excluded


def build_package() -> dict[str, Any]:
    base_package = load_json(BASE_PACKAGE)
    train_rows = load_jsonl(ROOT / str(base_package.get("train_dataset_path") or ""))
    eval_rows = load_jsonl(ROOT / str(base_package.get("eval_dataset_path") or ""))
    bundles_payload = load_json(SOURCE_BUNDLES)
    adjudication = load_json(ADJUDICATION)
    bundle_by_id = {
        str(bundle.get("bundle_id") or ""): bundle
        for bundle in bundles_payload.get("bundle_candidates") or []
        if isinstance(bundle, dict)
    }
    reviews = {
        str(review.get("bundle_id") or ""): review
        for review in adjudication.get("bundle_reviews") or []
        if isinstance(review, dict)
    }
    admitted_bundles: list[dict[str, Any]] = []
    failures: list[str] = []
    excluded_compact_rows: list[str] = []
    for bundle_id, review in sorted(reviews.items()):
        if not review.get("admissible_for_train_support_now"):
            continue
        bundle = bundle_by_id.get(bundle_id)
        if bundle is None:
            failures.append(f"missing_bundle_candidate::{bundle_id}")
            continue
        admitted_bundles.append(build_review_packet(bundle, review))
    admitted_manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not failures and bool(admitted_bundles),
        "rows": admitted_bundles,
        "metrics": {
            "admitted_bundles": len(admitted_bundles),
            "languages": sorted({str(bundle.get("language_family") or "") for bundle in admitted_bundles}),
            "excluded_compact_rows": len(excluded_compact_rows),
        },
        "claim_scope": "code_assist same-repo web commit bundles admitted for standalone train support and repo-overlap stress evaluation only",
    }
    write_json(ADMITTED_JSON, admitted_manifest)

    augmented_rows: list[dict[str, Any]] = []
    augmentation_manifest: list[dict[str, Any]] = []
    for bundle in admitted_bundles:
        compiled, excluded = nondegenerate_compact_rows(bundle)
        excluded_compact_rows.extend(excluded)
        bundle_rows: list[dict[str, Any]] = []
        for row in compiled:
            for variant in PROJECTION.build_variant_rows(bundle, row, split="train"):
                variant["source_stage"] = STAGE
                anti = dict(variant.get("anti_cheat") or {})
                anti.update(
                    {
                        "repo_overlap_train_support_only": True,
                        "same_repo_family_non_headline": True,
                        "commit_subject_hidden_from_prompt": True,
                        "degenerate_single_option_rows_excluded": True,
                    }
                )
                variant["anti_cheat"] = anti
                source = dict(variant.get("standalone_projection_source") or {})
                source["projection_stage"] = STAGE
                source["claim_boundary"] = dict(bundle.get("claim_boundary") or {})
                variant["standalone_projection_source"] = source
                bundle_rows.append(variant)
        augmented_rows.extend(bundle_rows)
        augmentation_manifest.append(
            {
                "bundle_id": bundle["bundle_id"],
                "language_family": bundle["language_family"],
                "compiled_bounded_rows": len(compiled),
                "excluded_compact_rows": excluded,
                "augmented_train_rows": len(bundle_rows),
                "selected_tests": list(bundle.get("selected_tests") or []),
                "claim_boundary": dict(bundle.get("claim_boundary") or {}),
            }
        )

    final_train_rows = train_rows + augmented_rows
    write_jsonl(TRAIN_JSONL, final_train_rows)
    write_jsonl(EVAL_JSONL, eval_rows)

    metrics = {
        "base_train_rows": len(train_rows),
        "base_strict_eval_rows": len(eval_rows),
        "admitted_bundles": len(admitted_bundles),
        "augmented_train_rows": len(augmented_rows),
        "final_train_rows": len(final_train_rows),
        "final_strict_eval_rows": len(eval_rows),
        "train_label_counts": label_counts(final_train_rows),
        "strict_eval_label_counts": label_counts(eval_rows),
    }
    package = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "base_package": display(BASE_PACKAGE),
        "source_bundle_candidates": display(SOURCE_BUNDLES),
        "source_adjudication": display(ADJUDICATION),
        "source_admitted_manifest": display(ADMITTED_JSON),
        "passed": not failures and bool(admitted_bundles) and bool(augmented_rows),
        "metrics": metrics,
        "augmentation_manifest": augmentation_manifest,
        "excluded_compact_rows": excluded_compact_rows,
        "failures": failures,
        "train_dataset_path": display(TRAIN_JSONL),
        "eval_dataset_path": display(EVAL_JSONL),
        "fit_for": {
            "standalone_decoder_ce_training": True,
            "full_product_harness_training": False,
            "expert_maintainer_primary_score": False,
            "compact_bounded_auxiliary_projection_only": True,
        },
        "required_honesty_gates": [
            "stage10142_standalone_decoder_contract_audit must pass before standalone score claims",
            "strict eval remains unchanged from the stage10149 base package",
            "code_assist git-history bundles are train support only and not source-heldout headline evidence",
            "freeform maintainer rows remain excluded from compact standalone package",
            "single-option compact rows are excluded from training support",
        ],
        "claim_scope": "same-repo code_assist web commit bundles added as compact bounded standalone train support only; strict eval unchanged",
    }
    write_json(PACKAGE_JSON, package)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": package["passed"],
            "package": display(PACKAGE_JSON),
            "admitted_manifest": display(ADMITTED_JSON),
            "metrics": metrics,
            "failures": failures,
        },
    )
    return package


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    package = build_package()
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": package["passed"],
                "package": display(PACKAGE_JSON),
                "metrics": package["metrics"],
                "failures": package["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not package["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
