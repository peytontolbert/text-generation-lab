#!/usr/bin/env python3
"""Scan raw local repositories for fresh sealed Rust/Web/C++ gap-fill roots."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12108
NAME = "stage12108_fresh_sealed_gap_fill_atlas"
OUT = ART / NAME
SUMMARY = OUT / "fresh_sealed_gap_fill_atlas.json"
MIRROR = SUM / f"{NAME}.json"
CANDIDATES = OUT / "fresh_sealed_gap_fill_candidates.jsonl"
REJECTED = OUT / "fresh_sealed_gap_fill_rejected.jsonl"

STAGE12107 = SUM / "stage12107_fresh_sealed_transition_root_materializer.json"

SCAN_BASES = [
    Path("/data/repositories"),
    Path("/data/agentkernel_other_repos"),
    Path("/data/parametergolf/helpful_repos"),
    ROOT / "helpful_repos",
]

PRUNE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "target",
    "build",
    "dist",
    ".next",
}

MANIFEST_LANG = {
    "Cargo.toml": "rust",
    "package.json": "web_js_ts_html",
    "CMakeLists.txt": "c_cpp",
    "Makefile": "c_cpp",
    "pyproject.toml": "python",
    "setup.py": "python",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def canonical(value: Any) -> str:
    text = str(value or "").lower().replace("\\", "/").strip("/")
    for prefix in (
        "/data/repositories/",
        "/data/parametergolf/helpful_repos/",
        "/data/agentkernel_other_repos/",
        "/data/agentkernel-seq2seq-text-lab/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    if "::" in text:
        text = text.split("::", 1)[0]
    parts = [part for part in text.split("/") if part]
    head = parts[0] if parts else text
    return re.sub(r"[^a-z0-9]+", "", head)


def task_type(row: dict[str, Any]) -> str:
    value = row.get("task_type")
    if value:
        return str(value)
    rid = str(row.get("row_id") or "")
    for suffix in ("next_action", "candidate_selection", "verifier_transition", "continue_or_stop"):
        if rid.endswith("::" + suffix) or ("::" + suffix + "::") in rid:
            return "transition_" + suffix
    return "unknown"


def gather_excluded_families() -> set[str]:
    excluded: set[str] = set()
    patterns = [
        "stage11897_transition_record_projection_rows/**/*.jsonl",
        "stage11943*/**/*.jsonl",
        "stage120*/**/*.jsonl",
        "stage12105_sealed_transition_candidate_atlas/**/*.jsonl",
        "stage12107_fresh_sealed_transition_root_materializer/**/*.jsonl",
    ]
    for pattern in patterns:
        for path in ART.glob(pattern):
            for row in read_jsonl(path):
                if task_type(row).startswith("transition_") or "transition" in str(row.get("row_id") or "") or row.get("stage12107_work_item"):
                    for key in ("repo_family", "repo_id", "root_id", "root_lineage_key", "source_root_id", "source_bundle_id", "source_path"):
                        if row.get(key):
                            excluded.add(canonical(row.get(key)))
    return excluded


def find_test_markers(path: Path) -> list[str]:
    markers = []
    for name in ("tests", "test", "__tests__", "spec", "crates"):
        if (path / name).exists():
            markers.append(name)
    return markers


def scan_manifest_roots() -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for base in SCAN_BASES:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            path = Path(root)
            parts = set(path.parts)
            if parts & PRUNE_DIRS:
                dirs[:] = []
                continue
            depth = len(path.relative_to(base).parts) if path != base else 0
            if depth > 5:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]
            manifests = sorted(set(files) & set(MANIFEST_LANG))
            if not manifests:
                continue
            real = str(path.resolve())
            if real in seen:
                continue
            seen.add(real)
            langs = sorted({MANIFEST_LANG[m] for m in manifests})
            lane = "mixed_build_config_dependency" if len(langs) > 1 else langs[0]
            rows.append({
                "source_path": real,
                "scan_base": str(base),
                "repo_family": canonical(str(path.relative_to(base)) if path != base else path.name),
                "language_guess": langs,
                "lane": lane,
                "manifests": manifests,
                "test_markers": find_test_markers(path),
                "path_depth_from_base": depth,
            })
    return rows


def command_plan(lane: str, manifests: list[str]) -> dict[str, list[str]]:
    if "Cargo.toml" in manifests or lane == "rust":
        return {"build_probe": ["cargo", "check", "--locked"], "test_probe": ["cargo", "test", "--locked", "--no-fail-fast"]}
    if "package.json" in manifests or lane == "web_js_ts_html":
        return {"build_probe": ["npm", "test", "--", "--runInBand"], "test_probe": ["npm", "test"]}
    if "CMakeLists.txt" in manifests:
        return {"build_probe": ["cmake", "-S", ".", "-B", "/data/tmp/stage12108_cmake_build"], "test_probe": ["ctest", "--test-dir", "/data/tmp/stage12108_cmake_build", "--output-on-failure"]}
    if "Makefile" in manifests:
        return {"build_probe": ["make", "-n"], "test_probe": ["make", "test"]}
    return {"build_probe": ["python", "-m", "py_compile", "."], "test_probe": ["python", "-m", "pytest", "-q"]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prior = read_json(STAGE12107)
    needed = {k: int(v) for k, v in prior["remaining_lane_quota"].items() if int(v) > 0}
    excluded = gather_excluded_families()

    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    lane_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()

    candidates = scan_manifest_roots()
    # Prefer roots with test markers and shallow package roots.
    candidates.sort(key=lambda r: (
        0 if r["test_markers"] else 1,
        r["path_depth_from_base"],
        r["repo_family"],
        r["source_path"],
    ))

    for row in candidates:
        reasons = []
        lane = row["lane"]
        repo = row["repo_family"]
        if lane not in needed:
            reasons.append("lane_not_needed_for_stage12107_gap")
        if repo in excluded:
            reasons.append("repo_family_overlaps_prior_transition_or_selected_work")
        if not row["test_markers"]:
            reasons.append("missing_test_marker")
        if repo_counts[repo] >= 4:
            reasons.append("repo_family_cap_reached")
        if lane_counts[lane] >= needed.get(lane, 0):
            reasons.append("lane_gap_already_filled")
        if reasons:
            rejected.append({**row, "reasons": reasons})
            for reason in reasons:
                rejection_counts[reason] += 1
            continue
        item = {
            **row,
            "stage12108_gap_fill_candidate": True,
            "root_id": "stage12108::" + re.sub(r"[^a-zA-Z0-9]+", "_", row["source_path"]).strip("_")[-96:],
            "root_lineage_key": "stage12108::" + re.sub(r"[^a-zA-Z0-9]+", "_", row["source_path"]).strip("_")[-96:],
            "sealed_split_role": "sealed_confirm_only",
            "train_support_only": False,
            "strict_eval_eligible": True,
            "source_heldout_admissible": True,
            "do_not_train": True,
            "command_plan": command_plan(lane, row["manifests"]),
            "required_projection_rows": [
                "transition_next_action",
                "transition_candidate_selection",
                "transition_verifier_transition",
                "transition_continue_or_stop",
            ],
            "anti_cheat_contract": {
                "deterministic_option_shuffle": True,
                "singleton_options": False,
                "target_label_not_visible_before_options": True,
                "target_value_not_visible_before_options": True,
                "semantic_candidate_identity_eval": True,
                "root_lineage_disjoint_from_prior_transition_stages": True,
            },
        }
        selected.append(item)
        lane_counts[lane] += 1
        repo_counts[repo] += 1

    remaining = {lane: max(0, needed[lane] - lane_counts.get(lane, 0)) for lane in needed}
    ready_gap_fill = all(v == 0 for v in remaining.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "gap_fill_candidates_ready" if ready_gap_fill else "gap_fill_partial_rust_or_web_source_shortage",
        "needed_from_stage12107": needed,
        "selected_candidates": len(selected),
        "selected_by_lane": dict(sorted(lane_counts.items())),
        "remaining_after_gap_fill": remaining,
        "raw_manifest_roots_scanned": len(candidates),
        "rejected_candidates": len(rejected),
        "rejection_counts": dict(rejection_counts.most_common()),
        "excluded_family_count": len(excluded),
        "repo_family_counts_top20": dict(repo_counts.most_common(20)),
        "next_stage_recommendation": {
            "stage": "stage12109_sealed_transition_probe_execution_plan",
            "action": "Merge Stage12107 work items with Stage12108 gap-fill candidates if the remaining gap is zero; otherwise acquire fresh Rust/Web roots outside prior transition families.",
            "remaining_gap": remaining,
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "candidates": rel(CANDIDATES),
            "rejected": rel(REJECTED),
        },
        "source_artifacts": {
            "stage12107_materializer": rel(STAGE12107),
        },
    }
    write_jsonl(CANDIDATES, selected)
    write_jsonl(REJECTED, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "selected_by_lane": summary["selected_by_lane"],
        "remaining_after_gap_fill": remaining,
        "top_rejections": dict(rejection_counts.most_common(8)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
