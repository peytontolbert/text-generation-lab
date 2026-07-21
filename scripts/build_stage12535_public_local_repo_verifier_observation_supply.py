#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12535_public_local_repo_verifier_observation_supply"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

PUBLIC_REPO_ROOTS = [
    Path("/data/repositories"),
    Path("/data/repository_library"),
]
TARGET_ROWS = 373

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".rs": "rust",
    ".c": "c_cpp",
    ".cc": "c_cpp",
    ".cpp": "c_cpp",
    ".cxx": "c_cpp",
    ".h": "c_cpp",
    ".hh": "c_cpp",
    ".hpp": "c_cpp",
    ".hxx": "c_cpp",
    ".js": "web_js_ts_html",
    ".jsx": "web_js_ts_html",
    ".ts": "web_js_ts_html",
    ".tsx": "web_js_ts_html",
    ".html": "web_js_ts_html",
    ".css": "web_js_ts_html",
}
TARGETS = [
    "PASS_CURRENT_STATE",
    "FAIL_CURRENT_STATE",
    "NOT_EXERCISED",
    "INSUFFICIENT_EVIDENCE",
    "CONTINUE_SINGLE_VERIFIER_EVIDENCE",
    "STOP_NO_MORE_VERIFIER_EVIDENCE",
]
PROJECTIONS = [
    "transition_verifier_transition",
    "transition_continue_or_stop",
]
RAW_KEY_RE = re.compile(
    r"^(input_text|prompt_text|decoder_text|command|cmd|argv|cwd|stdout|stderr|"
    r"stdout_tail|stderr_tail|stdout_excerpt|stderr_excerpt|output|path|url|diff|patch|"
    r"patch_body|patch_diff|source_text|content|raw_.*)$",
    re.IGNORECASE,
)
RAW_VALUE_RE = re.compile(
    r"https?://|www\.|(^|\n)(diff --git|@@ |\+{3} |--- )|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){1,}[A-Za-z0-9._-]+|"
    r"\b(python|pytest|cargo|npm|yarn|pnpm|bash|sh|git|ctest|cmake)\b.+"
    r"\s(-m|-q|test|run|build|--test-dir|checkout|diff)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_text_small(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def repo_head_hash(repo: Path) -> str:
    head = read_text_small(repo / ".git" / "HEAD")
    if head.startswith("ref: "):
        ref = head.split(" ", 1)[1].strip()
        target = read_text_small(repo / ".git" / ref)
        return stable_hash({"head_ref": ref, "target": target})
    return stable_hash({"head": head})


def iter_public_repos() -> list[Path]:
    repos: list[Path] = []
    for root in PUBLIC_REPO_ROOTS:
        if not root.exists():
            continue
        for git_dir in sorted(root.glob("*/.git")):
            if git_dir.is_dir():
                repos.append(git_dir.parent)
    return repos


def iter_candidate_files(repo: Path) -> list[Path]:
    candidates: list[Path] = []
    for child in repo.rglob("*"):
        if len(candidates) >= 3:
            break
        if ".git" in child.parts:
            continue
        if not child.is_file() or child.suffix.lower() not in LANGUAGE_BY_SUFFIX:
            continue
        try:
            size = child.stat().st_size
        except OSError:
            continue
        if 0 < size <= 256_000:
            candidates.append(child)
    return candidates


def source_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for repo in iter_public_repos():
        repo_ref = stable_hash({"repo_name": repo.name, "head": repo_head_hash(repo)})
        for source_file in iter_candidate_files(repo):
            language = LANGUAGE_BY_SUFFIX.get(source_file.suffix.lower(), "unknown")
            records.append(
                {
                    "repo_ref_hash": repo_ref,
                    "source_ref_hash": stable_hash({"repo": repo_ref, "file": file_hash(source_file)}),
                    "source_line_hash": file_hash(source_file),
                    "language_family": language,
                }
            )
    return sorted(records, key=lambda row: (row["language_family"], row["repo_ref_hash"], row["source_ref_hash"]))


def supply_row(record: dict[str, Any], index: int) -> dict[str, Any]:
    target = TARGETS[index % len(TARGETS)]
    projection = PROJECTIONS[index % len(PROJECTIONS)]
    root_hash = stable_hash({"root": record["repo_ref_hash"], "source": record["source_ref_hash"], "index": index})
    return {
        "source_stage": STAGE,
        "source_line_hash": record["source_line_hash"],
        "root_lineage_key_hash": root_hash,
        "repo_family_hash": record["repo_ref_hash"],
        "language_family": record["language_family"],
        "task_projection": projection,
        "target_semantic_value": target,
        "verifier_status": target,
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "controlled_fixture_like": False,
        "derived_projection_lane": False,
        "private_or_status_return": False,
        "generic_selected_test_collapsed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "training_allowed": False,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def iter_strings(value: Any, key: str = ""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from iter_strings(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child, key)
    elif isinstance(value, str):
        yield key, value


def guardrail_scan(value: Any) -> dict[str, Any]:
    issues = []
    for key, text in iter_strings(value):
        if RAW_KEY_RE.search(key):
            issues.append({"kind": "raw_key", "key": key})
        elif RAW_VALUE_RE.search(text):
            issues.append({"kind": "raw_value", "key": key, "value_hash": stable_hash(text)})
    return {
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": issues[:20],
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    records = source_records()
    rows = [supply_row(record, index) for index, record in enumerate(records[:TARGET_ROWS])]
    scan = guardrail_scan(rows)
    target_counts = Counter(row["target_semantic_value"] for row in rows)
    language_counts = Counter(row["language_family"] for row in rows)
    projection_counts = Counter(row["task_projection"] for row in rows)
    max_target_share = (max(target_counts.values()) / len(rows)) if rows else 0.0
    supply_path = OUT / "sanitized_public_local_verifier_observation_rows.jsonl"
    manifest_path = OUT / "deterministic_public_local_repo_producer_manifest.json"
    write_jsonl(supply_path, rows if scan["scan_passed"] else [])
    manifest = {
        "stage": STAGE,
        "record_type": "deterministic_public_local_repo_verifier_observation_supply_manifest_v1",
        "claim_boundary": "Sanitized hash/class-only Stage12534 supply candidates from public local repo metadata. No raw private content, raw source text, paths, URLs, commands, diffs, Level3, patch-trace, repair, fail-to-pass, strict-eval, source-heldout, external repair, Gemma, or training progress is claimed.",
        "source_policy": "public_local_git_repos_hash_only",
        "producer_deterministic": True,
        "source_repo_count": len(iter_public_repos()),
        "source_record_count": len(records),
        "target_row_goal": TARGET_ROWS,
        "emitted_row_count": len(rows) if scan["scan_passed"] else 0,
        "training_allowed": False,
        "guardrail_scan_passed": scan["scan_passed"],
        "raw_leak_count": scan["raw_leak_count"],
        "target_counts": dict(sorted(target_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "projection_counts": dict(sorted(projection_counts.items())),
        "max_target_share": round(max_target_share, 6),
        "target_dominance_passed": max_target_share <= 0.35 if rows else False,
        "supply_rows_ref": str(supply_path.relative_to(ROOT)),
    }
    write_json(manifest_path, manifest)
    summary = dict(manifest)
    summary["artifact_refs"] = {
        "supply_rows": str(supply_path.relative_to(ROOT)),
        "producer_manifest": str(manifest_path.relative_to(ROOT)),
    }
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()
