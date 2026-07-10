from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


DIRECT_GROUNDING_ROLES = {"seed_change", "verification_constraint", "repo_graph_neighbor", "test_neighbor"}


def _verification_targets(example: dict[str, Any]) -> list[str]:
    query = dict(example.get("query") or {})
    targets = dict(example.get("targets") or {})
    final_state = dict(targets.get("final_state") or {})
    selected = [str(item) for item in list(query.get("selected_tests") or []) if str(item)]
    if selected:
        return selected
    return [str(item) for item in list(final_state.get("verification_targets") or []) if str(item)]


def _verification_family_signature(example: dict[str, Any]) -> str:
    stems = []
    for path in _verification_targets(example):
        stem = Path(str(path)).stem.lower()
        if stem.startswith("test_"):
            stem = stem[5:]
        if stem.endswith("_test"):
            stem = stem[:-5]
        if stem:
            stems.append(stem)
    return "|".join(sorted(set(stems)))


def audit_packable_example_quality(
    *,
    examples_path: Path,
    family_share_warn_threshold: float = 0.12,
    source_share_warn_threshold: float = 0.70,
    program_share_warn_threshold: float = 0.20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    examples = read_jsonl(examples_path)
    verification_family_counts: Counter[str] = Counter()
    program_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    per_example_rows: list[dict[str, Any]] = []
    quality_scores: list[float] = []
    context_sizes: list[int] = []
    external_row_counts: list[int] = []

    for example in examples:
        example_id = str(example.get("example_id") or "")
        program_id = str(example.get("program_id") or example.get("repo_id") or "")
        family = _verification_family_signature(example)
        context_rows = [dict(row) for row in example.get("context_rows", []) if isinstance(row, dict)]
        quality = dict(example.get("quality") or {})
        quality_score = float(quality.get("quality_score") or 0.0)
        external_rows = [row for row in context_rows if str(row.get("source_type") or "") != "local_repo"]

        verification_family_counts[family] += 1
        program_counts[program_id] += 1
        quality_scores.append(quality_score)
        context_sizes.append(len(context_rows))
        external_row_counts.append(len(external_rows))

        for row in context_rows:
            role_counts[str(row.get("role") or "")] += 1
            source_counts[str(row.get("source_type") or "")] += 1

        per_example_rows.append({
            "example_id": example_id,
            "program_id": program_id,
            "verification_family": family,
            "quality_score": quality_score,
            "context_row_count": len(context_rows),
            "external_row_count": len(external_rows),
            "selected_test_count": len(_verification_targets(example)),
        })

    example_count = len(examples)
    total_context_rows = sum(context_sizes)
    total_source_rows = sum(source_counts.values())
    direct_grounding_rows = sum(role_counts.get(role, 0) for role in DIRECT_GROUNDING_ROLES)
    top_family, top_family_count = ("", 0)
    if verification_family_counts:
        top_family, top_family_count = verification_family_counts.most_common(1)[0]
    top_program, top_program_count = ("", 0)
    if program_counts:
        top_program, top_program_count = program_counts.most_common(1)[0]

    warning_flags: list[str] = []
    top_family_share = (top_family_count / example_count) if example_count else 0.0
    top_program_share = (top_program_count / example_count) if example_count else 0.0
    repo_source_share = (source_counts.get("repo", 0) / total_source_rows) if total_source_rows else 0.0
    local_repo_share = (source_counts.get("local_repo", 0) / total_source_rows) if total_source_rows else 0.0
    direct_grounding_share = (direct_grounding_rows / total_source_rows) if total_source_rows else 0.0

    if top_family_share > float(family_share_warn_threshold):
        warning_flags.append("high_verification_family_concentration")
    if top_program_share > float(program_share_warn_threshold):
        warning_flags.append("high_program_concentration")
    if repo_source_share > float(source_share_warn_threshold):
        warning_flags.append("high_repo_source_share")
    if local_repo_share < 0.03:
        warning_flags.append("low_local_repo_source_share")
    if direct_grounding_share < 0.08:
        warning_flags.append("low_direct_grounding_share")

    summary = {
        "example_count": example_count,
        "program_count": len(program_counts),
        "verification_family_count": len(verification_family_counts),
        "avg_quality_score": (sum(quality_scores) / len(quality_scores)) if quality_scores else 0.0,
        "avg_context_row_count": (sum(context_sizes) / len(context_sizes)) if context_sizes else 0.0,
        "avg_external_row_count": (sum(external_row_counts) / len(external_row_counts)) if external_row_counts else 0.0,
        "top_verification_family": top_family,
        "top_verification_family_count": top_family_count,
        "top_verification_family_share": top_family_share,
        "top_program_id": top_program,
        "top_program_count": top_program_count,
        "top_program_share": top_program_share,
        "source_counts": dict(sorted(source_counts.items())),
        "role_counts": dict(sorted(role_counts.items())),
        "direct_grounding_rows": direct_grounding_rows,
        "direct_grounding_share": direct_grounding_share,
        "source_shares": {
            key: (value / total_source_rows) if total_source_rows else 0.0
            for key, value in sorted(source_counts.items())
        },
        "top_verification_families": [
            {"verification_family": key, "count": value, "share": (value / example_count) if example_count else 0.0}
            for key, value in verification_family_counts.most_common(20)
        ],
        "top_programs": [
            {"program_id": key, "count": value, "share": (value / example_count) if example_count else 0.0}
            for key, value in program_counts.most_common(20)
        ],
        "warning_flags": warning_flags,
        "thresholds": {
            "family_share_warn_threshold": float(family_share_warn_threshold),
            "source_share_warn_threshold": float(source_share_warn_threshold),
            "program_share_warn_threshold": float(program_share_warn_threshold),
        },
    }
    per_example_rows.sort(key=lambda row: (-float(row["quality_score"]), row["example_id"]))
    return per_example_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit packable example dataset quality and concentration.")
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--family-share-warn-threshold", type=float, default=0.12)
    parser.add_argument("--source-share-warn-threshold", type=float, default=0.70)
    parser.add_argument("--program-share-warn-threshold", type=float, default=0.20)
    args = parser.parse_args()

    rows, summary = audit_packable_example_quality(
        examples_path=args.examples,
        family_share_warn_threshold=args.family_share_warn_threshold,
        source_share_warn_threshold=args.source_share_warn_threshold,
        program_share_warn_threshold=args.program_share_warn_threshold,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output, summary)


if __name__ == "__main__":
    main()
