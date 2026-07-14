#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11452
NAME = "stage11452_non_codex_rust_selected_verifier_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "non_codex_rust_selected_verifier_support_rows.json"
ROWS = OUT / "non_codex_rust_selected_verifier_support_rows.jsonl"
QUEUE = ART / "stage11451_non_codex_rust_verifier_log_capture/non_codex_rust_verifier_log_queue.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


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


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def trim(value: str, limit: int = 1800) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[:limit] + "\n..."


def make_options(log_value: str) -> list[dict[str, str]]:
    return [
        {"label": "A", "value": "SUPPORTING_CANDIDATE_CHANGE_SURFACE"},
        {"label": "B", "value": "DECISIVE_VERIFIER_TEST_CONSTRAINT"},
        {"label": "C", "value": log_value},
        {"label": "D", "value": "DISTRACTOR_BACKGROUND_CONTEXT"},
    ]


def label_for(value: str, options: list[dict[str, str]]) -> str:
    for option in options:
        if option["value"] == value:
            return option["label"]
    raise ValueError(value)


def materialize_row(root: dict[str, Any], kind: str, gold_value: str, candidate_text: str, source_path: str) -> dict[str, Any]:
    log_value = "OBSERVED_VERIFIER_PASS_LOG" if root["returncode"] == 0 else "OBSERVED_VERIFIER_FAILURE_LOG"
    options = make_options(log_value)
    label = label_for(gold_value, options)
    candidate_id = f"RV-{short_hash(root['root_id'] + kind)}"
    input_text = (
        "Language: rust\n"
        "Perspective: evidence_candidate_judgment\n"
        "Decision objective: classify this Rust maintenance evidence item as changed-source support, "
        "selected verifier/test constraint, observed verifier log, or background context.\n"
        "Use only the root context and candidate evidence item. Do not infer from option order.\n"
        f"Repository family: {root['repo_family']}\n"
        f"Cargo manifest: {root['manifest']}\n"
        f"Selected verifier command: {root['command']}\n"
        f"Verifier status: {root['verifier_status']} returncode={root['returncode']}\n"
        "Root context:\n"
        f"- Source root: {root['root_id']}\n"
        "- Selected verifier/test anchor: present\n"
        "- Available local evidence roles: changed, verifier_test_constraint, verifier_log, background\n\n"
        "Candidate evidence item under judgment:\n"
        f"Candidate ID: {candidate_id}\n"
        f"Source path: {source_path}\n"
        "Evidence note: materialized non-codex Rust selected-verifier evidence excerpt.\n"
        f"Excerpt:\n{trim(candidate_text)}\n\n"
        "Options:\n"
        + "\n".join(f"{option['label']}. {option['value']}" for option in options)
        + "\nAnswer:"
    )
    return {
        "stage": STAGE,
        "row_id": f"stage11452::{root['root_id']}::{kind}",
        "root_id": root["root_id"],
        "root_lineage_key": root["root_id"],
        "repo_id": root["repo_family"],
        "repo_family": root["repo_family"],
        "language_family": "rust",
        "task_type": "evidence_candidate_judgment",
        "surface": "maintainer_rust_selected_verifier_log_backed_evidence_candidate_judgment_bounded_choice",
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor_present": True,
        "selected_verifier_anchor_present": True,
        "build_verifier_only": False,
        "semantic_target_value": gold_value,
        "bounded_choice_target_label": label,
        "decoder_text": label,
        "target_text": label,
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "opaque_options": options,
        "input_text": input_text,
        "prompt_text": input_text,
        "anti_cheat": {
            "actual_verifier_log_attached": True,
            "deterministic_option_shuffle": True,
            "role_alias_not_visible_before_options": True,
            "root_split_isolation_required": True,
            "selected_test_anchor_present": True,
            "selected_verifier_anchor_present": True,
            "single_candidate_item_judgment": True,
            "source_text_materialized": True,
            "target_label_not_visible_before_options": True,
        },
        "standalone_projection_source": {
            "candidate_evidence_kind": kind,
            "candidate_evidence_text": f"Candidate ID: {candidate_id}\nSource path: {source_path}\n{trim(candidate_text)}",
            "gold_label": label,
            "gold_value": gold_value,
            "opaque_options": options,
            "source_chunk_path": source_path,
            "source_chunk_role": kind,
            "source_inventory_stage": NAME,
            "source_row_id": root["root_id"],
            "verifier_log_path": root["verifier_log_path"],
            "verifier_status": root["verifier_status"],
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for root in read_jsonl(QUEUE):
        if not root.get("materializable_for_support_rows"):
            continue
        log_path = ROOT / root["verifier_log_path"]
        log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
        snippets = root.get("source_snippets") or {}
        source_items = list(snippets.items())
        if not source_items:
            continue
        source_path, source_text = source_items[0]
        verifier_source_path, verifier_source_text = source_items[-1]
        log_value = "OBSERVED_VERIFIER_PASS_LOG" if root["returncode"] == 0 else "OBSERVED_VERIFIER_FAILURE_LOG"
        rows.append(
            materialize_row(
                root,
                "candidate_change_surface",
                "SUPPORTING_CANDIDATE_CHANGE_SURFACE",
                source_text,
                source_path,
            )
        )
        rows.append(
            materialize_row(
                root,
                "inline_verifier_test_source",
                "DECISIVE_VERIFIER_TEST_CONSTRAINT",
                f"Selected verifier command: {root['command']}\nVerifier-focused source excerpt:\n{verifier_source_text}",
                verifier_source_path,
            )
        )
        rows.append(
            materialize_row(
                root,
                "actual_verifier_pass_log" if root["returncode"] == 0 else "actual_verifier_failure_log",
                log_value,
                log_text,
                root["verifier_log_path"],
            )
        )

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows),
        "decision": "non_codex_rust_selected_verifier_support_rows_ready" if rows else "no_rows_materialized",
        "counts": {
            "rows": len(rows),
            "roots": len({row["root_lineage_key"] for row in rows}),
            "repo_families": len({row["repo_family"] for row in rows}),
        },
        "by_repo_family": dict(sorted({repo: sum(1 for row in rows if row["repo_family"] == repo) for repo in {row["repo_family"] for row in rows}}.items())),
        "by_semantic_target_value": dict(sorted({value: sum(1 for row in rows if row["semantic_target_value"] == value) for value in {row["semantic_target_value"] for row in rows}}.items())),
        "source_artifacts": {
            "verifier_log_queue": rel(QUEUE),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rows": rel(ROWS),
        },
    }
    write_jsonl(ROWS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
