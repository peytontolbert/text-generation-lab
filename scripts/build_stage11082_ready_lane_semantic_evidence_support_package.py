#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11082
NAME = "stage11082_ready_lane_semantic_evidence_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "ready_lane_semantic_evidence_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_JSONL = OUT_DIR / "added_semantic_evidence_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage11061_ready_lane_fresh_support_package"
BASE_SUMMARY = BASE_DIR / "ready_lane_fresh_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

WORK_ITEMS = ARTIFACTS / "stage11060_ready_lane_row_construction_manifest" / "row_construction_work_items.jsonl"
CANDIDATE_ROWS = ARTIFACTS / "stage10938_explicit_verifier_ledger_strict_candidates" / "strict_candidate_rows.jsonl"

EVIDENCE_ROLE_OPTIONS = [
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]
PAIRWISE_NEGATIVE_DEFAULT = "candidate_change_surface"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def parsed_query_lines(query_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in str(query_text).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def candidate_ref_for_lane(work_item: dict[str, Any]) -> dict[str, Any] | None:
    candidate_anchor = work_item.get("candidate_anchor_ref") or {}
    return candidate_anchor if candidate_anchor else None


def candidate_gold_value(work_item: dict[str, Any], candidate_rows_by_id: dict[str, dict[str, Any]]) -> tuple[str, str]:
    candidate_anchor = candidate_ref_for_lane(work_item) or {}
    candidate_row_id = str(candidate_anchor.get("row_id") or "")
    candidate_row = candidate_rows_by_id.get(candidate_row_id) or {}
    anchor_source = candidate_row.get("standalone_projection_source") or candidate_anchor.get("standalone_projection_source") or {}
    gold = str(anchor_source.get("gold_value") or "")
    if gold:
        return gold, "candidate_anchor"
    repo_family = str(work_item.get("repo_family") or "")
    verifier_targets = list(work_item.get("verification_targets") or [])
    if repo_family in {"dbt-core", "repository_library"}:
        return "verifier_and_test_constraint", "repo_heuristic"
    if repo_family == "tiktoken":
        return "symptom_or_call_path_analogue", "repo_heuristic"
    if repo_family == "chroma":
        return "candidate_change_surface", "repo_heuristic"
    if len(verifier_targets) > 1:
        return "verifier_and_test_constraint", "multi_target_heuristic"
    return "candidate_change_surface", "fallback_heuristic"


def evidence_lines_for_work_item(work_item: dict[str, Any]) -> dict[str, str]:
    query = parsed_query_lines(str(work_item.get("query_text") or ""))
    changed_files = query.get("Changed files", "unknown")
    verification_targets = query.get("Verification targets", "unknown")
    verifier_route = query.get("Verifier route", "unknown")
    key_symbols = query.get("Key symbols", "unknown")
    first_changed = changed_files.split(",")[0].strip() if changed_files else "unknown_surface"
    first_symbol = key_symbols.split(",")[0].strip() if key_symbols else "unknown_symbol"
    return {
        "candidate_change_surface": (
            f"candidate_change_surface [{first_changed}]: Changed-file evidence points directly at {first_changed} as the candidate edit surface under the visible root state."
        ),
        "nearby_definition_or_usage_context": (
            f"nearby_definition_or_usage_context [{first_symbol}]: Nearby symbol/use context highlights {first_symbol} inside the same root state, but does not by itself prove the verifier target."
        ),
        "symptom_or_call_path_analogue": (
            f"symptom_or_call_path_analogue [{verification_targets}]: The visible failure/call-path analogue ties the issue to {verification_targets} through the exposed verification path."
        ),
        "verifier_and_test_constraint": (
            f"verifier_and_test_constraint [{verification_targets}]: Selected verification targets plus {verifier_route} constrain the intended repair surface more specifically than the changed file alone."
        ),
    }


def normalize_train_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["expected_enabled_loss"] = "decoder_ce"
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["same_surface_eval_admissible"] = False
    anti_cheat["train_support_only"] = True
    anti_cheat["fresh_ready_lane_support"] = True
    updated["anti_cheat"] = anti_cheat
    return updated


def render_semantic_prompt(
    work_item: dict[str, Any],
    *,
    task_line: str,
    answer_rule: str,
    option_values: list[str],
) -> str:
    query = parsed_query_lines(str(work_item.get("query_text") or ""))
    lines = [
        f"Language: {work_item.get('language_family')}",
        "Perspective: evidence_citation",
        f"Task: {task_line}",
        f"Repository: {query.get('Repository', work_item.get('repo_id', 'unknown'))}",
        f"Execution route: {query.get('Execution route', 'unknown')}",
        f"Verifier route: {query.get('Verifier route', 'unknown')}",
        f"Changed files: {query.get('Changed files', 'unknown')}",
        f"Verification targets: {query.get('Verification targets', 'unknown')}",
        "Evidence:",
    ]
    evidence_map = evidence_lines_for_work_item(work_item)
    for value in EVIDENCE_ROLE_OPTIONS:
        lines.append(evidence_map[value])
    lines.append("Semantic evidence role options:")
    for value in option_values:
        lines.append(f"- {value}")
    lines.append(answer_rule)
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def build_semantic_role_row(
    work_item: dict[str, Any],
    *,
    gold_value: str,
    gold_source: str,
) -> dict[str, Any]:
    prompt = render_semantic_prompt(
        work_item,
        task_line=(
            "Choose the semantic evidence role that most specifically justifies the edit-target decision. "
            "Prefer the strongest visible verifier/test constraint only when the packet actually supports that stronger claim."
        ),
        answer_rule="Output rule: Return only the semantic evidence role string.",
        option_values=EVIDENCE_ROLE_OPTIONS,
    )
    return normalize_train_row(
        {
            "anti_cheat": {
                "explicit_selected_test_ledger": True,
                "heuristic_gold_value": gold_source != "candidate_anchor",
                "opaque_labels_removed": True,
                "semantic_role_target": True,
                "target_path_strings_hidden_pre_options": True,
            },
            "decoder_text": gold_value,
            "input_text": prompt,
            "language_family": work_item.get("language_family"),
            "objective_family": "semantic_evidence_role_generation",
            "prompt_text": prompt,
            "query_text": str(work_item.get("query_text") or ""),
            "repo_family": work_item.get("repo_family"),
            "repo_id": work_item.get("repo_id"),
            "row_id": f"stage11082::{work_item.get('root_id')}::evidence_citation::semantic_role_full_v1",
            "selected_test_anchor": bool(work_item.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": work_item.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "candidate_anchor_ref": work_item.get("candidate_anchor_ref"),
                "gold_value": gold_value,
                "gold_value_source": gold_source,
                "projection_mode": "stage11082_ready_lane_semantic_evidence_role_full",
                "source_workstream": work_item.get("workstream"),
                "work_item_priority": work_item.get("priority"),
            },
            "surface": "maintainer_bundle_semantic_evidence_role",
            "target_text": gold_value,
            "target_token_len": max(1, len(gold_value.split())),
            "task_type": "evidence_citation",
            "verifier_anchor": bool(work_item.get("verification_targets")),
        }
    )


def build_pairwise_contrast_row(
    work_item: dict[str, Any],
    *,
    gold_value: str,
    gold_source: str,
) -> dict[str, Any] | None:
    negative_value = PAIRWISE_NEGATIVE_DEFAULT
    if gold_value == negative_value:
        if "verifier_and_test_constraint" in EVIDENCE_ROLE_OPTIONS:
            negative_value = "verifier_and_test_constraint"
        else:
            return None
    if negative_value == gold_value:
        return None
    prompt = render_semantic_prompt(
        work_item,
        task_line=(
            "Resolve the evidence-role contrast directly. Between the tempting changed-surface cue and the stronger causal support cue, "
            "return the role that is actually justified by the visible packet."
        ),
        answer_rule="Output rule: Return only the winning semantic evidence role string from the two listed options.",
        option_values=[gold_value, negative_value],
    )
    return normalize_train_row(
        {
            "anti_cheat": {
                "explicit_selected_test_ledger": True,
                "heuristic_gold_value": gold_source != "candidate_anchor",
                "pairwise_negative": negative_value,
                "semantic_contrast_target": True,
                "target_path_strings_hidden_pre_options": True,
            },
            "decoder_text": gold_value,
            "input_text": prompt,
            "language_family": work_item.get("language_family"),
            "objective_family": "semantic_evidence_role_pairwise_contrast",
            "prompt_text": prompt,
            "query_text": str(work_item.get("query_text") or ""),
            "repo_family": work_item.get("repo_family"),
            "repo_id": work_item.get("repo_id"),
            "row_id": f"stage11082::{work_item.get('root_id')}::evidence_citation::semantic_role_pairwise_contrast_v1",
            "selected_test_anchor": bool(work_item.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": work_item.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "candidate_anchor_ref": work_item.get("candidate_anchor_ref"),
                "gold_value": gold_value,
                "gold_value_source": gold_source,
                "negative_value": negative_value,
                "projection_mode": "stage11082_ready_lane_semantic_evidence_role_pairwise_contrast",
                "source_workstream": work_item.get("workstream"),
                "work_item_priority": work_item.get("priority"),
            },
            "surface": "maintainer_bundle_semantic_evidence_role",
            "target_text": gold_value,
            "target_token_len": max(1, len(gold_value.split())),
            "task_type": "evidence_citation",
            "verifier_anchor": bool(work_item.get("verification_targets")),
        }
    )


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    work_items = load_jsonl(WORK_ITEMS)
    candidate_rows_by_id = {
        str(row.get("row_id") or ""): row for row in load_jsonl(CANDIDATE_ROWS)
    }

    evidence_work_items = [
        row for row in work_items if str(row.get("workstream") or "") == "explicit_ledger_evidence_row_construction"
    ]

    semantic_rows: list[dict[str, Any]] = []
    for item in evidence_work_items:
        gold_value, gold_source = candidate_gold_value(item, candidate_rows_by_id)
        semantic_rows.append(build_semantic_role_row(item, gold_value=gold_value, gold_source=gold_source))
        contrast_row = build_pairwise_contrast_row(item, gold_value=gold_value, gold_source=gold_source)
        if contrast_row is not None:
            semantic_rows.append(contrast_row)

    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    added_rows = [row for row in semantic_rows if str(row.get("row_id") or "") not in existing_ids]
    train_rows = [*base_train, *added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(added_rows),
        "decision": "ready_lane_semantic_evidence_support_ready",
        "claim_scope": [
            "Add semantic evidence-role supervision on top of the clean ready-lane support package without changing validation, strict, or stress rows.",
            "Move evidence training away from answer-letter dependence by supervising direct role strings and pairwise contrasts against candidate_change_surface.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "work_items": rel(WORK_ITEMS),
            "candidate_rows": rel(CANDIDATE_ROWS),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "rows_added_total": len(added_rows),
            "semantic_role_full_rows": sum(1 for row in added_rows if str(row.get("objective_family") or "") == "semantic_evidence_role_generation"),
            "semantic_pairwise_rows": sum(1 for row in added_rows if str(row.get("objective_family") or "") == "semantic_evidence_role_pairwise_contrast"),
            "added_by_language": count_by(added_rows, "language_family"),
            "added_by_repo_family": count_by(added_rows, "repo_family"),
            "added_by_target_text": count_by(added_rows, "target_text"),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
            "base_train_rows_after_stage11061": base_summary.get("metrics", {}).get("train_rows_after"),
        },
        "findings": [
            "The ready-lane evidence roots can now supervise direct semantic evidence-role generation instead of only opaque answer letters.",
            "Each root also emits a pairwise contrast row against candidate_change_surface unless the gold role already is candidate_change_surface.",
            "This package is still support-only: it preserves the current heldout contract and canary while changing the training geometry for the blocked evidence lane.",
        ],
        "limits": [
            "Gold evidence roles still inherit the current candidate-anchor or heuristic mapping from the ready-lane work items.",
            "This stage does not alter the scorer architecture; it only improves the supervision surface available to the next probe.",
            "Rust evidence remains support-only and non-promotable until fresh reviewed non-aliased heldout replacements exist.",
        ],
        "required_honesty_gates": [
            "Do not report movement on these rows as heldout generalization.",
            "Keep the current cleaned strict contract unchanged when evaluating any probe that uses this package.",
            "Treat heuristic gold rows as support-only and keep them out of promotable strict slices.",
        ],
        "next_best_step": "Use this package for the next evidence-focused probe or scorer-head experiment, then re-audit the cleaned canary and reserved residual bank before considering any new promotion claim.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_JSONL, added_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
