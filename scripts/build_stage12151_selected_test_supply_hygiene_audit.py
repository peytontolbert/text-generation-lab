#!/usr/bin/env python3
"""Audit selected-test supply before corrected row materialization.

The audit is deliberately pre-row: it checks whether the currently admitted
selected-test successes have enough provenance to become training support rows
without carrying dependency/cache evidence or missing reproducibility data.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
STAGE = "stage12151_selected_test_supply_hygiene_audit"
OUT = REPO / "runs" / "local" / "artifacts" / STAGE
SUMMARY = REPO / "runs" / "summaries" / f"{STAGE}.json"

SUPPLY = REPO / "runs/local/artifacts/stage12146_selected_test_supply_rollup/selected_test_supply_rollup.jsonl"
RUST = REPO / "runs/local/artifacts/stage12144_rust_hydrated_selected_test_success_package/rust_hydrated_selected_test_successes.jsonl"
WEB = REPO / "runs/local/artifacts/stage12145_web_hydrated_selected_test_success_package/web_hydrated_selected_test_results.jsonl"
PY = REPO / "runs/local/artifacts/stage12143_no_install_selected_test_expansion/selected_test_expansion_results.jsonl"

DEPENDENCY_MARKERS = (
    "node_modules/",
    "/node_modules/",
    ".git/",
    "/.git/",
    "target/debug/",
    "target/release/",
    "/target/",
    ".venv/",
    "/.venv/",
    "__pycache__/",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(path: str | None) -> str | None:
    if not path:
        return None
    head = Path(path) / ".git" / "HEAD"
    if not head.exists():
        return None
    text = head.read_text(encoding="utf-8", errors="ignore").strip()
    if text.startswith("ref: "):
        ref = Path(path) / ".git" / text[5:]
        if ref.exists():
            return ref.read_text(encoding="utf-8", errors="ignore").strip()
        packed = Path(path) / ".git" / "packed-refs"
        if packed.exists():
            ref_name = text[5:]
            for line in packed.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line and not line.startswith("#") and line.endswith(" " + ref_name):
                    return line.split()[0]
        return None
    return text or None


def has_dependency_path(paths: list[str]) -> str | None:
    blob = "\n".join(paths)
    for marker in DEPENDENCY_MARKERS:
        if marker in blob:
            return marker
    return None


def record_blockers(record: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    details: dict[str, Any] = {}
    language = record.get("language_family") or record.get("language")
    repo_family = record.get("repo_family")
    checkout = record.get("checkout_path") or record.get("local_root")
    commit = record.get("commit_sha") or git_head(checkout)
    selected_tests = record.get("selected_tests") or record.get("selected_test_ids") or []

    if not repo_family:
        blockers.append("missing_repo_family")
    if not selected_tests:
        blockers.append("missing_selected_test_ids")
    if not checkout:
        blockers.append("missing_checkout_path")
    if language in {"rust", "web_js_ts_html"} and not commit:
        blockers.append("missing_commit_sha")
    if record.get("strict_eval_eligible") is True:
        blockers.append("strict_eval_eligible_true_in_supply")
    if record.get("train_support_only") is not True:
        blockers.append("train_support_only_not_true")

    visible_paths: list[str] = []
    for key in ("visible_rust_sources", "visible_source_files", "source_files", "test_files"):
        value = record.get(key)
        if isinstance(value, list):
            visible_paths.extend(str(item) for item in value)
    dep_marker = has_dependency_path(visible_paths)
    if dep_marker:
        blockers.append(f"dependency_path_visible:{dep_marker}")

    source_hashes: dict[str, str] = {}
    test_hashes: dict[str, str] = {}
    for item in record.get("source_test_evidence_hashes") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        rel = item.get("path")
        digest = item.get("sha256")
        if not rel or not digest:
            continue
        marker = has_dependency_path([str(rel)])
        if marker:
            blockers.append(f"dependency_path_visible:{marker}")
            continue
        if kind == "test":
            test_hashes[str(rel)] = str(digest)
        elif kind == "source":
            source_hashes[str(rel)] = str(digest)
    if checkout:
        root = Path(checkout)
        clean_paths = [
            p
            for p in visible_paths
            if not has_dependency_path([p])
            and not p.startswith("/")
            and (root / p).exists()
            and (root / p).is_file()
        ]
        for rel in clean_paths[:12]:
            digest = sha256_file(root / rel)
            if digest:
                bucket = test_hashes if rel.startswith("test") or "/tests/" in rel or rel.startswith("tests/") else source_hashes
                bucket[rel] = digest

        # Rust unit tests are often embedded in src/*.rs, so selected-test
        # provenance can legitimately live in source hashes rather than a
        # separate tests/ file. Count the source file as test-backed only when
        # the test name is visibly present in the file.
        if language == "rust" and not test_hashes:
            selected_names = [str(test).split("::")[-1] for test in selected_tests]
            for rel, digest in list(source_hashes.items()):
                path = root / rel
                if not path.exists() or not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(name and name in text for name in selected_names):
                    test_hashes[rel] = digest
                    break

    details.update(
        {
            "language_family": language,
            "repo_family": repo_family,
            "checkout_path": checkout,
            "commit_sha": commit,
            "selected_tests": selected_tests,
            "visible_path_count": len(visible_paths),
            "source_hash_count": len(source_hashes),
            "test_hash_count": len(test_hashes),
            "source_hashes": source_hashes,
            "test_hashes": test_hashes,
        }
    )

    if checkout and not source_hashes:
        blockers.append("no_project_source_hashes_captured")
    if checkout and not test_hashes:
        blockers.append("no_test_hashes_captured")

    return blockers, details


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    supply = load_jsonl(SUPPLY)
    hydrated = []
    for source_stage, path in (("stage12144", RUST), ("stage12145", WEB), ("stage12143", PY)):
        for record in load_jsonl(path):
            if record.get("admissible_for_row_materialization_request") or record.get("admission_ready_for_row_materialization"):
                record = dict(record)
                record.setdefault("source_stage", source_stage)
                hydrated.append(record)

    by_repo: dict[str, dict[str, Any]] = {}
    for record in hydrated:
        key = str(record.get("repo_family"))
        by_repo[key] = record

    audited = []
    blocker_counts = Counter()
    for item in supply:
        if item.get("status") != "ready_for_row_materialization":
            continue
        source = by_repo.get(str(item.get("repo_family")), item)
        merged = dict(source)
        merged.update({k: v for k, v in item.items() if v is not None})
        blockers, details = record_blockers(merged)
        for blocker in blockers:
            blocker_counts[blocker] += 1
        audited.append(
            {
                "repo_family": item.get("repo_family"),
                "root_id": item.get("root_id"),
                "language_family": item.get("language_family"),
                "source_stage": item.get("source_stage"),
                "passed": not blockers,
                "blockers": blockers,
                "details": details,
            }
        )

    passed_records = [row for row in audited if row["passed"]]
    summary = {
        "stage": STAGE,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "input_supply": str(SUPPLY.relative_to(REPO)),
        "audited_ready_records": len(audited),
        "passed_records": len(passed_records),
        "blocked_records": len(audited) - len(passed_records),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "records": audited,
        "decision": (
            "ready_supply_hygiene_passed_for_stage12149_inputs"
            if len(passed_records) == len(audited) and audited
            else "block_or_repair_failed_supply_records_before_stage12149_training_use"
        ),
        "training_allowed": False,
        "strict_eval_eligible": False,
        "promotion_eligible": False,
    }
    (OUT / "selected_test_supply_hygiene_records.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in audited) + ("\n" if audited else ""),
        encoding="utf-8",
    )
    for path in (OUT / "summary.json", SUMMARY):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
