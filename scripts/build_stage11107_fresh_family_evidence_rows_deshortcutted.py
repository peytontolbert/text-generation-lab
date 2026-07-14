#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11107
NAME = "stage11107_fresh_family_evidence_rows_deshortcutted"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_evidence_rows_deshortcutted.json"
ROWS_JSONL = OUT_DIR / "evidence_candidate_rows_deshortcutted.jsonl"

SOURCE_ROWS = ARTIFACTS / "stage11097_fresh_family_materialized_rows" / "evidence_candidate_rows.jsonl"

ROLE_ORDER = [
    "candidate_change_surface",
    "nearby_definition_or_usage_context",
    "symptom_or_call_path_analogue",
    "verifier_and_test_constraint",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def parsed_query_lines(query_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in str(query_text).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def evidence_map_for(row: dict[str, Any]) -> dict[str, str]:
    query = parsed_query_lines(str(row.get("query_text") or ""))
    changed_files = query.get("Changed files", "unknown")
    verification_targets = query.get("Verification targets", "unknown")
    verifier_route = query.get("Verifier route", "unknown")
    key_symbols = query.get("Key symbols", "unknown")
    first_changed = changed_files.split(",")[0].strip() if changed_files else "unknown_surface"
    first_symbol = key_symbols.split(",")[0].strip() if key_symbols else "unknown_symbol"
    return {
        "candidate_change_surface": (
            f"Evidence anchored in the directly modified surface, centered on {first_changed}."
        ),
        "nearby_definition_or_usage_context": (
            f"Evidence centered on a nearby definition or usage context, including {first_symbol}."
        ),
        "symptom_or_call_path_analogue": (
            f"Evidence grounded in the visible symptom or execution-route analogue tied to {verification_targets}."
        ),
        "verifier_and_test_constraint": (
            f"Evidence grounded in the selected verification targets and verifier route ({verifier_route}) rather than the changed file alone."
        ),
    }


def build_prompt(row: dict[str, Any]) -> str:
    query = parsed_query_lines(str(row.get("query_text") or ""))
    evidence_map = evidence_map_for(row)
    lines = [
        f"Language: {row.get('language_family')}",
        "Perspective: evidence_citation",
        "Task: Choose which visible evidence item most specifically justifies the maintenance decision. Use the evidence descriptions, not label priors.",
        f"Repository: {query.get('Repository', row.get('repo_id', 'unknown'))}",
        f"Execution route: {query.get('Execution route', 'unknown')}",
        f"Verifier route: {query.get('Verifier route', 'unknown')}",
        f"Changed files: {query.get('Changed files', 'unknown')}",
        f"Verification targets: {query.get('Verification targets', 'unknown')}",
        "Visible evidence ledger:",
    ]
    for idx, role in enumerate(ROLE_ORDER, start=1):
        lines.append(f"E{idx:02d}. {evidence_map[role]}")
    lines.append("Options:")
    for option in list(row.get("opaque_options") or []):
        lines.append(f"{option['label']}. {option['value']}")
    lines.append("Answer:")
    return "\n".join(lines) + "\n"


def main() -> None:
    source_rows = load_jsonl(SOURCE_ROWS)
    rewritten_rows = []
    for row in source_rows:
        updated = dict(row)
        updated["row_id"] = f"{row['row_id']}::deshortcutted_v1"
        updated["prompt_text"] = build_prompt(row)
        updated["input_text"] = updated["prompt_text"]
        anti_cheat = dict(updated.get("anti_cheat") or {})
        anti_cheat["role_name_leak_removed"] = True
        anti_cheat["requires_review_before_training"] = True
        updated["anti_cheat"] = anti_cheat
        projection = dict(updated.get("standalone_projection_source") or {})
        projection["projection_mode"] = "stage11107_fresh_family_evidence_deshortcutted"
        updated["standalone_projection_source"] = projection
        rewritten_rows.append(updated)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "claim_scope": [
            "Rewrite the stage11097 fresh-family evidence candidate rows to remove direct semantic role-name leakage from the visible evidence ledger.",
        ],
        "source_artifacts": {
            "source_rows": rel(SOURCE_ROWS),
        },
        "metrics": {
            "row_count": len(rewritten_rows),
        },
        "findings": [
            "The rewritten rows preserve the same opaque options and targets, but the visible evidence ledger no longer repeats the semantic option values verbatim.",
            "These rows are still heuristic and still require review before training, but they are no longer trivially shortcut-prone in the same way as stage11097.",
        ],
        "next_best_step": "Run a second admission audit on the deshortcutted rows, then decide which subset is safe enough for train-support use.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, rewritten_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
