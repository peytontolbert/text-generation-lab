#!/usr/bin/env python3
"""Create the support-materialization request from verifier-grounded smoke failures."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11742
NAME = "stage11742_source_heldout_failure_support_request"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_failure_support_request.json"
WORK_ITEMS = OUT / "support_materialization_work_items.jsonl"

DECISION = ART / "stage11741_verifier_grounded_successor_decision/verifier_grounded_successor_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    decision = load_json(DECISION)
    misses = decision.get("misses") or []
    work_items = [
        {
            "work_item_id": "stage11742_python_verifier_outcome_selected_test_support",
            "priority": 1,
            "language_family": "python",
            "failure_family": "verifier_outcome_selected_test_vs_implementation_surface",
            "observed_failure_rows": [
                row.get("source_row_id") or row.get("row_id")
                for row in misses
                if row.get("language_family") == "python"
            ],
            "required_support_roots": 12,
            "required_strict_analogue_roots": 4,
            "candidate_geometry": [
                "selected_test_anchor",
                "nearby_test_distractor_same_repo",
                "integration_test_distractor",
                "implementation_only_no_verifier",
            ],
            "must_include": [
                "executable pytest log",
                "selected test path only inside candidate options",
                "at least one same-file-family distractor test",
                "observed verifier transition field",
            ],
            "do_not_train_on": "stage11727 bigram_language_model strict smoke root",
        },
        {
            "work_item_id": "stage11742_rust_verifier_outcome_selected_test_support",
            "priority": 2,
            "language_family": "rust",
            "failure_family": "verifier_outcome_selected_inline_test_vs_nearby_inline_test",
            "observed_failure_rows": [
                row.get("source_row_id") or row.get("row_id")
                for row in misses
                if row.get("language_family") == "rust"
            ],
            "required_support_roots": 12,
            "required_strict_analogue_roots": 4,
            "candidate_geometry": [
                "selected_inline_test_anchor",
                "nearby_inline_test_distractor",
                "external_integration_test_distractor",
                "implementation_only_no_verifier",
            ],
            "must_include": [
                "executable cargo test log",
                "selected inline test identifier only inside candidate options",
                "same module sibling test distractor",
                "observed verifier transition field",
            ],
            "do_not_train_on": "stage11732 tokenizers strict smoke root",
        },
        {
            "work_item_id": "stage11742_cpp_abstain_attractor_support",
            "priority": 3,
            "language_family": "c_cpp",
            "failure_family": "abstain_attractor_despite_executable_verifier_evidence",
            "observed_failure_rows": [
                row.get("source_row_id") or row.get("row_id")
                for row in misses
                if row.get("language_family") == "c_cpp"
            ],
            "required_support_roots": 16,
            "required_strict_analogue_roots": 4,
            "candidate_geometry": [
                "candidate_change_surface",
                "verifier_and_test_constraint",
                "nearby_training_or_factory_surface",
                "abstain_insufficient_evidence",
            ],
            "must_include": [
                "executable C/C++ verifier log",
                "paired answerable row with verifier evidence present",
                "paired insufficient-evidence row with verifier evidence removed",
                "same library family distractor surface",
            ],
            "do_not_train_on": "stage11718 sentencepiece strict smoke root",
        },
    ]

    anti_leak_requirements = [
        "same root_id never crosses train/validation/strict",
        "strict smoke roots from Stage11718/11727/11732 remain eval-only canaries",
        "target label and target value must not appear before candidate options",
        "candidate labels must be deterministic-shuffled and presentation-only",
        "selected verifier path/test id may appear only inside candidate options",
        "each row must include source_snapshot_id and root_lineage_key",
        "Gemma comparison must use same manifest and same prompt renderer",
    ]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "materialize_disjoint_support_for_source_heldout_failure_families",
        "passed": True,
        "source_decision": rel(DECISION),
        "work_item_count": len(work_items),
        "work_items": work_items,
        "anti_leak_requirements": anti_leak_requirements,
        "promotion_gate_for_next_probe": {
            "must_preserve_selected_frontier": "stage11507 protected compact gates",
            "must_preserve_verifier_grounded_smoke_canary": "score must exceed 6/12 without training on smoke roots",
            "minimum_success": {
                "verifier_grounded_source_heldout_successor": ">=8/12",
                "python_verifier_outcome": "correct",
                "rust_verifier_outcome": "correct",
                "c_cpp": ">=2/4",
            },
            "gemma_requirement": "same-manifest Gemma3-12B backend still required before public comparison claim",
        },
        "claim_boundary": [
            "This is a materialization request, not a training result.",
            "It exists because verifier grounding alone did not move the source-heldout smoke plateau.",
            "The requested support rows must be disjoint analogues, not replays of strict smoke rows.",
        ],
        "outputs": {"summary": rel(SUMMARY), "work_items": rel(WORK_ITEMS)},
    }
    write_json(SUMMARY, artifact)
    write_jsonl(WORK_ITEMS, work_items)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "work_item_count": len(work_items)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
