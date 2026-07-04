#!/usr/bin/env python3
"""Mine closed-authority BIND_TEST_TO_SYMBOL rows from local /arxiv repos.

This is a targeted recovery miner. It only emits seed candidate rows where a
call made from a test file resolves to a definition in a non-test file in the
same repository. It never emits raw source, raw symbol names, body text, or
training-authorized rows.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_stage8603_arxiv_symbol_binding_candidates import (
    AUTHORITY_CLOSED,
    audit_rows,
    build_repo_index,
    make_row,
    scan_python_repo,
    sanitize_name_features,
    stable_hash,
    write_json,
    write_jsonl,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_test_bind_rows(
    repo_summary: dict[str, Any],
    *,
    max_rows_per_repo: int,
    max_py_files: int,
) -> list[dict[str, Any]]:
    repo_id = repo_summary["repo_id"]
    repo_path = Path(repo_summary["path"])
    facts = scan_python_repo(repo_path, max_py_files=max_py_files)
    if not facts:
        return []
    index = build_repo_index(facts)
    rows: list[dict[str, Any]] = []
    row_index_base = 8_617_000_000 + (int(stable_hash(repo_id, n=8), 16) % 1_000_000)

    for fact in facts:
        if len(rows) >= max_rows_per_repo:
            break
        if not fact.is_test:
            continue
        for call_name in fact.calls:
            if len(rows) >= max_rows_per_repo:
                break
            target_facts = [candidate for candidate in index["def_to_fact"].get(call_name, []) if not candidate.is_test]
            if not target_facts:
                continue
            row = make_row(
                row_index_base + len(rows),
                repo_id,
                str(repo_path),
                "test",
                "BIND_TEST_TO_SYMBOL",
                {
                    "test_call_shape": sanitize_name_features(call_name),
                    "source_file_is_test": True,
                    "candidate_defined_outside_test": True,
                },
                "symbol",
                facts,
                target_facts[:8],
            )
            row["row_id"] = f"stage8617_row_{stable_hash(repo_id, fact.rel_path, call_name, str(len(rows)), n=12)}"
            row["target"]["binding_action"] = "BIND_TEST_TO_SYMBOL"
            row["loss_mask"] = {
                "symbol_binding_ce": False,
                "decoder_ce": False,
                "denoise_ce": False,
                "runtime_reward": False,
            }
            row["authority"] = dict(AUTHORITY_CLOSED)
            row.setdefault("anti_cheat", {})["stage8617_test_bind_patch_row"] = True
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-summaries", default="runs/local/artifacts/stage8600_arxiv_corpus_index/repository_summaries.jsonl")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8617_symbol_binding_test_patch")
    parser.add_argument("--max-repos", type=int, default=120)
    parser.add_argument("--max-rows-per-repo", type=int, default=12)
    parser.add_argument("--max-py-files-per-repo", type=int, default=1200)
    args = parser.parse_args()

    summaries = load_jsonl(Path(args.repo_summaries))
    python_repos = [
        row
        for row in sorted(summaries, key=lambda r: int(r.get("maintainer_usefulness_score", 0)), reverse=True)
        if int((row.get("language_file_counts") or {}).get("python", 0)) > 0
    ][: args.max_repos]

    rows: list[dict[str, Any]] = []
    for summary in python_repos:
        rows.extend(
            build_test_bind_rows(
                summary,
                max_rows_per_repo=args.max_rows_per_repo,
                max_py_files=args.max_py_files_per_repo,
            )
        )

    out = Path(args.output_dir)
    audit = audit_rows(rows)
    audit["stage8617_binding_action_counts"] = dict(Counter(row["target"]["binding_action"] for row in rows))
    audit["stage8617_query_kind_counts"] = dict(Counter(row["query"]["query_kind"] for row in rows))
    audit["stage8617_loss_enabled_rows"] = sum(1 for row in rows if any(row.get("loss_mask", {}).values()))
    passed = (
        audit["rows"] > 0
        and audit["binding_action_counts"].get("BIND_TEST_TO_SYMBOL", 0) > 0
        and audit["query_kind_counts"].get("test", 0) == audit["rows"]
        and audit["endpoint_failures"] == 0
        and audit["label_id_leak_rows"] == 0
        and audit["raw_source_rows"] == 0
        and audit["authority_rows"] == 0
        and audit["decoder_ce_rows"] == 0
        and audit["stage8617_loss_enabled_rows"] == 0
    )

    write_jsonl(out / "symbol_binding_test_patch_rows.jsonl", rows)
    write_json(out / "audit_card.json", audit)
    summary = {
        "stage": 8617,
        "name": "stage8617_reconstructed_symbol_binding_test_patch",
        "passed": passed,
        "summary": "Mined closed-authority test-file call bindings to recover true BIND_TEST_TO_SYMBOL seed rows. Rows remain candidates only; all losses and authority stay closed pending counterfactual/audit stages.",
        "metrics": audit,
        "artifacts": {
            "manifest": str(out / "symbol_binding_test_patch_rows.jsonl"),
            "audit_card": str(out / "audit_card.json"),
        },
        "gates": {
            "model_ready_training_rows": 0,
            "loss_enabled_rows": audit["stage8617_loss_enabled_rows"],
            "body_emission_authorized": False,
            "source_emission_authorized": False,
            "runtime_authorized": False,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "transition_head_training_authorized_next": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False,
        },
        "next_best_step": "Merge Stage8617 test-bind candidates with Stage8604 rows, rebuild symbol-binding counterfactual obligations, then rerun readiness and shortcut audits before any symbol_binding_ce training.",
    }
    write_json(Path("runs/summaries/stage8617_reconstructed_symbol_binding_test_patch.json"), summary)
    print(json.dumps({"passed": passed, "metrics": audit, "output_dir": str(out)}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
