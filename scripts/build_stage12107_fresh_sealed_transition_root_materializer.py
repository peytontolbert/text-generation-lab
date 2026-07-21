#!/usr/bin/env python3
"""Materialization work queue for fresh sealed transition roots.

This stage does not train and does not claim sealed rows. It converts the
Stage11969 local source atlas into root-disjoint work items for Stage12104.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12107
NAME = "stage12107_fresh_sealed_transition_root_materializer"
OUT = ART / NAME
SUMMARY = OUT / "fresh_sealed_transition_root_materializer.json"
MIRROR = SUM / f"{NAME}.json"
WORK_ITEMS = OUT / "fresh_sealed_transition_materialization_work_items.jsonl"
REJECTED = OUT / "fresh_sealed_transition_materialization_rejected.jsonl"

REQUEST = SUM / "stage12106_fresh_sealed_transition_root_materialization_request.json"
SOURCE_QUEUE = ART / "stage11969_transition_root_250_local_source_atlas/transition_root_250_local_source_queue.jsonl"

TASK_TARGETS = {
    "transition_next_action": 90,
    "transition_candidate_selection": 65,
    "transition_verifier_transition": 65,
    "transition_continue_or_stop": 40,
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


def root_lineage(row: dict[str, Any]) -> str:
    base = f"{row.get('repo_family_key')}::{row.get('source_path')}"
    return "stage12107::" + hashlib.sha1(base.encode()).hexdigest()[:16]


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
    ]
    for pattern in patterns:
        for path in ART.glob(pattern):
            for row in read_jsonl(path):
                if task_type(row).startswith("transition_") or "transition" in str(row.get("row_id") or ""):
                    for key in ("repo_family", "repo_id", "root_id", "root_lineage_key", "source_root_id", "source_bundle_id"):
                        if row.get(key):
                            excluded.add(canonical(row.get(key)))
    return excluded


def lane(row: dict[str, Any]) -> str:
    langs = set(row.get("language_guess") or [])
    if {"python", "c_cpp"} <= langs or len(langs & {"python", "rust", "c_cpp", "web_js_ts_html"}) > 1:
        return "mixed_build_config_dependency"
    for lang in ("c_cpp", "python", "rust", "web_js_ts_html"):
        if lang in langs:
            return lang
    return "unknown"


def source_snippet(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False}
    candidates = []
    for child in sorted(path.iterdir(), key=lambda p: p.name)[:200]:
        if child.is_file() and child.name in {"pyproject.toml", "Cargo.toml", "package.json", "CMakeLists.txt", "Makefile", "setup.py"}:
            try:
                text = child.read_text(encoding="utf-8", errors="replace")[:1200]
            except OSError:
                text = ""
            candidates.append({"path": str(child), "text_prefix": text})
    test_dirs = [str(path / d) for d in ("tests", "test", "__tests__", "spec", "crates") if (path / d).exists()]
    return {"available": True, "manifest_snippets": candidates[:3], "test_dirs": test_dirs[:5]}


def command_plan(row: dict[str, Any], root: Path) -> dict[str, Any]:
    langs = set(row.get("language_guess") or [])
    manifests = set(row.get("manifests") or [])
    if "rust" in langs or "Cargo.toml" in manifests:
        return {
            "build_probe": ["cargo", "check", "--locked"],
            "test_probe": ["cargo", "test", "--locked", "--no-fail-fast"],
            "not_exercised_probe": ["cargo", "test", "--locked", "stage12107_nonexistent_filter"],
        }
    if "web_js_ts_html" in langs or "package.json" in manifests:
        return {
            "build_probe": ["npm", "test", "--", "--runInBand"],
            "test_probe": ["npm", "test"],
            "not_exercised_probe": ["npm", "test", "--", "stage12107_nonexistent_filter"],
        }
    if "c_cpp" in langs or {"CMakeLists.txt", "Makefile"} & manifests:
        return {
            "build_probe": ["make", "-n"],
            "test_probe": ["make", "test"],
            "not_exercised_probe": ["make", "-n", "stage12107_nonexistent_target"],
        }
    return {
        "build_probe": ["python", "-m", "py_compile", "."],
        "test_probe": ["python", "-m", "pytest", "-q"],
        "not_exercised_probe": ["python", "-m", "pytest", "-q", "-k", "stage12107_nonexistent_filter"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = read_json(REQUEST)
    source_rows = read_jsonl(SOURCE_QUEUE)
    excluded = gather_excluded_families()

    work: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    lane_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    rejection_counts: Counter[str] = Counter()

    quota = request["fresh_root_materialization_contract"]["new_roots_by_language_or_lane"]
    max_total = request["fresh_root_materialization_contract"]["target_new_unique_roots"]

    for row in source_rows:
        repo_key = canonical(row.get("repo_family_key") or row.get("source_path"))
        root_key = root_lineage(row)
        reasons = []
        if row.get("blockers"):
            reasons.append("source_atlas_blockers")
        if repo_key in excluded:
            reasons.append("repo_family_overlaps_discovery_or_prior_transition_stage")
        if root_key in seen_roots:
            reasons.append("duplicate_source_root")
        root_path = Path(str(row.get("source_path") or ""))
        if not root_path.exists():
            reasons.append("source_path_missing")
        ln = lane(row)
        if ln not in quota:
            reasons.append("unsupported_or_unknown_language_lane")
        if lane_counts[ln] >= quota.get(ln, 0):
            reasons.append("lane_quota_already_filled")
        # Keep a strict repo-family cap for sealed roots. LangGraph-like monorepos
        # are useful, but not enough to prove sealed transfer by themselves.
        if repo_counts[repo_key] >= 4:
            reasons.append("repo_family_cap_reached")

        audit = {
            "repo_family_key": row.get("repo_family_key"),
            "source_path": row.get("source_path"),
            "lane": ln,
            "root_lineage_key": root_key,
            "reasons": reasons,
        }
        if reasons:
            rejected.append(audit)
            for reason in reasons:
                rejection_counts[reason] += 1
            continue

        snippets = source_snippet(root_path)
        item = {
            "stage12107_work_item": True,
            "work_item_id": root_key,
            "root_id": root_key,
            "root_lineage_key": root_key,
            "repo_family": str(row.get("repo_family_key")),
            "repo_family_key_normalized": repo_key,
            "source_path": str(root_path),
            "language_lane": ln,
            "language_guess": row.get("language_guess") or [],
            "manifests": row.get("manifests") or [],
            "test_markers": row.get("test_markers") or [],
            "materialization_status_lanes": row.get("materialization_status_lanes") or [],
            "sealed_split_role": "sealed_confirm_only",
            "train_support_only": False,
            "strict_eval_eligible": True,
            "source_heldout_admissible": True,
            "do_not_train": True,
            "source_evidence_preview": snippets,
            "command_plan": command_plan(row, root_path),
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
            "next_materialization_steps": [
                "run build_probe and test_probe in isolated temp/cache environment",
                "capture stdout/stderr/returncode/duration as verifier evidence",
                "derive verifier transition without training on row",
                "create semantic candidate objects for all four transition tasks",
                "run Stage12108 admission audit before route/Gemma scoring",
            ],
        }
        work.append(item)
        seen_roots.add(root_key)
        lane_counts[ln] += 1
        repo_counts[repo_key] += 1
        if len(work) >= max_total:
            break

    remaining = {k: max(0, v - lane_counts.get(k, 0)) for k, v in quota.items()}
    task_projection_capacity = {task: len(work) for task in TASK_TARGETS}
    task_remaining = {task: max(0, target - task_projection_capacity[task]) for task, target in TASK_TARGETS.items()}
    ready_for_execution = len(work) >= max_total and all(v == 0 for v in remaining.values())

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "fresh_sealed_work_queue_ready" if ready_for_execution else "fresh_sealed_work_queue_partial_supply_gap",
        "do_not_train": True,
        "source_rows_scanned": len(source_rows),
        "work_items": len(work),
        "rejected_items": len(rejected),
        "lane_counts": dict(sorted(lane_counts.items())),
        "remaining_lane_quota": remaining,
        "task_projection_capacity_if_all_roots_materialize": task_projection_capacity,
        "remaining_preferred_task_projection_rows": task_remaining,
        "repo_family_counts_top20": dict(repo_counts.most_common(20)),
        "rejection_counts": dict(rejection_counts.most_common()),
        "excluded_family_count": len(excluded),
        "ready_for_execution": ready_for_execution,
        "next_stage_recommendation": {
            "stage": "stage12108_fresh_sealed_transition_execution_or_gap_fill",
            "action": (
                "Execute verifier/build probes for these work items, but first fill missing Rust/web lanes if strict 100-root sealed target is required."
                if not ready_for_execution
                else "Execute verifier/build probes for all work items, then admit rows before route/Gemma scoring."
            ),
            "hard_gap": remaining,
        },
        "source_artifacts": {
            "stage12106_request": rel(REQUEST),
            "stage11969_source_queue": rel(SOURCE_QUEUE),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "work_items": rel(WORK_ITEMS),
            "rejected_items": rel(REJECTED),
        },
    }

    write_jsonl(WORK_ITEMS, work)
    write_jsonl(REJECTED, rejected)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "work_items": len(work),
        "lane_counts": summary["lane_counts"],
        "remaining_lane_quota": remaining,
        "top_rejections": dict(rejection_counts.most_common(8)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
