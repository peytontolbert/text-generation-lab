#!/usr/bin/env python3
"""Materialize contract-aware evidence-citation rows from the stage11177 queue.

The stage11177 queue is intentionally only a materialization request. This
script joins those requests back to concrete long-context retrieval rows and
admits only rows whose visible evidence can support the requested role under
the stage11175 evidence-role contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUEUE_DIR = ROOT / "runs/local/artifacts/stage11177_root_disjoint_evidence_materialization_queue"
SOURCE_RETRIEVAL = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11178_contract_aware_evidence_rows"

ROLE_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]
TARGET_ROLES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
}
LABELS = list("ABCDEFGHIJ")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_query_index(root_id: str) -> int | None:
    match = re.search(r"::q(\d+)$", root_id)
    return int(match.group(1)) if match else None


def parse_query_lines(query_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in query_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower().replace(" ", "_")] = value.strip()
    return fields


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def short_list(values: list[str], limit: int = 3) -> str:
    if not values:
        return "none recorded"
    head = values[:limit]
    suffix = "" if len(values) <= limit else f" (+{len(values) - limit} more)"
    return ", ".join(head) + suffix


def retrieval_index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        q = (row.get("metadata") or {}).get("query_index")
        if isinstance(q, int):
            out[(str(row.get("pack_id")), q)] = row
    return out


def role_supports(retrieval: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for support in retrieval.get("support_scores") or []:
        if isinstance(support, dict):
            grouped[str(support.get("role") or "unknown")].append(support)
    for values in grouped.values():
        values.sort(key=lambda s: (-int(s.get("score") or 0), str(s.get("path") or "")))
    return grouped


def first_path(supports: list[dict[str, Any]]) -> str | None:
    for support in supports:
        path = support.get("path")
        if path:
            return str(path)
    return None


def evidence_facts(work_item: dict[str, Any], retrieval: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    fields = parse_query_lines(str(retrieval.get("query_text") or ""))
    changed_files = split_csv(fields.get("changed_files"))
    verification_targets = split_csv(fields.get("verification_targets"))
    key_symbols = split_csv(fields.get("key_symbols"))
    supports = role_supports(retrieval)

    seed_path = first_path(supports.get("seed_change", [])) or (changed_files[0] if changed_files else None)
    verifier_path = first_path(supports.get("verification_constraint", [])) or (
        verification_targets[0] if verification_targets else None
    )
    symptom_path = (
        first_path(supports.get("trace_analogue", []))
        or first_path(supports.get("cross_repo_analogue", []))
        or None
    )
    algorithm_path = first_path(supports.get("algorithm_grounding", []))

    blockers: list[str] = []
    if not seed_path:
        blockers.append("missing_candidate_surface_path")
    if not verifier_path:
        blockers.append("missing_verifier_or_selected_test_path")
    if not (symptom_path or key_symbols):
        blockers.append("missing_symptom_or_call_path_evidence")

    if symptom_path and seed_path and symptom_path == seed_path:
        blockers.append("symptom_path_duplicates_candidate_surface")
    if verifier_path and seed_path and verifier_path == seed_path:
        blockers.append("verifier_path_duplicates_candidate_surface")

    verifier_route = fields.get("verifier_route") or str(work_item.get("verifier_id") or "UNKNOWN")
    execution_route = fields.get("execution_route") or "UNKNOWN"

    facts = {
        "candidate_change_surface": (
            f"Changed-surface evidence: changed file path `{seed_path}` is listed among the source surfaces touched by "
            f"the root; changed-file set preview: {short_list(changed_files)}."
        ),
        "verifier_and_test_constraint": (
            f"Verifier/test evidence: selected verifier target `{verifier_path}` is tied to route `{verifier_route}`; "
            f"verification target preview: {short_list(verification_targets)}."
        ),
        "symptom_or_call_path_analogue": (
            f"Symptom/call-path evidence: execution route `{execution_route}` is associated with "
            f"{'support path `' + symptom_path + '`' if symptom_path else 'key symbols'}; "
            f"symbol preview: {short_list(key_symbols)}."
        ),
        "nearby_definition_or_usage_context": (
            f"Nearby context evidence: repository `{fields.get('repository') or work_item.get('repo_family')}` has "
            f"background support `{algorithm_path or fields.get('transition_target') or 'verification_targets'}` that is "
            "not by itself the decisive role."
        ),
    }
    return facts, blockers


def shuffled_options(seed: str) -> list[dict[str, str]]:
    values = list(ROLE_VALUES)
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    keyed = sorted((digest[i % len(digest)], value) for i, value in enumerate(values))
    return [{"label": LABELS[i], "value": value} for i, (_, value) in enumerate(keyed)]


def row_prompt(
    work_item: dict[str, Any],
    retrieval: dict[str, Any],
    facts: dict[str, str],
    options: list[dict[str, str]],
) -> str:
    fields = parse_query_lines(str(retrieval.get("query_text") or ""))
    lines = [
        f"Language: {work_item.get('language_family')}",
        "Perspective: evidence_citation",
        "Task: choose the evidence role that is most specifically justified by the visible ledger. Do not answer from option position or prior role frequency.",
        f"Repository family: {work_item.get('repo_family')}",
        f"Execution route: {fields.get('execution_route') or 'UNKNOWN'}",
        f"Verifier route: {fields.get('verifier_route') or work_item.get('verifier_id') or 'UNKNOWN'}",
        "",
        "Visible evidence ledger:",
        f"E01. {facts['candidate_change_surface']}",
        f"E02. {facts['verifier_and_test_constraint']}",
        f"E03. {facts['symptom_or_call_path_analogue']}",
        f"E04. {facts['nearby_definition_or_usage_context']}",
        "",
        "Options:",
    ]
    lines.extend(f"{opt['label']}. {opt['value']}" for opt in options)
    lines.append("Answer:")
    return "\n".join(lines)


def build_row(work_item: dict[str, Any], retrieval: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    target = str(work_item.get("target_gold_value") or "")
    facts, blockers = evidence_facts(work_item, retrieval)
    if target not in TARGET_ROLES:
        blockers.append("unsupported_target_role")
    if target == "verifier_and_test_constraint" and not work_item.get("verifier_anchor"):
        blockers.append("target_requires_verifier_anchor")
    if blockers:
        return None, {
            "work_item_id": work_item.get("work_item_id"),
            "source_root_id": work_item.get("source_root_id"),
            "repo_family": work_item.get("repo_family"),
            "language_family": work_item.get("language_family"),
            "target_gold_value": target,
            "blockers": sorted(set(blockers)),
        }

    options = shuffled_options(str(work_item.get("work_item_id")))
    target_label = next(opt["label"] for opt in options if opt["value"] == target)
    prompt = row_prompt(work_item, retrieval, facts, options)
    row_id = f"stage11178::{work_item.get('source_root_id')}::evidence_citation::{target}"

    row = {
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "gold_label_not_in_prompt_before_options": True,
            "root_disjoint_from_current_clean_eval": True,
            "stage11175_contract_checked": True,
            "train_support_only": True,
            "visible_role_facts_are_distinct": True,
        },
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": work_item.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "opaque_options": options,
        "repo_family": work_item.get("repo_family"),
        "root_id": work_item.get("source_root_id"),
        "root_lineage_key": work_item.get("root_lineage_key"),
        "row_id": row_id,
        "source_family_id": work_item.get("source_family_id"),
        "source_retrieval_row_id": retrieval.get("row_id"),
        "split": "train",
        "standalone_projection_source": {
            "evidence_facts": facts,
            "gold_label": target_label,
            "gold_value": target,
            "gold_value_source": "stage11177_role_specific_materialization_request",
            "opaque_options": options,
            "source_work_item_id": work_item.get("work_item_id"),
        },
        "strict_eval_eligible": False,
        "target_text": target_label,
        "task_type": "evidence_citation",
        "train_support_only": True,
    }
    return row, None


def main() -> None:
    work_items = load_jsonl(QUEUE_DIR / "materialization_work_items.jsonl")
    retrieval_rows = load_jsonl(SOURCE_RETRIEVAL)
    retrieval_by_key = retrieval_index(retrieval_rows)

    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    missing_source = 0

    for work_item in work_items:
        query_index = parse_query_index(str(work_item.get("source_root_id") or ""))
        retrieval = retrieval_by_key.get((str(work_item.get("snapshot_id")), query_index or -1))
        if retrieval is None:
            missing_source += 1
            blocked.append(
                {
                    "work_item_id": work_item.get("work_item_id"),
                    "source_root_id": work_item.get("source_root_id"),
                    "repo_family": work_item.get("repo_family"),
                    "language_family": work_item.get("language_family"),
                    "target_gold_value": work_item.get("target_gold_value"),
                    "blockers": ["missing_retrieval_source_row"],
                }
            )
            continue
        row, blocked_card = build_row(work_item, retrieval)
        if row is not None:
            admitted.append(row)
        elif blocked_card is not None:
            blocked.append(blocked_card)

    role_counts = Counter((row["standalone_projection_source"] or {}).get("gold_value") for row in admitted)
    lang_counts = Counter(str(row.get("language_family")) for row in admitted)
    blocked_reasons = Counter(reason for card in blocked for reason in card.get("blockers", []))
    min_role_count = min((role_counts.get(role, 0) for role in TARGET_ROLES), default=0)

    summary = {
        "stage": 11178,
        "created_at": now_utc(),
        "input_queue": rel(QUEUE_DIR / "materialization_work_items.jsonl"),
        "source_retrieval_rows": rel(SOURCE_RETRIEVAL),
        "admitted_rows": len(admitted),
        "blocked_rows": len(blocked),
        "missing_source_rows": missing_source,
        "language_counts": dict(sorted(lang_counts.items())),
        "gold_value_counts": dict(sorted(role_counts.items())),
        "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        "balanced_role_floor": min_role_count,
        "trainable_now": bool(admitted) and min_role_count >= 1,
        "promotion_eligible": False,
        "decision": (
            "materialized_train_support_rows"
            if admitted and min_role_count >= 1
            else "insufficient_contract_clean_materialization"
        ),
        "notes": [
            "Rows are train-support candidates only; no strict/eval promotion is implied.",
            "Rows are joined to concrete strict_long_context retrieval records by snapshot_id and query index.",
            "Blocked rows are emitted instead of fabricating evidence when source or role-separated facts are missing.",
        ],
        "outputs": {
            "admitted_rows": rel(OUT_DIR / "contract_aware_evidence_rows.jsonl"),
            "blocked_rows": rel(OUT_DIR / "blocked_evidence_materialization_rows.jsonl"),
            "summary": rel(OUT_DIR / "contract_aware_evidence_rows.json"),
        },
    }

    write_jsonl(OUT_DIR / "contract_aware_evidence_rows.jsonl", admitted)
    write_jsonl(OUT_DIR / "blocked_evidence_materialization_rows.jsonl", blocked)
    write_json(OUT_DIR / "contract_aware_evidence_rows.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
