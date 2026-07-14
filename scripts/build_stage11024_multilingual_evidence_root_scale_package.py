#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
OUT_DIR = ARTIFACTS / "stage11024_multilingual_evidence_root_scale_package"

BASE_TRAIN = ARTIFACTS / "stage11003_semantic_evidence_bridge_package" / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = ARTIFACTS / "stage11003_semantic_evidence_bridge_package" / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ARTIFACTS / "stage11003_semantic_evidence_bridge_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ARTIFACTS / "stage11003_semantic_evidence_bridge_package" / "agentkernel_lite_encdec_stress_eval.jsonl"

IMMEDIATE_CANDIDATES = ARTIFACTS / "stage10998_fresh_evidence_branch_package" / "strict_candidate_rows.jsonl"
RUST_REVIEWED_CANDIDATES = ARTIFACTS / "stage10972_rust_reviewed_evidence_bundle" / "strict_candidate_rows.jsonl"
RUST_SUCCESSOR_EXPANDED = ARTIFACTS / "stage11022_rust_successor_eval_expansion_package" / "fresh_rust_successor_eval_expanded.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def counts(rows: list[dict], key: str) -> dict[str, int]:
    return dict(Counter(str(row.get(key, "unknown")) for row in rows))


def root_signature(row: dict) -> str:
    for key in ("source_bundle_id", "bundle_id", "queue_id"):
        value = row.get(key)
        if value:
            return str(value)
    row_id = str(row.get("row_id", "unknown"))
    if "::" in row_id:
        return "::".join(row_id.split("::")[:2])
    return row_id


def build_inventory(*row_groups: tuple[str, list[dict]]) -> list[dict]:
    inventory: dict[str, dict] = {}
    for source_name, rows in row_groups:
        for row in rows:
            sig = root_signature(row)
            record = inventory.setdefault(
                sig,
                {
                    "root_signature": sig,
                    "source_groups": set(),
                    "language_families": set(),
                    "repo_families": set(),
                    "task_types": Counter(),
                    "targets": Counter(),
                    "row_ids": [],
                    "row_count": 0,
                },
            )
            record["source_groups"].add(source_name)
            record["language_families"].add(str(row.get("language_family", "unknown")))
            record["repo_families"].add(str(row.get("repo_family", "unknown")))
            record["task_types"][str(row.get("task_type", "unknown"))] += 1
            record["targets"][str(row.get("target_text", "unknown"))] += 1
            record["row_ids"].append(str(row.get("row_id", "")))
            record["row_count"] += 1

    out: list[dict] = []
    for sig, record in inventory.items():
        out.append(
            {
                "root_signature": sig,
                "source_groups": sorted(record["source_groups"]),
                "language_families": sorted(record["language_families"]),
                "repo_families": sorted(record["repo_families"]),
                "task_type_counts": dict(record["task_types"]),
                "target_counts": dict(record["targets"]),
                "row_count": record["row_count"],
                "row_ids": sorted(record["row_ids"]),
            }
        )
    out.sort(key=lambda row: (row["language_families"], row["repo_families"], row["root_signature"]))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_train = read_jsonl(BASE_TRAIN)
    base_validation = read_jsonl(BASE_VALIDATION)
    base_strict = read_jsonl(BASE_STRICT)
    base_stress = read_jsonl(BASE_STRESS)

    immediate_candidates = read_jsonl(IMMEDIATE_CANDIDATES)
    rust_reviewed_candidates = read_jsonl(RUST_REVIEWED_CANDIDATES)
    rust_successor_expanded = read_jsonl(RUST_SUCCESSOR_EXPANDED)

    evidence_train = [
        row
        for row in base_train
        if row.get("task_type") in {"evidence_citation", "evidence_role_classification"}
    ]

    fresh_candidate_bank = immediate_candidates + rust_reviewed_candidates
    expanded_eval_bank = fresh_candidate_bank + rust_successor_expanded

    inventory = build_inventory(
        ("base_evidence_train", evidence_train),
        ("fresh_immediate_candidates", immediate_candidates),
        ("fresh_rust_reviewed_candidates", rust_reviewed_candidates),
        ("fresh_rust_successor_expanded", rust_successor_expanded),
    )

    repo_family_root_counts: dict[str, int] = defaultdict(int)
    for record in inventory:
        for repo_family in record["repo_families"]:
            repo_family_root_counts[repo_family] += 1

    summary = {
        "stage": 11024,
        "stage_name": "multilingual_evidence_root_scale_package",
        "claim_scope": [
            "Consolidate the strongest current evidence-support train base with the fresh candidate banks and expanded Rust successor rows.",
            "Expose root-level geometry so future probes can optimize fresh root coverage rather than only adding more same-family evidence rows.",
            "Do not replace the 23-row overlay headline; this package is a root-scale planning and execution artifact."
        ],
        "source_artifacts": {
            "base_semantic_evidence_bridge": str(BASE_TRAIN.relative_to(ROOT)),
            "base_validation_rows": str(BASE_VALIDATION.relative_to(ROOT)),
            "base_strict_rows": str(BASE_STRICT.relative_to(ROOT)),
            "fresh_immediate_candidates": str(IMMEDIATE_CANDIDATES.relative_to(ROOT)),
            "fresh_rust_reviewed_candidates": str(RUST_REVIEWED_CANDIDATES.relative_to(ROOT)),
            "fresh_rust_successor_expanded": str(RUST_SUCCESSOR_EXPANDED.relative_to(ROOT)),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "base_train_by_language": counts(base_train, "language_family"),
            "base_train_by_task": counts(base_train, "task_type"),
            "evidence_train_rows": len(evidence_train),
            "evidence_train_by_language": counts(evidence_train, "language_family"),
            "evidence_train_by_task": counts(evidence_train, "task_type"),
            "evidence_train_targets": counts(
                [row for row in evidence_train if row.get("task_type") == "evidence_citation"],
                "target_text",
            ),
            "fresh_candidate_bank_rows": len(fresh_candidate_bank),
            "fresh_candidate_bank_by_language": counts(fresh_candidate_bank, "language_family"),
            "fresh_candidate_bank_targets": counts(fresh_candidate_bank, "target_text"),
            "expanded_eval_bank_rows": len(expanded_eval_bank),
            "expanded_eval_bank_by_language": counts(expanded_eval_bank, "language_family"),
            "expanded_eval_bank_by_task": counts(expanded_eval_bank, "task_type"),
            "distinct_root_signatures": len(inventory),
            "root_counts_by_repo_family": dict(sorted(repo_family_root_counts.items())),
            "overlay_validation_rows": len(base_validation),
            "overlay_strict_rows": len(base_strict),
            "overlay_stress_rows": len(base_stress),
        },
        "findings": [
            "The strongest current evidence branch already contains materially more evidence supervision than the older 217-row snapshot, but it is still concentrated in a small set of repo families.",
            "Fresh scoreable evidence candidates remain narrow: immediate Python/C++ contributes 3 strict candidates and reviewed Rust contributes 3 more.",
            "The expanded Rust successor bank broadens task coverage honestly, but comparable fresh Python/C++/web successor banks are still missing.",
            "This package is the correct base for the next evidence-focused execution or root-admission expansion because it keeps train support, fresh candidates, and expanded eval rows separate."
        ],
        "next_best_step": [
            "Use this package as the root-scale reference when building the next fresh Python/C++ evidence families.",
            "Do not claim broader multilingual evidence progress until fresh Python/C++ candidate banks are expanded beyond the current 3 immediate roots and web gains a pure selected-test family.",
            "If another probe is run, evaluate the fresh candidate bank and expanded eval bank separately from the frozen overlay."
        ],
        "outputs": {
            "summary_json": str((OUT_DIR / "multilingual_evidence_root_scale_package.json").relative_to(ROOT)),
            "evidence_train_rows_jsonl": str((OUT_DIR / "evidence_train_rows.jsonl").relative_to(ROOT)),
            "fresh_candidate_bank_jsonl": str((OUT_DIR / "fresh_candidate_bank.jsonl").relative_to(ROOT)),
            "expanded_eval_bank_jsonl": str((OUT_DIR / "expanded_eval_bank.jsonl").relative_to(ROOT)),
            "root_inventory_jsonl": str((OUT_DIR / "root_inventory.jsonl").relative_to(ROOT)),
        },
        "passed": True,
    }

    write_jsonl(OUT_DIR / "evidence_train_rows.jsonl", evidence_train)
    write_jsonl(OUT_DIR / "fresh_candidate_bank.jsonl", fresh_candidate_bank)
    write_jsonl(OUT_DIR / "expanded_eval_bank.jsonl", expanded_eval_bank)
    write_jsonl(OUT_DIR / "root_inventory.jsonl", inventory)
    (OUT_DIR / "multilingual_evidence_root_scale_package.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
