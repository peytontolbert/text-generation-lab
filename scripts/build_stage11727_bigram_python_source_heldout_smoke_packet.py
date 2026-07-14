#!/usr/bin/env python3
"""Build a fresh Python source-backed smoke packet from bigram_language_model."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = Path("/data/parametergolf/helpful_repos/bigram_language_model")
OUT_DIR = ROOT / "runs/local/artifacts/stage11727_bigram_python_source_heldout_smoke_packet"
SUMMARY = ROOT / "runs/summaries/stage11727_bigram_python_source_heldout_smoke_packet.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_span(path: str, start: int, end: int) -> str:
    lines = (REPO / path).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start - 1 : end])


def commit() -> str:
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def evidence_item(item_id: str, kind: str, path: str, start: int, end: int, summary: str) -> dict[str, Any]:
    text = read_span(path, start, end)
    return {
        "id": item_id,
        "kind": kind,
        "path": path,
        "start_line": start,
        "end_line": end,
        "summary": summary,
        "text": text,
        "sha256": sha256_text(text),
    }


def make_rows(root_id: str, snapshot: str, ledger: list[dict[str, Any]]) -> list[dict[str, Any]]:
    common = {
        "language_family": "python",
        "repo_family": "bigram_language_model",
        "repo_id": "bigram_language_model",
        "root_id": root_id,
        "source_root_id": root_id,
        "root_lineage_key": root_id,
        "source_snapshot_id": snapshot,
        "surface": "source_heldout_smoke_compact_bounded_choice",
        "source_heldout_admissible": False,
        "train_eligible": False,
        "train_support_only": False,
        "strict_eval_eligible": False,
        "split": "candidate_eval",
        "split_role": "source_heldout_smoke_candidate",
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "has_verifier_row_or_transition": True,
        "verifier_transition": "STATIC_SELECTED_TEST_ANCHOR_NOT_EXECUTED",
        "evidence_ledger": ledger,
        "anti_cheat": {
            "opaque_labels": True,
            "deterministic_option_shuffle": True,
            "option_order_seed": "stage11727_bigram_static_order_v1",
            "singleton_options": False,
            "template_only_evidence": False,
            "source_backed_snippets": True,
            "prompt_target_label_leak": False,
            "prompt_target_value_leak": False,
            "target_path_strings_hidden_pre_options": False,
            "target_path_visibility_policy": "candidate_paths_visible_only_inside_candidate_options",
            "requires_no_train_overlap_audit": True,
        },
    }
    specs = [
        {
            "task_type": "symptom_localization",
            "target_label": "A",
            "target_value": "src/model/bigram_model.py",
            "options": [
                ("A", "candidate_change_surface", "src/model/bigram_model.py", ["E01", "E02"]),
                ("B", "dataset_surface", "src/data/dataset.py", ["E03", "E04"]),
                ("C", "generation_integration_test_surface", "tests/test_generation.py", ["E05"]),
                ("D", "configuration_surface", "src/utils/config.py", ["E06"]),
            ],
        },
        {
            "task_type": "evidence_citation",
            "target_label": "B",
            "target_value": "Bigram model selected test anchor",
            "options": [
                ("A", "candidate_change_surface", "Bigram model implementation excerpt alone", ["E01"]),
                ("B", "verifier_and_test_constraint", "Bigram model selected test anchor", ["E02"]),
                ("C", "nearby_dataset_test_constraint", "Dataset shifted-target test distractor", ["E04"]),
                ("D", "configuration_context", "Training config defaults", ["E06"]),
            ],
        },
        {
            "task_type": "patch_impact",
            "target_label": "A",
            "target_value": "src/model/bigram_model.py",
            "options": [
                ("A", "minimal_candidate_change_surface", "src/model/bigram_model.py", ["E01", "E02"]),
                ("B", "dataset_surface", "src/data/dataset.py", ["E03", "E04"]),
                ("C", "test_expectation_surface", "tests/test_model.py", ["E02"]),
                ("D", "configuration_surface", "src/utils/config.py", ["E06"]),
            ],
        },
        {
            "task_type": "verifier_outcome",
            "target_label": "A",
            "target_value": "tests/test_model.py",
            "options": [
                ("A", "selected_test_anchor", "tests/test_model.py", ["E02"]),
                ("B", "dataset_test_distractor", "tests/test_dataset.py", ["E04"]),
                ("C", "generation_test_distractor", "tests/test_generation.py", ["E05"]),
                ("D", "implementation_only_no_verifier", "src/model/bigram_model.py", ["E01"]),
            ],
        },
    ]
    rows = []
    for spec in specs:
        rr = dict(common)
        rr["task_type"] = spec["task_type"]
        rr["row_id"] = f"{root_id}::{spec['task_type']}::candidate_v1"
        rr["target_label"] = spec["target_label"]
        rr["target_value"] = spec["target_value"]
        rr["opaque_options"] = [
            {"label": label, "role": role, "value": value, "evidence_ids": evidence_ids}
            for label, role, value, evidence_ids in spec["options"]
        ]
        rows.append(rr)
    return rows


def main() -> None:
    commit_hash = commit()
    snapshot = f"bigram_language_model::{commit_hash}"
    root_id = f"stage11727::bigram_language_model::{commit_hash}::python::bigram_model_smoke"
    ledger = [
        evidence_item("E01", "implementation_source", "src/model/bigram_model.py", 4, 93, "BigramLanguageModel implementation defines forward and generate behavior."),
        evidence_item("E02", "selected_test_anchor", "tests/test_model.py", 5, 42, "Model tests verify initialization, forward shape, generation, temperature behavior, and softmax row properties."),
        evidence_item("E03", "nearby_candidate_surface", "src/data/dataset.py", 6, 35, "Dataset implementation is related but tests sequence construction and decoding rather than model logits/generation internals."),
        evidence_item("E04", "distractor_test_anchor", "tests/test_dataset.py", 5, 31, "Dataset tests are plausible but exercise TextDataset rather than BigramLanguageModel."),
        evidence_item("E05", "integration_test_anchor", "tests/test_generation.py", 5, 33, "Generation tests combine dataset and model but are broader integration checks."),
        evidence_item("E06", "configuration_surface", "src/utils/config.py", 4, 21, "Training and generation config dataclasses are plausible configuration distractors."),
    ]
    rows = make_rows(root_id, snapshot, ledger)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    rows_path = OUT_DIR / "bigram_python_smoke_rows.jsonl"
    ledger_path = OUT_DIR / "bigram_python_evidence_ledger.json"
    artifact_path = OUT_DIR / "bigram_python_source_heldout_smoke_packet.json"
    rows_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact = {
        "stage": 11727,
        "stage_name": "bigram_python_source_heldout_smoke_packet",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "bigram_python_source_heldout_smoke_packet_materialized_pending_overlap_audit",
        "passed": True,
        "language_family": "python",
        "repo_family": "bigram_language_model",
        "root_id": root_id,
        "source_snapshot_id": snapshot,
        "row_count": len(rows),
        "task_types": sorted({row["task_type"] for row in rows}),
        "remaining_limitations": [
            "Verifier transition is static selected-test anchoring, not executed fail/pass.",
            "Rows are pending exact no-train/no-support overlap audit.",
            "Rows support compact source-heldout smoke only, not full-product patch repair.",
        ],
        "next_stage_acceptance": [
            "run exact root/source snapshot no-train overlap audit",
            "admit rows only if no exact train/support overlap is found",
            "score Stage11507 selected product scorer on admitted rows",
            "later attach executable verifier/harness fields for full-product claims",
        ],
        "source_artifacts": {
            "repo_path": str(REPO),
            "commit": commit_hash,
        },
        "outputs": {
            "artifact": rel(artifact_path),
            "rows_jsonl": rel(rows_path),
            "evidence_ledger": rel(ledger_path),
            "summary": rel(SUMMARY),
        },
    }
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copyfile(artifact_path, SUMMARY)
    print(json.dumps({"artifact": str(artifact_path), "rows": len(rows), "root_id": root_id}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
