#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10763
NAME = "stage10763_multilingual_root_admission_seed_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "multilingual_root_admission_seed_manifest.json"
ADMISSION_JSONL = OUT_DIR / "root_admission_seed_manifest.jsonl"
QUEUE_JSONL = OUT_DIR / "first_wave_materialization_queue.jsonl"
REVIEWED_JSONL = OUT_DIR / "reviewed_root_roles.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"
REVIEWED_ROOTS = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl"
QUALITY_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
FRONTIER_QUEUE = ROOT / "runs/local/artifacts/stage10730_multilingual_root_scale_frontier_queue/multilingual_root_scale_frontier_queue.json"
CURRENT_STRICT = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/agentkernel_lite_encdec_strict_eval.jsonl"
CURRENT_RESIDUALS = ROOT / "runs/local/artifacts/stage10762_hf_local_repaired_support_probe_audit/strict_miss_rows.jsonl"

VERIFIER_SCORES = {
    "PASS_TRACE_VERIFICATION_TARGETS": 110,
    "PASS_TARGETED_TEST_SELECTION": 95,
    "PASS_BROAD_VERIFICATION_DISCOVERY": 75,
    "PASS_BROAD_TEST_DISCOVERY": 60,
    "UNKNOWN": 20,
}

LANGUAGE_BOOSTS = {
    "python": 20,
    "rust": 55,
    "c_cpp": 35,
    "web_js_ts_html": 50,
}

QUEUE_LIMITS = {
    "python": 16,
    "rust": 12,
    "c_cpp": 16,
    "web_js_ts_html": 12,
}

REPO_CAPS = {
    "python": 2,
    "rust": 3,
    "c_cpp": 3,
    "web_js_ts_html": 2,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def quality_tier(verifier_id: str) -> str:
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        return "gold"
    if verifier_id == "PASS_TARGETED_TEST_SELECTION":
        return "silver"
    if verifier_id == "PASS_BROAD_VERIFICATION_DISCOVERY":
        return "bronze"
    return "quarantine"


def semantic_lane(language_family: str, verifier_id: str) -> str:
    if language_family == "python":
        if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
            return "python_verifier_disambiguation"
        return "python_general_root_supply"
    if language_family == "rust":
        return "rust_evidence_citation_contrast"
    if language_family == "c_cpp":
        return "cpp_materialization_breadth"
    if language_family == "web_js_ts_html":
        return "web_verifier_anchor_acquisition"
    return "generic"


def admit_role(language_family: str, verifier_id: str, repo_family: str, reviewed_roots: set[str]) -> str:
    if verifier_id == "UNKNOWN":
        return "quarantine_unknown_verifier"
    if language_family == "python" and repo_family == "agentkernel":
        return "repo_cap_overflow_candidate"
    if language_family == "web_js_ts_html":
        return "materialize_pure_web_candidate"
    if language_family == "rust":
        return "materialize_fresh_rust_candidate"
    if language_family == "c_cpp":
        return "materialize_cpp_candidate"
    return "materialize_priority"


def reason_codes(language_family: str, verifier_id: str, repo_family: str) -> list[str]:
    reasons: list[str] = []
    if verifier_id == "UNKNOWN":
        reasons.append("unknown_verifier")
    if language_family == "python" and repo_family == "agentkernel":
        reasons.append("python_repo_dominance_risk")
    if language_family == "rust":
        reasons.append("rust_supply_underweight")
    if language_family == "web_js_ts_html":
        reasons.append("web_verifier_anchor_gap")
    if language_family == "c_cpp":
        reasons.append("cpp_materialization_candidate")
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        reasons.append("trace_verifier_preferred")
    elif verifier_id == "PASS_TARGETED_TEST_SELECTION":
        reasons.append("selected_test_verifier_preferred")
    return reasons


def priority_score(language_family: str, verifier_id: str, repo_family: str, repo_count: int) -> int:
    score = VERIFIER_SCORES.get(verifier_id, 20) + LANGUAGE_BOOSTS.get(language_family, 0)
    # Prefer repo diversity when supply is already concentrated.
    score += max(0, 14 - min(repo_count, 14))
    if language_family == "python" and repo_family == "agentkernel":
        score -= 20
    if language_family == "rust":
        score += 8
    if language_family == "web_js_ts_html":
        score += 5
    return score


def parse_miss_lookup(strict_rows: list[dict[str, Any]], residual_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    strict_by_id = {str(row["row_id"]): row for row in strict_rows}
    misses: dict[str, dict[str, Any]] = {}
    for miss in residual_rows:
        row_id = str(miss["row_id"])
        row = strict_by_id.get(row_id)
        if not row:
            continue
        root_id = str(row.get("source_bundle_id") or row.get("source_root_id") or row_id)
        misses[root_id] = {
            "row_id": row_id,
            "root_id": root_id,
            "language_family": str(row.get("language_family") or "unknown"),
            "task_type": str(row.get("task_type") or "unknown"),
            "target_text": str(row.get("target_text") or ""),
            "repo_family": str(row.get("repo_family") or row.get("repo_id") or "unknown"),
        }
    return misses


def select_queue(candidates: list[dict[str, Any]], limit: int, repo_cap: int) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    by_score = sorted(candidates, key=lambda row: (-int(row["priority_score"]), str(row["root_id"])))

    for row in by_score:
        repo_family = str(row["repo_family"])
        if repo_counts[repo_family] >= repo_cap:
            continue
        queue.append(row)
        repo_counts[repo_family] += 1
        if len(queue) >= limit:
            return queue

    for row in by_score:
        if row in queue:
            continue
        queue.append(row)
        if len(queue) >= limit:
            break
    return queue


def main() -> None:
    compiled_roots = load_jsonl(COMPILED_ROOTS)
    reviewed_roots = load_jsonl(REVIEWED_ROOTS)
    quality_contract = load_json(QUALITY_CONTRACT)
    frontier_queue = load_json(FRONTIER_QUEUE)
    strict_rows = load_jsonl(CURRENT_STRICT)
    residual_rows = load_jsonl(CURRENT_RESIDUALS)

    reviewed_root_ids = {str(row["root_id"]) for row in reviewed_roots}
    repo_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    for row in compiled_roots:
        language_family = str(row.get("language_family") or "unknown")
        repo_family = str(row.get("repo_family") or row.get("repo_id") or "unknown")
        repo_counts_by_language[language_family][repo_family] += 1

    residual_lookup = parse_miss_lookup(strict_rows, residual_rows)

    admission_rows: list[dict[str, Any]] = []
    queue_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compiled_roots:
        language_family = str(row.get("language_family") or "unknown")
        if language_family not in QUEUE_LIMITS:
            continue
        repo_family = str(row.get("repo_family") or row.get("repo_id") or "unknown")
        verifier_id = str(row.get("verifier_id") or "UNKNOWN")
        repo_count = repo_counts_by_language[language_family][repo_family]
        record = {
            "root_id": str(row["root_id"]),
            "repo_id": str(row.get("repo_id") or "unknown"),
            "repo_family": repo_family,
            "language_family": language_family,
            "task_family": str(row.get("task_family") or "unknown"),
            "snapshot_id": str(row.get("snapshot_id") or "unknown"),
            "environment_id": str(row.get("environment_id") or "unknown"),
            "source_family_id": str(((row.get("provenance") or {}).get("source_family_id")) or "unknown"),
            "pack_id": str(((row.get("provenance") or {}).get("pack_id")) or "unknown"),
            "query_index": int(((row.get("provenance") or {}).get("query_index")) or -1),
            "verifier_id": verifier_id,
            "compiled_repo_family_root_count": int(repo_count),
            "quality_tier": quality_tier(verifier_id),
            "semantic_lane": semantic_lane(language_family, verifier_id),
            "provisional_admit_role": admit_role(language_family, verifier_id, repo_family, reviewed_root_ids),
            "priority_score": priority_score(language_family, verifier_id, repo_family, repo_count),
            "reason_codes": reason_codes(language_family, verifier_id, repo_family),
            "reviewed_root_already_present": str(row["root_id"]) in reviewed_root_ids,
        }
        admission_rows.append(record)
        if record["provisional_admit_role"] != "quarantine_unknown_verifier":
            queue_candidates[language_family].append(record)

    admission_rows.sort(key=lambda row: (row["language_family"], -int(row["priority_score"]), row["root_id"]))

    queue_rows: list[dict[str, Any]] = []
    for language_family, candidates in queue_candidates.items():
        selected = select_queue(candidates, QUEUE_LIMITS[language_family], REPO_CAPS[language_family])
        for rank, row in enumerate(selected, start=1):
            queue_rows.append(
                {
                    **row,
                    "queue_rank": rank,
                    "queue_lane": language_family,
                }
            )
    queue_rows.sort(key=lambda row: (row["language_family"], int(row["queue_rank"]), row["root_id"]))

    reviewed_rows: list[dict[str, Any]] = []
    for row in reviewed_roots:
        root_id = str(row["root_id"])
        reviewed_rows.append(
            {
                "root_id": root_id,
                "repo_id": str(row.get("repo_id") or "unknown"),
                "repo_family": str(row.get("repo_family") or row.get("repo_id") or "unknown"),
                "language_family": str(row.get("language_family") or "unknown"),
                "record_type": str(row.get("record_type") or "unknown"),
                "split_role": str(row.get("split_role") or "unknown"),
                "strict_eval_eligible": bool(row.get("strict_eval_eligible")),
                "train_support_only": bool(row.get("train_support_only")),
                "source_heldout_admissible": bool(row.get("source_heldout_admissible")),
                "selected_test_anchor": bool(row.get("selected_test_anchor")),
                "verifier_anchor": bool(row.get("verifier_anchor")),
                "same_surface_eval_admissible": bool(row.get("same_surface_eval_admissible")),
                "stress_overlap_only": bool(row.get("stress_overlap_only")),
                "residual_canary_root": root_id in residual_lookup,
                "residual_details": residual_lookup.get(root_id),
            }
        )
    reviewed_rows.sort(key=lambda row: (row["language_family"], row["split_role"], row["root_id"]))

    admission_counts = Counter(row["provisional_admit_role"] for row in admission_rows)
    queue_counts = Counter(row["language_family"] for row in queue_rows)
    quality_counts = {lang: Counter(row["quality_tier"] for row in admission_rows if row["language_family"] == lang) for lang in QUEUE_LIMITS}

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "multilingual_root_admission_seed_manifest_ready",
        "claim_scope": [
            "Convert the current compiled-root substrate into a first root-admission seed manifest with quality tiers and provisional admit roles.",
            "Translate the live standalone residuals into explicit scaling lanes rather than another same-surface support probe.",
            "Prepare a first-wave multilingual materialization queue that can grow toward 20k+ roots per language under the existing anti-cheat contract.",
        ],
        "current_truth": {
            "compiled_root_counts_by_language": dict(
                sorted(Counter(str(row["language_family"]) for row in admission_rows).items())
            ),
            "reviewed_root_counts_by_language": dict(
                sorted(Counter(str(row["language_family"]) for row in reviewed_rows).items())
            ),
            "current_residual_roots": list(residual_lookup.values()),
        },
        "admission_metrics": {
            "compiled_root_records": len(admission_rows),
            "reviewed_root_records": len(reviewed_rows),
            "first_wave_queue_roots": len(queue_rows),
            "admit_role_counts": dict(sorted(admission_counts.items())),
            "first_wave_queue_counts_by_language": dict(sorted(queue_counts.items())),
            "quality_tier_counts_by_language": {
                lang: dict(sorted(counter.items())) for lang, counter in quality_counts.items()
            },
        },
        "phase_targets": (frontier_queue.get("phase_targets") or quality_contract.get("scale_targets") or {}),
        "anti_cheat_contract": [
            "Root remains the atomic split unit.",
            "No promotable row may expose gold target strings before the candidate set.",
            "Fresh-root materialization is preferred over same-surface replay for both current residual lanes.",
            "Rust support roots that are abstention-heavy remain support-only until matched by non-abstention reviewed citation roots.",
            "Python compiled roots from dominant repo families should be throttled by repo caps before scale claims are widened.",
        ],
        "headline_findings": [
            "The compiler substrate is real but badly imbalanced: Python dominates raw root count, while Rust and Web are still supply-limited.",
            "C/C++ is the best immediate scale lane because it already has materially larger compiled supply and stronger verifier structure than Rust or Web.",
            "Python scaling should continue, but with explicit repo-family caps and verifier-disambiguation preference so more roots do not just mean more agentkernel repeats.",
            "The current standalone misses still localize the next high-value reviewed-root acquisition work: Python verifier disambiguation and Rust evidence-citation contrast.",
        ],
        "next_best_step": "Materialize the first-wave queue into reviewed maintainer bundles, starting with C/C++ breadth, then fresh Rust citation roots and fresh pure-web verifier roots, while keeping the repaired 24-row canary frozen.",
        "source_artifacts": {
            "compiled_roots": display(COMPILED_ROOTS),
            "reviewed_roots": display(REVIEWED_ROOTS),
            "quality_contract": display(QUALITY_CONTRACT),
            "frontier_queue": display(FRONTIER_QUEUE),
            "current_strict_eval_rows": display(CURRENT_STRICT),
            "current_residual_rows": display(CURRENT_RESIDUALS),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "admission_manifest": display(ADMISSION_JSONL),
            "first_wave_queue": display(QUEUE_JSONL),
            "reviewed_root_roles": display(REVIEWED_JSONL),
        },
    }

    write_jsonl(ADMISSION_JSONL, admission_rows)
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_jsonl(REVIEWED_JSONL, reviewed_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "compiled_root_records": payload["admission_metrics"]["compiled_root_records"],
            "first_wave_queue_roots": payload["admission_metrics"]["first_wave_queue_roots"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
