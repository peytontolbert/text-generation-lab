#!/usr/bin/env python3
"""Build a compact read-only index for local /arxiv software corpora.

This script does not modify /arxiv. It summarizes available datasets and
repositories into small JSON/JSONL cards under runs/local/artifacts so the
curriculum compiler can decide which sources are suitable for the rebuilt
100M software-maintainer training path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LANG_EXTENSIONS = {
    "python": {".py", ".pyi", ".ipynb"},
    "rust": {".rs"},
    "c_family": {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"},
    "web_js_ts_html": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css"},
    "java_jvm": {".java", ".kt", ".kts", ".scala", ".groovy"},
    "go": {".go"},
    "shell": {".sh", ".bash", ".zsh", ".fish"},
    "docs": {".md", ".rst", ".txt"},
    "config": {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".xml"},
}

BUILD_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "Cargo.toml",
    "Cargo.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "CMakeLists.txt",
    "Makefile",
    "meson.build",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}

DATASET_SUFFIXES = {
    ".json",
    ".jsonl",
    ".parquet",
    ".csv",
    ".tsv",
    ".arrow",
    ".txt",
    ".md",
    ".gz",
    ".zip",
    ".tar",
    ".zst",
}

INTERNAL_TOKEN_PAT = re.compile(
    r"(<MTC|</MTC|POLICY_|AUTHORITY_|GEMMA_|RUNTIME_|HIDDEN_|INTERNAL_)",
    re.IGNORECASE,
)
TEST_PATH_PAT = re.compile(r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)(test_|.*_test\.|.*\.spec\.)", re.IGNORECASE)
DOC_PATH_PAT = re.compile(r"(^|/)(docs?|examples?|tutorials?)(/|$)|readme|changelog|contributing", re.IGNORECASE)


@dataclass
class RepoSummary:
    repo_id: str
    path: str
    scanned_files: int
    scan_truncated: bool
    total_bytes_scanned: int
    language_file_counts: dict[str, int]
    extension_counts: dict[str, int]
    build_files: list[str]
    readme_files: list[str]
    test_files: int
    doc_files: int
    likely_primary_languages: list[str]
    maintainer_usefulness_score: int
    recommended_curriculum_uses: list[str]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def classify_language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for lang, suffixes in LANG_EXTENSIONS.items():
        if suffix in suffixes:
            return lang
    return None


def recommend_repo_uses(summary: RepoSummary) -> list[str]:
    uses: set[str] = set()
    langs = set(summary.likely_primary_languages)
    if summary.build_files:
        uses.add("repo_state_graph_v1")
        uses.add("intent_to_build_strategy")
    if summary.test_files:
        uses.add("symbol_binding")
        uses.add("edit_localization")
        uses.add("verifier_repair")
    if langs & {"python", "rust", "c_family", "web_js_ts_html", "java_jvm", "go"}:
        uses.add("patch_operator")
        uses.add("bounded_decoder_arguments")
    if summary.doc_files or summary.readme_files:
        uses.add("repo_capability_catalog")
        uses.add("maintainer_qa")
    return sorted(uses)


def repo_score(
    language_counts: Counter[str],
    build_files: list[str],
    test_files: int,
    doc_files: int,
    scanned_files: int,
) -> int:
    score = 0
    score += min(30, 3 * len([c for c in language_counts.values() if c > 0]))
    score += min(25, 5 * len(build_files))
    score += min(25, test_files // 5)
    score += min(10, doc_files // 5)
    score += min(10, scanned_files // 100)
    return score


def scan_repository(repo_dir: Path, repos_root: Path, max_files: int) -> RepoSummary:
    language_counts: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()
    build_files: list[str] = []
    readme_files: list[str] = []
    test_files = 0
    doc_files = 0
    scanned_files = 0
    total_bytes = 0
    truncated = False

    for root, dirs, files in os.walk(repo_dir, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", "target", "dist", "build"}
        ]
        for name in files:
            if scanned_files >= max_files:
                truncated = True
                break
            path = Path(root) / name
            rel_path = rel(path, repo_dir)
            scanned_files += 1
            suffix = path.suffix.lower()
            ext_counts[suffix or "<none>"] += 1
            lang = classify_language(path)
            if lang:
                language_counts[lang] += 1
            if name in BUILD_FILES:
                build_files.append(rel_path)
            lower_name = name.lower()
            if lower_name.startswith("readme"):
                readme_files.append(rel_path)
            if TEST_PATH_PAT.search(rel_path):
                test_files += 1
            if DOC_PATH_PAT.search(rel_path):
                doc_files += 1
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
        if truncated:
            break

    primary = [lang for lang, _count in language_counts.most_common(4)]
    summary = RepoSummary(
        repo_id=repo_dir.name,
        path=str(repo_dir),
        scanned_files=scanned_files,
        scan_truncated=truncated,
        total_bytes_scanned=total_bytes,
        language_file_counts=dict(language_counts),
        extension_counts=dict(ext_counts.most_common(30)),
        build_files=sorted(build_files)[:50],
        readme_files=sorted(readme_files)[:20],
        test_files=test_files,
        doc_files=doc_files,
        likely_primary_languages=primary,
        maintainer_usefulness_score=repo_score(language_counts, build_files, test_files, doc_files, scanned_files),
        recommended_curriculum_uses=[],
    )
    summary.recommended_curriculum_uses = recommend_repo_uses(summary)
    return summary


def scan_repositories(root: Path, max_repos: int, max_files_per_repo: int) -> tuple[list[RepoSummary], dict[str, Any]]:
    summaries: list[RepoSummary] = []
    if not root.exists():
        return summaries, {"exists": False, "root": str(root)}

    repo_dirs = sorted([p for p in root.iterdir() if p.is_dir() and not p.is_symlink()], key=lambda p: p.name)
    for repo_dir in repo_dirs[:max_repos]:
        summaries.append(scan_repository(repo_dir, root, max_files_per_repo))

    lang_totals: Counter[str] = Counter()
    build_file_totals: Counter[str] = Counter()
    use_totals: Counter[str] = Counter()
    truncated = 0
    for summary in summaries:
        lang_totals.update(summary.language_file_counts)
        for build in summary.build_files:
            build_file_totals[Path(build).name] += 1
        use_totals.update(summary.recommended_curriculum_uses)
        if summary.scan_truncated:
            truncated += 1

    aggregate = {
        "exists": True,
        "root": str(root),
        "repo_dirs_seen": len(repo_dirs),
        "repo_dirs_indexed": len(summaries),
        "max_repos": max_repos,
        "max_files_per_repo": max_files_per_repo,
        "truncated_repo_scans": truncated,
        "language_file_counts": dict(lang_totals),
        "build_file_counts": dict(build_file_totals.most_common()),
        "recommended_curriculum_use_counts": dict(use_totals),
        "top_repositories_by_usefulness": [
            {
                "repo_id": s.repo_id,
                "score": s.maintainer_usefulness_score,
                "languages": s.likely_primary_languages,
                "uses": s.recommended_curriculum_uses,
                "build_files": s.build_files[:8],
                "test_files": s.test_files,
            }
            for s in sorted(summaries, key=lambda item: item.maintainer_usefulness_score, reverse=True)[:50]
        ],
    }
    return summaries, aggregate


def scan_datasets(root: Path, max_files: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows, {"exists": False, "root": str(root)}

    suffix_counts: Counter[str] = Counter()
    top_dir_counts: Counter[str] = Counter()
    total_size = 0
    scanned = 0
    skipped_after_cap = False
    internal_name_hits = 0
    software_name_hits = 0
    likely_software_terms = re.compile(r"(code|repo|patch|bug|fix|swe|software|python|rust|github|commit|test)", re.IGNORECASE)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        suffix = path.suffix.lower()
        if suffix not in DATASET_SUFFIXES:
            continue
        if scanned >= max_files:
            skipped_after_cap = True
            break
        scanned += 1
        relative = rel(path, root)
        parts = relative.split(os.sep)
        top_dir = parts[0] if len(parts) > 1 else "<root>"
        top_dir_counts[top_dir] += 1
        suffix_counts[suffix] += 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        total_size += size
        internal_name = bool(INTERNAL_TOKEN_PAT.search(relative))
        software_name = bool(likely_software_terms.search(relative))
        internal_name_hits += int(internal_name)
        software_name_hits += int(software_name)
        rows.append(
            {
                "path": str(path),
                "relative_path": relative,
                "top_dir": top_dir,
                "suffix": suffix,
                "size_bytes": size,
                "name_has_internal_token_marker": internal_name,
                "name_suggests_software_maintenance": software_name,
                "recommended_initial_route": "candidate_software_dataset" if software_name else "inventory_only",
            }
        )

    aggregate = {
        "exists": True,
        "root": str(root),
        "files_indexed": scanned,
        "max_files": max_files,
        "scan_truncated": skipped_after_cap,
        "total_size_bytes_indexed": total_size,
        "suffix_counts": dict(suffix_counts),
        "top_dir_counts": dict(top_dir_counts.most_common(100)),
        "name_internal_marker_hits": internal_name_hits,
        "name_software_maintenance_hits": software_name_hits,
        "top_candidate_datasets": sorted(
            [row for row in rows if row["name_suggests_software_maintenance"]],
            key=lambda r: r["size_bytes"],
            reverse=True,
        )[:100],
    }
    return rows, aggregate


def build_candidate_training_sources(
    dataset_rows: list[dict[str, Any]], repo_summaries: list[RepoSummary]
) -> dict[str, Any]:
    repo_candidates = [
        {
            "repo_id": s.repo_id,
            "path": s.path,
            "score": s.maintainer_usefulness_score,
            "languages": s.likely_primary_languages,
            "uses": s.recommended_curriculum_uses,
            "build_files": s.build_files[:10],
            "test_files": s.test_files,
            "doc_files": s.doc_files,
            "authority": "closed_read_only_source_candidate",
        }
        for s in sorted(repo_summaries, key=lambda item: item.maintainer_usefulness_score, reverse=True)
        if s.maintainer_usefulness_score > 0
    ][:200]
    dataset_candidates = [
        {
            "path": row["path"],
            "suffix": row["suffix"],
            "size_bytes": row["size_bytes"],
            "route": row["recommended_initial_route"],
            "authority": "closed_inventory_only_until_schema_audit",
        }
        for row in sorted(dataset_rows, key=lambda r: (r["name_suggests_software_maintenance"], r["size_bytes"]), reverse=True)
        if row["name_suggests_software_maintenance"]
    ][:200]
    return {
        "repositories": repo_candidates,
        "datasets": dataset_candidates,
        "recommended_next_manifests": [
            "repo_capability_catalog",
            "repo_state_graph_v1",
            "intent_to_build_strategy",
            "symbol_binding",
            "edit_localization",
            "patch_operator",
            "verifier_repair",
            "bounded_decoder_arguments",
            "bounded_decoder_ce",
            "denoise_repair",
        ],
        "authority": {
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "source_emission_authorized": False,
            "body_emission_authorized": False,
            "gemma_execution_authorized_next": False,
            "harness_execution_authorized_next": False,
            "scoring_authorized_next": False,
            "controller_complete_merge_authorized_next": False,
            "promotion_ready": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets-root", default="/arxiv/datasets")
    parser.add_argument("--repositories-root", default="/arxiv/repositories")
    parser.add_argument("--output-dir", default="runs/local/artifacts/stage8600_arxiv_corpus_index")
    parser.add_argument("--max-dataset-files", type=int, default=5000)
    parser.add_argument("--max-repos", type=int, default=500)
    parser.add_argument("--max-files-per-repo", type=int, default=20000)
    args = parser.parse_args()

    datasets_root = Path(args.datasets_root)
    repos_root = Path(args.repositories_root)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dataset_rows, dataset_inventory = scan_datasets(datasets_root, args.max_dataset_files)
    repo_summaries, repo_inventory = scan_repositories(repos_root, args.max_repos, args.max_files_per_repo)
    training_sources = build_candidate_training_sources(dataset_rows, repo_summaries)

    write_json(out / "dataset_inventory.json", dataset_inventory)
    write_jsonl(out / "dataset_files.jsonl", dataset_rows)
    write_json(out / "repository_inventory.json", repo_inventory)
    write_jsonl(out / "repository_summaries.jsonl", [asdict(s) for s in repo_summaries])
    write_json(out / "candidate_training_sources.json", training_sources)

    compact = {
        "datasets_root": str(datasets_root),
        "repositories_root": str(repos_root),
        "dataset_files_indexed": dataset_inventory.get("files_indexed", 0),
        "repo_dirs_indexed": repo_inventory.get("repo_dirs_indexed", 0),
        "repo_dirs_seen": repo_inventory.get("repo_dirs_seen", 0),
        "top_languages": repo_inventory.get("language_file_counts", {}),
        "recommended_curriculum_use_counts": repo_inventory.get("recommended_curriculum_use_counts", {}),
        "artifact_dir": str(out),
    }
    write_json(out / "compact_summary.json", compact)
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
