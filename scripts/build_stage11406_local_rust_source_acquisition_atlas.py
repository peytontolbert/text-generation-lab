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
STAGE = 11406
NAME = "stage11406_local_rust_source_acquisition_atlas"
OUT = ART / NAME
SUMMARY = OUT / "local_rust_source_acquisition_atlas.json"
OUT_ROOTS = OUT / "local_rust_source_roots.jsonl"
OUT_READY = OUT / "local_rust_materialization_candidate_roots.jsonl"

SEARCH_ROOTS = [Path("/data/repositories"), Path("/data/tmp")]
RESERVED_REPO_FAMILIES = {"prusti-dev", "rust", "rust-analyzer"}
KNOWN_WEAK_REPO_FAMILIES = {"tokenizers"}
MAX_FILES_PER_KIND = 50


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def repo_family_for(path: Path) -> str:
    parts = path.parts
    for root in SEARCH_ROOTS:
        try:
            rel_parts = path.relative_to(root).parts
            return rel_parts[0] if rel_parts else path.name
        except ValueError:
            continue
    return path.name


def stable_root_id(path: Path) -> str:
    text = str(path)
    safe = []
    for ch in text:
        safe.append(ch.lower() if ch.isalnum() else "_")
    return "local_rust_root::" + "".join(safe).strip("_")


def safe_read(path: Path, limit: int = 1200) -> str:
    try:
        return path.read_text(errors="replace")[:limit]
    except OSError:
        return ""


def find_files(root: Path, pattern: str) -> list[Path]:
    try:
        return sorted(root.rglob(pattern))[:MAX_FILES_PER_KIND]
    except OSError:
        return []


def first_snippet(paths: list[Path]) -> dict[str, str] | None:
    for path in paths:
        text = safe_read(path)
        if text.strip():
            return {"path": str(path), "excerpt": text}
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cargo_files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.exists():
            cargo_files.extend(sorted(root.rglob("Cargo.toml")))

    records: list[dict[str, Any]] = []
    ready: list[dict[str, Any]] = []
    seen_dirs: set[Path] = set()
    for cargo in sorted(cargo_files):
        crate_dir = cargo.parent
        if crate_dir in seen_dirs:
            continue
        seen_dirs.add(crate_dir)
        repo_family = repo_family_for(crate_dir)
        src_files = find_files(crate_dir / "src", "*.rs") if (crate_dir / "src").exists() else []
        test_files = find_files(crate_dir / "tests", "*.rs") if (crate_dir / "tests").exists() else []
        example_files = find_files(crate_dir / "examples", "*.rs") if (crate_dir / "examples").exists() else []
        bench_files = find_files(crate_dir / "benches", "*.rs") if (crate_dir / "benches").exists() else []
        verifier_files = test_files or example_files or bench_files
        source_snippet = first_snippet(src_files)
        verifier_snippet = first_snippet(verifier_files)
        source_path = source_snippet["path"] if source_snippet else None
        verifier_path = verifier_snippet["path"] if verifier_snippet else None
        blocked_reasons: list[str] = []
        if repo_family in RESERVED_REPO_FAMILIES:
            blocked_reasons.append("reserved_strict_repo_family")
        if repo_family in KNOWN_WEAK_REPO_FAMILIES:
            blocked_reasons.append("known_weak_or_quarantined_repo_family")
        if not src_files:
            blocked_reasons.append("missing_src_rs_files")
        if not verifier_files:
            blocked_reasons.append("missing_tests_examples_or_benches")
        if not source_snippet:
            blocked_reasons.append("missing_readable_source_excerpt")
        if not verifier_snippet:
            blocked_reasons.append("missing_readable_verifier_excerpt")

        record = {
            "root_id": stable_root_id(crate_dir),
            "repo_family": repo_family,
            "crate_dir": str(crate_dir),
            "cargo_toml": str(cargo),
            "source_file_count_sampled": len(src_files),
            "test_file_count_sampled": len(test_files),
            "example_file_count_sampled": len(example_files),
            "bench_file_count_sampled": len(bench_files),
            "candidate_change_surface_path": source_path,
            "verifier_or_test_constraint_path": verifier_path,
            "blocked_reasons": blocked_reasons,
            "materialization_candidate": not blocked_reasons,
            "source_excerpt_preview": source_snippet,
            "verifier_excerpt_preview": verifier_snippet,
        }
        records.append(record)
        if not blocked_reasons:
            ready.append(
                {
                    "root_id": record["root_id"],
                    "repo_family": repo_family,
                    "crate_dir": str(crate_dir),
                    "candidate_change_surface_path": source_path,
                    "verifier_or_test_constraint_path": verifier_path,
                    "required_next_step": "build bounded evidence-candidate rows with distinct changed-source and verifier/test evidence",
                    "train_support_only": True,
                    "strict_eval_eligible": False,
                }
            )

    by_repo = Counter(row["repo_family"] for row in records)
    ready_by_repo = Counter(row["repo_family"] for row in ready)
    blocked_reason_counts = Counter(reason for row in records for reason in row["blocked_reasons"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "local_rust_source_atlas_ready",
        "counts": {
            "cargo_roots_examined": len(records),
            "materialization_candidate_roots": len(ready),
            "unique_repo_families": len(by_repo),
            "candidate_repo_families": len(ready_by_repo),
            "minimum_new_roots_needed_for_rust_support_package": 10,
        },
        "by_repo_family": dict(sorted(by_repo.items())),
        "candidate_by_repo_family": dict(sorted(ready_by_repo.items())),
        "blocked_reason_counts": dict(sorted(blocked_reason_counts.items())),
        "quality_gate": {
            "enough_roots_for_stage11404_retry": len(ready) >= 10,
            "enough_repo_breadth_for_stage11404_retry": len(ready_by_repo) >= 3,
            "can_build_support_rows_without_more_source_acquisition": len(ready) >= 10 and len(ready_by_repo) >= 3,
        },
        "interpretation": (
            "Local Rust source snapshots exist, but ready materialization candidates are concentrated in a few repo families. "
            "They should be converted into train-support rows only if each row includes real .rs source evidence, a verifier/test "
            "anchor, and distinct evidence-role candidates."
        ),
        "recommended_next_action": (
            "Materialize bounded train-support rows from ready local Rust crates, then rerun the Stage11404 admission gate. "
            "If repo breadth stays below three, acquire or hydrate more non-tokenizers Rust repositories before training."
        ),
        "outputs": {
            "summary": rel(SUMMARY),
            "all_roots": rel(OUT_ROOTS),
            "candidate_roots": rel(OUT_READY),
        },
    }

    write_jsonl(OUT_ROOTS, records)
    write_jsonl(OUT_READY, ready)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
