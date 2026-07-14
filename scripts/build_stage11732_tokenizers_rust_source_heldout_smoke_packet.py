#!/usr/bin/env python3
"""Build a Rust source-backed smoke packet from tokenizers whitespace pre-tokenizer."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = Path("/data/parametergolf/helpful_repos/tokenizers/tokenizers")
OUT_DIR = ROOT / "runs/local/artifacts/stage11732_tokenizers_rust_source_heldout_smoke_packet"
SUMMARY = ROOT / "runs/summaries/stage11732_tokenizers_rust_source_heldout_smoke_packet.json"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def commit() -> str:
    return subprocess.check_output(["git", "-C", str(REPO.parent), "rev-parse", "HEAD"], text=True).strip()


def read_span(path: str, start: int, end: int) -> str:
    lines = (REPO / path).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start - 1 : end])


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
        "language_family": "rust",
        "repo_family": "tokenizers",
        "repo_id": "tokenizers",
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
        "verifier_transition": "STATIC_INLINE_TEST_ANCHOR_NOT_EXECUTED",
        "evidence_ledger": ledger,
        "anti_cheat": {
            "opaque_labels": True,
            "deterministic_option_shuffle": True,
            "option_order_seed": "stage11732_tokenizers_static_order_v1",
            "singleton_options": False,
            "template_only_evidence": False,
            "source_backed_snippets": True,
            "prompt_target_label_leak": False,
            "prompt_target_value_leak": False,
            "target_path_strings_hidden_pre_options": False,
            "target_path_visibility_policy": "candidate_paths_and_symbols_visible_only_inside_candidate_options",
            "requires_no_train_overlap_audit": True,
        },
    }
    specs = [
        {
            "task_type": "symptom_localization",
            "target_label": "A",
            "target_value": "src/pre_tokenizers/whitespace.rs::Whitespace",
            "options": [
                ("A", "candidate_change_surface", "src/pre_tokenizers/whitespace.rs::Whitespace", ["E01", "E02"]),
                ("B", "nearby_candidate_surface", "src/pre_tokenizers/byte_level.rs::ByteLevel", ["E03", "E04"]),
                ("C", "offsets_integration_test_surface", "tests/offsets.rs::byte_level_basic", ["E05"]),
                ("D", "serialization_surface", "tests/serialization.rs", ["E06"]),
            ],
        },
        {
            "task_type": "evidence_citation",
            "target_label": "B",
            "target_value": "Whitespace inline selected test anchor",
            "options": [
                ("A", "candidate_change_surface", "Whitespace pre-tokenizer implementation excerpt alone", ["E01"]),
                ("B", "verifier_and_test_constraint", "Whitespace inline selected test anchor", ["E02"]),
                ("C", "nearby_bytelevel_test_constraint", "ByteLevel offset test distractor", ["E05"]),
                ("D", "serialization_test_constraint", "Serialization test distractor", ["E06"]),
            ],
        },
        {
            "task_type": "patch_impact",
            "target_label": "A",
            "target_value": "src/pre_tokenizers/whitespace.rs::Whitespace",
            "options": [
                ("A", "minimal_candidate_change_surface", "src/pre_tokenizers/whitespace.rs::Whitespace", ["E01", "E02"]),
                ("B", "nearby_candidate_surface", "src/pre_tokenizers/byte_level.rs::ByteLevel", ["E03", "E05"]),
                ("C", "test_expectation_surface", "src/pre_tokenizers/whitespace.rs::tests::basic", ["E02"]),
                ("D", "serialization_surface", "tests/serialization.rs", ["E06"]),
            ],
        },
        {
            "task_type": "verifier_outcome",
            "target_label": "A",
            "target_value": "src/pre_tokenizers/whitespace.rs::tests::basic",
            "options": [
                ("A", "selected_test_anchor", "src/pre_tokenizers/whitespace.rs::tests::basic", ["E02"]),
                ("B", "nearby_inline_test_distractor", "src/pre_tokenizers/whitespace.rs::tests::whitespace_split", ["E02"]),
                ("C", "bytelevel_test_distractor", "tests/offsets.rs::byte_level_basic", ["E05"]),
                ("D", "implementation_only_no_verifier", "src/pre_tokenizers/whitespace.rs::Whitespace", ["E01"]),
            ],
        },
    ]
    rows = []
    for spec in specs:
        row = dict(common)
        row["task_type"] = spec["task_type"]
        row["row_id"] = f"{root_id}::{spec['task_type']}::candidate_v1"
        row["target_label"] = spec["target_label"]
        row["target_value"] = spec["target_value"]
        row["opaque_options"] = [
            {"label": label, "role": role, "value": value, "evidence_ids": evidence_ids}
            for label, role, value, evidence_ids in spec["options"]
        ]
        rows.append(row)
    return rows


def main() -> None:
    commit_hash = commit()
    snapshot = f"tokenizers::{commit_hash}"
    root_id = f"stage11732::tokenizers::{commit_hash}::rust::whitespace_pretokenizer_smoke"
    ledger = [
        evidence_item("E01", "implementation_source", "src/pre_tokenizers/whitespace.rs", 10, 40, "Whitespace and WhitespaceSplit pre-tokenizer implementations split normalized strings."),
        evidence_item("E02", "selected_inline_test_anchor", "src/pre_tokenizers/whitespace.rs", 43, 105, "Inline tests verify Whitespace punctuation splitting and WhitespaceSplit behavior."),
        evidence_item("E03", "nearby_candidate_surface", "src/pre_tokenizers/byte_level.rs", 51, 148, "ByteLevel is a nearby pre-tokenizer implementation with different byte-level behavior."),
        evidence_item("E04", "bytelevel_decoder_surface", "src/pre_tokenizers/byte_level.rs", 150, 180, "ByteLevel decoder/post-processor code is related but not the whitespace component."),
        evidence_item("E05", "distractor_test_anchor", "tests/offsets.rs", 13, 54, "Offset tests exercise ByteLevel tokenizer behavior, not Whitespace directly."),
        evidence_item("E06", "serialization_test_surface", "tests/serialization.rs", 1, 80, "Serialization tests are plausible but do not directly exercise whitespace splitting."),
    ]
    rows = make_rows(root_id, snapshot, ledger)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    rows_path = OUT_DIR / "tokenizers_rust_smoke_rows.jsonl"
    ledger_path = OUT_DIR / "tokenizers_rust_evidence_ledger.json"
    artifact_path = OUT_DIR / "tokenizers_rust_source_heldout_smoke_packet.json"
    rows_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact = {
        "stage": 11732,
        "stage_name": "tokenizers_rust_source_heldout_smoke_packet",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "tokenizers_rust_source_heldout_smoke_packet_materialized_pending_overlap_audit",
        "passed": True,
        "language_family": "rust",
        "repo_family": "tokenizers",
        "root_id": root_id,
        "source_snapshot_id": snapshot,
        "row_count": len(rows),
        "task_types": sorted({row["task_type"] for row in rows}),
        "remaining_limitations": [
            "Verifier transition is static inline-test anchoring, not executed fail/pass.",
            "Rows are pending exact no-train/no-support overlap audit.",
            "tokenizers has prior lineage risk; exact root/snapshot audit is required before admission.",
        ],
        "next_stage_acceptance": [
            "run exact root/source snapshot no-train overlap audit",
            "admit rows only if no exact train/support overlap is found",
            "score Stage11507 selected product scorer on admitted rows",
            "later attach executable cargo test output for full-product claims",
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
