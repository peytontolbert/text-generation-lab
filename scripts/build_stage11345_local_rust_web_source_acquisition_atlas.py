#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11345
NAME = "stage11345_local_rust_web_source_acquisition_atlas"
OUT = ART / NAME
SUMMARY = OUT / "local_rust_web_source_acquisition_atlas.json"
OUT_CANDIDATES = OUT / "local_rust_web_source_candidates.jsonl"
OUT_BLOCKED = OUT / "local_rust_web_source_blocked.jsonl"

CANARY_TRAIN = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_train_rows.jsonl"
CANARY_STRICT = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl"
CANARY_VALIDATION = ART / "stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl"
STAGE11344 = ART / "stage11344_rust_web_source_verifier_blocker_audit/rust_web_source_verifier_blocker_audit.json"

SCAN_BASES = [
    Path("/data/repositories"),
    Path("/data/code_assist"),
    Path("/data/Arguslocal"),
    Path("/data/workoutapp"),
    Path("/data/bestclinic"),
    Path("/data/gpu_hosting"),
    Path("/arxiv/repositories"),
]
MAX_REPOS = 80
MAX_FILES_PER_KIND = 30
MAX_DEPTH_FROM_BASE = 2
MAX_WALK_DIRS_PER_REPO = 40
RUST_SUFFIXES = {".rs"}
WEB_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".html", ".vue", ".svelte", ".css"}
TEST_HINTS = ("test", "tests", "spec", "__tests__", "fixture", "fixtures", "e2e")
SOURCE_SKIP_PARTS = {".git", "node_modules", "target", "dist", "build", ".venv", "venv", "__pycache__"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def repo_name(path: Path) -> str:
    return path.name.replace("__", "_").replace("-", "_").lower()


def repo_family_variants(value: str) -> set[str]:
    v = str(value or "").lower()
    return {v, v.replace("-", "_"), v.replace("_", "-")}


def collect_used_families() -> dict[str, set[str]]:
    used = {"train": set(), "validation": set(), "strict": set()}
    for split, path in [("train", CANARY_TRAIN), ("validation", CANARY_VALIDATION), ("strict", CANARY_STRICT)]:
        for row in read_jsonl(path):
            for key in ("repo_family", "repo_id"):
                value = row.get(key)
                if value:
                    used[split].update(repo_family_variants(str(value)))
            lineage = str(row.get("root_lineage_key") or "")
            if "::" in lineage:
                used[split].update(repo_family_variants(lineage.split("::", 1)[0]))
    return used


def is_under(base: Path, path: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def depth_from(base: Path, path: Path) -> int:
    try:
        return len(path.relative_to(base).parts)
    except ValueError:
        return 999


def discover_repo_roots() -> list[Path]:
    roots: set[Path] = set()
    markers = {"Cargo.toml", "package.json", "tsconfig.json", "vite.config.ts", "next.config.js"}
    for base in SCAN_BASES:
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            path = Path(dirpath)
            rel_depth = depth_from(base, path)
            if rel_depth > MAX_DEPTH_FROM_BASE + 1:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SOURCE_SKIP_PARTS and not d.startswith(".")]
            if ".git" in dirnames or markers.intersection(filenames):
                roots.add(path)
                if len(roots) >= MAX_REPOS:
                    return sorted(roots, key=lambda p: str(p))[:MAX_REPOS]
    return sorted(roots, key=lambda p: str(p))[:MAX_REPOS]


def safe_files(repo: Path, suffixes: set[str], limit: int = MAX_FILES_PER_KIND) -> list[Path]:
    out: list[Path] = []
    walked = 0
    try:
        for dirpath, dirnames, filenames in os.walk(repo):
            walked += 1
            if walked > MAX_WALK_DIRS_PER_REPO or len(out) >= limit:
                break
            dirnames[:] = [d for d in dirnames if d not in SOURCE_SKIP_PARTS and not d.startswith(".")]
            rel_dir = Path(dirpath).relative_to(repo)
            if any(part in SOURCE_SKIP_PARTS for part in rel_dir.parts):
                dirnames[:] = []
                continue
            for filename in filenames:
                if len(out) >= limit:
                    break
                path = Path(dirpath) / filename
                if path.suffix.lower() in suffixes:
                    out.append(path)
    except (OSError, PermissionError, ValueError):
        return out
    return out


def split_test_source(files: list[Path], repo: Path) -> tuple[list[str], list[str]]:
    tests: list[str] = []
    sources: list[str] = []
    for path in files:
        rel_path = str(path.relative_to(repo))
        lowered = rel_path.lower()
        if any(hint in lowered for hint in TEST_HINTS):
            tests.append(rel_path)
        else:
            sources.append(rel_path)
    return sources[:MAX_FILES_PER_KIND], tests[:MAX_FILES_PER_KIND]


def snippet(path: Path, max_lines: int = 18) -> dict[str, Any]:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except (OSError, UnicodeError):
        return {"path": str(path), "text": "", "sha256": None, "line_start": None, "line_end": None}
    anchors = [
        i for i, line in enumerate(lines)
        if any(tok in line.lower() for tok in ("test", "assert", "expect", "fn ", "function", "describe", "it(", "export", "class"))
    ]
    start = max(0, (anchors[0] if anchors else 0) - 2)
    part = lines[start:start + max_lines]
    text = "\n".join(part)
    return {
        "path": str(path),
        "line_start": start + 1 if part else None,
        "line_end": start + len(part) if part else None,
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest() if text else None,
        "text": text[:1800],
    }


def nearest_git_root(repo: Path) -> Path | None:
    current = repo
    for _ in range(8):
        if (current / ".git" / "HEAD").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def git_head(repo: Path) -> tuple[str | None, Path | None]:
    git_root = nearest_git_root(repo)
    if git_root is None:
        return None, None
    head = git_root / ".git" / "HEAD"
    try:
        value = head.read_text(errors="replace").strip()
        if value.startswith("ref:"):
            ref = value.split(None, 1)[1]
            ref_path = git_root / ".git" / ref
            if ref_path.exists():
                return ref_path.read_text(errors="replace").strip(), git_root
        return value, git_root
    except OSError:
        return None, git_root


def classify_repo(repo: Path) -> dict[str, Any]:
    rust_files = safe_files(repo, RUST_SUFFIXES)
    web_files = safe_files(repo, WEB_SUFFIXES)
    rust_sources, rust_tests = split_test_source(rust_files, repo)
    web_sources, web_tests = split_test_source(web_files, repo)
    has_rust = bool((repo / "Cargo.toml").exists() or rust_files)
    has_web = bool((repo / "package.json").exists() or (repo / "tsconfig.json").exists() or web_files)
    head, git_root = git_head(repo)
    return {
        "repo_path": str(repo),
        "repo_family": repo_name(repo),
        "git_head": head,
        "git_repo_root": str(git_root) if git_root else None,
        "git_repo_family": repo_name(git_root) if git_root else None,
        "has_rust": has_rust,
        "has_web": has_web,
        "rust_source_paths": rust_sources[:12],
        "rust_test_paths": rust_tests[:12],
        "web_source_paths": web_sources[:12],
        "web_test_paths": web_tests[:12],
        "rust_file_count_sampled": len(rust_files),
        "web_file_count_sampled": len(web_files),
    }


def build_candidate(row: dict[str, Any], language: str, used: dict[str, set[str]]) -> dict[str, Any]:
    repo = Path(row["repo_path"])
    if language == "rust":
        source_paths = row["rust_source_paths"]
        test_paths = row["rust_test_paths"]
    else:
        source_paths = row["web_source_paths"]
        test_paths = row["web_test_paths"]
    family_variants = repo_family_variants(row["repo_family"])
    if row.get("git_repo_family"):
        family_variants.update(repo_family_variants(row["git_repo_family"]))
    overlap = {split: sorted(family_variants & vals) for split, vals in used.items() if family_variants & vals}
    source_path = repo / source_paths[0] if source_paths else None
    test_path = repo / test_paths[0] if test_paths else None
    blockers: list[str] = []
    if not source_paths:
        blockers.append("missing_candidate_source_path")
    if not test_paths:
        blockers.append("missing_selected_test_or_verifier_path")
    if overlap.get("strict") or overlap.get("validation"):
        blockers.append("repo_family_overlaps_protected_eval")
    if overlap.get("train"):
        blockers.append("repo_family_already_in_train_support")
    if not row.get("git_head"):
        blockers.append("missing_git_head_or_locked_commit")
    candidate = {
        "candidate_id": f"stage11345::{language}::{row['repo_family']}::{hashlib.sha256(str(repo).encode()).hexdigest()[:10]}",
        "language_family": language,
        "repo_family": row["repo_family"],
        "repo_path": row["repo_path"],
        "git_head": row.get("git_head"),
        "git_repo_root": row.get("git_repo_root"),
        "git_repo_family": row.get("git_repo_family"),
        "candidate_change_surface_paths": source_paths[:5],
        "verifier_and_test_constraint_paths": test_paths[:5],
        "protected_overlap": overlap,
        "blockers": blockers,
        "admissible_for_materialization_review": not blockers or blockers == ["repo_family_already_in_train_support"],
        "promotable_without_review": False,
        "snippets": {
            "candidate_change_surface": snippet(source_path) if source_path else None,
            "verifier_and_test_constraint": snippet(test_path) if test_path else None,
        },
        "required_next_review": [
            "confirm task root and bug/fix semantics",
            "select symptom_or_call_path evidence distinct from source and verifier",
            "run or recover selected verifier output",
            "assign root split before row projection",
            "anti-cheat review for role aliases and target leaks",
        ],
    }
    return candidate


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    used = collect_used_families()
    repo_roots = discover_repo_roots()
    repo_cards = [classify_repo(repo) for repo in repo_roots]
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for card in repo_cards:
        if card["has_rust"]:
            cand = build_candidate(card, "rust", used)
            (candidates if cand["admissible_for_materialization_review"] else blocked).append(cand)
        if card["has_web"]:
            cand = build_candidate(card, "web_js_ts_html", used)
            (candidates if cand["admissible_for_materialization_review"] else blocked).append(cand)

    write_jsonl(OUT_CANDIDATES, candidates)
    write_jsonl(OUT_BLOCKED, blocked)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "local_rust_web_source_acquisition_atlas_ready",
        "counts": {
            "repo_roots_scanned": len(repo_roots),
            "candidate_rows": len(candidates),
            "blocked_rows": len(blocked),
            "candidates_by_language": dict(sorted(Counter(c["language_family"] for c in candidates).items())),
            "blocked_by_language": dict(sorted(Counter(c["language_family"] for c in blocked).items())),
            "candidate_repo_families": len({c["repo_family"] for c in candidates}),
            "blocked_repo_families": len({c["repo_family"] for c in blocked}),
            "blocker_counts": dict(sorted(Counter(b for c in blocked for b in c.get("blockers", [])).items())),
        },
        "quality_gate": {
            "training_rows_emitted": 0,
            "why": "This stage only identifies local source/test candidates. It does not invent gold labels, verifier transitions, or maintainer roots.",
            "next_required_stage": "materialize reviewed roots from candidates with distinct source/verifier/symptom evidence and recovered verifier output.",
        },
        "used_family_counts": {k: len(v) for k, v in used.items()},
        "source_artifacts": {
            "stage11344_summary": rel(STAGE11344),
            "canary_train": rel(CANARY_TRAIN),
            "canary_validation": rel(CANARY_VALIDATION),
            "canary_strict": rel(CANARY_STRICT),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "candidates": rel(OUT_CANDIDATES),
            "blocked": rel(OUT_BLOCKED),
        },
        "recommended_next_action": "Review candidate rows with no protected eval overlap, then build source+verifier maintainer roots only where a real task/verifier transition can be recovered.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
