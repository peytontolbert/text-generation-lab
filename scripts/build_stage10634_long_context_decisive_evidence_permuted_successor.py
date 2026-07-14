#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10634
NAME = "stage10634_long_context_decisive_evidence_permuted_successor"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

COMPILED_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
COMPILED_ROOTS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
HELDOUT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"

SUCCESSOR_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_permuted_successor_rows.jsonl"
SUCCESSOR_STRICT_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_permuted_successor_strict_rows.jsonl"
SUCCESSOR_TRAIN_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_permuted_successor_train_rows.jsonl"
SUCCESSOR_JSON = OUT_DIR / "long_context_decisive_evidence_permuted_successor.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

_LIST_RE = re.compile(r"^\s*\[.*\]\s*$", re.DOTALL)
_REMOVE_LINES = (
    "Transition target:",
    "Execution route:",
    "Verifier route:",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def parse_target_list(value: str) -> list[str]:
    raw = str(value).strip()
    if not raw or not _LIST_RE.match(raw):
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def label_for_position(idx: int) -> str:
    return f"E{idx + 1}"


def stable_hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def permute_evidence_items(row_id: str, evidence_items: list[str]) -> tuple[list[str], int]:
    gold = evidence_items[0]
    negatives = evidence_items[1:]
    negatives = sorted(
        negatives,
        key=lambda item: hashlib.sha256(f"{row_id}::{item}".encode("utf-8")).hexdigest(),
    )
    ordered = [gold] + negatives
    shift = stable_hash(row_id) % len(ordered)
    permuted = ordered[shift:] + ordered[:shift]
    gold_pos = permuted.index(gold)
    return permuted, gold_pos


def sanitize_prompt(input_text: str, option_lines: list[str]) -> str:
    kept_lines: list[str] = []
    for line in input_text.splitlines():
        if any(line.startswith(prefix) for prefix in _REMOVE_LINES):
            continue
        kept_lines.append(line)
    kept_lines.append("Task: Choose the decisive evidence option that best justifies the maintenance decision.")
    kept_lines.append("Evidence options:")
    kept_lines.extend(option_lines)
    return "\n".join(kept_lines)


def build_successor_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("target_family") != "bounded_decision":
        return None
    if row.get("target_subtype") != "decisive_evidence":
        return None

    evidence_items = parse_target_list(row.get("target_text", ""))
    if len(evidence_items) < 2:
        return None

    permuted_items, gold_pos = permute_evidence_items(str(row.get("row_id", "")), evidence_items)
    options = [
        {"label": label_for_position(i), "value": item}
        for i, item in enumerate(permuted_items)
    ]
    option_lines = [f"{option['label']}: {option['value']}" for option in options]

    successor = dict(row)
    successor["input_text"] = sanitize_prompt(str(row.get("input_text", "")), option_lines)
    successor["target_text"] = label_for_position(gold_pos)
    successor["target_subtype"] = "decisive_evidence_option"
    successor["candidate_options"] = options
    anti_cheat = dict(successor.get("anti_cheat", {}))
    anti_cheat["prompt_target_leak"] = False
    anti_cheat["route_shortcut_removed"] = True
    anti_cheat["visible_candidate_contract"] = True
    anti_cheat["target_value_hidden_behind_label"] = True
    anti_cheat["gold_candidate_position"] = gold_pos
    successor["anti_cheat"] = anti_cheat
    successor["successor_stage"] = STAGE
    successor["successor_lineage_role"] = "decisive_evidence_visible_candidate_permuted_successor"
    successor["candidate_order_strategy"] = "row_id_hash_rotation_with_negative_hash_sort"
    successor["gold_evidence_value"] = evidence_items[0]
    return successor


def row_language(row: dict[str, Any], root_language_lookup: dict[str, str]) -> str:
    return str(
        row.get("language_family")
        or row.get("language")
        or root_language_lookup.get(str(row.get("root_id", "")), "unknown")
    )


def prompt_has_removed_shortcut_markers(input_text: str) -> bool:
    return not any(prefix in input_text for prefix in _REMOVE_LINES)


def target_leaks_into_prompt(row: dict[str, Any]) -> bool:
    target = str(row.get("target_text", "")).strip()
    if not target:
        return False
    input_text = str(row.get("input_text", ""))
    options_marker = "Evidence options:\n"
    prefix = input_text.split(options_marker, 1)[0] if options_marker in input_text else input_text
    return target in prefix


def gold_position(row: dict[str, Any]) -> int | None:
    target = str(row.get("target_text", ""))
    for idx, option in enumerate(row.get("candidate_options") or []):
        if str(option.get("label", "")) == target:
            return idx
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    compiled_rows = load_jsonl(COMPILED_ROWS_JSONL)
    compiled_roots = load_jsonl(COMPILED_ROOTS_JSONL)
    root_language_lookup = {row["root_id"]: row.get("language_family", "unknown") for row in compiled_roots}
    heldout_rows = load_jsonl(HELDOUT_ROWS_JSONL)
    heldout_ids = {row["row_id"] for row in heldout_rows}

    successor_rows: list[dict[str, Any]] = []
    for row in compiled_rows:
        successor = build_successor_row(row)
        if successor is not None:
            successor_rows.append(successor)

    strict_rows = [row for row in successor_rows if row["row_id"] in heldout_ids]
    train_rows = [row for row in successor_rows if row["row_id"] not in heldout_ids]

    prompt_leak_count = sum(1 for row in successor_rows if target_leaks_into_prompt(row))
    missing_option_count = sum(1 for row in successor_rows if not row.get("candidate_options"))
    remaining_shortcut_marker_count = sum(
        1 for row in successor_rows if not prompt_has_removed_shortcut_markers(str(row.get("input_text", "")))
    )
    target_label_counts = Counter(str(row.get("target_text", "")) for row in successor_rows)
    strict_target_label_counts = Counter(str(row.get("target_text", "")) for row in strict_rows)
    gold_position_counts = Counter(gold_position(row) for row in successor_rows)
    strict_gold_position_counts = Counter(gold_position(row) for row in strict_rows)

    passed = (
        prompt_leak_count == 0
        and missing_option_count == 0
        and remaining_shortcut_marker_count == 0
        and len(strict_target_label_counts) > 1
        and len(strict_gold_position_counts) > 1
        and strict_gold_position_counts.get(0, 0) < len(strict_rows)
    )

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": passed,
        "claim_boundary": [
            "This successor repairs decisive_evidence with visible candidates and per-row gold-label position diversity.",
            "It is still only a repaired evidence-selection head, not a maintainer-grade benchmark by itself.",
            "The main purpose is to remove the constant first-slot shortcut found in the stage10629/10632 strict path.",
        ],
        "inputs": {
            "compiled_rows": str(COMPILED_ROWS_JSONL.relative_to(ROOT)),
            "compiled_roots": str(COMPILED_ROOTS_JSONL.relative_to(ROOT)),
            "heldout_rows": str(HELDOUT_ROWS_JSONL.relative_to(ROOT)),
        },
        "metrics": {
            "successor_rows": len(successor_rows),
            "strict_rows": len(strict_rows),
            "train_rows": len(train_rows),
            "rows_by_language": dict(sorted(Counter(row_language(row, root_language_lookup) for row in successor_rows).items())),
            "strict_rows_by_language": dict(sorted(Counter(row_language(row, root_language_lookup) for row in strict_rows).items())),
            "prompt_target_leak_count": prompt_leak_count,
            "remaining_shortcut_marker_count": remaining_shortcut_marker_count,
            "missing_option_count": missing_option_count,
            "target_label_counts": dict(sorted(target_label_counts.items())),
            "strict_target_label_counts": dict(sorted(strict_target_label_counts.items())),
            "gold_position_counts": {str(k): v for k, v in sorted(gold_position_counts.items())},
            "strict_gold_position_counts": {str(k): v for k, v in sorted(strict_gold_position_counts.items())},
            "strict_target_label_unique_count": len(strict_target_label_counts),
            "strict_gold_position_unique_count": len(strict_gold_position_counts),
        },
        "next_best_step": (
            "Replace the stage10629 decisive-evidence head with this permuted successor in the repaired long-context package, "
            "then rerun the target_100m probe and require the strict slice to survive without constant-slot shortcuts."
        ),
        "outputs": {
            "all_rows": str(SUCCESSOR_ROWS_JSONL.relative_to(ROOT)),
            "strict_rows": str(SUCCESSOR_STRICT_ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(SUCCESSOR_TRAIN_ROWS_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(SUCCESSOR_ROWS_JSONL, successor_rows)
    write_jsonl(SUCCESSOR_STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(SUCCESSOR_TRAIN_ROWS_JSONL, train_rows)
    write_json(SUCCESSOR_JSON, audit)
    write_json(RUN_SUMMARY_JSON, audit)


if __name__ == "__main__":
    main()
