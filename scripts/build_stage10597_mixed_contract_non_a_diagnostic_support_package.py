#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10597
NAME = "stage10597_mixed_contract_non_a_diagnostic_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "mixed_contract_non_a_diagnostic_support_package.json"
TRAIN_ROWS_JSONL = OUT_DIR / "train_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def main() -> None:
    support_rows = load_jsonl(SUPPORT_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)

    strict_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in strict_rows:
        strict_by_root.setdefault(str(row.get("root_id") or ""), []).append(row)

    selected_roots: list[str] = []
    selected_reason: dict[str, str] = {}
    for root_id, bucket in sorted(strict_by_root.items()):
        retrieve = next((row for row in bucket if str(row.get("target_subtype") or "") == "retrieve_answer_abstain"), None)
        verifier = next((row for row in bucket if str(row.get("target_subtype") or "") == "verifier_outcome_masked"), None)
        target_texts = {str(retrieve.get("target_text") or "") if retrieve else "", str(verifier.get("target_text") or "") if verifier else ""}
        target_texts.discard("")
        if any(label in {"B", "D"} for label in target_texts):
            selected_roots.append(root_id)
            selected_reason[root_id] = "/".join(sorted(target_texts))

    diagnostic_rows: list[dict[str, Any]] = []
    for root_id in selected_roots:
        for row in strict_by_root[root_id]:
            copied = clone(row)
            copied["split"] = "train"
            copied.setdefault("anti_cheat", {})
            copied["anti_cheat"]["same_surface_diagnostic_replay"] = True
            copied["anti_cheat"]["non_promotable_same_surface_support"] = True
            copied["diagnostic_support_stage"] = STAGE
            copied["diagnostic_support_reason"] = selected_reason[root_id]
            diagnostic_rows.append(copied)

    train_rows = [clone(row) for row in support_rows] + diagnostic_rows
    train_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    strict_rows_out = [clone(row) for row in strict_rows]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Builds a clearly non-promotable diagnostic support package for the stage10591 mixed-contract interface.",
            "Keeps the original stage10591 train rows and adds only strict roots whose retrieve/verifier targets are non-A so we can test whether missing B/D support caused the stage10594 collapse.",
            "This package is for diagnosis only and must not be used to upgrade any claim because it reuses same-surface strict roots as training support.",
        ],
        "inputs": {
            "support_rows": display(SUPPORT_ROWS),
            "strict_rows": display(STRICT_ROWS),
        },
        "rows": {
            "base_support_rows": len(support_rows),
            "diagnostic_added_rows": len(diagnostic_rows),
            "train_rows": len(train_rows),
            "strict_eval_rows": len(strict_rows_out),
        },
        "selected_roots": {
            "count": len(selected_roots),
            "reasons": dict(sorted(selected_reason.items())),
            "language_counts": dict(sorted(Counter(str((strict_by_root[root_id][0].get("language_family") or "")) for root_id in selected_roots).items())),
        },
        "target_subtype_counts": {
            "train": dict(sorted(Counter(str(row.get("target_subtype") or "") for row in train_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("target_subtype") or "") for row in strict_rows_out).items())),
        },
        "truthful_read": [
            "This package is intentionally non-promotable because it injects same-surface strict roots back into train support.",
            "Its only purpose is to answer a narrow question: does the stage10594 collapse come from missing B/D mixed-contract supervision, or does the model fail even when shown those patterns directly?",
            "If a follow-up probe does not move, the problem is more likely representation or optimization than simple support scarcity.",
        ],
        "outputs": {
            "train_rows": display(TRAIN_ROWS_JSONL),
            "strict_eval_rows": display(STRICT_ROWS_JSONL),
            "package_json": display(SUMMARY_JSON),
        },
    }

    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows_out)
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps(payload["rows"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
