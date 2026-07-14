#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11190
NAME = "stage11190_reserved_residual_partial_replacement_rows"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reserved_residual_partial_replacement_rows.json"
ROWS_JSONL = OUT_DIR / "replacement_strict_candidate_rows.jsonl"

WORK_ITEMS = ARTIFACTS / "stage11189_reserved_residual_replacement_source_miner/replacement_materialization_work_items.jsonl"

OPTION_VALUES = [
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
]


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


def stable_shuffle(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}\0{value}".encode()).hexdigest())


def first_path(paths: list[str]) -> str:
    return paths[0] if paths else "MISSING_PATH"


def compact_paths(paths: list[str], limit: int = 3) -> str:
    shown = paths[:limit]
    extra = len(paths) - len(shown)
    text = ", ".join(shown) if shown else "none"
    if extra > 0:
        text += f" (+{extra} more)"
    return text


def disjoint_paths(role_paths: dict[str, list[str]]) -> dict[str, list[str]]:
    candidate = list(dict.fromkeys(role_paths.get("candidate_change_surface") or []))
    candidate_set = set(candidate)
    verifier = [path for path in dict.fromkeys(role_paths.get("verifier_and_test_constraint") or []) if path not in candidate_set]
    verifier_set = set(verifier)
    symptom = [
        path
        for path in dict.fromkeys(role_paths.get("symptom_or_call_path_analogue") or [])
        if path not in candidate_set and path not in verifier_set
    ]
    return {
        "candidate_change_surface": candidate,
        "verifier_and_test_constraint": verifier,
        "symptom_or_call_path_analogue": symptom,
    }


def option_label_line_leaks(text: str, label: str) -> bool:
    return bool(re.search(rf"(?m)^\s*{re.escape(label)}[.)]\s+", text))


def build_row(item: dict[str, Any]) -> dict[str, Any]:
    row_id = item["work_item_id"].replace("stage11189::", "stage11190::")
    values = stable_shuffle(OPTION_VALUES, row_id)
    labels = [chr(ord("A") + i) for i in range(len(values))]
    options = [{"label": label, "value": value} for label, value in zip(labels, values)]
    gold_value = item["target_gold_value"]
    gold_label = next(opt["label"] for opt in options if opt["value"] == gold_value)
    original_role_paths = item.get("role_paths") or {}
    role_paths = disjoint_paths(original_role_paths)
    candidate_paths = role_paths.get("candidate_change_surface") or []
    verifier_paths = role_paths.get("verifier_and_test_constraint") or []
    symptom_paths = role_paths.get("symptom_or_call_path_analogue") or []
    evidence_facts = {
        "candidate_change_surface": (
            "Evidence item E01: a modified source surface is present at "
            f"`{first_path(candidate_paths)}`; changed surface preview: {compact_paths(candidate_paths)}."
        ),
        "verifier_and_test_constraint": (
            "Evidence item E02: an execution verifier or selected test target is present at "
            f"`{first_path(verifier_paths)}`; verifier/test preview: {compact_paths(verifier_paths)}."
        ),
        "symptom_or_call_path_analogue": (
            "Evidence item E03: a call-path, symptom, or runtime-support analogue is present at "
            f"`{first_path(symptom_paths)}`; support preview: {compact_paths(symptom_paths)}."
        ),
        "nearby_definition_or_usage_context": (
            "Evidence item E04: surrounding repository context is available, but it is not the uniquely decisive item."
        ),
    }
    prompt = "\n".join(
        [
            f"Language: {item.get('language_family')}",
            "Perspective: evidence_citation",
            "Task: choose which evidence item is the most decisive support for the maintainer decision. Use the visible evidence, not option order.",
            f"Repository family: {item.get('repo_family')}",
            "",
            "Visible evidence ledger:",
            evidence_facts["candidate_change_surface"],
            evidence_facts["verifier_and_test_constraint"],
            evidence_facts["symptom_or_call_path_analogue"],
            evidence_facts["nearby_definition_or_usage_context"],
            "",
            "Options:",
            *[f"{opt['label']}. {opt['value']}" for opt in options],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": item.get("source_root_id"),
        "root_lineage_key": item.get("root_lineage_key"),
        "repo_family": item.get("repo_family"),
        "language_family": item.get("language_family"),
        "task_type": "evidence_citation",
        "split": "strict_candidate",
        "strict_eval_eligible": False,
        "strict_replacement_candidate": True,
        "train_support_only": False,
        "source_family_id": item.get("source_family_id"),
        "source_retrieval_row_id": item.get("source_row_id"),
        "replacement_for_blocked_row_id": item.get("replacement_for_blocked_row_id"),
        "input_text": prompt,
        "target_text": gold_label,
        "decoder_text": gold_label,
        "bounded_choice_target_label": gold_label,
        "opaque_options": options,
        "loss_mask": {"decoder_ce": True},
        "expected_enabled_loss": "decoder_ce",
        "standalone_projection_source": {
            "gold_value": gold_value,
            "gold_label": gold_label,
            "opaque_options": options,
            "evidence_facts": evidence_facts,
            "source_work_item_id": item.get("work_item_id"),
            "source_row_id": item.get("source_row_id"),
            "role_paths": role_paths,
            "original_role_paths": original_role_paths,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "gold_label_not_in_prompt_before_options": not option_label_line_leaks(prompt.split("Options:", 1)[0], gold_label),
            "target_role_not_named_as_answer_before_options": gold_value not in prompt.split("Options:", 1)[0],
            "visible_role_facts_are_distinct": not (
                set(candidate_paths) & set(verifier_paths)
                or set(candidate_paths) & set(symptom_paths)
                or set(verifier_paths) & set(symptom_paths)
            ),
            "not_train_support": True,
            "replacement_for_quarantined_reserved_row": True,
        },
    }


def main() -> None:
    items = load_jsonl(WORK_ITEMS)
    rows = [build_row(item) for item in items]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "decision": "partial_replacement_rows_materialized" if rows else "no_replacement_rows_materialized",
        "promotion_eligible": False,
        "reason_not_promotion_eligible": "Rows require admission audit before strict replacement use; Rust replacement slots remain unfilled.",
        "source_artifacts": {"work_items": rel(WORK_ITEMS)},
        "counts": {
            "input_work_items": len(items),
            "materialized_rows": len(rows),
            "by_language": {lang: sum(1 for row in rows if row.get("language_family") == lang) for lang in sorted({row.get("language_family") for row in rows})},
            "by_gold_value": {value: sum(1 for row in rows if (row.get("standalone_projection_source") or {}).get("gold_value") == value) for value in sorted({(row.get("standalone_projection_source") or {}).get("gold_value") for row in rows})},
        },
        "outputs": {"summary_json": rel(SUMMARY_JSON), "rows_jsonl": rel(ROWS_JSONL)},
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
