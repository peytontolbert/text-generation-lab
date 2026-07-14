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
STAGE = 11097
NAME = "stage11097_fresh_family_materialized_rows"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_materialized_rows.json"
SCOREABLE_ROWS_JSONL = OUT_DIR / "scoreable_support_rows.jsonl"
EVIDENCE_ROWS_JSONL = OUT_DIR / "evidence_candidate_rows.jsonl"
VERIFIER_ROWS_JSONL = OUT_DIR / "verifier_support_rows.jsonl"
ALL_ROWS_JSONL = OUT_DIR / "all_materialized_rows.jsonl"

WORK_ITEMS = ARTIFACTS / "stage11096_fresh_family_row_construction_manifest" / "fresh_family_row_construction_work_items.jsonl"
PACKET_ROWS = ARTIFACTS / "stage11094_fresh_family_materialization_packet" / "fresh_family_packet_rows.jsonl"

EVIDENCE_ROLE_OPTIONS = [
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]
RAA_OPTIONS = [
    "ANSWER_WITH_RETRIEVED_EVIDENCE",
    "RETRIEVE_MORE",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "NEEDS_VERIFIER",
]
VERIFIER_TRANSITIONS = {
    "gold": "FAIL_TO_PASS",
    "distractor_near": "NOT_EXERCISED",
    "distractor_far": "PASS_TO_PASS",
}


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


def hashed_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest())


def relabel_option_values(values: list[str]) -> list[dict[str, str]]:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [{"label": labels[idx], "value": value} for idx, value in enumerate(values)]


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
    anti_cheat["fresh_family_materialized"] = True
    updated["anti_cheat"] = anti_cheat
    return updated


def normalize_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "strict_eval_candidate"
    updated["train_support_only"] = False
    updated["strict_eval_eligible"] = False
    updated["source_heldout_admissible"] = False
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["same_surface_eval_admissible"] = False
    anti_cheat["requires_review_before_training"] = True
    anti_cheat["fresh_family_materialized"] = True
    updated["anti_cheat"] = anti_cheat
    return updated


def packet_prompt_for_scoreable(row: dict[str, Any]) -> str:
    query = parsed_query_lines(str(row.get("query_text") or ""))
    task = str(row.get("target_subtype") or "")
    task_line = {
        "retrieve_answer_abstain": (
            "Task: Decide whether the visible root evidence is already sufficient to answer, whether more retrieval is needed, whether the model should abstain, or whether a verifier is still needed."
        ),
        "verifier_outcome": (
            "Task: Predict the verifier route outcome directly supported by the visible root evidence and selected verification targets."
        ),
    }.get(task, "Task: Choose the best semantic action from the visible root evidence.")
    lines = [
        f"Language: {row.get('language_family')}",
        f"Perspective: {task}",
        task_line,
        f"Repository: {query.get('Repository', row.get('repo_id', 'unknown'))}",
        f"Verifier route: {query.get('Verifier route', 'unknown')}",
        f"Execution route: {query.get('Execution route', 'unknown')}",
        f"Changed files: {query.get('Changed files', 'unknown')}",
        f"Verification targets: {query.get('Verification targets', 'unknown')}",
        f"Key symbols: {query.get('Key symbols', 'unknown')}",
        "Visible evidence handles:",
    ]
    for idx, evidence_id in enumerate(list(row.get("visible_evidence_ids") or [])[:8], start=1):
        lines.append(f"E{idx}. {evidence_id}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def build_scoreable_support_row(row: dict[str, Any]) -> dict[str, Any]:
    prompt = packet_prompt_for_scoreable(row)
    target_text = str(row.get("target_text_parsed") or row.get("target_text") or "")
    return normalize_train_row(
        {
            "anti_cheat": {
                "opaque_labels": False,
                "prompt_target_visible_by_design": False,
                "scoreable_packet_row_reused": True,
            },
            "decoder_text": target_text,
            "input_text": prompt,
            "language_family": row.get("language_family"),
            "objective_family": "decoder_ce",
            "prompt_text": prompt,
            "query_text": str(row.get("query_text") or ""),
            "repo_family": row.get("repo_family"),
            "repo_id": row.get("repo_id"),
            "row_id": f"stage11097::{row.get('row_id')}::support",
            "selected_test_anchor": bool(row.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": row.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "projection_mode": "stage11097_fresh_family_scoreable_support",
                "source_row_id": row.get("row_id"),
                "target_subtype": row.get("target_subtype"),
            },
            "surface": "long_context_compact_state_projection",
            "target_text": target_text,
            "target_token_len": max(1, len(target_text.split())),
            "task_type": str(row.get("target_subtype") or ""),
            "verifier_anchor": bool(row.get("verification_targets")),
        }
    )


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
            f"nearby_definition_or_usage_context [{first_symbol}]: Nearby definition or usage context highlights {first_symbol} inside the same root state, but does not by itself prove the verifier target."
        ),
        "symptom_or_call_path_analogue": (
            f"symptom_or_call_path_analogue [{verification_targets}]: The visible symptom or call-path analogue ties the issue to {verification_targets} through the exposed verification path."
        ),
        "verifier_and_test_constraint": (
            f"verifier_and_test_constraint [{verification_targets}]: Selected verification targets plus {verifier_route} constrain the intended repair surface more specifically than the changed file alone."
        ),
    }


def heuristic_evidence_gold(work_item: dict[str, Any]) -> tuple[str, str]:
    verification_targets = list(work_item.get("verification_targets") or [])
    expected_changed_files = list(work_item.get("expected_changed_files") or [])
    repo_family = str(work_item.get("repo_family") or "")

    if len(verification_targets) > 1:
        return "verifier_and_test_constraint", "multi_verification_targets"
    if repo_family in {"falco", "cuEmbed"}:
        return "candidate_change_surface", "single_target_cpp_family"
    if repo_family in {"mem0"}:
        return "verifier_and_test_constraint", "web_selected_test_bias"
    if expected_changed_files and verification_targets:
        changed_join = " ".join(expected_changed_files).lower()
        target_join = " ".join(verification_targets).lower()
        if any(token in target_join for token in ["test", "spec"]):
            return "verifier_and_test_constraint", "target_mentions_tests"
        if any(token in changed_join for token in ["test", "spec"]):
            return "candidate_change_surface", "changed_surface_test_heavy"
    return "verifier_and_test_constraint", "fallback_verifier_constraint"


def evidence_prompt(work_item: dict[str, Any], options: list[dict[str, str]]) -> str:
    query = parsed_query_lines(str(work_item.get("query_text") or ""))
    lines = [
        f"Language: {work_item.get('language_family')}",
        "Perspective: evidence_citation",
        "Task: Choose the visible evidence key that most specifically justifies the maintenance decision. Prefer the strongest packet-visible justification rather than defaulting to the changed file.",
        f"Repository: {query.get('Repository', work_item.get('repo_id', 'unknown'))}",
        f"Execution route: {query.get('Execution route', 'unknown')}",
        f"Verifier route: {query.get('Verifier route', 'unknown')}",
        f"Changed files: {query.get('Changed files', 'unknown')}",
        f"Verification targets: {query.get('Verification targets', 'unknown')}",
        "Visible evidence ledger:",
    ]
    evidence_map = evidence_lines_for_work_item(work_item)
    for idx, value in enumerate(EVIDENCE_ROLE_OPTIONS, start=1):
        lines.append(f"E{idx:02d}. {evidence_map[value]}")
    lines.append("Options:")
    for option in options:
        lines.append(f"{option['label']}. {option['value']}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def build_evidence_candidate_rows(work_item: dict[str, Any]) -> list[dict[str, Any]]:
    gold_value, gold_source = heuristic_evidence_gold(work_item)
    variants = ["verifier_first", "candidate_first"]
    rows: list[dict[str, Any]] = []
    for variant in variants:
        ordered_values = hashed_order(EVIDENCE_ROLE_OPTIONS, f"{work_item['root_id']}::{variant}")
        options = relabel_option_values(ordered_values)
        target_label = next(option["label"] for option in options if option["value"] == gold_value)
        prompt = evidence_prompt(work_item, options)
        row = normalize_candidate_row(
            {
                "anti_cheat": {
                    "deterministic_option_shuffle": True,
                    "explicit_selected_test_ledger": True,
                    "heuristic_gold_value": True,
                    "opaque_labels": True,
                    "target_path_strings_hidden_pre_options": True,
                },
                "decoder_text": target_label,
                "input_text": prompt,
                "language_family": work_item.get("language_family"),
                "objective_family": "bounded_decoder_ce",
                "opaque_options": options,
                "prompt_text": prompt,
                "query_text": str(work_item.get("query_text") or ""),
                "repo_family": work_item.get("repo_family"),
                "repo_id": work_item.get("repo_id"),
                "row_id": f"stage11097::{work_item.get('root_id')}::evidence_citation::{variant}",
                "selected_test_anchor": bool(work_item.get("verification_targets")),
                "source_root_id": work_item.get("root_id"),
                "split_role": "candidate_not_admitted",
                "standalone_projection_source": {
                    "gold_value": gold_value,
                    "gold_value_source": gold_source,
                    "projection_mode": "stage11097_fresh_family_evidence_candidate",
                    "work_item_priority": work_item.get("priority"),
                },
                "surface": "maintainer_bundle_compact_bounded_choice",
                "target_text": target_label,
                "target_token_len": 1,
                "task_type": "evidence_citation",
                "verifier_anchor": bool(work_item.get("verification_targets")),
            }
        )
        rows.append(row)
    return rows


def verifier_prompt(work_item: dict[str, Any], options: list[dict[str, str]]) -> str:
    query = parsed_query_lines(str(work_item.get("query_text") or ""))
    lines = [
        f"Language: {work_item.get('language_family')}",
        "Perspective: verifier_outcome_semantic_transition",
        "Task: Choose which opaque verifier target is most directly expected to flip from FAIL to PASS if the visible candidate repair surface is correct.",
        f"Repository: {query.get('Repository', work_item.get('repo_id', 'unknown'))}",
        f"Execution route: {query.get('Execution route', 'unknown')}",
        f"Changed files: {query.get('Changed files', 'unknown')}",
        f"Verification targets: {query.get('Verification targets', 'unknown')}",
        "Visible verifier/test evidence:",
        f"selected_tests: {query.get('Verification targets', 'unknown')}",
        f"verifier_route: {query.get('Verifier route', 'unknown')}",
        "Options:",
    ]
    for option in options:
        lines.append(f"{option['label']}. {option['value']}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def verifier_candidates(work_item: dict[str, Any]) -> tuple[list[str], str, str]:
    verification_targets = list(work_item.get("verification_targets") or [])
    candidate_paths = list(dict.fromkeys(verification_targets))[:4]
    if not candidate_paths:
        candidate_paths = ["unknown_test_target"]
    while len(candidate_paths) < 2:
        candidate_paths.append(f"nearby_same_family_distractor_{len(candidate_paths)+1}")
    gold_path = candidate_paths[0]
    values = []
    for idx, path in enumerate(candidate_paths, start=1):
        transition = VERIFIER_TRANSITIONS["gold"] if idx == 1 else (
            VERIFIER_TRANSITIONS["distractor_near"] if idx == 2 else VERIFIER_TRANSITIONS["distractor_far"]
        )
        values.append(f"T{idx} | {transition} | {path}")
    gold_value = values[0]
    return values, gold_value, "verification_target_primary"


def build_verifier_support_row(work_item: dict[str, Any]) -> dict[str, Any]:
    values, gold_value, gold_source = verifier_candidates(work_item)
    ordered_values = hashed_order(values, f"{work_item['root_id']}::verifier_transition")
    options = relabel_option_values(ordered_values)
    target_label = next(option["label"] for option in options if option["value"] == gold_value)
    prompt = verifier_prompt(work_item, options)
    return normalize_train_row(
        {
            "anti_cheat": {
                "deterministic_option_shuffle": True,
                "opaque_verifier_target_ids": True,
                "semantic_transition_visible": True,
                "singleton_verifier_rows": False,
                "target_path_strings_hidden_pre_options": True,
            },
            "decoder_text": target_label,
            "input_text": prompt,
            "language_family": work_item.get("language_family"),
            "objective_family": "bounded_decoder_ce",
            "opaque_options": options,
            "prompt_text": prompt,
            "query_text": str(work_item.get("query_text") or ""),
            "repo_family": work_item.get("repo_family"),
            "repo_id": work_item.get("repo_id"),
            "row_id": f"stage11097::{work_item.get('root_id')}::verifier_outcome_semantic_transition::support",
            "selected_test_anchor": bool(work_item.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": work_item.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "gold_value": gold_value,
                "gold_value_source": gold_source,
                "projection_mode": "stage11097_fresh_family_verifier_support",
                "work_item_priority": work_item.get("priority"),
            },
            "surface": "maintainer_bundle_compact_bounded_choice",
            "target_text": target_label,
            "target_token_len": 1,
            "task_type": "verifier_outcome_semantic_transition",
            "verifier_anchor": True,
        }
    )


def main() -> None:
    work_items = load_jsonl(WORK_ITEMS)
    packet_rows = load_jsonl(PACKET_ROWS)

    scoreable_rows = [
        build_scoreable_support_row(row)
        for row in packet_rows
        if bool((row.get("scoreability") or {}).get("scoreable_now"))
    ]

    evidence_work_items = [row for row in work_items if str(row.get("workstream") or "") == "explicit_ledger_evidence_row_construction"]
    verifier_work_items = [row for row in work_items if str(row.get("workstream") or "") == "verifier_transition_row_construction"]

    evidence_rows: list[dict[str, Any]] = []
    for item in evidence_work_items:
        evidence_rows.extend(build_evidence_candidate_rows(item))

    verifier_rows = [build_verifier_support_row(item) for item in verifier_work_items]
    all_rows = [*scoreable_rows, *evidence_rows, *verifier_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(all_rows),
        "decision": "fresh_family_rows_materialized",
        "claim_scope": [
            "Materialize concrete fresh-family support and candidate rows from the stage11096 row-construction manifest.",
            "Keep scoreable verifier/retrieve packet rows usable immediately while marking fresh evidence rows as candidate-only until review catches up.",
        ],
        "metrics": {
            "scoreable_support_rows": len(scoreable_rows),
            "evidence_candidate_rows": len(evidence_rows),
            "verifier_support_rows": len(verifier_rows),
            "all_rows": len(all_rows),
            "all_rows_by_language": count_by(all_rows, "language_family"),
            "all_rows_by_task": count_by(all_rows, "task_type"),
            "all_rows_by_repo_family": count_by(all_rows, "repo_family"),
            "heuristic_evidence_rows": sum(1 for row in evidence_rows if bool((row.get("anti_cheat") or {}).get("heuristic_gold_value"))),
        },
        "headline_findings": [
            "Fresh-family scoreable packet rows are now concrete train-support rows for retrieve_answer_abstain and verifier_outcome.",
            "Evidence-ledger rows are materialized as explicit bounded candidates with recorded option shuffle, but remain non-promotable until anti-cheat review confirms the heuristic golds.",
            "Verifier-transition rows are materialized as support-only opaque target competitions with no singleton options.",
        ],
        "limits": [
            "Evidence candidate gold values are heuristic at this stage and should not be treated as heldout proof.",
            "Web rows remain mixed and should stay off the promotable path until selected-test anchoring is stronger.",
        ],
        "next_best_step": [
            "Audit the evidence candidate rows for role balance, heuristic label skew, and option-order hygiene.",
            "Merge the support-eligible rows into the next train package while keeping validation and strict heldout unchanged.",
        ],
        "source_artifacts": {
            "work_items": rel(WORK_ITEMS),
            "packet_rows": rel(PACKET_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "scoreable_rows_jsonl": rel(SCOREABLE_ROWS_JSONL),
            "evidence_rows_jsonl": rel(EVIDENCE_ROWS_JSONL),
            "verifier_rows_jsonl": rel(VERIFIER_ROWS_JSONL),
            "all_rows_jsonl": rel(ALL_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(SCOREABLE_ROWS_JSONL, scoreable_rows)
    write_jsonl(EVIDENCE_ROWS_JSONL, evidence_rows)
    write_jsonl(VERIFIER_ROWS_JSONL, verifier_rows)
    write_jsonl(ALL_ROWS_JSONL, all_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
