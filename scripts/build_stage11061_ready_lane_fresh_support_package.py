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
STAGE = 11061
NAME = "stage11061_ready_lane_fresh_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "ready_lane_fresh_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_ROWS_JSONL = OUT_DIR / "added_ready_lane_support_rows.jsonl"
HEURISTIC_ROWS_JSONL = OUT_DIR / "heuristic_support_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence"
BASE_SUMMARY = BASE_DIR / "successor_residual_support_plus_priority_evidence.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

WORK_ITEMS = ARTIFACTS / "stage11060_ready_lane_row_construction_manifest" / "row_construction_work_items.jsonl"
READY_PACKET_ROWS = ARTIFACTS / "stage11059_ready_lane_materialization_packet" / "ready_packet_rows.jsonl"
CANDIDATE_ROWS = ARTIFACTS / "stage10938_explicit_verifier_ledger_strict_candidates" / "strict_candidate_rows.jsonl"

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


def short_text(text: str, limit: int = 180) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def parsed_query_lines(query_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in query_text.splitlines():
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
    updated["fresh_ready_lane_support"] = True
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["same_surface_eval_admissible"] = False
    anti_cheat["train_support_only"] = True
    anti_cheat["fresh_ready_lane_support"] = True
    updated["anti_cheat"] = anti_cheat
    return updated


def packet_prompt_for_scoreable(row: dict[str, Any]) -> str:
    query = parsed_query_lines(str(row.get("query_text") or ""))
    task = str(row.get("target_subtype") or "")
    task_line = {
        "retrieve_answer_abstain": (
            "Task: Decide whether the visible root evidence is already sufficient to answer, whether more retrieval is needed, or whether the model should abstain."
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
    query = parsed_query_lines(str(row.get("query_text") or ""))
    target_text = str(row.get("target_text_parsed") or row.get("target_text") or "")
    return normalize_train_row(
        {
            "anti_cheat": {
                "opaque_labels": False,
                "prompt_target_visible_by_design": False,
                "ready_lane_packet_projection": True,
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
            "row_id": f"stage11061::{row.get('row_id')}::support",
            "selected_test_anchor": bool(row.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": row.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "projection_mode": "stage11061_ready_packet_scoreable_support",
                "source_row_id": row.get("row_id"),
                "target_subtype": row.get("target_subtype"),
                "verifier_route": query.get("Verifier route", ""),
            },
            "surface": "long_context_compact_state_projection",
            "target_text": target_text,
            "target_token_len": max(1, len(target_text.split())),
            "task_type": str(row.get("target_subtype") or ""),
            "verifier_anchor": bool(row.get("verification_targets")),
        }
    )


def candidate_gold_value(work_item: dict[str, Any], candidate_rows_by_id: dict[str, dict[str, Any]]) -> tuple[str, str]:
    candidate_anchor = work_item.get("candidate_anchor_ref") or {}
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


def evidence_prompt(work_item: dict[str, Any], options: list[dict[str, str]]) -> str:
    query = parsed_query_lines(str(work_item.get("query_text") or ""))
    lines = [
        f"Language: {work_item.get('language_family')}",
        "Perspective: evidence_citation",
        "Task: Choose the visible evidence key that most specifically justifies the edit-target decision. Prefer the strongest packet-visible justification rather than defaulting to the changed file.",
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
    lines.append("Options:")
    for option in options:
        lines.append(f"{option['label']}. {option['value']}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def build_evidence_support_rows(work_item: dict[str, Any], candidate_rows_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    gold_value, gold_source = candidate_gold_value(work_item, candidate_rows_by_id)
    variants = ["verifier_first", "candidate_first"]
    rows: list[dict[str, Any]] = []
    for variant in variants:
        ordered_values = hashed_order(EVIDENCE_ROLE_OPTIONS, f"{work_item['root_id']}::{variant}")
        options = relabel_option_values(ordered_values)
        target_label = next(option["label"] for option in options if option["value"] == gold_value)
        prompt = evidence_prompt(work_item, options)
        row = normalize_train_row(
            {
                "anti_cheat": {
                    "deterministic_option_shuffle": True,
                    "explicit_selected_test_ledger": True,
                    "heuristic_gold_value": gold_source != "candidate_anchor",
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
                "row_id": f"stage11061::{work_item.get('root_id')}::evidence_citation::{variant}",
                "selected_test_anchor": bool(work_item.get("verification_targets")),
                "source_heldout_admissible": False,
                "source_root_id": work_item.get("root_id"),
                "split_role": "train_support_only",
                "standalone_projection_source": {
                    "candidate_anchor_ref": work_item.get("candidate_anchor_ref"),
                    "gold_value": gold_value,
                    "gold_value_source": gold_source,
                    "projection_mode": "stage11061_ready_lane_evidence_support",
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
    reviewed = list(work_item.get("reviewed_bundle_refs") or [])
    selected_tests: list[str] = []
    for bundle in reviewed:
        selected_tests.extend(list(bundle.get("selected_tests") or []))
    candidate_paths = []
    for path in verification_targets + selected_tests:
        if path not in candidate_paths:
            candidate_paths.append(path)
    if not candidate_paths:
        candidate_paths = ["unknown_test_target"]
    gold_path = verification_targets[0] if verification_targets else candidate_paths[0]
    gold_source = "verification_target_primary" if verification_targets else "fallback_candidate"
    values = []
    for idx, path in enumerate(candidate_paths[:4], start=1):
        transition = VERIFIER_TRANSITIONS["gold"] if path == gold_path else (
            VERIFIER_TRANSITIONS["distractor_near"] if idx == 2 else VERIFIER_TRANSITIONS["distractor_far"]
        )
        values.append(f"T{idx} | {transition} | {path}")
    if len(values) == 1:
        values.append(f"T2 | {VERIFIER_TRANSITIONS['distractor_near']} | nearby_same_family_distractor")
    gold_value = next(value for value in values if gold_path in value)
    return values, gold_value, gold_source


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
            "row_id": f"stage11061::{work_item.get('root_id')}::verifier_outcome_semantic_transition::support",
            "selected_test_anchor": bool(work_item.get("verification_targets")),
            "source_heldout_admissible": False,
            "source_root_id": work_item.get("root_id"),
            "split_role": "train_support_only",
            "standalone_projection_source": {
                "gold_value": gold_value,
                "gold_value_source": gold_source,
                "projection_mode": "stage11061_ready_lane_verifier_support",
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
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    work_items = load_jsonl(WORK_ITEMS)
    ready_rows = load_jsonl(READY_PACKET_ROWS)
    candidate_rows_by_id = {
        str(row.get("row_id") or ""): row for row in load_jsonl(CANDIDATE_ROWS)
    }

    scoreable_packet_rows = [
        build_scoreable_support_row(row)
        for row in ready_rows
        if bool((row.get("scoreability") or {}).get("scoreable_now"))
    ]

    evidence_work_items = [row for row in work_items if str(row.get("workstream") or "") == "explicit_ledger_evidence_row_construction"]
    verifier_work_items = [row for row in work_items if str(row.get("workstream") or "") == "verifier_transition_row_construction"]

    evidence_rows: list[dict[str, Any]] = []
    heuristic_rows: list[dict[str, Any]] = []
    for item in evidence_work_items:
        built = build_evidence_support_rows(item, candidate_rows_by_id)
        evidence_rows.extend(built)
        if all(bool((row.get("anti_cheat") or {}).get("heuristic_gold_value")) for row in built):
            heuristic_rows.extend(built)

    verifier_rows = [build_verifier_support_row(item) for item in verifier_work_items]

    added_rows = [*scoreable_packet_rows, *evidence_rows, *verifier_rows]
    existing_ids = {str(row.get("row_id") or "") for row in base_train}
    deduped_added_rows = [row for row in added_rows if str(row.get("row_id") or "") not in existing_ids]
    train_rows = [*base_train, *deduped_added_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(deduped_added_rows),
        "decision": "ready_lane_fresh_support_package_ready",
        "claim_scope": [
            "Extend the successor residual support package with concrete fresh-ready-lane support rows built from the stage11060 row-construction work items.",
            "Reuse already scoreable ready-packet rows directly for retrieve/answer/abstain and verifier-route supervision.",
            "Add explicit-ledger evidence rows and verifier-transition support rows while keeping validation/strict/stress unchanged.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "work_items": rel(WORK_ITEMS),
            "ready_packet_rows": rel(READY_PACKET_ROWS),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "rows_added_total": len(deduped_added_rows),
            "scoreable_packet_rows_added": len(scoreable_packet_rows),
            "evidence_rows_added": len(evidence_rows),
            "verifier_rows_added": len(verifier_rows),
            "heuristic_support_rows": len(heuristic_rows),
            "added_by_language": count_by(deduped_added_rows, "language_family"),
            "added_by_task": count_by(deduped_added_rows, "task_type"),
            "added_by_repo_family": count_by(deduped_added_rows, "repo_family"),
            "base_train_rows_after_stage11051": base_summary.get("metrics", {}).get("train_rows_after"),
            "validation_rows_unchanged": len(validation_rows),
            "strict_rows_unchanged": len(strict_rows),
            "stress_rows_unchanged": len(stress_rows),
        },
        "findings": [
            "The ready-lane packet is now executable as train support rather than remaining a planning-only packet.",
            "Python explicit-ledger rows keep the higher-confidence candidate-anchor geometry from the existing strict-candidate family.",
            "Rust evidence rows are included as heuristic support only and are explicitly marked non-promotable until fresh reviewed evidence candidates exist.",
            "C/C++ verifier-transition rows are added as support-only semantic-transition training, with opaque verifier IDs and no singleton options.",
        ],
        "limits": [
            "Validation and strict are copied unchanged; this stage is support-only and not a new heldout result.",
            "Rust evidence gold values are partly heuristic because the ready lane lacks fresh reviewed strict-candidate anchors for those roots.",
            "Multi-target C/C++ verifier roots still need richer reviewed target adjudication before promotion claims.",
        ],
        "required_honesty_gates": [
            "Do not report movement on any stage11061-added rows as heldout generalization.",
            "Keep heuristic Rust evidence rows separate from promotable strict successors until reviewed replacements exist.",
            "Preserve the existing 23-row successor validation/strict overlay unchanged when evaluating any probe from this package.",
        ],
        "next_best_step": "Run one bounded support probe from the latest clean runtime, report the unchanged successor overlay separately, and inspect whether the added ready-lane support changes the reserved residual bank.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_rows_jsonl": rel(ADDED_ROWS_JSONL),
            "heuristic_rows_jsonl": rel(HEURISTIC_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_ROWS_JSONL, deduped_added_rows)
    write_jsonl(HEURISTIC_ROWS_JSONL, heuristic_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
