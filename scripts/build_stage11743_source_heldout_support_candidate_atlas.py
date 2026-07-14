#!/usr/bin/env python3
"""Atlas candidate roots for Stage11742 source-heldout failure support."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11743
NAME = "stage11743_source_heldout_support_candidate_atlas"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_candidate_atlas.json"
CANDIDATES = OUT / "source_heldout_support_candidates.jsonl"

HELPFUL = Path("/data/parametergolf/helpful_repos")
REQUEST = ART / "stage11742_source_heldout_failure_support_request/source_heldout_failure_support_request.json"

STRICT_FORBIDDEN_ROOTS = {
    "bigram_language_model": "stage11727 bigram_language_model strict smoke root",
    "sentencepiece": "stage11718 sentencepiece strict smoke root",
    "tokenizers/tokenizers": "stage11732 tokenizers strict smoke root",
}

RUST_SUPPORT_FILES = [
    ART / "stage11452_non_codex_rust_selected_verifier_support_rows/non_codex_rust_selected_verifier_support_rows.jsonl",
    ART / "stage11413_non_candle_rust_verifier_log_backed_support/non_candle_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11417_third_family_rust_verifier_log_backed_support/third_family_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11420_perftree_rust_build_verifier_backed_support/perftree_rust_build_verifier_backed_support_rows.jsonl",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def git_head(path: Path) -> str | None:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(path), text=True, capture_output=True, timeout=10)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def repo_dirs() -> list[Path]:
    if not HELPFUL.exists():
        return []
    out = []
    for child in sorted(HELPFUL.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            out.append(child)
    return out


def py_files(repo: Path) -> tuple[list[Path], list[Path]]:
    tests = sorted([p for p in repo.rglob("test*.py") if ".git" not in p.parts])
    sources = sorted(
        [
            p
            for p in repo.rglob("*.py")
            if ".git" not in p.parts and "tests" not in p.parts and "test" not in p.name.lower()
        ]
    )
    return tests[:20], sources[:20]


def candidate_python(repo: Path) -> dict[str, Any] | None:
    tests, sources = py_files(repo)
    if len(tests) < 2 or not sources:
        return None
    repo_name = repo.name
    if repo_name == "bigram_language_model":
        role = "quarantine_strict_smoke_root"
    else:
        role = "execution_candidate"
    return {
        "candidate_id": f"stage11743::python::{repo_name}",
        "language_family": "python",
        "repo_family": repo_name,
        "repo_path": str(repo),
        "source_snapshot_id": git_head(repo),
        "admit_role": role,
        "readiness": "needs_pytest_execution" if role == "execution_candidate" else "quarantine",
        "target_failure_family": "verifier_outcome_selected_test_vs_implementation_surface",
        "test_file_count": len(tests),
        "source_file_count": len(sources),
        "sample_tests": [str(p.relative_to(repo)) for p in tests[:6]],
        "sample_sources": [str(p.relative_to(repo)) for p in sources[:6]],
        "blockers": [] if role == "execution_candidate" else [STRICT_FORBIDDEN_ROOTS["bigram_language_model"]],
    }


def candidate_cpp(repo: Path) -> dict[str, Any] | None:
    cmake = sorted(repo.rglob("CMakeLists.txt"))
    makefiles = sorted(repo.rglob("Makefile"))
    cpp_sources = sorted([p for p in repo.rglob("*") if p.suffix in {".cc", ".cpp", ".c", ".h", ".hpp"} and ".git" not in p.parts])
    test_like = [p for p in cpp_sources if "test" in p.name.lower() or "/test" in str(p).lower()]
    if not cpp_sources or not (cmake or makefiles):
        return None
    repo_name = repo.name
    role = "quarantine_strict_smoke_root" if repo_name == "sentencepiece" else "execution_candidate"
    return {
        "candidate_id": f"stage11743::c_cpp::{repo_name}",
        "language_family": "c_cpp",
        "repo_family": repo_name,
        "repo_path": str(repo),
        "source_snapshot_id": git_head(repo),
        "admit_role": role,
        "readiness": "needs_build_verifier_probe" if role == "execution_candidate" else "quarantine_or_non_bpe_only",
        "target_failure_family": "abstain_attractor_despite_executable_verifier_evidence",
        "cmake_count": len(cmake),
        "makefile_count": len(makefiles),
        "cpp_source_count": len(cpp_sources),
        "test_like_source_count": len(test_like),
        "sample_build_files": [str(p.relative_to(repo)) for p in (cmake + makefiles)[:6]],
        "sample_test_like_sources": [str(p.relative_to(repo)) for p in test_like[:6]],
        "blockers": [] if role == "execution_candidate" else [STRICT_FORBIDDEN_ROOTS["sentencepiece"]],
    }


def rust_existing_support() -> list[dict[str, Any]]:
    by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in RUST_SUPPORT_FILES:
        for row in read_jsonl(path):
            by_root[str(row.get("root_lineage_key") or row.get("root_id") or "")].append(row)
    out = []
    for root, rows in sorted(by_root.items()):
        if not root:
            continue
        repo_family = str(rows[0].get("repo_family") or rows[0].get("repo_id") or "unknown")
        roles = sorted({str((row.get("standalone_projection_source") or {}).get("candidate_evidence_kind") or row.get("semantic_target_value") or "") for row in rows})
        has_selected = any(row.get("selected_test_anchor_present") is True or row.get("selected_verifier_anchor_present") is True for row in rows)
        has_actual_log = any(((row.get("anti_cheat") or {}).get("actual_verifier_log_attached") is True) for row in rows)
        selected_test_geometry = any("inline" in role and "test" in role for role in roles)
        out.append(
            {
                "candidate_id": f"stage11743::rust_existing::{repo_family}::{abs(hash(root))}",
                "language_family": "rust",
                "repo_family": repo_family,
                "root_lineage_key": root,
                "admit_role": "partial_support_inventory",
                "readiness": "usable_for_evidence_role_support"
                if has_actual_log and has_selected
                else "needs_selected_test_materialization",
                "target_failure_family": "verifier_outcome_selected_inline_test_vs_nearby_inline_test",
                "row_count": len(rows),
                "has_actual_verifier_log": has_actual_log,
                "has_selected_verifier_anchor": has_selected,
                "has_same_module_selected_test_geometry": selected_test_geometry,
                "roles": roles[:12],
                "source_artifacts": sorted({rel(path) for path in RUST_SUPPORT_FILES if path.exists()}),
                "blockers": []
                if selected_test_geometry
                else ["does_not_yet_match_same_module_selected_test_vs_sibling_test_geometry"],
            }
        )
    return out


def rust_local_cargo_candidates() -> list[dict[str, Any]]:
    out = []
    for cargo in sorted(HELPFUL.rglob("Cargo.toml")) if HELPFUL.exists() else []:
        if ".git" in cargo.parts:
            continue
        repo = cargo.parent
        repo_rel = str(repo.relative_to(HELPFUL))
        role = "quarantine_strict_smoke_root" if repo_rel == "tokenizers/tokenizers" else "execution_candidate"
        rust_files = sorted([p for p in repo.rglob("*.rs") if ".git" not in p.parts])
        out.append(
            {
                "candidate_id": f"stage11743::rust_cargo::{repo_rel.replace('/', '__')}",
                "language_family": "rust",
                "repo_family": repo_rel,
                "repo_path": str(repo),
                "source_snapshot_id": git_head(repo),
                "admit_role": role,
                "readiness": "needs_cargo_test_probe" if role == "execution_candidate" else "quarantine",
                "target_failure_family": "verifier_outcome_selected_inline_test_vs_nearby_inline_test",
                "rust_file_count": len(rust_files),
                "sample_rust_files": [str(p.relative_to(repo)) for p in rust_files[:8]],
                "blockers": [] if role == "execution_candidate" else [STRICT_FORBIDDEN_ROOTS["tokenizers/tokenizers"]],
            }
        )
    return out


def main() -> None:
    request = load_json(REQUEST)
    candidates: list[dict[str, Any]] = []
    for repo in repo_dirs():
        py = candidate_python(repo)
        if py:
            candidates.append(py)
        cpp = candidate_cpp(repo)
        if cpp:
            candidates.append(cpp)
    candidates.extend(rust_local_cargo_candidates())
    candidates.extend(rust_existing_support())

    counts = Counter((row["language_family"], row["admit_role"], row["readiness"]) for row in candidates)
    by_language = defaultdict(int)
    for row in candidates:
        by_language[row["language_family"]] += 1
    readyish = [
        row
        for row in candidates
        if row.get("admit_role") in {"execution_candidate", "partial_support_inventory"}
        and not str(row.get("readiness", "")).startswith("quarantine")
    ]
    hard_ready = [
        row
        for row in candidates
        if row.get("readiness") in {"usable_for_evidence_role_support"}
        and not row.get("blockers")
    ]
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "source_heldout_failure_support_candidate_atlas_built",
        "passed": True,
        "request": rel(REQUEST),
        "candidate_count": len(candidates),
        "readyish_candidate_count": len(readyish),
        "hard_ready_candidate_count": len(hard_ready),
        "by_language": dict(sorted(by_language.items())),
        "counts": {str(key): value for key, value in sorted(counts.items())},
        "interpretation": [
            "Python has multiple local pytest-style execution candidates, but they need verifier execution and anti-leak rendering before admission.",
            "Rust local Cargo supply is thin; existing 114xx verifier-log-backed rows are useful but mostly partial for the specific selected-test-vs-sibling-test failure.",
            "C/C++ has source/build candidates, but most need focused build-verifier probes before they can support the abstain-attractor lane.",
            "Strict smoke roots are explicitly quarantined and must remain eval-only canaries.",
        ],
        "next_actions": [
            "Run Stage11744 Python pytest feasibility on the top execution candidates.",
            "Run a Rust selected-test geometry audit over the existing 114xx rows before using them for verifier_outcome support.",
            "Run C/C++ build feasibility on faiss or bitsandbytes before creating abstain counterfactual rows.",
        ],
        "claim_boundary": [
            "This is an atlas only; no new rows are admitted for training yet.",
            "Counts are supply candidates, not capability scale.",
        ],
        "outputs": {"summary": rel(SUMMARY), "candidates": rel(CANDIDATES)},
    }
    write_json(SUMMARY, artifact)
    write_jsonl(CANDIDATES, candidates)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "candidate_count": len(candidates),
                "by_language": artifact["by_language"],
                "readyish_candidate_count": len(readyish),
                "hard_ready_candidate_count": len(hard_ready),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
