#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11108
NAME = "stage11108_fresh_family_evidence_admission_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "fresh_family_evidence_admission_audit.json"
ADMITTED_ROWS_JSONL = OUT_DIR / "admitted_evidence_rows.jsonl"
BLOCKED_ROWS_JSONL = OUT_DIR / "blocked_evidence_rows.jsonl"

SOURCE_ROWS = (
    ARTIFACTS
    / "stage11107_fresh_family_evidence_rows_deshortcutted"
    / "evidence_candidate_rows_deshortcutted.jsonl"
)


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


def main() -> None:
    rows = load_jsonl(SOURCE_ROWS)
    admitted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        prompt_prefix = prompt.split("Options:", 1)[0]
        opaque_options = list(row.get("opaque_options") or [])
        option_values = [str(option.get("value") or "") for option in opaque_options]
        anti_cheat = dict(row.get("anti_cheat") or {})
        reasons: list[str] = []

        leaked_values = [value for value in option_values if value and value in prompt_prefix]
        if leaked_values:
            reasons.append("role_name_leak_in_prompt_prefix")
        if not anti_cheat.get("deterministic_option_shuffle"):
            reasons.append("deterministic_option_shuffle_missing")
        if not anti_cheat.get("explicit_selected_test_ledger"):
            reasons.append("explicit_selected_test_ledger_missing")
        if not anti_cheat.get("role_name_leak_removed"):
            reasons.append("role_name_leak_removed_flag_missing")
        if len(opaque_options) < 4:
            reasons.append("insufficient_option_competition")
        if str(row.get("task_type") or "") != "evidence_citation":
            reasons.append("unexpected_task_type")

        if reasons:
            blocked_rows.append(
                {
                    "row_id": row.get("row_id"),
                    "repo_family": row.get("repo_family"),
                    "language_family": row.get("language_family"),
                    "target_text": row.get("target_text"),
                    "reasons": reasons,
                }
            )
            continue

        admitted = dict(row)
        admitted_anti_cheat = dict(anti_cheat)
        admitted_anti_cheat["admitted_train_support_only"] = True
        admitted["anti_cheat"] = admitted_anti_cheat
        admitted["split"] = "train"
        admitted["split_role"] = "support_only_admitted"
        admitted["train_support_only"] = True
        admitted["strict_eval_eligible"] = False
        admitted["source_heldout_admissible"] = False
        admitted_rows.append(admitted)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": bool(admitted_rows) and not blocked_rows,
        "claim_scope": [
            "Audit the deshortcutted fresh-family evidence rows for train-support admission only.",
            "Require zero prompt-prefix role-name leakage and preserve explicit anti-cheat markers before any train admission.",
        ],
        "source_artifacts": {
            "deshortcutted_rows": rel(SOURCE_ROWS),
        },
        "metrics": {
            "row_count": len(rows),
            "admitted_rows": len(admitted_rows),
            "blocked_rows": len(blocked_rows),
            "admitted_by_language": dict(sorted(Counter(str(row.get("language_family") or "") for row in admitted_rows).items())),
            "admitted_by_repo_family": dict(sorted(Counter(str(row.get("repo_family") or "") for row in admitted_rows).items())),
            "admitted_by_target": dict(sorted(Counter(str(row.get("target_text") or "") for row in admitted_rows).items())),
        },
        "headline_findings": [
            "The rewritten evidence rows can only be admitted as train-support-only rows, never as promotable strict or same-surface eval rows.",
            "Admission is gated on zero role-name leakage before options and on deterministic option-shuffle metadata.",
        ],
        "limits": [
            "These rows still rely on heuristic gold projection and require later reviewer replacement with stronger root families.",
            "No Rust evidence rows are present in this admitted batch.",
        ],
        "next_best_step": "Merge the admitted subset into the latest clean support package and run one support-only probe if the row geometry looks balanced enough.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "admitted_rows_jsonl": rel(ADMITTED_ROWS_JSONL),
            "blocked_rows_jsonl": rel(BLOCKED_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(ADMITTED_ROWS_JSONL, admitted_rows)
    write_jsonl(BLOCKED_ROWS_JSONL, blocked_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
