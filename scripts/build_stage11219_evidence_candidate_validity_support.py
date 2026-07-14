#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11219
NAME = "stage11219_evidence_candidate_validity_support"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_candidate_validity_support.json"
ROWS_JSONL = OUT_DIR / "evidence_candidate_validity_rows.jsonl"
SOURCE_ROWS = ARTIFACTS / "stage11205_fresh_verifier_constraint_evidence_support/admitted_fresh_verifier_constraint_evidence_rows.jsonl"

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


def source_prompt_without_options(row: dict[str, Any]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "").strip()
    marker = "\nOptions:\n"
    if marker in prompt:
        return prompt.split(marker, 1)[0].rstrip()
    return prompt


def make_binary_options(row_id: str) -> tuple[list[dict[str, str]], str]:
    # Deterministic label rotation prevents a constant A=positive shortcut.
    checksum = sum(ord(ch) for ch in row_id)
    if checksum % 2 == 0:
        return ([{"label": "A", "value": POSITIVE_VALUE}, {"label": "B", "value": NEGATIVE_VALUE}], "A")
    return ([{"label": "A", "value": NEGATIVE_VALUE}, {"label": "B", "value": POSITIVE_VALUE}], "B")


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    out_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in source_rows:
        projection = row.get("standalone_projection_source") or {}
        options = projection.get("opaque_options") or row.get("opaque_options") or []
        gold_value = str(projection.get("gold_value") or row.get("gold_value") or "").strip()
        if not options or not gold_value:
            blocked.append({"row_id": row.get("row_id"), "reason": "missing_options_or_gold"})
            continue
        base_prompt = source_prompt_without_options(row)
        for option in options:
            if not isinstance(option, dict):
                continue
            role = str(option.get("value") or "").strip()
            if not role:
                continue
            candidate_row_id = f"stage11219::{row.get('row_id')}::{role}"
            binary_options, positive_label = make_binary_options(candidate_row_id)
            is_positive = role == gold_value
            target_label = positive_label if is_positive else next(opt["label"] for opt in binary_options if opt["value"] == NEGATIVE_VALUE)
            fact = candidate_fact(row, role)
            prompt = (
                f"{base_prompt}\n\nCandidate evidence item under review:\n"
                f"Role: {role}\n"
                f"Visible fact: {fact}\n\n"
                "Task: decide whether this candidate is the decisive evidence item for the maintainer decision.\n\n"
                "Options:\n"
                f"{binary_options[0]['label']}. {binary_options[0]['value']}\n"
                f"{binary_options[1]['label']}. {binary_options[1]['value']}\n"
                "Answer:"
            )
            payload = {
                "row_id": candidate_row_id,
                "source_row_id": row.get("row_id"),
                "root_id": root_key(row),
                "source_root_id": row.get("source_root_id") or root_key(row),
                "repo_family": row.get("repo_family") or projection.get("source_canonical_name"),
                "language_family": row.get("language_family"),
                "task_type": "evidence_candidate_validity",
                "split": "train",
                "package_split": "train",
                "prompt_text": prompt,
                "input_text": prompt,
                "target_text": target_label,
                "decoder_text": target_label,
                "bounded_choice_target_label": target_label,
                "target": {
                    "bounded_choice_target_label": target_label,
                    "target_text": target_label,
                    "decoder_text": target_label,
                    "semantic_value": POSITIVE_VALUE if is_positive else NEGATIVE_VALUE,
                    "candidate_role": role,
                    "gold_role": gold_value,
                },
                "standalone_projection_source": {
                    "projection_mode": "stage11219_evidence_candidate_validity_binary",
                    "source_row_id": row.get("row_id"),
                    "source_gold_value": gold_value,
                    "candidate_role": role,
                    "candidate_fact": fact,
                    "is_decisive_candidate": is_positive,
                    "gold_value": POSITIVE_VALUE if is_positive else NEGATIVE_VALUE,
                    "opaque_options": binary_options,
                },
                "opaque_options": binary_options,
                "expected_enabled_loss": "decoder_ce",
                "disable_losses": [],
                "loss_mask": {"decoder_ce": True},
                "target_token_len": 1,
                "anti_cheat": {
                    "binary_candidate_validity": True,
                    "derived_from_admitted_stage11205": True,
                    "opaque_labels": True,
                    "deterministic_option_shuffle": True,
                    "train_support_only": True,
                    "same_surface_eval_admissible": False,
                    "candidate_role_visible_by_design": True,
                    "target_label_not_visible_pre_options": True,
                },
            }
            out_rows.append(payload)
    counts = Counter((row.get("language_family"), (row.get("target") or {}).get("semantic_value")) for row in out_rows)
    by_source_root = defaultdict(int)
    for row in out_rows:
        by_source_root[row["root_id"]] += 1
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not blocked and bool(out_rows),
        "decision": "evidence_candidate_validity_support_built" if not blocked and out_rows else "evidence_candidate_validity_support_blocked",
        "counts": {
            "source_rows": len(source_rows),
            "candidate_validity_rows": len(out_rows),
            "blocked_rows": len(blocked),
            "unique_roots": len(by_source_root),
            "by_language_and_semantic_value": {f"{lang}::{value}": count for (lang, value), count in sorted(counts.items())},
        },
        "quality_gates": {
            "train_support_only": True,
            "root_disjointness_inherited_from_stage11205": True,
            "one_positive_per_source_row": all(sum(1 for r in out_rows if r.get("source_row_id") == src.get("row_id") and (r.get("target") or {}).get("semantic_value") == POSITIVE_VALUE) == 1 for src in source_rows),
            "all_rows_have_binary_options": all(len((r.get("standalone_projection_source") or {}).get("opaque_options") or []) == 2 for r in out_rows),
        },
        "blocked": blocked,
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS)},
        "outputs": {"summary_json": rel(SUMMARY_JSON), "rows_jsonl": rel(ROWS_JSONL)},
        "next_recommended_stage": "Train with these rows as support only, while keeping clean strict and clean residual successor as gates.",
    }
    write_jsonl(ROWS_JSONL, out_rows)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
