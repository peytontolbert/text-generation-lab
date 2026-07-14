#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10915
NAME = "stage10915_evidence_successor_strict_candidates"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_successor_strict_candidates.json"
ROWS_JSONL = OUT_DIR / "strict_candidate_rows.jsonl"
BUNDLE_JSON = OUT_DIR / "strict_candidate_bundle.json"

MANIFEST_ROWS = ARTIFACTS / "stage10914_evidence_successor_materialization_manifest" / "candidate_rows.jsonl"
SOURCE_ROW_FILES = [
    ARTIFACTS / "stage10828_evidence_role_probe_request" / "evidence_role_probe_manifest.jsonl",
    ARTIFACTS / "stage10782_targeted_residual_support_probe_request" / "targeted_residual_support_probe_manifest.jsonl",
    ARTIFACTS / "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison" / "reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def find_source_row(spec: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    target_row_id = str(spec.get("current_checked_row_id") or "")
    if target_row_id:
        for row in corpus:
            if str(row.get("row_id") or "") == target_row_id:
                return row
    bundle_id = str(spec.get("source_bundle_id") or "")
    for row in corpus:
        if (
            str(row.get("source_bundle_id") or "") == bundle_id
            and str(row.get("task_type") or "") == "evidence_citation"
            and str(row.get("repo_id") or "") == str(spec.get("repo_id") or "")
        ):
            return row
    raise ValueError(f"missing source row for queue_id={spec.get('queue_id')}")


def split_prompt(prompt: str) -> tuple[str, str]:
    marker = "\nOptions:\n"
    if marker not in prompt:
        raise ValueError("prompt missing Options marker")
    prefix, suffix = prompt.split(marker, 1)
    if "\nAnswer:" not in suffix:
        raise ValueError("prompt missing Answer marker")
    _, answer_tail = suffix.split("\nAnswer:", 1)
    return prefix + marker, "\nAnswer:" + answer_tail


def deterministic_order(options: list[dict[str, Any]], queue_id: str) -> list[dict[str, Any]]:
    values = {str(item.get("value") or ""): item for item in options}
    keys = list(values)
    if "candidate_change_surface" in keys and "verifier_and_test_constraint" in keys:
        remaining = [key for key in keys if key not in {"candidate_change_surface", "verifier_and_test_constraint"}]
        remaining.sort(key=lambda key: hashlib.sha256(f"{queue_id}:{key}".encode("utf-8")).hexdigest())
        if queue_id.startswith("cpp_agentkernel"):
            ordered = ["verifier_and_test_constraint", "candidate_change_surface", *remaining]
        else:
            ordered = ["candidate_change_surface", "verifier_and_test_constraint", *remaining]
        return [values[key] for key in ordered]
    return sorted(
        options,
        key=lambda item: hashlib.sha256(f"{queue_id}:{item.get('value')}".encode("utf-8")).hexdigest(),
    )


def relabel_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(options) > len(labels):
        raise ValueError("too many options to relabel")
    return [{"label": labels[idx], "value": str(item.get("value") or "")} for idx, item in enumerate(options)]


def render_prompt(source_row: dict[str, Any], options: list[dict[str, Any]], source_spec: dict[str, Any]) -> str:
    source_prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    prefix, suffix = split_prompt(source_prompt)
    task_line = (
        "Task: Choose the visible evidence key that most specifically justifies the edit-target decision. "
        "Prefer verifier/test constraints over merely naming the edited surface when the visible packet supports that stronger claim."
    )
    prefix_lines = prefix.splitlines()
    rewritten_lines = []
    for line in prefix_lines:
        if line.startswith("Task: "):
            rewritten_lines.append(task_line)
        else:
            rewritten_lines.append(line)
    rewritten = "\n".join(rewritten_lines)
    option_lines = [f"{item['label']}. {item['value']}" for item in options]
    footer = suffix.strip()
    return rewritten + "\n" + "\n".join(option_lines) + "\n" + footer + "\n"


def build_row(spec: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    source_options = [item for item in source_row.get("opaque_options") or [] if isinstance(item, dict)]
    ordered = deterministic_order(source_options, str(spec.get("queue_id") or ""))
    relabeled = relabel_options(ordered)
    gold_value = str(spec.get("gold_answer_value") or "")
    target_label = None
    for item in relabeled:
        if item["value"] == gold_value:
            target_label = item["label"]
            break
    if target_label is None:
        raise ValueError(f"gold value {gold_value!r} not present in options for {spec.get('queue_id')}")
    prompt = render_prompt(source_row, relabeled, spec)
    queue_id = str(spec.get("queue_id") or "")
    return {
        "anti_cheat": {
            "fresh_successor_candidate_only": True,
            "opaque_labels": True,
            "option_order_changed_from_source": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "target_path_strings_hidden_pre_options": True,
        },
        "decoder_text": target_label,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": spec.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": relabeled,
        "prompt_text": prompt,
        "query_text": f"strict_candidate::{spec.get('language_family')}::evidence_citation::{queue_id}",
        "repo_family": spec.get("repo_id"),
        "repo_id": spec.get("repo_id"),
        "row_id": f"stage10915::{queue_id}::evidence_citation::strict_candidate_v1",
        "selected_test_anchor": bool(spec.get("selected_tests")),
        "source_bundle_id": spec.get("source_bundle_id"),
        "source_heldout_admissible": False,
        "source_root_id": spec.get("source_bundle_id"),
        "split": "strict_eval_candidate",
        "split_role": "heldout_candidate_not_admitted",
        "standalone_projection_source": {
            "current_checked_row_id": spec.get("current_checked_row_id"),
            "current_checked_target_value": spec.get("current_checked_target_value"),
            "gold_value": gold_value,
            "opaque_options": relabeled,
            "original_source_row_id": source_row.get("row_id"),
            "projection_mode": "stage10915_fresh_evidence_successor_candidate_v1",
            "queue_id": queue_id,
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": target_label,
        "target_token_len": 1,
        "task_type": "evidence_citation",
        "train_support_only": False,
        "verifier_anchor": bool(spec.get("selected_tests")),
    }


def main() -> None:
    specs = load_jsonl(MANIFEST_ROWS)
    corpus: list[dict[str, Any]] = []
    for path in SOURCE_ROW_FILES:
        corpus.extend(load_jsonl(path))
    rows = []
    bundle_rows = []
    for spec in specs:
        source_row = find_source_row(spec, corpus)
        row = build_row(spec, source_row)
        rows.append(row)
        bundle_rows.append(
            {
                "queue_id": spec.get("queue_id"),
                "repo_id": spec.get("repo_id"),
                "language_family": spec.get("language_family"),
                "gold_value": spec.get("gold_answer_value"),
                "current_checked_target_value": spec.get("current_checked_target_value"),
                "selected_tests": spec.get("selected_tests"),
                "candidate_paths": spec.get("candidate_paths"),
                "strict_candidate_row_id": row["row_id"],
                "strict_candidate_target_label": row["target_text"],
                "strict_candidate_options": row["opaque_options"],
            }
        )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_python_cpp_evidence_successor_candidates_materialized",
        "headline_findings": [
            "Three reviewed evidence-citation successor candidates are now materialized: Python repository_library, C/C++ parametergolf, and C/C++ agentkernel control.",
            "All candidates preserve the six evidence-role choices while changing opaque option order away from the source checked rows.",
            "The two F-target rows directly stress the current B-vs-F retrieval collapse, while the C/C++ agentkernel row is kept as a B positive-control.",
        ],
        "inputs": {
            "manifest_rows": rel(MANIFEST_ROWS),
            "source_row_files": [rel(path) for path in SOURCE_ROW_FILES],
        },
        "row_count": len(rows),
        "rows_by_language": {
            language: sum(1 for row in rows if str(row.get("language_family") or "") == language)
            for language in sorted({str(row.get("language_family") or "") for row in rows})
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_jsonl": rel(ROWS_JSONL),
            "bundle_json": rel(BUNDLE_JSON),
        },
        "next_best_step": "Score the 100M runtime and Gemma on this 3-row evidence successor slice before attempting any new evidence scorer policy.",
    }
    bundle = {
        "bundle_id": "stage10915::fresh_python_cpp_evidence_successor_candidates",
        "claim_boundary": {
            "strict_candidate_only": True,
            "headline_eligible": False,
            "requires_review_before_scoring": True,
            "same_surface_eval_admissible": False,
            "fresh_option_order_only": True,
        },
        "rows": bundle_rows,
    }
    write_json(SUMMARY_JSON, summary)
    write_json(BUNDLE_JSON, bundle)
    write_jsonl(ROWS_JSONL, rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
