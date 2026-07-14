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
STAGE = 11411
NAME = "stage11411_non_candle_inline_rust_verifier_atlas"
OUT = ART / NAME
SUMMARY = OUT / "non_candle_inline_rust_verifier_atlas.json"
QUEUE = OUT / "non_candle_inline_rust_verifier_queue.jsonl"

SCAN_ROOTS = [
    Path("/data/repositories/git"),
    Path("/data/repositories/perftree"),
    Path("/data/repositories/linux/rust"),
    Path("/data/repositories/LLaMA-Adapter"),
]
EXCLUDED_REPO_FAMILIES = {"candle", "tokenizers", "rust", "rust-analyzer", "prusti-dev"}
MAX_CRATES_PER_REPO = 12


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
        return path.parts[-2] if len(path.parts) > 1 else path.name


def stable_id(path: Path) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(path)).strip("_")
    return f"local_non_candle_inline_rust::{safe}"


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(errors="replace").splitlines()
    except OSError:
        return []


def has_inline_test(path: Path) -> bool:
    for line in read_lines(path):
        stripped = line.strip()
        if stripped.startswith("#[test]") or stripped.startswith("#[cfg(test)]"):
            return True
    return False


def first_inline_test_file(crate_dir: Path) -> Path | None:
    for path in sorted((crate_dir / "src").rglob("*.rs")) if (crate_dir / "src").exists() else []:
        if has_inline_test(path):
            return path
    return None


def first_source_file(crate_dir: Path, avoid: Path | None) -> Path | None:
    for path in sorted((crate_dir / "src").rglob("*.rs")) if (crate_dir / "src").exists() else []:
        if avoid is not None and path == avoid:
            continue
        if path.read_text(errors="replace").strip():
            return path
    return avoid


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cargo_files: list[Path] = []
    for root in SCAN_ROOTS:
        if root.exists():
            cargo_files.extend(sorted(root.rglob("Cargo.toml")))

    queue: list[dict[str, Any]] = []
    repo_seen: Counter[str] = Counter()
    for cargo in sorted(cargo_files):
        crate_dir = cargo.parent
        repo = repo_family(crate_dir)
        if repo in EXCLUDED_REPO_FAMILIES:
            continue
        if repo_seen[repo] >= MAX_CRATES_PER_REPO:
            continue
        inline_test = first_inline_test_file(crate_dir)
        source_file = first_source_file(crate_dir, inline_test)
        blockers: list[str] = []
        if not (crate_dir / "Cargo.toml").exists():
            blockers.append("missing_cargo_manifest")
        if inline_test is None:
            blockers.append("missing_inline_test_anchor")
        if source_file is None:
            blockers.append("missing_source_file")
        command = f"cargo test --manifest-path {cargo}" if not blockers else None
        materializable = not blockers
        repo_seen[repo] += 1
        queue.append(
            {
                "root_id": stable_id(crate_dir),
                "repo_family": repo,
                "crate_dir": str(crate_dir),
                "cargo_toml": str(cargo),
                "candidate_change_surface_path": str(source_file) if source_file else None,
                "inline_test_anchor_path": str(inline_test) if inline_test else None,
                "inferred_verifier_command": command,
                "required_actual_verifier_log": True,
                "blockers": blockers,
                "can_attempt_verifier_log_capture": materializable,
                "train_support_allowed_now": False,
            }
        )

    by_repo = Counter(row["repo_family"] for row in queue)
    ready = [row for row in queue if row["can_attempt_verifier_log_capture"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "non_candle_inline_rust_verifier_atlas_ready",
        "counts": {
            "crate_roots_examined": len(queue),
            "can_attempt_verifier_log_capture": len(ready),
            "unique_repo_families": len(by_repo),
            "candidate_repo_families": len({row["repo_family"] for row in ready}),
        },
        "by_repo_family": dict(sorted(by_repo.items())),
        "ready_by_repo_family": dict(sorted(Counter(row["repo_family"] for row in ready).items())),
        "quality_gate": {
            "verifier_logs_present": False,
            "train_rows_emitted": False,
            "ready_for_log_capture": bool(ready),
            "probe_ready": False,
        },
        "recommended_next_action": "Run verifier log capture for can_attempt_verifier_log_capture rows, then materialize only if logs are real and anti-cheat gates pass.",
        "outputs": {
            "summary": rel(SUMMARY),
            "queue": rel(QUEUE),
        },
    }
    write_jsonl(QUEUE, queue)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
