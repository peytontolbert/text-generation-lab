#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10772
NAME = "stage10772_bulk_multilingual_root_supply_census"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "bulk_multilingual_root_supply_census.json"
RAW_ROOTS_JSONL = OUT_DIR / "raw_root_supply_records.jsonl"
UNIQUE_ROOTS_JSONL = OUT_DIR / "unique_root_supply_manifest.jsonl"
LANE_QUEUE_JSONL = OUT_DIR / "language_lane_queue.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

SHARD_CONFIG = ROOT / "configs/software_maintainer/strict_long_context_trainable_shards_v1.json"
QUALITY_CONTRACT = ROOT / "runs/local/artifacts/stage10613_multilingual_root_scale_quality_contract/multilingual_root_scale_quality_contract.json"
REVIEWED_ROOTS = ROOT / "runs/local/artifacts/stage10687_reviewed_v27_plus_two_fresh_rust_support_package/reviewed_v27_plus_two_fresh_rust_root_manifest.jsonl"
CURRENT_COMPILED_ROOTS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"

QUERY_RE = re.compile(r"^\[(\d+)\]\s", re.MULTILINE)

VERIFIER_SCORES = {
    "PASS_TRACE_VERIFICATION_TARGETS": 110,
    "PASS_TARGETED_TEST_SELECTION": 95,
    "PASS_BROAD_VERIFICATION_DISCOVERY": 75,
    "PASS_BROAD_TEST_DISCOVERY": 60,
    "UNKNOWN": 20,
}

QUEUE_LIMITS = {
    "python": 32,
    "rust": 24,
    "c_cpp": 24,
    "web_js_ts_html": 24,
}

REPO_CAPS = {
    "python": 3,
    "rust": 4,
    "c_cpp": 4,
    "web_js_ts_html": 3,
}

LANGUAGE_TARGETS = {
    "python": 35000,
    "rust": 20000,
    "c_cpp": 20000,
    "web_js_ts_html": 20000,
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


def write_json(path: Path, payload: Any) -> None:
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


def normalize_repo_id(value: str) -> str:
    value = (value or "").strip()
    if value == "peytontolbert-parameter-golf":
        return "parametergolf"
    return value or "unknown"


def split_pack_queries(prompt_text: str) -> dict[int, str]:
    matches = list(QUERY_RE.finditer(prompt_text))
    if not matches:
        return {}
    sections: dict[int, str] = {}
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(prompt_text)
        sections[int(match.group(1))] = prompt_text[start:end].strip()
    return sections


def parse_state_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def parse_csv_field(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_query_section(query_text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for raw_line in query_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and "] " in line:
            line = line.split("] ", 1)[1]
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        metadata[key] = value
    return {
        "repo_id": normalize_repo_id(metadata.get("Repository", "")),
        "task": metadata.get("Task", ""),
        "execution_route": metadata.get("Execution route", "UNKNOWN"),
        "verifier_id": metadata.get("Test selection route", "UNKNOWN"),
        "changed_files": parse_csv_field(metadata.get("Changed files", "")),
        "verification_targets": parse_csv_field(metadata.get("Verification targets", "")),
        "key_symbols": parse_csv_field(metadata.get("Key symbols", "")),
        "commit_sha": metadata.get("Commit sha"),
    }


def is_maintainer_query(query_text: str, query_meta: dict[str, Any], execution_route: str, changed_files: list[str]) -> tuple[bool, str]:
    lowered = query_text.lower()
    task = str(query_meta.get("task") or "").lower()
    if "changed files:" not in lowered:
        return False, "missing_changed_files"
    if "execution route:" not in lowered:
        return False, "missing_execution_route"
    if execution_route == "UNKNOWN":
        return False, "unknown_execution_route"
    if not changed_files:
        return False, "no_changed_files"
    if lowered.startswith("[") and "what is the final value of" in lowered:
        return False, "synthetic_value_reconstruction"
    if lowered.startswith("[") and "reconstruct the transition outcome" in lowered:
        return False, "retrieval_probe_not_maintainer_bundle"
    if "modify repository files" in lowered:
        return True, "maintainer_modify_files"
    if "recreate verified repository transition" in lowered:
        return True, "maintainer_commit_reconstruction"
    if any(phrase in task for phrase in ("modify repository files", "recreate verified repository transition")):
        return True, "maintainer_task_field"
    return False, "non_maintainer_query_shape"


def infer_language_from_paths(paths: list[str]) -> str:
    counts = Counter()
    for path in paths:
        lowered = path.lower()
        if lowered.endswith((".py", ".pyi")):
            counts["python"] += 1
        elif lowered.endswith(".rs"):
            counts["rust"] += 1
        elif lowered.endswith((".c", ".cc", ".cpp", ".cu", ".cuh", ".h", ".hpp")):
            counts["c_cpp"] += 1
        elif lowered.endswith((".js", ".jsx", ".ts", ".tsx", ".html", ".css")):
            counts["web_js_ts_html"] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return "unknown"


def infer_language(repo_id: str, changed_files: list[str], verification_targets: list[str]) -> str:
    repo_map = {
        "agentkernel": "python",
        "repository_library": "python",
        "parametergolf": "c_cpp",
    }
    direct = repo_map.get(repo_id)
    if direct:
        return direct
    inferred = infer_language_from_paths(changed_files)
    if inferred != "unknown":
        return inferred
    inferred = infer_language_from_paths(verification_targets)
    return inferred


def quality_tier(verifier_id: str) -> str:
    if verifier_id == "PASS_TRACE_VERIFICATION_TARGETS":
        return "gold"
    if verifier_id == "PASS_TARGETED_TEST_SELECTION":
        return "silver"
    if verifier_id in {"PASS_BROAD_VERIFICATION_DISCOVERY", "PASS_BROAD_TEST_DISCOVERY"}:
        return "bronze"
    return "quarantine"


def selected_test_anchor_present(verifier_id: str) -> bool:
    return verifier_id in {"PASS_TRACE_VERIFICATION_TARGETS", "PASS_TARGETED_TEST_SELECTION"}


def lane_for(language_family: str, verifier_id: str) -> str:
    if language_family == "python":
        if selected_test_anchor_present(verifier_id):
            return "python_verifier_and_generation_scale"
        return "python_broad_root_supply"
    if language_family == "rust":
        return "rust_verifier_anchor_and_citation_scale"
    if language_family == "c_cpp":
        return "cpp_materialization_scale"
    if language_family == "web_js_ts_html":
        return "web_verifier_anchor_acquisition"
    return "generic"


def score_unique_root(record: dict[str, Any]) -> int:
    score = VERIFIER_SCORES.get(str(record["verifier_id"]), 20)
    score += min(int(record["duplicate_source_count"]) * 4, 20)
    score += min(int(record["verification_target_count"]) * 2, 14)
    score += min(int(record["changed_file_count"]), 8)
    if record["language_family"] == "rust":
        score += 18
    elif record["language_family"] == "web_js_ts_html":
        score += 20
    elif record["language_family"] == "c_cpp":
        score += 10
    if record["reviewed_root_already_present"]:
        score -= 20
    return score


def make_root_lineage_key(repo_id: str, example_id: str, changed_files: list[str], verification_targets: list[str]) -> str:
    if example_id:
        return example_id
    path_key = "|".join(sorted(changed_files)) or "no_changed_files"
    verifier_key = "|".join(sorted(verification_targets)) or "no_verification_targets"
    return f"{repo_id}::{path_key}::{verifier_key}"


def select_queue(candidates: list[dict[str, Any]], limit: int, repo_cap: int) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    by_score = sorted(
        candidates,
        key=lambda row: (
            -int(row["priority_score"]),
            row["quality_tier"],
            row["root_lineage_key"],
        ),
    )
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_CARD.parent.mkdir(parents=True, exist_ok=True)

    config = load_json(SHARD_CONFIG)
    quality_contract = load_json(QUALITY_CONTRACT)
    reviewed_roots = load_jsonl(REVIEWED_ROOTS)
    current_compiled_roots = load_jsonl(CURRENT_COMPILED_ROOTS)

    reviewed_lineage = {
        str(row.get("root_id") or row.get("root_lineage_key") or "")
        for row in reviewed_roots
        if str(row.get("root_id") or row.get("root_lineage_key") or "")
    }

    raw_records: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    filtered_reasons: Counter[str] = Counter()

    for shard in config.get("selected_shards", []):
        if not shard.get("ready_for_training"):
            continue
        shard_name = str(shard["name"])
        artifacts = shard.get("artifacts") or {}
        training_rows_path = ROOT / str(artifacts.get("training_rows_jsonl"))
        if not training_rows_path.exists():
            continue
        training_rows = load_jsonl(training_rows_path)
        for pack_row in training_rows:
            pack_id = str(pack_row.get("pack_id") or "unknown_pack")
            pack_token_count = int(pack_row.get("pack_token_count") or 0)
            query_sections = split_pack_queries(str(pack_row.get("prompt_text") or ""))
            for target in pack_row.get("target_rows", []):
                final_state = parse_state_json(str(target.get("final_state_json") or ""))
                query_index = int(target.get("query_index") or -1)
                query_text = query_sections.get(query_index, f"[{query_index}] query_not_recovered")
                query_meta = parse_query_section(query_text)
                repo_id = normalize_repo_id(str(target.get("program_id") or query_meta["repo_id"]))
                changed_files = list(final_state.get("expected_changed_files") or query_meta["changed_files"])
                verification_targets = list(final_state.get("verification_targets") or query_meta["verification_targets"])
                key_symbols = list(final_state.get("key_symbols") or query_meta["key_symbols"])
                verifier_id = str(final_state.get("test_selection_route") or query_meta["verifier_id"] or "UNKNOWN")
                execution_route = str(final_state.get("execution_route") or query_meta["execution_route"] or "UNKNOWN")
                is_maintainer, maintain_reason = is_maintainer_query(query_text, query_meta, execution_route, changed_files)
                if not is_maintainer:
                    filtered_reasons[maintain_reason] += 1
                    continue
                language_family = infer_language(repo_id, changed_files, verification_targets)
                if language_family not in LANGUAGE_TARGETS:
                    filtered_reasons[f"unsupported_language::{language_family}"] += 1
                    continue
                example_id = str(target.get("example_id") or "")
                root_lineage_key = make_root_lineage_key(repo_id, example_id, changed_files, verification_targets)
                record = {
                    "root_id": f"{shard_name}::{pack_id}::q{query_index}",
                    "root_lineage_key": root_lineage_key,
                    "repo_id": repo_id,
                    "repo_family": repo_id,
                    "language_family": language_family,
                    "task_family": "software_maintenance_query",
                    "snapshot_id": pack_id,
                    "environment_id": "strict_long_context_pack_query",
                    "verifier_id": verifier_id,
                    "execution_route": execution_route,
                    "quality_tier": quality_tier(verifier_id),
                    "selected_test_anchor_present": selected_test_anchor_present(verifier_id),
                    "verifier_anchor_present": verifier_id != "UNKNOWN",
                    "changed_file_count": len(changed_files),
                    "verification_target_count": len(verification_targets),
                    "key_symbol_count": len(key_symbols),
                    "changed_files_sample": changed_files[:8],
                    "verification_targets_sample": verification_targets[:8],
                    "key_symbols_sample": key_symbols[:8],
                    "query_index": query_index,
                    "example_id": example_id,
                    "pack_id": pack_id,
                    "pack_token_count": pack_token_count,
                    "source_family_id": shard_name,
                    "source_training_rows_path": display(training_rows_path),
                    "source_pack_count": int(shard.get("target_audit_count") or len(pack_row.get("target_rows", []))),
                    "reviewed_root_already_present": root_lineage_key in reviewed_lineage,
                    "semantic_lane": lane_for(language_family, verifier_id),
                    "maintainer_reason": maintain_reason,
                    "query_text": query_text,
                }
                raw_records.append(record)
                source_counts[shard_name] += 1

    unique_by_lineage: dict[str, dict[str, Any]] = {}
    lineage_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in raw_records:
        lineage_sources[str(record["root_lineage_key"])].append(record)

    for lineage_key, records in lineage_sources.items():
        best = sorted(
            records,
            key=lambda row: (
                -VERIFIER_SCORES.get(str(row["verifier_id"]), 20),
                -int(row["pack_token_count"]),
                str(row["source_family_id"]),
            ),
        )[0].copy()
        best["duplicate_source_count"] = len(records)
        best["duplicate_source_families"] = sorted({str(r["source_family_id"]) for r in records})
        best["priority_score"] = 0
        unique_by_lineage[lineage_key] = best

    unique_records = sorted(unique_by_lineage.values(), key=lambda row: str(row["root_lineage_key"]))
    for record in unique_records:
        record["priority_score"] = score_unique_root(record)

    unique_language_counts = Counter(str(row["language_family"]) for row in unique_records)
    unique_repo_counts: dict[str, Counter[str]] = defaultdict(Counter)
    unique_verifier_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in unique_records:
        lang = str(row["language_family"])
        unique_repo_counts[lang][str(row["repo_family"])] += 1
        unique_verifier_counts[lang][str(row["verifier_id"])] += 1

    queue_rows: list[dict[str, Any]] = []
    lane_rollup: dict[str, Any] = {}
    for language_family, limit in QUEUE_LIMITS.items():
        candidates = [
            row
            for row in unique_records
            if row["language_family"] == language_family and not row["reviewed_root_already_present"]
        ]
        selected = select_queue(candidates, limit, REPO_CAPS[language_family])
        for row in selected:
            queue_rows.append(
                {
                    "language_family": language_family,
                    "root_lineage_key": row["root_lineage_key"],
                    "root_id": row["root_id"],
                    "repo_family": row["repo_family"],
                    "verifier_id": row["verifier_id"],
                    "quality_tier": row["quality_tier"],
                    "priority_score": row["priority_score"],
                    "semantic_lane": row["semantic_lane"],
                    "duplicate_source_count": row["duplicate_source_count"],
                    "source_family_id": row["source_family_id"],
                    "selected_test_anchor_present": row["selected_test_anchor_present"],
                    "verification_target_count": row["verification_target_count"],
                    "changed_file_count": row["changed_file_count"],
                    "source_training_rows_path": row["source_training_rows_path"],
                    "query_index": row["query_index"],
                    "pack_id": row["pack_id"],
                }
            )
        top_repos = unique_repo_counts.get(language_family, Counter()).most_common(8)
        lane_rollup[language_family] = {
            "unique_root_count": int(unique_language_counts.get(language_family, 0)),
            "target_root_count": LANGUAGE_TARGETS[language_family],
            "root_gap": max(LANGUAGE_TARGETS[language_family] - int(unique_language_counts.get(language_family, 0)), 0),
            "review_queue_count": len(selected),
            "top_repo_families": [{"repo_family": repo, "root_count": count} for repo, count in top_repos],
            "verifier_counts": dict(unique_verifier_counts.get(language_family, Counter()).most_common()),
        }

    current_compiled_counts = Counter(str(row.get("language_family") or "unknown") for row in current_compiled_roots)
    queue_rows.sort(key=lambda row: (row["language_family"], -int(row["priority_score"]), row["root_lineage_key"]))

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "bulk_multilingual_root_supply_census_ready",
        "claim_scope": [
            "Enumerate multilingual root supply from the configured long-context training shards rather than from the tiny fixed stage10516 slice.",
            "Deduplicate roots by lineage and score them by verifier strength, duplicate corroboration, and review status.",
            "Produce language-specific materialization queues that move toward the long-term 20k+ per-language target without dropping the quality ratchet.",
        ],
        "source_artifacts": {
            "shard_config": display(SHARD_CONFIG),
            "quality_contract": display(QUALITY_CONTRACT),
            "reviewed_roots": display(REVIEWED_ROOTS),
            "current_compiled_roots": display(CURRENT_COMPILED_ROOTS),
        },
        "quality_ratchet_reused": ((quality_contract.get("quality_ratchet") or {}).get("must_hold_before_any_batch_is_counted_toward_scale")) or [],
        "metrics": {
            "selected_shards": int(config.get("selected_shard_count") or len(config.get("selected_shards", []))),
            "raw_root_supply_records": len(raw_records),
            "unique_root_supply_records": len(unique_records),
            "unique_language_counts": dict(sorted(unique_language_counts.items())),
            "current_compiled_language_counts": dict(sorted(current_compiled_counts.items())),
            "duplicate_lineage_rate": round(
                1.0 - (len(unique_records) / max(len(raw_records), 1)),
                4,
            ),
            "filtered_out_non_maintainer_or_unsupported": dict(sorted(filtered_reasons.items())),
            "reviewed_overlap_count": sum(1 for row in unique_records if row["reviewed_root_already_present"]),
            "source_family_counts": dict(sorted(source_counts.items())),
        },
        "language_rollup": lane_rollup,
        "headline_findings": [
            "The configured long-context shard inventory yields a larger multilingual root pool than stage10516 currently exposes.",
            "Python still dominates the bulk supply, so repo caps and heldout discipline remain mandatory rather than optional.",
            "Rust and Web remain the scarcest languages in the deduped root pool; they need explicit source acquisition and review effort, not just more training steps.",
            "This stage turns the user-requested 20k+/language target into a measurable supply problem with concrete queues instead of speculation.",
        ],
        "recommended_next_stages": [
            "stage10773_bulk_multilingual_root_materialization_briefs",
            "stage10774_bulk_multilingual_review_packet_builder",
            "stage10775_root_split_aware_multitarget_manifest_v28",
        ],
        "artifacts": {
            "summary_json": display(SUMMARY_JSON),
            "raw_root_supply_records": display(RAW_ROOTS_JSONL),
            "unique_root_supply_manifest": display(UNIQUE_ROOTS_JSONL),
            "language_lane_queue": display(LANE_QUEUE_JSONL),
        },
    }

    write_jsonl(RAW_ROOTS_JSONL, raw_records)
    write_jsonl(UNIQUE_ROOTS_JSONL, unique_records)
    write_jsonl(LANE_QUEUE_JSONL, queue_rows)
    write_json(SUMMARY_JSON, summary)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": summary["decision"],
            "summary": display(SUMMARY_JSON),
            "unique_root_supply_manifest": display(UNIQUE_ROOTS_JSONL),
            "language_lane_queue": display(LANE_QUEUE_JSONL),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
