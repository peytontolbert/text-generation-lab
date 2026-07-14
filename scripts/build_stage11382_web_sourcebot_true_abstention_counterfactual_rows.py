#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11382
NAME = "stage11382_web_sourcebot_true_abstention_counterfactual_rows"
OUT = ART / NAME
SUMMARY = OUT / "web_sourcebot_true_abstention_counterfactual_rows.json"
ROWS_OUT = OUT / "web_sourcebot_true_abstention_counterfactual_rows.jsonl"
SOURCE = ART / "stage11374_web_sourcebot_combined_current_score/web_sourcebot_combined_support_rows.jsonl"
PROTECTED = [
    ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl",
    ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl",
    ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


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


def field(row: dict[str, Any], name: str, default: str = "") -> str:
    value = row.get(name, default)
    return str(value if value is not None else default)


def task_observation(prompt: str) -> str:
    marker = "Task observation:\n"
    if marker not in prompt:
        return ""
    rest = prompt.split(marker, 1)[1]
    for next_marker in ["Visible source evidence:", "Visible verifier/test evidence:", "Executed verifier evidence:", "Options:"]:
        if next_marker in rest:
            rest = rest.split(next_marker, 1)[0]
    return rest.strip()


def make_prompt(row: dict[str, Any], variant: str) -> str:
    prompt = row.get("prompt_text") or row.get("input_text") or ""
    observation = task_observation(prompt)
    repo_family = field(row, "repo_family", "backend")
    commit = field(row, "git_commit", "a698afdf131d0ab132c23e7936ad3ae05ab45896")
    if variant == "no_verifier":
        withheld = (
            "Only the task observation and broad repository family are visible. "
            "No selected test, execution output, source span, trace, or candidate implementation body is visible."
        )
    else:
        withheld = (
            "Visible snippets are intentionally incomplete: they name a likely backend area but omit the selected test, "
            "assertion, executed output, and the implementation lines needed to distinguish candidate fixes."
        )
    return "\n".join(
        [
            "Language: web_js_ts_html",
            "Perspective: abstention_insufficient_evidence",
            "Task: Decide whether the currently visible evidence is enough for a final singleton maintenance answer.",
            f"Repository family: {repo_family}",
            f"Git commit: {commit}",
            "Task observation:",
            observation,
            "Visible evidence state:",
            withheld,
            "Anti-cheat note: candidate labels are presentation aliases; choose abstention when the evidence is underdetermined.",
            "Options:",
            "A. Answer with the visible source/test/execution evidence.",
            "B. Retrieve more source before answering.",
            "C. Use external web research before answering.",
            "D. ABSTAIN_INSUFFICIENT_EVIDENCE",
            "Answer:",
            "",
        ]
    )


def make_row(row: dict[str, Any], variant: str) -> dict[str, Any]:
    root = root_key(row)
    out = {
        "row_id": f"stage11382::{row.get('row_id')}::{variant}",
        "root_id": f"{root}::stage11382_true_abstention_counterfactual::{variant}",
        "source_root_id": root,
        "language_family": "web_js_ts_html",
        "task_type": "abstention_insufficient_evidence",
        "split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "target_text": "D",
        "decoder_text": "D",
        "target": {"decoder_text": "D", "bounded_choice_target_label": "D", "target_text": "D"},
        "semantic_target_value": "ABSTAIN_INSUFFICIENT_EVIDENCE",
        "loss_mask": {"decoder_ce": True},
        "prompt_text": make_prompt(row, variant),
        "input_text": make_prompt(row, variant),
        "opaque_options": [
            {"label": "A", "text": "Answer with the visible source/test/execution evidence.", "value": "ANSWER_WITH_VISIBLE_EVIDENCE"},
            {"label": "B", "text": "Retrieve more source before answering.", "value": "RETRIEVE_MORE_SOURCE"},
            {"label": "C", "text": "Use external web research before answering.", "value": "NEEDS_EXTERNAL_WEB_RESEARCH"},
            {"label": "D", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        ],
        "anti_cheat": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "counterfactual_evidence_ablation": True,
            "target_string_visible_only_as_option": True,
            "source_row_id": row.get("row_id"),
        },
        "provenance": {
            "source_artifact": rel(SOURCE),
            "source_row_id": row.get("row_id"),
            "construction": "source-backed evidence-ablation counterfactual; decisive verifier/source evidence withheld",
            "verifier_execution_source": "stage11364/stage11373 executed Sourcebot tests; not re-scored as strict eval",
        },
    }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_rows = [row for row in read_jsonl(SOURCE) if row.get("task_type") == "abstention_insufficient_evidence"]
    protected_roots = {root_key(row) for path in PROTECTED for row in read_jsonl(path)}
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        if root_key(source) in protected_roots:
            raise SystemExit(f"source root overlaps protected eval/heldout: {source.get('row_id')}")
        rows.append(make_row(source, "no_verifier"))
        rows.append(make_row(source, "partial_context_only"))
    overlaps = sorted({root_key(row) for row in rows} & protected_roots)
    if overlaps:
        raise SystemExit(f"protected root overlap: {overlaps[:5]}")
    write_jsonl(ROWS_OUT, rows)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(rows) == 6,
        "decision": "web_true_abstention_counterfactual_train_support_rows_materialized",
        "counts": {
            "source_abstention_rows": len(source_rows),
            "counterfactual_rows": len(rows),
            "protected_roots": len(protected_roots),
        },
        "source_artifacts": {"source": rel(SOURCE), "protected": [rel(path) for path in PROTECTED]},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS_OUT)},
        "promotion_boundary": {
            "train_support_only": True,
            "strict_eval_eligible": False,
            "not_a_headline_eval": True,
            "purpose": "teach Web support that abstention is correct when selected tests/source spans are missing",
        },
        "recommended_next_action": "combine these rows with Stage11378 and rerun a conservative diagnostic probe; reject if canary validation remains below 20/23",
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "counts": summary["counts"], "outputs": summary["outputs"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
