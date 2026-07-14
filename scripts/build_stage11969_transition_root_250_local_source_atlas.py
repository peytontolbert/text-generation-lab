#!/usr/bin/env python3
"""Build a local source atlas for fresh Transition-Root-250 materialization."""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11969
NAME = "stage11969_transition_root_250_local_source_atlas"
OUT = ART / NAME
SUMMARY = OUT / "transition_root_250_local_source_atlas.json"
QUEUE = OUT / "transition_root_250_local_source_queue.jsonl"
BASE_RECORDS = ART / "stage11955_transition_5k_v1_multisource_package/verified_transition_records_5k_v1.jsonl"
CONTRACT = ART / "stage11967_transition_root_250_supply_contract/transition_root_250_supply_contract.json"
MINER = ART / "stage11968_transition_root_250_candidate_miner/transition_root_250_candidate_miner.json"

SCAN_BASES = [
    Path("/data/repositories"),
    Path("/data/agentkernel_other_repos"),
    Path("/data/parametergolf/helpful_repos"),
    ROOT / "helpful_repos",
    ROOT,
]

MANIFESTS = {"Cargo.toml", "pyproject.toml", "setup.py", "package.json", "CMakeLists.txt", "Makefile"}
TEST_DIRS = {"tests", "test", "__tests__", "spec", "crates"}
PRUNE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "target",
    "build",
    "dist",
    "runs",
}
LANG_DEFICITS = {"python": 37, "c_cpp": 34, "rust": 23}
STATUS_DEFICITS = {
    "FAIL_TO_PASS": 30,
    "PASS_CURRENT_BUILD": 34,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def nested(d: dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def record_root(record: dict[str, Any]) -> str:
    return str(
        record.get("root_id")
        or record.get("root_lineage_key")
        or nested(record, "task_intent", "root_id")
        or record.get("source_lineage_ref")
        or ""
    )


def base_family_keys() -> set[str]:
    keys: set[str] = set()
    for record in read_jsonl(BASE_RECORDS):
        rid = record_root(record)
        if rid:
            keys.update(normalize_family_keys(rid))
        repo = str(record.get("repo_id") or nested(record, "task_intent", "repo_id") or "")
        if repo:
            keys.update(normalize_family_keys(repo))
    return keys


def canonical_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def normalize_family_keys(value: str) -> set[str]:
    primary = normalize_family_key(value)
    keys = {primary, canonical_key(primary)}
    text = value.lower().replace("\\", "/").strip("/")
    if "::" in text:
        parts = [part for part in text.split("::") if part]
        for part in parts[1:3]:
            keys.add(part)
            keys.add(canonical_key(part))
    return {key for key in keys if key}


def normalize_family_key(value: str) -> str:
    text = value.lower().replace("\\", "/")
    for prefix in ("/data/repositories/", "/data/parametergolf/helpful_repos/", "/data/agentkernel_other_repos/"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    text = text.strip("/")
    if "::" in text:
        text = text.split("::", 1)[0]
    parts = [p for p in text.split("/") if p]
    if not parts:
        return text
    if parts[0] in {"stage11955", "stage11958", "root", "repo"} and len(parts) > 1:
        return parts[1]
    if parts[0] == "candle" and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def language_guess(manifests: set[str], files: set[str], dirs: set[str]) -> list[str]:
    langs: list[str] = []
    if "Cargo.toml" in manifests:
        langs.append("rust")
    if {"pyproject.toml", "setup.py"} & manifests:
        langs.append("python")
    if "package.json" in manifests:
        langs.append("web_js_ts_html")
    if {"CMakeLists.txt", "Makefile"} & manifests:
        langs.append("c_cpp")
    if not langs:
        if any(name.endswith(".rs") for name in files):
            langs.append("rust")
        if any(name.endswith(".py") for name in files):
            langs.append("python")
        if any(name.endswith((".cc", ".cpp", ".c", ".h", ".hpp")) for name in files):
            langs.append("c_cpp")
        if any(name.endswith((".ts", ".tsx", ".js", ".jsx", ".html")) for name in files):
            langs.append("web_js_ts_html")
    return langs or ["unknown"]


def likely_status_lanes(manifests: set[str], test_markers: set[str], langs: list[str]) -> list[str]:
    lanes: set[str] = set()
    if test_markers:
        lanes.add("PASS_TO_PASS")
        lanes.add("NOT_EXERCISED")
    if {"Cargo.toml", "CMakeLists.txt", "Makefile", "pyproject.toml", "package.json"} & manifests:
        lanes.add("PASS_CURRENT_BUILD")
    if test_markers and any(lang in {"python", "rust", "c_cpp", "web_js_ts_html"} for lang in langs):
        lanes.add("INSUFFICIENT_EVIDENCE")
    return sorted(lanes)


def score_candidate(row: dict[str, Any], consumed_families: set[str]) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    blockers: list[str] = []
    family = row["repo_family_key"]
    langs = row["language_guess"]
    status_lanes = row["materialization_status_lanes"]
    family_keys = normalize_family_keys(family)
    if family_keys & consumed_families:
        blockers.append("repo_family_already_present_in_base_records")
        score -= 40
    primary = [lang for lang in langs if lang in LANG_DEFICITS]
    if primary:
        for lang in primary:
            score += min(30, LANG_DEFICITS[lang])
            reasons.append(f"language_root_deficit::{lang}")
    else:
        score -= 15
        reasons.append("not_primary_language_deficit_lane")
    for status in status_lanes:
        if status in STATUS_DEFICITS:
            score += min(35, STATUS_DEFICITS[status])
            reasons.append(f"status_materialization_lane::{status}")
    if row["test_markers"]:
        score += 20
        reasons.append("has_test_directory_marker")
    else:
        blockers.append("missing_test_directory_marker")
    if row["manifest_score"] >= 2:
        score += 10
        reasons.append("multiple_build_or_package_markers")
    if row["path_depth_from_base"] > 2 and family not in {"linux", "langchain-ai__langgraph", "crewAIInc__crewAI"}:
        score -= 5
        reasons.append("nested_package_candidate")
    if blockers:
        score -= 15 * len(blockers)
    return score, reasons, blockers


def scan_sources() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
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
            if depth > 3:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]
            file_set = set(files)
            dir_set = set(dirs)
            manifests = file_set & MANIFESTS
            test_markers = dir_set & TEST_DIRS
            if not manifests:
                continue
            key = str(path.resolve())
            if key in seen_paths:
                continue
            seen_paths.add(key)
            langs = language_guess(manifests, file_set, dir_set)
            family = normalize_family_key(str(path.relative_to(base)) if path != base else path.name)
            status_lanes = likely_status_lanes(manifests, test_markers, langs)
            rows.append(
                {
                    "source_path": str(path),
                    "scan_base": str(base),
                    "repo_family_key": family,
                    "path_depth_from_base": depth,
                    "manifests": sorted(manifests),
                    "test_markers": sorted(test_markers),
                    "language_guess": langs,
                    "materialization_status_lanes": status_lanes,
                    "manifest_score": len(manifests),
                }
            )
    return rows


def main() -> None:
    contract = read_json(CONTRACT)
    miner = read_json(MINER)
    consumed_families = base_family_keys()
    rows = scan_sources()
    queued: list[dict[str, Any]] = []
    for row in rows:
        score, reasons, blockers = score_candidate(row, consumed_families)
        role = "candidate_materialization"
        if "repo_family_already_present_in_base_records" in blockers:
            role = "duplicate_or_lineage_review"
        elif "missing_test_directory_marker" in blockers:
            role = "source_inventory_only"
        queued.append({**row, "priority_score": score, "admit_role": role, "priority_reasons": reasons, "blockers": blockers})
    queued.sort(key=lambda r: (-r["priority_score"], r["admit_role"], r["source_path"]))

    role_counts = Counter(row["admit_role"] for row in queued)
    lang_counts: Counter[str] = Counter()
    status_lane_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for row in queued:
        if row["admit_role"] == "candidate_materialization":
            family_counts[row["repo_family_key"]] += 1
            for lang in row["language_guess"]:
                lang_counts[lang] += 1
            for status in row["materialization_status_lanes"]:
                status_lane_counts[status] += 1

    top_candidates = [row for row in queued if row["admit_role"] == "candidate_materialization"][:80]
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "local_source_atlas_ready_not_trainable_yet",
        "why_now": [
            "Stage11968 found no new admissible roots in the Stage11944 inventory because most usable roots were already consumed into Stage11955.",
            "Stage11967 deficits require fresh independent non-web roots and real verifier/status materialization, especially FAIL_TO_PASS and PASS_CURRENT_BUILD.",
            "This stage inventories local source supply only; it does not certify verifier transitions or emit train rows.",
        ],
        "source_artifacts": {
            "stage11967_contract": rel(CONTRACT),
            "stage11968_candidate_miner": rel(MINER),
            "base_records": rel(BASE_RECORDS),
        },
        "contract_deficits_relevant_to_atlas": {
            "language_root_deficits": LANG_DEFICITS,
            "status_record_deficits": STATUS_DEFICITS,
        },
        "scan": {
            "scan_bases": [str(path) for path in SCAN_BASES if path.exists()],
            "manifest_candidates": len(rows),
            "consumed_base_family_keys": len(consumed_families),
            "role_counts": dict(role_counts),
        },
        "candidate_materialization_summary": {
            "rows": role_counts.get("candidate_materialization", 0),
            "repo_families": len(family_counts),
            "language_guess_counts": dict(lang_counts),
            "status_lane_counts": dict(status_lane_counts),
            "top_20": top_candidates[:20],
        },
        "duplicate_or_lineage_review_count": role_counts.get("duplicate_or_lineage_review", 0),
        "source_inventory_only_count": role_counts.get("source_inventory_only", 0),
        "next_stage_recommendation": {
            "stage": "stage11970_transition_root_250_materialization_plan",
            "action": "Select candidate_materialization roots from this atlas, run lightweight verifier/build probes, and emit real verified_transition_record_v1 rows only after observed transitions exist.",
            "priority_order": [
                "non-web PASS_CURRENT_BUILD roots",
                "non-web testable roots suitable for controlled FAIL_TO_PASS mutation",
                "Rust roots with cargo test or cargo check anchors",
                "Python/C++ roots with focused tests and low environment hydration cost",
            ],
            "do_not_train_until": [
                "observed verifier transition is attached",
                "candidate actions/options have at least two semantic competitors",
                "anti-cheat fields are completed",
                "root lineage is checked against Stage11955/11958 and protected eval roots",
            ],
        },
        "notes": {
            "stage11968_decision": miner.get("decision"),
            "stage11967_decision": contract.get("decision"),
            "milestone_decomposition_policy": "defer; useful later, but Stage11967/11969 keep the immediate bottleneck on transition-root supply.",
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "queue": rel(QUEUE),
        },
    }
    write_jsonl(QUEUE, queued)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
