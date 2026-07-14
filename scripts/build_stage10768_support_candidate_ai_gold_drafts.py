#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10768
NAME = "stage10768_support_candidate_ai_gold_drafts"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "support_candidate_ai_gold_drafts.json"
INDEX_JSONL = OUT_DIR / "support_candidate_ai_gold_index.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

ENRICHED_INDEX = ROOT / "runs/local/artifacts/stage10767_support_ready_packet_enrichment/enriched_packet_index.jsonl"

PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]
EVIDENCE_KEYS = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
    "external_analogue_reference",
    "algorithmic_background_reference",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def is_test_path(value: str) -> bool:
    lower = value.lower()
    name = Path(lower).name
    return (
        "/tests/" in lower
        or lower.startswith("tests/")
        or "test_" in name
        or name.endswith("_test.py")
        or name.endswith("_tests.rs")
        or name.endswith(".test.ts")
    )


def choose_primary_candidate(values: list[str], language_family: str) -> str:
    non_tests = [v for v in values if not is_test_path(v)]
    tests = [v for v in values if is_test_path(v)]
    if language_family == "c_cpp":
        for v in non_tests:
            if v.endswith((".cpp", ".cc", ".cxx", ".cu")):
                return v
        for v in non_tests:
            if v.endswith((".h", ".hpp", ".hh", ".hxx")):
                return v
    if language_family == "python":
        for v in non_tests:
            if v.endswith(".py"):
                return v
    return non_tests[0] if non_tests else (tests[0] if tests else values[0])


def confidence(label: str) -> str:
    return {
        "symptom_localization": "medium",
        "evidence_citation": "high",
        "alternative_hypothesis_elimination": "medium",
        "patch_impact": "medium",
        "verifier_outcome": "high",
        "minimal_fix_selection": "low",
        "regression_risk": "low",
        "abstention_insufficient_evidence": "medium",
    }[label]


def draft_for_perspective(enriched: dict[str, Any], perspective: str) -> dict[str, Any]:
    language_family = str(enriched["language_family"])
    options = list(enriched["competition_contract"]["candidate_values"])
    tests = list(enriched["compiled_brief_summary"].get("verification_targets_sample") or [])
    changed = list(enriched["compiled_brief_summary"].get("changed_files_sample") or [])
    primary = choose_primary_candidate(options, language_family)
    first_test = tests[0] if tests else None

    if perspective == "symptom_localization":
        gold_value = primary
        answer_kind = "candidate_path"
        evidence = ["candidate_change_surface", "symptom_or_call_path_analogue", "verifier_and_test_constraint"]
        rationale = "Primary implementation-side candidate favored over tests and generic placeholders."
    elif perspective == "evidence_citation":
        gold_value = "verifier_and_test_constraint"
        answer_kind = "evidence_role"
        evidence = ["verifier_and_test_constraint", "symptom_or_call_path_analogue"]
        rationale = "Visible verifier/test constraint is the strongest explicit support for the transition target."
    elif perspective == "alternative_hypothesis_elimination":
        gold_value = "candidate_change_surface"
        answer_kind = "evidence_role"
        evidence = ["candidate_change_surface", "verifier_and_test_constraint"]
        rationale = "Changed implementation paths are the main alternative set to eliminate against the verifier signal."
    elif perspective == "patch_impact":
        gold_value = primary
        answer_kind = "candidate_path"
        evidence = ["candidate_change_surface", "verifier_and_test_constraint"]
        rationale = "Behavior change should be attributed to the most plausible implementation-side candidate."
    elif perspective == "verifier_outcome":
        gold_value = first_test or "ABSTAIN_INSUFFICIENT_EVIDENCE"
        answer_kind = "selected_test" if first_test else "abstain"
        evidence = ["verifier_and_test_constraint"]
        rationale = "Verifier projection is anchored on the visible selected test preview."
    elif perspective == "minimal_fix_selection":
        gold_value = primary
        answer_kind = "candidate_path"
        evidence = ["candidate_change_surface", "nearby_definition_or_usage_context"]
        rationale = "Prefer the smallest plausible implementation-side file over test or placeholder surfaces."
    elif perspective == "regression_risk":
        gold_value = changed[0] if changed else primary
        answer_kind = "candidate_path"
        evidence = ["candidate_change_surface", "external_analogue_reference"]
        rationale = "Regression risk is tied to the most visible changed surface until richer snippets arrive."
    else:
        gold_value = "ABSTAIN_INSUFFICIENT_EVIDENCE"
        answer_kind = "abstain"
        evidence = ["symptom_or_call_path_analogue", "verifier_and_test_constraint"]
        rationale = "Current packet remains a support candidate; abstention stays the honest fallback before full snippet materialization."

    return {
        "perspective": perspective,
        "provisional_gold_value": gold_value,
        "answer_kind": answer_kind,
        "confidence": confidence(perspective),
        "supporting_evidence_keys": evidence,
        "rationale": rationale,
        "needs_confirmation": True,
    }


def snippet_plan(enriched: dict[str, Any]) -> dict[str, Any]:
    changed = list(enriched["compiled_brief_summary"].get("changed_files_sample") or [])
    tests = list(enriched["compiled_brief_summary"].get("verification_targets_sample") or [])
    language_family = str(enriched["language_family"])
    primary = choose_primary_candidate(list(enriched["competition_contract"]["candidate_values"]), language_family)
    return {
        "priority_paths": [primary] + [p for p in changed if p != primary][:3] + tests[:2],
        "required_snippet_roles": [
            "implementation_or_candidate_surface",
            "verifier_or_test_constraint",
            "nearby_competing_candidate",
        ],
        "materialization_goal": "Replace path-summary evidence with concrete snippet text before scoreable use.",
    }


def main() -> None:
    rows = load_jsonl(ENRICHED_INDEX)
    index_rows: list[dict[str, Any]] = []

    for row in rows:
        enriched_path = ROOT / row["enriched_candidate"]
        enriched = load_json(enriched_path)
        packet_dir = enriched_path.parent

        gold_payload = {
            "stage": STAGE,
            "root_id": row["root_id"],
            "language_family": row["language_family"],
            "repo_family": row["repo_family"],
            "status": "provisional_ai_gold_draft",
            "entries": [draft_for_perspective(enriched, perspective) for perspective in PERSPECTIVES],
            "not_scoreable_reason": "Provisional AI draft only; concrete snippets and confirmation are still required.",
        }
        plan_payload = {
            "stage": STAGE,
            "root_id": row["root_id"],
            "language_family": row["language_family"],
            "repo_family": row["repo_family"],
            "status": "snippet_materialization_plan",
            **snippet_plan(enriched),
        }

        gold_path = packet_dir / "provisional_ai_gold_draft.json"
        plan_path = packet_dir / "snippet_materialization_plan.json"
        write_json(gold_path, gold_payload)
        write_json(plan_path, plan_payload)

        index_rows.append(
            {
                "root_id": row["root_id"],
                "language_family": row["language_family"],
                "repo_family": row["repo_family"],
                "enrichment_status": row["enrichment_status"],
                "provisional_gold_path": display(gold_path),
                "snippet_plan_path": display(plan_path),
                "package_ready_after_snippets_and_confirmation": True,
                "candidate_option_count": int(row["candidate_option_count"]),
            }
        )

    index_rows.sort(key=lambda r: (r["language_family"], r["repo_family"], r["root_id"]))
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "support_candidate_ai_gold_drafts_attached",
        "claim_scope": [
            "Attach provisional AI gold drafts to the four enriched C/C++ and Python support candidates.",
            "Add snippet materialization plans so the next reviewed support package can be built from concrete evidence rather than path summaries.",
            "Keep every gold draft explicitly provisional and non-scoreable until confirmation and snippet enrichment are complete.",
        ],
        "metrics": {
            "drafted_support_candidates": len(index_rows),
            "drafted_by_language": dict(sorted(Counter(r["language_family"] for r in index_rows).items())),
        },
        "headline_findings": [
            "All four enriched C/C++ and Python support candidates now carry provisional AI gold drafts across all eight perspectives.",
            "Each candidate also has a snippet materialization plan that identifies the first files/tests to turn into concrete visible evidence.",
            "This is enough to package the four candidates into the next reviewed multilingual support stage once snippet text is added.",
        ],
        "next_best_step": "Materialize concrete snippet text for these four candidates and assemble them into the next reviewed multilingual support package; then repeat the same workflow for the two fresh Rust packets.",
        "source_artifacts": {
            "enriched_index": display(ENRICHED_INDEX),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "support_candidate_ai_gold_index": display(INDEX_JSONL),
        },
    }

    write_jsonl(INDEX_JSONL, index_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "drafted_support_candidates": payload["metrics"]["drafted_support_candidates"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
