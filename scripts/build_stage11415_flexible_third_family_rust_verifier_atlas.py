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
STAGE = 11415
NAME = "stage11415_flexible_third_family_rust_verifier_atlas"
OUT = ART / NAME
SUMMARY = OUT / "flexible_third_family_rust_verifier_atlas.json"
QUEUE = OUT / "flexible_third_family_rust_verifier_queue.jsonl"

SEARCH_ROOTS = [Path("/data/repositories"), Path("/data/tmp")]
EXCLUDED_FOR_PROMOTION = {"candle", "git", "rust", "rust-analyzer", "prusti-dev", "tokenizers"}
DIAGNOSTIC_ONLY = {"tokenizers"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def repo_family(path: Path) -> str:
    try:
        return path.relative_to(Path("/data/repositories")).parts[0]
    except ValueError:
        try:
            return path.relative_to(Path("/data/tmp")).parts[0]
        except ValueError:
            return "unknown"


def stable_id(path: Path) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(path)).strip("_")
    return f"local_flexible_rust::{safe}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def has_test_marker(path: Path) -> bool:
    text = read_text(path)
    return "#[test]" in text or "#[cfg(test)]" in text


def rust_files(crate_dir: Path) -> list[Path]:
    ignored_parts = {".git", "target"}
    files = []
    for path in sorted(crate_dir.rglob("*.rs")):
        if ignored_parts & set(path.parts):
            continue
        files.append(path)
    return files


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cargo_files = []
    for root in SEARCH_ROOTS:
        if root.exists():
            cargo_files.extend(sorted(root.rglob("Cargo.toml")))

    queue = []
    for cargo in sorted(cargo_files):
        crate_dir = cargo.parent
        repo = repo_family(crate_dir)
        files = rust_files(crate_dir)
        test_file = next((path for path in files if has_test_marker(path)), None)
        source_file = next((path for path in files if path != test_file), test_file)
        blockers = []
        if not files:
            blockers.append("missing_rust_files_under_crate")
        if test_file is None:
            blockers.append("missing_inline_or_file_test_anchor")
        if source_file is None:
            blockers.append("missing_source_file")
        if repo in EXCLUDED_FOR_PROMOTION:
            blockers.append("excluded_or_already_counted_repo_family")
        if repo in DIAGNOSTIC_ONLY:
            blockers.append("diagnostic_only_repo_family")
        can_attempt = not any(
            reason in blockers
            for reason in ("missing_rust_files_under_crate", "missing_inline_or_file_test_anchor", "missing_source_file")
        )
        queue.append(
            {
                "root_id": stable_id(crate_dir),
                "repo_family": repo,
                "crate_dir": str(crate_dir),
                "cargo_toml": str(cargo),
                "candidate_change_surface_path": str(source_file) if source_file else None,
                "test_anchor_path": str(test_file) if test_file else None,
                "inferred_verifier_command": f"cargo test --manifest-path {cargo}" if can_attempt else None,
                "blockers": blockers,
                "can_attempt_verifier_log_capture": can_attempt,
                "promotion_eligible_family": repo not in EXCLUDED_FOR_PROMOTION,
                "train_support_allowed_now": False,
            }
        )

    ready = [row for row in queue if row["can_attempt_verifier_log_capture"]]
    promotion_ready = [row for row in ready if row["promotion_eligible_family"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "flexible_third_family_rust_verifier_atlas_ready",
        "counts": {
            "crate_roots_examined": len(queue),
            "can_attempt_verifier_log_capture": len(ready),
            "promotion_eligible_attempts": len(promotion_ready),
            "promotion_eligible_repo_families": len({row["repo_family"] for row in promotion_ready}),
        },
        "ready_by_repo_family": dict(sorted(Counter(row["repo_family"] for row in ready).items())),
        "promotion_eligible_by_repo_family": dict(sorted(Counter(row["repo_family"] for row in promotion_ready).items())),
        "blocker_counts": dict(sorted(Counter(reason for row in queue for reason in row["blockers"]).items())),
        "quality_gate": {
            "verifier_logs_present": False,
            "train_rows_emitted": False,
            "has_third_family_candidate": bool(promotion_ready),
            "probe_ready": False,
        },
        "recommended_next_action": (
            "Capture verifier logs for promotion-eligible third-family candidates first. Tokenizers rows may be diagnostic only "
            "unless a separate non-overlap signoff is produced."
        ),
        "outputs": {"summary": rel(SUMMARY), "queue": rel(QUEUE)},
    }
    write_jsonl(QUEUE, queue)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
