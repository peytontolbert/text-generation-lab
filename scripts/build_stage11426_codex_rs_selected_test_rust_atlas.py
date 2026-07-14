#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11426
NAME = "stage11426_codex_rs_selected_test_rust_atlas"
OUT = ART / NAME
SUMMARY = OUT / "codex_rs_selected_test_rust_atlas.json"
QUEUE = OUT / "codex_rs_selected_test_rust_queue.jsonl"

CODEX_RS = Path("/data/agentkernel/other_repos/codex/codex-rs")
EXCLUDED_REPO_FAMILIES = {"candle", "git", "tokenizers", "perftree", "LLaMA-Adapter"}
MAX_CANDIDATES = 24


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


def safe_read(path: Path, limit: int = 2400) -> str:
    try:
        return path.read_text(errors="replace")[:limit]
    except OSError:
        return ""


def crate_name(cargo_toml: Path) -> str:
    text = safe_read(cargo_toml, limit=4000)
    in_package = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "[package]":
            in_package = True
            continue
        if line.startswith("[") and line != "[package]":
            in_package = False
        if in_package and line.startswith("name") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    return cargo_toml.parent.name


def has_test_marker(path: Path) -> bool:
    text = safe_read(path, limit=16000)
    return any(marker in text for marker in ("#[test]", "#[tokio::test]", "#[cfg(test)]", "mod tests", "assert_eq!", "assert!"))


def source_file_for(crate_dir: Path, test_path: Path) -> Path | None:
    candidates = []
    for name in ("src/lib.rs", "src/main.rs"):
        path = crate_dir / name
        if path.exists():
            candidates.append(path)
    if test_path.name.endswith(".rs") and "/src/" in str(test_path):
        candidates.append(test_path)
    for path in sorted(set(candidates), key=lambda p: (len(str(p)), str(p))):
        text = safe_read(path)
        if text.strip():
            return path
    return None


def root_id_for(crate_dir: Path) -> str:
    slug = str(crate_dir).strip("/").replace("/", "_").replace("-", "_")
    return f"local_selected_test_rust::{slug}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cargo_roots = sorted(CODEX_RS.rglob("Cargo.toml"))
    rows: list[dict[str, Any]] = []
    blockers: dict[str, int] = {}
    for cargo_toml in cargo_roots:
        crate_dir = cargo_toml.parent
        if "target" in crate_dir.parts:
            continue
        name = crate_name(cargo_toml)
        test_files = [path for path in sorted(crate_dir.rglob("*.rs")) if "target" not in path.parts and has_test_marker(path)]
        if not test_files:
            blockers["missing_selected_test_anchor"] = blockers.get("missing_selected_test_anchor", 0) + 1
            continue
        test_path = test_files[0]
        source_path = source_file_for(crate_dir, test_path)
        if source_path is None:
            blockers["missing_source_snippet"] = blockers.get("missing_source_snippet", 0) + 1
            continue
        root_id = root_id_for(crate_dir)
        row = {
            "root_id": root_id,
            "root_lineage_key": root_id,
            "repo_family": "codex-rs",
            "crate_name": name,
            "crate_dir": str(crate_dir),
            "cargo_toml": str(cargo_toml),
            "candidate_change_surface_path": str(source_path),
            "test_anchor_path": str(test_path),
            "inferred_verifier_command": f"cargo test --manifest-path {cargo_toml}",
            "can_attempt_verifier_log_capture": True,
            "promotion_eligible_family": True,
            "selected_test_anchor_present": True,
            "build_verifier_only": False,
            "blockers": [],
            "anti_cheat_contract": {
                "cargo_manifest_present": True,
                "rust_source_path_present": True,
                "selected_test_anchor_present": True,
                "reserved_or_eval_lineage": False,
                "diagnostic_only_repo_family": False,
                "excluded_precounted_repo_family": "codex-rs" in EXCLUDED_REPO_FAMILIES,
            },
        }
        rows.append(row)
        if len(rows) >= MAX_CANDIDATES:
            break

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "codex_rs_selected_test_rust_candidates_ready" if rows else "codex_rs_selected_test_rust_candidates_absent",
        "counts": {
            "cargo_roots_examined": len(cargo_roots),
            "selected_test_candidates": len(rows),
            "max_candidates_emitted": MAX_CANDIDATES,
            "unique_repo_families": len({row["repo_family"] for row in rows}),
        },
        "blocker_counts": dict(sorted(blockers.items())),
        "quality_gate": {
            "has_selected_test_candidates": bool(rows),
            "all_have_cargo_manifest": all(Path(row["cargo_toml"]).exists() for row in rows),
            "all_have_source_path": all(Path(row["candidate_change_surface_path"]).exists() for row in rows),
            "all_have_test_anchor": all(Path(row["test_anchor_path"]).exists() for row in rows),
            "verifier_logs_present": False,
            "train_rows_emitted": False,
            "probe_ready": False,
        },
        "recommended_next_action": "Capture verifier logs for a capped subset of codex-rs selected-test candidates, then materialize train-support-only rows if logs exist.",
        "outputs": {"summary": rel(SUMMARY), "queue": rel(QUEUE)},
    }
    write_jsonl(QUEUE, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
