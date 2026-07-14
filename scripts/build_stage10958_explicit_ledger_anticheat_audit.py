#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10958
NAME = "stage10958_explicit_ledger_anticheat_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "explicit_ledger_anticheat_audit.json"

ROWS_JSONL = ARTIFACTS / "stage10934_explicit_verifier_ledger_support_package" / "added_explicit_verifier_ledger_rows.jsonl"
PACKAGE_JSON = ARTIFACTS / "stage10934_explicit_verifier_ledger_support_package" / "explicit_verifier_ledger_support_package.json"

LEGACY_TARGET_LEAK_PHRASES = [
    "Prefer the verifier/test ledger when the selected tests narrow the repair surface more strongly than the changed file alone.",
    "Prefer the changed candidate surface only when it is the strongest packet-visible justification over the verifier/test ledger.",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_prompt(prompt: str) -> tuple[str, str, str]:
    before_evidence, rest = prompt.split("\nEvidence:\n", 1)
    evidence_text, rest = rest.split("\nOptions:\n", 1)
    return before_evidence, evidence_text, rest


def main() -> None:
    rows = load_jsonl(ROWS_JSONL)
    package = load_json(PACKAGE_JSON)

    task_lines = Counter()
    legacy_task_line_hits = []
    selected_test_missing = []
    gold_positions = []
    gold_labels_by_queue: dict[str, list[str]] = defaultdict(list)
    label_to_value_by_queue: dict[str, list[dict[str, str]]] = defaultdict(list)
    header_path_leak_rows = []

    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        header, _evidence, _options_tail = split_prompt(prompt)
        header_lines = header.splitlines()
        task_line = next((line for line in header_lines if line.startswith("Task: ")), "")
        task_lines[task_line] += 1

        for phrase in LEGACY_TARGET_LEAK_PHRASES:
            if phrase in task_line:
                legacy_task_line_hits.append(str(row.get("row_id") or ""))

        if not row.get("selected_test_anchor"):
            selected_test_missing.append(str(row.get("row_id") or ""))

        options = list(row.get("opaque_options") or [])
        target_label = str(row.get("target_text") or "")
        queue_id = str((row.get("standalone_projection_source") or {}).get("queue_id") or "")
        gold_labels_by_queue[queue_id].append(target_label)
        label_to_value_by_queue[queue_id].extend(
            [{"label": str(opt.get("label") or ""), "value": str(opt.get("value") or "")} for opt in options if isinstance(opt, dict)]
        )
        for idx, opt in enumerate(options):
            if str(opt.get("label") or "") == target_label:
                gold_positions.append(idx)
                break

        candidate_paths = list((row.get("standalone_projection_source") or {}).get("candidate_paths") or [])
        selected_tests = list((row.get("standalone_projection_source") or {}).get("selected_tests") or [])
        header_text = "\n".join(header_lines)
        if any(path and path in header_text for path in candidate_paths + selected_tests):
            header_path_leak_rows.append(str(row.get("row_id") or ""))

    position_counts = dict(sorted(Counter(gold_positions).items()))
    queue_label_diversity = {
        queue_id: sorted(set(labels))
        for queue_id, labels in sorted(gold_labels_by_queue.items())
    }
    queue_label_position_ok = {
        queue_id: len(set(labels)) > 1
        for queue_id, labels in gold_labels_by_queue.items()
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not legacy_task_line_hits and not header_path_leak_rows and not selected_test_missing,
        "claim_scope": [
            "Audit the stage10934 explicit-ledger support rows for obvious prompt-conditioning and option-label shortcut risks before reuse in another probe.",
            "Verify that the reviewed immediate Python/C++ materialization branch no longer leaks the gold evidence role through task wording.",
        ],
        "source_package": rel(PACKAGE_JSON),
        "source_rows": rel(ROWS_JSONL),
        "metrics": {
            "row_count": len(rows),
            "unique_task_lines": len(task_lines),
            "legacy_task_line_hits": len(legacy_task_line_hits),
            "selected_test_anchor_missing_rows": len(selected_test_missing),
            "header_path_leak_rows": len(header_path_leak_rows),
            "gold_label_position_counts": position_counts,
            "gold_label_position_unique_count": len(position_counts),
            "queue_label_diversity": queue_label_diversity,
            "queue_label_position_varies": queue_label_position_ok,
            "package_metrics_snapshot": package.get("metrics"),
        },
        "findings": [
            "The explicit-ledger task line is now target-agnostic across all added rows."
            if not legacy_task_line_hits else
            "At least one explicit-ledger row still contains the older gold-conditioned task wording.",
            "All rows retain selected-test anchors from the reviewed packets."
            if not selected_test_missing else
            "Some rows lost their selected-test anchor despite being explicit-ledger rows.",
            "Gold labels occupy multiple option positions across the package, reducing direct label-position shortcut risk."
            if len(position_counts) > 1 else
            "Gold labels collapsed to a single option position across the package.",
        ],
        "violations": {
            "legacy_task_line_hits": legacy_task_line_hits,
            "selected_test_missing": selected_test_missing,
            "header_path_leak_rows": header_path_leak_rows,
        },
        "next_best_step": "Use the cleaned stage10934 package as the explicit-ledger support base for the next diagnostic probe, while keeping it support-only and separate from any fresh heldout claim.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
