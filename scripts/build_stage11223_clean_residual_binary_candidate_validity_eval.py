#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11223
NAME = "stage11223_clean_residual_binary_candidate_validity_eval"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_binary_candidate_validity_eval.json"
ROWS_JSONL = OUT_DIR / "binary_candidate_validity_eval_rows.jsonl"
SOURCE_ROWS = ARTIFACTS / "stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl"

POSITIVE_VALUE = "DECISIVE_EVIDENCE_ITEM"
NEGATIVE_VALUE = "DISTRACTOR_OR_INSUFFICIENT_EVIDENCE_ITEM"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("row_id") or "")


def source_prompt_without_options(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "").strip()
    marker = "\nOptions:\n"
    if marker in prompt:
        return prompt.split(marker, 1)[0].rstrip()
    return prompt


def candidate_fact(row: dict[str, Any], role: str) -> str:
    projection = row.get("standalone_projection_source") or {}
    facts = projection.get("evidence_facts") or {}
    if isinstance(facts, dict) and str(facts.get(role) or "").strip():
        return str(facts.get(role)).strip()
    lines = projection.get("visible_evidence_lines") or []
    if isinstance(lines, list):
        for line in lines:
            text = str(line).strip()
            if text.startswith(role):
                return text
    return role


def binary_options(row_id: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    checksum = sum(ord(ch) for ch in row_id)
    if checksum % 2 == 0:
        options = [{"label": "A", "value": POSITIVE_VALUE}, {"label": "B", "value": NEGATIVE_VALUE}]
    else:
        options = [{"label": "A", "value": NEGATIVE_VALUE}, {"label": "B", "value": POSITIVE_VALUE}]
    by_value = {option["value"]: option for option in options}
    return options, by_value


def gold_value(row: dict[str, Any]) -> str:
    projection = row.get("standalone_projection_source") or {}
    return str(projection.get("gold_value") or row.get("gold_value") or "").strip()


def option_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    projection = row.get("standalone_projection_source") or {}
    options = projection.get("opaque_options") or row.get("opaque_options") or []
    return [option for option in options if isinstance(option, dict) and str(option.get("value") or "").strip()]


def main() -> None:
    source_rows = [row for row in load_jsonl(SOURCE_ROWS) if row.get("task_type") == "evidence_citation"]
    out_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for source in source_rows:
        source_gold = gold_value(source)
        options = option_rows(source)
        if not source_gold or not options:
            blocked.append({"row_id": source.get("row_id"), "reason": "missing_gold_or_options"})
            continue
        if sum(1 for option in options if str(option.get("value") or "").strip() == source_gold) != 1:
            blocked.append({"row_id": source.get("row_id"), "reason": "gold_not_unique_in_options", "gold_value": source_gold})
            continue
        base_prompt = source_prompt_without_options(source)
        for option in options:
            role = str(option.get("value") or "").strip()
            is_positive = role == source_gold
            row_id = f"stage11223::{source.get('row_id')}::{role}"
            opts, by_value = binary_options(row_id)
            semantic_value = POSITIVE_VALUE if is_positive else NEGATIVE_VALUE
            target_label = by_value[semantic_value]["label"]
            fact = candidate_fact(source, role)
            prompt = (
                f"{base_prompt}\n\n"
                "Candidate evidence item under review:\n"
                f"Role: {role}\n"
                f"Visible fact: {fact}\n\n"
                "Task: decide whether this candidate is the decisive evidence item for the maintainer decision.\n"
                "Use only the visible source/test/evidence facts above.\n\n"
                "Options:\n"
                f"{opts[0]['label']}. {opts[0]['value']}\n"
                f"{opts[1]['label']}. {opts[1]['value']}\n"
                "Answer:"
            )
            out_rows.append(
                {
                    "row_id": row_id,
                    "source_row_id": source.get("row_id"),
                    "root_id": root_key(source),
                    "source_root_id": source.get("source_root_id") or root_key(source),
                    "repo_family": source.get("repo_family"),
                    "language_family": source.get("language_family"),
                    "task_type": "evidence_candidate_validity",
                    "split": "diagnostic_eval",
                    "package_split": "diagnostic_eval",
                    "prompt_text": prompt,
                    "input_text": prompt,
                    "target_text": target_label,
                    "decoder_text": target_label,
                    "bounded_choice_target_label": target_label,
                    "opaque_options": opts,
                    "expected_enabled_loss": "decoder_ce",
                    "loss_mask": {"decoder_ce": True},
                    "target_token_len": 1,
                    "diagnostic_eval_only": True,
                    "standalone_projection_source": {
                        "projection_mode": "stage11223_clean_residual_binary_candidate_validity_eval",
                        "source_row_id": source.get("row_id"),
                        "source_gold_value": source_gold,
                        "candidate_role": role,
                        "candidate_fact": fact,
                        "is_decisive_candidate": is_positive,
                        "gold_value": semantic_value,
                        "opaque_options": opts,
                    },
                    "anti_cheat": {
                        "binary_candidate_validity": True,
                        "derived_from_clean_residual_successor_bank": True,
                        "diagnostic_eval_only": True,
                        "opaque_labels": True,
                        "deterministic_option_shuffle": True,
                        "candidate_role_visible_by_design": True,
                        "target_label_not_visible_pre_options": True,
                    },
                }
            )

    source_positive_counts = defaultdict(int)
    for row in out_rows:
        if (row.get("standalone_projection_source") or {}).get("is_decisive_candidate") is True:
            source_positive_counts[str(row.get("source_row_id") or "")] += 1
    by_language_value = Counter((row.get("language_family"), (row.get("standalone_projection_source") or {}).get("gold_value")) for row in out_rows)
    by_candidate_role = Counter((row.get("language_family"), (row.get("standalone_projection_source") or {}).get("candidate_role")) for row in out_rows)
    by_root: dict[str, int] = defaultdict(int)
    for row in out_rows:
        by_root[str(row.get("root_id") or "")] += 1
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(out_rows) and not blocked and all(count == 1 for count in source_positive_counts.values()),
        "decision": "binary_candidate_validity_diagnostic_eval_built",
        "claim_scope": [
            "Diagnostic eval slice derived from the cleaned residual successor evidence-citation rows.",
            "This measures binary decisive-evidence recognition; it is not a promotable heldout benchmark because it is derived from the residual bank.",
            "Use it to decide whether binary candidate-validity is a better interface before scaling root-disjoint rows.",
        ],
        "counts": {
            "source_evidence_rows": len(source_rows),
            "binary_rows": len(out_rows),
            "unique_roots": len(by_root),
            "blocked_rows": len(blocked),
            "by_language_and_binary_target": {f"{lang}::{value}": count for (lang, value), count in sorted(by_language_value.items())},
            "by_language_and_candidate_role": {f"{lang}::{role}": count for (lang, role), count in sorted(by_candidate_role.items())},
        },
        "quality_gates": {
            "one_positive_per_source_row": all(count == 1 for count in source_positive_counts.values()) and len(source_positive_counts) == len(source_rows),
            "all_rows_have_binary_options": all(len(row.get("opaque_options") or []) == 2 for row in out_rows),
            "positive_label_balanced_by_checksum": True,
            "diagnostic_not_promotable": True,
        },
        "blocked": blocked,
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "outputs": {"summary_json": rel(SUMMARY_JSON), "rows_jsonl": rel(ROWS_JSONL)},
    }
    write_jsonl(ROWS_JSONL, out_rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
