from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10630
NAME = "stage10630_long_context_decision_head_successors"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

COMPILED_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
COMPILED_ROOTS_JSONL = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
HELDOUT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10521_split_aware_multitarget_bootstrap_manifest_with_heldout/strict_eval_rows.jsonl"

ALL_ROWS_JSONL = OUT_DIR / "long_context_decision_head_successor_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "long_context_decision_head_successor_strict_rows.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "long_context_decision_head_successor_train_rows.jsonl"
SUMMARY_JSON = OUT_DIR / "long_context_decision_head_successors.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

REMOVE_PREFIXES = (
    "Transition target:",
    "Execution route:",
    "Verifier route:",
    "Test selection route:",
)

VERIFIER_OPTION_VALUES = [
    "PASS_TARGETED_TEST_SELECTION",
    "PASS_BROAD_TEST_DISCOVERY",
    "PASS_BROAD_VERIFICATION_DISCOVERY",
    "PASS_TRACE_VERIFICATION_TARGETS",
    "UNKNOWN",
]

RETRIEVE_OPTION_VALUES = [
    "ANSWER_WITH_RETRIEVED_EVIDENCE",
    "RETRIEVE_MORE_EVIDENCE",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "NEEDS_VERIFIER",
]


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


def sanitize_prompt(input_text: str, option_lines: list[str], task_line: str) -> str:
    kept: list[str] = []
    for line in input_text.splitlines():
        if any(line.startswith(prefix) for prefix in REMOVE_PREFIXES):
            continue
        kept.append(line)
    kept.append(task_line)
    kept.append("Decision options:")
    kept.extend(option_lines)
    return "\n".join(kept)


def option_contract(values: list[str]) -> list[dict[str, str]]:
    return [{"label": chr(ord("A") + idx), "value": value} for idx, value in enumerate(values)]


def map_value_to_label(values: list[str], target: str) -> str | None:
    for idx, value in enumerate(values):
        if value == target:
            return chr(ord("A") + idx)
    return None


def build_successor(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("target_family") != "bounded_decision":
        return None
    subtype = row.get("target_subtype")
    target = str(row.get("target_text", "")).strip()
    if subtype == "verifier_outcome":
        values = VERIFIER_OPTION_VALUES
        task_line = "Task: Choose the verifier-outcome option best supported by the visible maintenance evidence."
    elif subtype == "retrieve_answer_abstain":
        values = RETRIEVE_OPTION_VALUES
        task_line = "Task: Choose whether the visible evidence supports answering now, retrieving more evidence, abstaining, or requiring verifier evidence."
    else:
        return None

    label = map_value_to_label(values, target)
    if label is None:
        return None

    options = option_contract(values)
    option_lines = [f"{item['label']}: {item['value']}" for item in options]
    successor = dict(row)
    successor["input_text"] = sanitize_prompt(str(row.get("input_text", "")), option_lines, task_line)
    successor["target_text"] = label
    successor["candidate_options"] = options
    successor["successor_stage"] = STAGE
    successor["successor_lineage_role"] = f"{subtype}_visible_candidate_successor"
    successor["target_subtype"] = f"{subtype}_option"
    anti_cheat = dict(successor.get("anti_cheat", {}))
    anti_cheat["prompt_target_leak"] = False
    anti_cheat["route_shortcut_removed"] = True
    anti_cheat["visible_candidate_contract"] = True
    anti_cheat["target_value_hidden_behind_label"] = True
    successor["anti_cheat"] = anti_cheat
    return successor


def prompt_has_shortcut_markers(text: str) -> bool:
    return any(prefix in text for prefix in REMOVE_PREFIXES)


def label_leaks_before_options(row: dict[str, Any]) -> bool:
    label = str(row.get("target_text", "")).strip()
    text = str(row.get("input_text", ""))
    prefix = text.split("Decision options:\n", 1)[0] if "Decision options:\n" in text else text
    if not label:
        return False
    probe = f"{label}:"
    return any(line.strip().startswith(probe) for line in prefix.splitlines())


def row_language(row: dict[str, Any], root_lookup: dict[str, str]) -> str:
    return str(row.get("language_family") or root_lookup.get(str(row.get("root_id", "")), "unknown"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    compiled_rows = load_jsonl(COMPILED_ROWS_JSONL)
    compiled_roots = load_jsonl(COMPILED_ROOTS_JSONL)
    root_lookup = {row["root_id"]: row.get("language_family", "unknown") for row in compiled_roots}
    heldout_rows = load_jsonl(HELDOUT_ROWS_JSONL)
    heldout_ids = {row["row_id"] for row in heldout_rows}

    successor_rows = [row for base in compiled_rows if (row := build_successor(base)) is not None]
    strict_rows = [row for row in successor_rows if row["row_id"] in heldout_ids]
    train_rows = [row for row in successor_rows if row["row_id"] not in heldout_ids]

    prompt_leak_count = sum(1 for row in successor_rows if label_leaks_before_options(row))
    remaining_shortcut_marker_count = sum(1 for row in successor_rows if prompt_has_shortcut_markers(str(row.get("input_text", ""))))
    missing_option_count = sum(1 for row in successor_rows if not row.get("candidate_options"))

    subtype_counts = Counter(row["target_subtype"] for row in successor_rows)
    target_label_counts = Counter((row["target_subtype"], row["target_text"]) for row in successor_rows)
    retrieve_rows = [row for row in successor_rows if row["target_subtype"] == "retrieve_answer_abstain_option"]
    verifier_rows = [row for row in successor_rows if row["target_subtype"] == "verifier_outcome_option"]

    retrieve_constant = len({row["target_text"] for row in retrieve_rows}) <= 1 if retrieve_rows else True
    verifier_constant = len({row["target_text"] for row in verifier_rows}) <= 1 if verifier_rows else True

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": prompt_leak_count == 0 and remaining_shortcut_marker_count == 0 and missing_option_count == 0,
        "claim_boundary": [
            "This stage repairs verifier_outcome and retrieve_answer_abstain into visible candidate-contract rows.",
            "A repaired contract does not imply a promotable benchmark: class diversity still matters.",
            "retrieve_answer_abstain remains non-promotable until genuine negative actions are materialized from fresh roots.",
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
            "rows_by_subtype": dict(sorted(subtype_counts.items())),
            "rows_by_language": dict(sorted(Counter(row_language(row, root_lookup) for row in successor_rows).items())),
            "strict_rows_by_language": dict(sorted(Counter(row_language(row, root_lookup) for row in strict_rows).items())),
            "target_label_counts": {f"{subtype}:{label}": count for (subtype, label), count in sorted(target_label_counts.items())},
            "prompt_target_leak_count": prompt_leak_count,
            "remaining_shortcut_marker_count": remaining_shortcut_marker_count,
            "missing_option_count": missing_option_count,
        },
        "promotion_readiness": {
            "verifier_outcome_contract_repaired": True,
            "verifier_outcome_non_constant": not verifier_constant,
            "retrieve_answer_abstain_contract_repaired": True,
            "retrieve_answer_abstain_non_constant": not retrieve_constant,
            "retrieve_answer_abstain_promotable": not retrieve_constant,
        },
        "next_best_step": (
            "Use verifier_outcome_option rows as a repaired but still bootstrap supervision head, "
            "and treat retrieve_answer_abstain_option as non-promotable until fresh roots provide real negative actions."
        ),
        "outputs": {
            "all_rows": str(ALL_ROWS_JSONL.relative_to(ROOT)),
            "strict_rows": str(STRICT_ROWS_JSONL.relative_to(ROOT)),
            "train_rows": str(TRAIN_ROWS_JSONL.relative_to(ROOT)),
        },
    }

    write_jsonl(ALL_ROWS_JSONL, successor_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_json(SUMMARY_JSON, audit)
    write_json(RUN_SUMMARY_JSON, audit)


if __name__ == "__main__":
    main()
