#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11383
NAME = "stage11383_web_sourcebot_abstention_counterfactual_combined_package"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_abstention_counterfactual_combined_package.json"
ROWS_OUT = OUT / "web_sourcebot_abstention_counterfactual_combined_rows.jsonl"

BASE_ROWS = ART / "stage11378_web_sourcebot_plus_abstention_preservation_package/web_sourcebot_plus_abstention_preservation_rows.jsonl"
WEB_ABSTAIN_ROWS = ART / "stage11382_web_sourcebot_true_abstention_counterfactual_rows/web_sourcebot_true_abstention_counterfactual_rows.jsonl"
PROTECTED = [
    ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl",
    ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl",
    ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("source_root_id") or row.get("root_lineage_key") or row.get("row_id") or "")


def target_value(row: dict[str, Any]) -> str:
    target = str(row.get("target_text") or row.get("target_label") or "")
    for option in row.get("opaque_options") or []:
        if isinstance(option, dict) and str(option.get("label")) == target:
            return str(option.get("value") or "")
    return str(row.get("semantic_target_value") or target)


def normalize(row: dict[str, Any], source: Path) -> dict[str, Any]:
    out = dict(row)
    out["split"] = "train"
    out["train_support_only"] = True
    out["strict_eval_eligible"] = False
    out["stage11383_source"] = rel(source)
    anti = dict(out.get("anti_cheat") or {})
    anti["train_support_only"] = True
    anti["strict_eval_eligible"] = False
    anti["stage11383_combined_package"] = True
    out["anti_cheat"] = anti
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected_rows = [row for path in PROTECTED for row in read_jsonl(path)]
    protected_roots = {root_key(row) for row in protected_rows}
    protected_ids = {str(row.get("row_id")) for row in protected_rows}

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in [BASE_ROWS, WEB_ABSTAIN_ROWS]:
        for row in read_jsonl(source):
            rid = str(row.get("row_id") or "")
            if not rid or rid in seen:
                continue
            if rid in protected_ids:
                raise SystemExit(f"protected row leaked into train: {rid}")
            if root_key(row) in protected_roots:
                raise SystemExit(f"protected root leaked into train: {rid}")
            if row.get("strict_eval_eligible") or row.get("train_support_only") is not True:
                raise SystemExit(f"non train-support row: {rid}")
            seen.add(rid)
            rows.append(normalize(row, source))

    counts = {
        "rows": len(rows),
        "language_counts": dict(Counter(str(row.get("language_family") or "unknown") for row in rows)),
        "task_counts": dict(Counter(str(row.get("task_type") or "unknown") for row in rows)),
        "target_value_counts": dict(Counter(target_value(row) for row in rows)),
        "protected_roots": len(protected_roots),
    }
    write_jsonl(ROWS_OUT, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "decision": "web_sourcebot_plus_true_abstention_counterfactual_combined_train_support_package",
        "counts": counts,
        "source_artifacts": {
            "base_rows": rel(BASE_ROWS),
            "web_true_abstention_rows": rel(WEB_ABSTAIN_ROWS),
            "protected": [rel(path) for path in PROTECTED],
        },
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS_OUT)},
        "recommended_next_action": "run one conservative diagnostic probe; reject if validation falls below 20/23",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": True, "counts": counts, "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
