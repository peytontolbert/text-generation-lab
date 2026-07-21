#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12327_external_adapter_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

OPEN_SWE_ROOT = Path("/arxiv/datasets/nvidia--Open-SWE-Traces")
OPEN_SWE_IMPORT = ROOT / "runs/local/artifacts/open_swe_trace_episodes_v1/open_swe_trace_episodes.jsonl"
BEARS_BUGS = Path("/arxiv/repositories/RepairThemAll/data/benchmarks/bears/bugs.json")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)
TEST_PATH_RE = re.compile(r"(?:^|[^A-Za-z0-9_./-])((?:tests?|test)/[A-Za-z0-9_./-]+(?:\.[A-Za-z0-9_]+)?(?:::[A-Za-z0-9_]+)*)")
VERIFY_MARKERS = ("pytest", "FAILED", "PASSED", "ERROR", "Traceback", "AssertionError", "mvn test", "cargo test", "npm test")


def stable_id(*parts: object) -> str:
    text = "::".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def safe_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def read_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def infer_language_from_paths(paths: list[str]) -> str:
    suffixes = Counter(Path(path).suffix.lower() for path in paths if path)
    if any(suffix in suffixes for suffix in (".py",)):
        return "python"
    if any(suffix in suffixes for suffix in (".rs",)):
        return "rust"
    if any(suffix in suffixes for suffix in (".cc", ".cpp", ".c", ".h", ".hpp")):
        return "c_cpp"
    if any(suffix in suffixes for suffix in (".js", ".jsx", ".ts", ".tsx", ".html", ".css")):
        return "web_js_ts_html"
    if any(suffix in suffixes for suffix in (".java",)):
        return "java"
    return "unknown"


def open_swe_parquet_inventory() -> dict[str, Any]:
    parquet_files = sorted((OPEN_SWE_ROOT / "data").glob("**/*.parquet")) if OPEN_SWE_ROOT.exists() else []
    dataset_counts = Counter(path.parent.name for path in parquet_files)
    return {
        "root": str(OPEN_SWE_ROOT),
        "exists": OPEN_SWE_ROOT.exists(),
        "parquet_file_count": len(parquet_files),
        "trajectory_family_counts": dict(sorted(dataset_counts.items())),
        "sample_files": [str(path) for path in parquet_files[:8]],
    }


def build_open_swe_candidates() -> list[dict[str, Any]]:
    imported = read_jsonl(OPEN_SWE_IMPORT, limit=250)
    rows: list[dict[str, Any]] = []
    for episode in imported:
        source = episode.get("source_metadata") or {}
        seed_paths = [str(path) for path in episode.get("seed_paths") or []]
        selected_tests = [str(test) for test in episode.get("selected_tests") or []]
        context_counts = episode.get("context_role_counts") or {}
        block_reasons = [
            "trace_support_only_not_repair_proof",
            "requires_same_source_verifier_causality_qc",
            "requires_raw_trace_to_safe_semantic_transition_extraction",
            "not_strict_or_source_heldout_admissible",
        ]
        if not seed_paths:
            block_reasons.append("missing_patch_path_refs")
        if not selected_tests:
            block_reasons.append("missing_verification_targets")
        if context_counts.get("verification_constraint", 0) == 0:
            block_reasons.append("missing_verification_constraint_context")
        rows.append(
            {
                "stage": STAGE,
                "record_type": "open_swe_trace_support_preflight_candidate",
                "candidate_id": f"stage12327::openswe::{episode.get('episode_id')}",
                "source_adapter": "Open-SWE-Traces",
                "source_record_ref": {
                    "dataset_name": source.get("dataset_name"),
                    "instance_id": source.get("instance_id"),
                    "trajectory_id": source.get("trajectory_id"),
                    "episode_id": episode.get("episode_id"),
                },
                "repo_family": episode.get("repo_id") or "unknown",
                "language_family": source.get("language") or infer_language_from_paths(seed_paths),
                "candidate_type": "trace_support_patch_plus_verify",
                "seed_path_count": len(seed_paths),
                "seed_path_hashes": [safe_hash(path)[:16] for path in seed_paths[:12]],
                "selected_test_count": len(selected_tests),
                "selected_test_hashes": [safe_hash(test)[:16] for test in selected_tests[:12]],
                "context_role_counts": context_counts,
                "trace_failure_types": source.get("trace_failure_types") or [],
                "trace_exception_types": source.get("trace_exception_types") or [],
                "admission": {
                    "training_allowed": False,
                    "train_support_allowed": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                    "repair_claim_admitted": False,
                    "admission_status": "preflight_only",
                    "reason": "Open-SWE traces can seed trace-support materialization after QC, but this preflight admits zero rows.",
                },
                "blocked_reasons": sorted(set(block_reasons)),
                "raw_content_policy": {
                    "raw_patch_emitted": False,
                    "raw_verifier_output_emitted": False,
                    "raw_issue_text_emitted": False,
                },
            }
        )
    if rows:
        return rows
    return build_open_swe_candidates_from_parquet(limit=250)


def patch_paths_from_diff(diff_text: str) -> list[str]:
    paths: list[str] = []
    for match in DIFF_HEADER_RE.finditer(str(diff_text or "")):
        paths.append(match.group(2).strip())
    return list(dict.fromkeys(path for path in paths if path))


def tests_from_text(text: str) -> list[str]:
    values: list[str] = []
    for match in TEST_PATH_RE.finditer(str(text or "")):
        candidate = match.group(1).strip()
        if candidate:
            values.append(candidate)
    return list(dict.fromkeys(values))


def trajectory_meta(trajectory: Any) -> dict[str, Any]:
    if not isinstance(trajectory, list):
        return {
            "turn_count": 0,
            "tool_turn_count": 0,
            "verification_turn_count": 0,
            "selected_tests": [],
            "failure_markers": [],
            "tool_names": [],
        }
    tool_names: list[str] = []
    selected_tests: list[str] = []
    failure_markers: list[str] = []
    verification_turns = 0
    pending_tool_name = ""
    for turn in trajectory:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "")
        if role == "assistant":
            calls = turn.get("tool_calls") or []
            if isinstance(calls, list) and calls:
                fn = ((calls[0] or {}).get("function") or {}) if isinstance(calls[0], dict) else {}
                pending_tool_name = str(fn.get("name") or "")
                if pending_tool_name:
                    tool_names.append(pending_tool_name)
            continue
        if role != "tool":
            continue
        content = str(turn.get("content") or "")
        if pending_tool_name:
            tool_names.append(pending_tool_name)
        if any(marker in content for marker in VERIFY_MARKERS):
            verification_turns += 1
            selected_tests.extend(tests_from_text(content))
            for marker in VERIFY_MARKERS:
                if marker in content:
                    failure_markers.append(marker)
        pending_tool_name = ""
    return {
        "turn_count": len(trajectory),
        "tool_turn_count": sum(1 for turn in trajectory if isinstance(turn, dict) and str(turn.get("role") or "") == "tool"),
        "verification_turn_count": verification_turns,
        "selected_tests": list(dict.fromkeys(selected_tests))[:24],
        "failure_markers": list(dict.fromkeys(failure_markers))[:24],
        "tool_names": list(dict.fromkeys(tool_names))[:24],
    }


def build_open_swe_candidates_from_parquet(*, limit: int) -> list[dict[str, Any]]:
    parquet_files = sorted((OPEN_SWE_ROOT / "data").glob("**/*.parquet")) if OPEN_SWE_ROOT.exists() else []
    rows: list[dict[str, Any]] = []
    try:
        import pyarrow.parquet as pq
    except Exception:
        return rows
    for parquet_path in parquet_files:
        table = pq.read_table(
            parquet_path,
            columns=["instance_id", "repo", "license", "language", "trajectory_id", "trajectory", "model_patch", "resolved", "metadata"],
        )
        for record in table.to_pylist():
            if int(record.get("resolved") or 0) != 1:
                continue
            paths = patch_paths_from_diff(str(record.get("model_patch") or ""))
            if not paths:
                continue
            trace = trajectory_meta(record.get("trajectory"))
            if int(trace.get("verification_turn_count") or 0) == 0:
                continue
            metadata = record.get("metadata") or {}
            block_reasons = [
                "trace_support_only_not_repair_proof",
                "requires_same_source_verifier_causality_qc",
                "requires_raw_trace_to_safe_semantic_transition_extraction",
                "not_strict_or_source_heldout_admissible",
            ]
            if not trace.get("selected_tests"):
                block_reasons.append("verification_signal_without_explicit_test_target")
            rows.append(
                {
                    "stage": STAGE,
                    "record_type": "open_swe_trace_support_preflight_candidate",
                    "candidate_id": f"stage12327::openswe::{stable_id(record.get('instance_id'), record.get('trajectory_id'))}",
                    "source_adapter": "Open-SWE-Traces",
                    "source_record_ref": {
                        "dataset_file": str(parquet_path),
                        "trajectory_family": parquet_path.parent.name,
                        "instance_id": record.get("instance_id"),
                        "trajectory_id": record.get("trajectory_id"),
                    },
                    "repo_family": record.get("repo") or "unknown",
                    "language_family": record.get("language") or infer_language_from_paths(paths),
                    "candidate_type": "trace_support_patch_plus_verify",
                    "seed_path_count": len(paths),
                    "seed_path_hashes": [safe_hash(path)[:16] for path in paths[:12]],
                    "selected_test_count": len(trace.get("selected_tests") or []),
                    "selected_test_hashes": [safe_hash(test)[:16] for test in (trace.get("selected_tests") or [])[:12]],
                    "trace_metadata": {
                        "turn_count": trace.get("turn_count"),
                        "tool_turn_count": trace.get("tool_turn_count"),
                        "verification_turn_count": trace.get("verification_turn_count"),
                        "tool_name_hashes": [safe_hash(name)[:16] for name in trace.get("tool_names") or []],
                        "failure_markers": trace.get("failure_markers") or [],
                        "metadata_category": metadata.get("category"),
                        "metadata_num_modified_files": metadata.get("num_modified_files"),
                        "metadata_num_modified_lines": metadata.get("num_modified_lines"),
                    },
                    "admission": {
                        "training_allowed": False,
                        "train_support_allowed": False,
                        "strict_eval_eligible": False,
                        "source_heldout_admissible": False,
                        "level3_admitted": False,
                        "patch_trace_admitted": False,
                        "repair_claim_admitted": False,
                        "admission_status": "preflight_only",
                        "reason": "Open-SWE traces can seed trace-support materialization after QC, but this preflight admits zero rows.",
                    },
                    "blocked_reasons": sorted(set(block_reasons)),
                    "raw_content_policy": {
                        "raw_patch_emitted": False,
                        "raw_verifier_output_emitted": False,
                        "raw_issue_text_emitted": False,
                        "raw_trajectory_emitted": False,
                    },
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def diff_paths_from_bears(record: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    patch_diff = record.get("patchDiff") or {}
    files = patch_diff.get("files") or {}
    for value in files.values():
        if isinstance(value, dict):
            for key in ("name", "fileName", "path", "oldName", "newName"):
                candidate = str(value.get(key) or "").strip()
                if candidate:
                    paths.append(candidate)
    diff_text = str(record.get("diff") or "")
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                paths.append(parts[3].removeprefix("b/"))
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = path.replace("\\", "/").lstrip("./")
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def selected_tests_from_bears(record: dict[str, Any]) -> list[str]:
    tests = record.get("tests") or {}
    details = tests.get("failureDetails") or []
    out: list[str] = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        test_class = str(detail.get("testClass") or "").strip()
        test_method = str(detail.get("testMethod") or "").strip()
        if test_class and test_method:
            out.append(f"{test_class}::{test_method}")
        elif test_class:
            out.append(test_class)
    return list(dict.fromkeys(out))





def open_swe_priority_candidate(row: dict[str, Any]) -> bool:
    if row.get("source_adapter") != "Open-SWE-Traces":
        return False
    if row.get("language_family") != "python":
        return False
    meta = row.get("trace_metadata") or {}
    if meta.get("metadata_category") != "bug-fix":
        return False
    if int(row.get("seed_path_count") or 0) < 1 or int(row.get("seed_path_count") or 0) > 3:
        return False
    if int(meta.get("metadata_num_modified_lines") or 0) > 80:
        return False
    if int(row.get("selected_test_count") or 0) < 1:
        return False
    markers = set(meta.get("failure_markers") or [])
    if not (markers & {"FAILED", "ERROR", "Traceback", "AssertionError"}):
        return False
    if "PASSED" not in markers:
        return False
    return True


def bears_reproduction_status(record: dict[str, Any]) -> dict[str, Any]:
    reproduction = record.get("reproductionBuggyBuild") or {}
    phases = reproduction.get("reproductionStatus") or {}
    if not isinstance(phases, dict):
        phases = {}
    return {
        "has_reproduction_record": bool(reproduction),
        "phase_names": sorted(phases),
        "phase_status_hash": safe_hash(json.dumps(phases, sort_keys=True))[:16],
    }


def build_bears_candidates() -> list[dict[str, Any]]:
    if not BEARS_BUGS.exists():
        return []
    data = json.loads(BEARS_BUGS.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for record in data:
        bug_type = str(record.get("type") or "unknown")
        repo = record.get("repository") or {}
        commits = record.get("commits") or {}
        buggy_commit = commits.get("buggyBuild") or {}
        fixer_commit = commits.get("fixerBuild") or {}
        paths = diff_paths_from_bears(record)
        selected_tests = selected_tests_from_bears(record)
        block_reasons = [
            "preflight_only_zero_admission",
            "requires_checkout_or_authoritative_command_output_join",
            "requires_same_source_patch_verifier_causality_qc",
            "not_strict_or_source_heldout_admissible",
        ]
        if bug_type != "failing_passing":
            block_reasons.append("not_failing_passing_repair_candidate")
        if not paths:
            block_reasons.append("missing_patch_path_refs")
        if not selected_tests:
            block_reasons.append("missing_failing_test_details")
        candidate_type = "bears_failing_passing_repair_candidate" if bug_type == "failing_passing" else "bears_nonrepair_metadata_candidate"
        rows.append(
            {
                "stage": STAGE,
                "record_type": "bears_repair_preflight_candidate",
                "candidate_id": f"stage12327::bears::{record.get('bugId')}",
                "source_adapter": "RepairThemAll/Bears",
                "source_record_ref": {
                    "bug_id": record.get("bugId"),
                    "benchmark_file": str(BEARS_BUGS),
                    "bug_type": bug_type,
                },
                "repo_family": repo.get("url") or repo.get("name") or "unknown",
                "language_family": infer_language_from_paths(paths) if paths else "java",
                "candidate_type": candidate_type,
                "buggy_commit_sha": buggy_commit.get("sha"),
                "fixer_commit_sha": fixer_commit.get("sha"),
                "buggy_build_id": (record.get("builds") or {}).get("buggyBuild", {}).get("id"),
                "fixer_build_id": (record.get("builds") or {}).get("fixerBuild", {}).get("id"),
                "patch_diff_hash": safe_hash(str(record.get("diff") or ""))[:24],
                "patch_path_count": len(paths),
                "patch_path_hashes": [safe_hash(path)[:16] for path in paths[:12]],
                "selected_test_count": len(selected_tests),
                "selected_test_hashes": [safe_hash(test)[:16] for test in selected_tests[:12]],
                "test_metrics": (record.get("tests") or {}).get("overallMetrics") or {},
                "reproduction_status": bears_reproduction_status(record),
                "admission": {
                    "training_allowed": False,
                    "train_support_allowed": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                    "repair_claim_admitted": False,
                    "admission_status": "preflight_only",
                    "reason": "Bears metadata can seed repair-candidate materialization only after command-output and causality QC.",
                },
                "blocked_reasons": sorted(set(block_reasons)),
                "raw_content_policy": {
                    "raw_patch_emitted": False,
                    "raw_verifier_output_emitted": False,
                    "raw_test_failure_detail_emitted": False,
                },
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    open_swe_candidates = build_open_swe_candidates()
    bears_candidates = build_bears_candidates()
    bears_failing_passing = [row for row in bears_candidates if row.get("source_record_ref", {}).get("bug_type") == "failing_passing"]
    bears_blocked_nonrepair = [row for row in bears_candidates if row.get("source_record_ref", {}).get("bug_type") != "failing_passing"]

    open_swe_priority = [row for row in open_swe_candidates if open_swe_priority_candidate(row)][:50]
    write_jsonl(OUT / "open_swe_trace_support_candidates.jsonl", open_swe_candidates)
    write_jsonl(OUT / "open_swe_priority_capped_trace_support_candidates.jsonl", open_swe_priority)
    write_jsonl(OUT / "bears_failing_passing_candidates.jsonl", bears_failing_passing)
    write_jsonl(OUT / "bears_nonrepair_blocked_candidates.jsonl", bears_blocked_nonrepair)

    summary = {
        "stage": STAGE,
        "decision": "external_adapter_preflight_complete_zero_admission",
        "claim_boundary": "Preflight/source-adapter candidates only. Zero training, strict-eval, source-heldout, Level-3, patch-trace, or repair rows admitted.",
        "training_allowed": False,
        "admitted_rows": 0,
        "open_swe_inventory": open_swe_parquet_inventory(),
        "open_swe_import_artifact": {
            "path": str(OPEN_SWE_IMPORT),
            "exists": OPEN_SWE_IMPORT.exists(),
            "sampled_preflight_candidates": len(open_swe_candidates),
            "priority_capped_candidates": len(open_swe_priority),
            "priority_contract": "Python bug-fix traces, 1-3 changed paths, <=80 modified lines, selected test present, failure+pass markers present; still zero admission.",
            "candidate_type_counts": dict(Counter(row.get("candidate_type") for row in open_swe_candidates)),
            "language_counts": dict(Counter(row.get("language_family") or "unknown" for row in open_swe_candidates)),
            "priority_language_counts": dict(Counter(row.get("language_family") or "unknown" for row in open_swe_priority)),
        },
        "bears_inventory": {
            "path": str(BEARS_BUGS),
            "exists": BEARS_BUGS.exists(),
            "total_records": len(bears_candidates),
            "type_counts": dict(Counter(row.get("source_record_ref", {}).get("bug_type") for row in bears_candidates)),
            "failing_passing_candidates": len(bears_failing_passing),
            "nonrepair_blocked_candidates": len(bears_blocked_nonrepair),
            "language_counts": dict(Counter(row.get("language_family") or "unknown" for row in bears_candidates)),
        },
        "hard_guards": [
            "Open-SWE resolved traces are trace-support only until raw trajectory is converted into safe transition records and causality-audited.",
            "Bears passing_passing rows are blocked from repair-proof counts.",
            "Bears failing_passing rows are still preflight only until command output, checkout lineage, and same-source patch-verifier causality pass.",
            "No raw diff body, raw verifier output, raw issue text, or raw test failure detail emitted in preflight artifacts.",
            "No Stage12327 artifact may satisfy the 500 train-support counter without a later admission stage.",
        ],
        "next_stage_recommendation": {
            "stage": "stage12328_external_adapter_qc_materialization_request",
            "open_swe": "Run capped trace extraction into safe transition-record review candidates; keep as trace-support unless verifier causality and state deltas pass.",
            "bears": "Hydrate failing_passing candidates with authoritative command/build/test output refs; reject passing_passing as repair proof.",
        },
    }
    write_json(OUT / "external_adapter_preflight_summary.json", summary)
    write_json(SUMMARY, summary)
    (OUT / "EXTERNAL_ADAPTER_PREFLIGHT_STAGE12327.md").write_text(
        "# Stage12327 External Adapter Preflight\n\n"
        "This stage profiles Open-SWE trace-support and RepairThemAll/Bears repair-candidate supply. "
        "It intentionally admits zero rows. Later stages must perform command-output QC, same-source causality checks, "
        "anti-leak rendering, and lineage audits before any candidate can count toward training.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
