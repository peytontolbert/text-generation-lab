#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11658
NAME = "stage11658_web_head_transfer_gap_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_head_transfer_gap_audit.json"

TRAIN_ROWS = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_probe_manifest.jsonl"
HELDOUT_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
TRAIN_AUDIT = ART / "stage11657_same_root_grouped_head_only_routed_audit/bounded_choice_eval_audit_grouped_web_gap_train_support__encoder_option_retrieval_web_task_candidate_head.json"
HELDOUT_AUDIT = ART / "stage11657_same_root_grouped_head_only_routed_audit/bounded_choice_eval_audit_web_heldout__encoder_option_retrieval_web_task_candidate_head.json"
ROUTED_SUMMARY = ART / "stage11657_same_root_grouped_head_only_routed_audit/same_root_grouped_head_only_routed_audit.json"

ROLE_VALUES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "abstain_insufficient_evidence",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "INSUFFICIENT_EVIDENCE_OPTION",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def option_records(row: dict[str, Any]) -> list[dict[str, Any]]:
    source = row.get("standalone_projection_source")
    if isinstance(source, dict) and isinstance(source.get("opaque_options"), list):
        return [opt for opt in source["opaque_options"] if isinstance(opt, dict)]
    if isinstance(row.get("opaque_options"), list):
        return [opt for opt in row["opaque_options"] if isinstance(opt, dict)]
    return []


def semantic_role(row: dict[str, Any], option: dict[str, Any]) -> str:
    if option.get("semantic_role"):
        return str(option["semantic_role"])
    value = str(option.get("value") or option.get("text") or "")
    if value in ROLE_VALUES:
        return value
    text = str(option.get("text") or "")
    lower = text.lower()
    if "abstain" in lower or "insufficient" in lower:
        return "abstain_insufficient_evidence"
    if "test" in lower or "verifier" in lower or "assert" in lower or "jest" in lower:
        return "verifier_and_test_constraint"
    if "implementation" in lower or "source" in lower or "::" in value or re.search(r"\.(tsx?|jsx?|html|css)\b", value):
        return "candidate_change_surface"
    if "not imported" in lower or "distractor" in lower or "unrelated" in lower:
        return "distractor_or_unrelated_surface"
    return "unknown"


def option_value_style(option: dict[str, Any]) -> str:
    value = str(option.get("value") or option.get("text") or "")
    text = str(option.get("text") or "")
    if value in ROLE_VALUES:
        return "semantic_role_literal"
    if "ABSTAIN" in value or "INSUFFICIENT" in value:
        return "abstain_literal"
    if re.search(r"\.(tsx?|jsx?|html|css|json|md)\b", value):
        return "path_or_symbol_handle"
    if len(text.split()) >= 5:
        return "natural_language_evidence_sentence"
    return "short_text_or_unknown"


def target_option(row: dict[str, Any]) -> dict[str, Any] | None:
    target = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
    for option in option_records(row):
        if str(option.get("label") or "") == target:
            return option
    return None


def prompt_markers(row: dict[str, Any]) -> list[str]:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    markers = []
    for marker in [
        "Decision criterion:",
        "Use only the visible source snippets",
        "Visible source evidence (opaque source IDs):",
        "Visible verifier/test evidence (opaque verifier IDs):",
        "Visible source evidence:",
        "Visible verifier/test evidence:",
        "Visible verifier execution evidence:",
        "Visible alternative/distractor evidence:",
        "Observed verifier transition:",
        "Verifier log excerpt:",
        "Task observation:",
        "Choose the implementation target",
    ]:
        if marker in prompt:
            markers.append(marker)
    return markers


def summarize_rows(rows: list[dict[str, Any]], cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    repo_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    root_counts: Counter[str] = Counter()
    option_count_counts: Counter[str] = Counter()
    option_style_counts: Counter[str] = Counter()
    option_role_counts: Counter[str] = Counter()
    target_label_counts: Counter[str] = Counter()
    target_role_counts: Counter[str] = Counter()
    target_style_counts: Counter[str] = Counter()
    marker_counts: Counter[str] = Counter()
    anti_cheat_counts: Counter[str] = Counter()
    prediction_counts: Counter[str] = Counter()
    miss_by_task: Counter[str] = Counter()
    correct_by_task: Counter[str] = Counter()
    rows_by_task: Counter[str] = Counter()
    miss_examples: list[dict[str, Any]] = []
    option_signature_counts: Counter[str] = Counter()
    for row in rows:
        row_id = str(row.get("row_id") or "")
        card = cards.get(row_id, {})
        repo_counts[str(row.get("repo_family") or row.get("git_repo_family") or row.get("web_heldout_source") or "unknown")] += 1
        task = str(row.get("task_type") or "unknown")
        task_counts[task] += 1
        rows_by_task[task] += 1
        root_counts[str(row.get("root_id") or row.get("root_lineage_key") or row_id)] += 1
        options = option_records(row)
        option_count_counts[str(len(options))] += 1
        target_label = str(row.get("bounded_choice_target_label") or row.get("target_text") or "")
        target_label_counts[target_label] += 1
        roles = [semantic_role(row, opt) for opt in options]
        styles = [option_value_style(opt) for opt in options]
        option_signature_counts["|".join(sorted(roles))] += 1
        option_role_counts.update(roles)
        option_style_counts.update(styles)
        target = target_option(row)
        if target is not None:
            target_role_counts[semantic_role(row, target)] += 1
            target_style_counts[option_value_style(target)] += 1
        marker_counts.update(prompt_markers(row))
        anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        for key, value in anti_cheat.items():
            if value is True:
                anti_cheat_counts[key] += 1
        predicted = str(card.get("constrained_choice_top1_label") or "")
        if predicted:
            prediction_counts[predicted] += 1
        if card.get("constrained_choice_match") is True:
            correct_by_task[task] += 1
        else:
            miss_by_task[task] += 1
            if len(miss_examples) < 25:
                miss_examples.append(
                    {
                        "row_id": row_id,
                        "task_type": task,
                        "repo_family": row.get("repo_family") or row.get("web_heldout_source"),
                        "target_label": target_label,
                        "target_role": semantic_role(row, target) if target is not None else None,
                        "predicted": predicted or None,
                        "full_vocab_top1_text": card.get("full_vocab_top1_text"),
                        "option_roles": roles,
                        "option_styles": styles,
                    }
                )
    task_accuracy = {
        task: {
            "correct": correct_by_task[task],
            "rows": rows_by_task[task],
            "accuracy": correct_by_task[task] / rows_by_task[task] if rows_by_task[task] else None,
        }
        for task in sorted(rows_by_task)
    }
    return {
        "rows": len(rows),
        "unique_roots": len(root_counts),
        "repo_counts": dict(repo_counts.most_common()),
        "task_counts": dict(task_counts.most_common()),
        "option_count_counts": dict(option_count_counts.most_common()),
        "option_style_counts": dict(option_style_counts.most_common()),
        "option_role_counts": dict(option_role_counts.most_common()),
        "target_label_counts": dict(target_label_counts.most_common()),
        "target_role_counts": dict(target_role_counts.most_common()),
        "target_style_counts": dict(target_style_counts.most_common()),
        "prompt_marker_counts": dict(marker_counts.most_common()),
        "anti_cheat_true_counts": dict(anti_cheat_counts.most_common()),
        "prediction_label_counts": dict(prediction_counts.most_common()),
        "task_accuracy": task_accuracy,
        "top_option_role_signatures": dict(option_signature_counts.most_common(20)),
        "miss_examples": miss_examples,
    }


def card_map(path: Path) -> dict[str, dict[str, Any]]:
    card = load_json(path)
    return {str(row.get("row_id")): row for row in card.get("row_cards") or [] if isinstance(row, dict)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train_rows = load_jsonl(TRAIN_ROWS)
    heldout_rows = load_jsonl(HELDOUT_ROWS)
    train_cards = card_map(TRAIN_AUDIT)
    heldout_cards = card_map(HELDOUT_AUDIT)
    train_summary = summarize_rows(train_rows, train_cards)
    heldout_summary = summarize_rows(heldout_rows, heldout_cards)
    train_roots = {str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id")) for row in train_rows}
    heldout_roots = {str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id")) for row in heldout_rows}
    routed = load_json(ROUTED_SUMMARY)

    findings = []
    if train_summary["option_style_counts"].get("path_or_symbol_handle", 0) > train_summary["option_style_counts"].get("natural_language_evidence_sentence", 0):
        findings.append("train_options_are_mostly_path_or_symbol_handles")
    if heldout_summary["option_style_counts"].get("natural_language_evidence_sentence", 0) > 0:
        findings.append("heldout_contains_natural_language_evidence_sentence_options_absent_or_underrepresented_in_train")
    if train_summary["prompt_marker_counts"].get("Decision criterion:", 0) and not heldout_summary["prompt_marker_counts"].get("Decision criterion:", 0):
        findings.append("train_prompts_have_explicit_decision_criterion_marker_not_present_in_heldout")
    if train_summary["prompt_marker_counts"].get("Observed verifier transition:", 0) and not heldout_summary["prompt_marker_counts"].get("Observed verifier transition:", 0):
        findings.append("train_prompts_use_observed_transition_marker_while_heldout_uses_execution_evidence_text")
    if routed["results"]["grouped_web_gap_train_support"]["correct"] >= 100 and routed["results"]["web_heldout"]["correct"] <= 10:
        findings.append("head_memorizes_or_fits_train_geometry_without_heldout_transfer")
    if not (train_roots & heldout_roots):
        findings.append("root_sets_are_disjoint_so_transfer_failure_is_not_from_root_overlap")

    recommendation = {
        "decision": "do_not_train_more_on_stage11648_shell_geometry_without_alignment",
        "next_intervention": "build_schema_aligned_web_bridge_rows_or_convert_train_rows_to_heldout_style_before_probing",
        "minimum_requirements": [
            "Use the same option-value style as heldout: natural-language evidence/candidate descriptions, not only path handles.",
            "Use the same prompt markers as heldout or deliberately normalize both train and heldout through one renderer.",
            "Keep root-disjoint OpenHands/Llama heldout untouched.",
            "Probe schema-aligned train support before any full-model run.",
            "Promotion still requires web heldout >38/66 and protected gates preserved.",
        ],
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_transfer_failure_explained_by_schema_and_option_geometry_mismatch",
        "findings": findings,
        "train_summary": train_summary,
        "heldout_summary": heldout_summary,
        "root_overlap": {
            "train_roots": len(train_roots),
            "heldout_roots": len(heldout_roots),
            "overlap_count": len(train_roots & heldout_roots),
            "overlap_examples": sorted(train_roots & heldout_roots)[:20],
        },
        "stage11657_scores": {
            key: {
                "correct": value.get("correct"),
                "rows": value.get("rows"),
                "accuracy": value.get("accuracy"),
                "scorer": value.get("scorer"),
            }
            for key, value in routed.get("results", {}).items()
        },
        "recommendation": recommendation,
        "source_artifacts": {
            "train_rows": rel(TRAIN_ROWS),
            "heldout_rows": rel(HELDOUT_ROWS),
            "train_audit": rel(TRAIN_AUDIT),
            "heldout_audit": rel(HELDOUT_AUDIT),
            "routed_summary": rel(ROUTED_SUMMARY),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "findings": findings, "recommendation": recommendation}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
