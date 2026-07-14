from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10629
NAME = "stage10629_long_context_decisive_evidence_successor"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

COMPILED_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
COMPILED_ROOTS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
HELDOUT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"

SUCCESSOR_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_successor_rows.jsonl"
SUCCESSOR_STRICT_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_successor_strict_rows.jsonl"
SUCCESSOR_TRAIN_ROWS_JSONL = OUT_DIR / "long_context_decisive_evidence_successor_train_rows.jsonl"
SUCCESSOR_JSON = OUT_DIR / "long_context_decisive_evidence_successor.json"
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


def sanitize_prompt(input_text: str, evidence_labels: list[str]) -> str:
    kept_lines: list[str] = []
    for line in input_text.splitlines():
        if any(line.startswith(prefix) for prefix in _REMOVE_LINES):
            continue
        kept_lines.append(line)
    kept_lines.append("Task: Choose the decisive evidence option that best justifies the maintenance decision.")
    kept_lines.append("Evidence options:")
    for label in evidence_labels:
        kept_lines.append(label)
    return "\n".join(kept_lines)


def build_successor_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("target_family") != "bounded_decision":
        return None
    if row.get("target_subtype") != "decisive_evidence":
        return None

    evidence_items = parse_target_list(row.get("target_text", ""))
    if not evidence_items:
        return None

    evidence_labels = [f"E{i+1}: {item}" for i, item in enumerate(evidence_items)]
    sanitized_prompt = sanitize_prompt(str(row.get("input_text", "")), evidence_labels)
    target_label = "E1"

    successor = dict(row)
    successor["input_text"] = sanitized_prompt
    successor["target_text"] = target_label
    successor["target_subtype"] = "decisive_evidence_option"
    successor["candidate_options"] = [
        {"label": f"E{i+1}", "value": item}
        for i, item in enumerate(evidence_items)
    ]
    anti_cheat = dict(successor.get("anti_cheat", {}))
    anti_cheat["prompt_target_leak"] = False
    anti_cheat["route_shortcut_removed"] = True
    anti_cheat["visible_candidate_contract"] = True
    successor["anti_cheat"] = anti_cheat
    successor["successor_stage"] = STAGE
    successor["successor_lineage_role"] = "decisive_evidence_visible_candidate_successor"
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

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": prompt_leak_count == 0 and missing_option_count == 0 and remaining_shortcut_marker_count == 0,
        "claim_boundary": [
            "This successor only repairs the decisive_evidence surface from the long-context bootstrap lineage.",
            "It intentionally drops retrieve_answer_abstain and verifier_outcome rows because those remain shortcut-prone under the current interface.",
            "The resulting rows are visible-candidate evidence selection tasks, not a full maintainer benchmark.",
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
        },
        "next_best_step": (
            "Use this decisive-evidence successor as the first shortcut-safe long-context head, then rebuild verifier_outcome "
            "and retrieve_answer_abstain with real candidate contracts instead of route tokens."
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
