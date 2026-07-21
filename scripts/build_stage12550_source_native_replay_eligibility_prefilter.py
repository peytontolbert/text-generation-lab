#!/usr/bin/env python3
"""Build the Stage12550 source-native replay eligibility prefilter.

This stage emits replay requests, never replay results or admission evidence.
Candidate-authored trace claims and prior-stage readiness flags are ignored.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12550_source_native_replay_eligibility_prefilter"
INPUT = ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
ELIGIBLE_OUT = OUT / "eligible_replay_requests.jsonl"
BLOCKED_OUT = OUT / "blocked_candidates.jsonl"
RECOVERY_OUT = OUT / "recovery_worklist.jsonl"
OUT_SUMMARY = OUT / "summary.json"
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CAP = 250

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
DIFF_HEADER_RE = re.compile(r"(?m)^diff --git a/(.+?) b/(.+?)$")
HUNK_RE = re.compile(r"(?m)^@@ .+ @@")
SHELL_CONTROL_RE = re.compile(r"(?:&&|\|\||[|;<>`]|\$\(|\n)")
EXIT_MARKER_RE = re.compile(r"(?:exit(?: code)?|status)\s*[:=]?\s*-?\d+", re.I)
TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|testing|fixtures?|snapshots?|__snapshots__|harness)(/|$)"
    r"|(^|/)test_[^/]+|_test\.[^/]+$|\.snap$|\.golden$",
    re.I,
)
CONFIG_PATH_RE = re.compile(
    r"(^|/)(Cargo\.toml|Cargo\.lock|build\.rs|Makefile|CMakeLists\.txt|meson\.build|"
    r"package(?:-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|pyproject\.toml|tox\.ini|"
    r"pytest\.ini|\.github|\.gitlab-ci\.yml|BUILD|WORKSPACE)(/|$)",
    re.I,
)
INLINE_RUST_TEST_RE = re.compile(r"(?m)^\+\s*#\s*\[\s*(?:tokio::)?test(?:\s*\([^]]*\))?\s*\]")

EXT_LANGUAGE = {
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".go": "go", ".rs": "rust", ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".java": "java", ".kt": "kotlin", ".rb": "ruby",
}
LANGUAGE_ALIASES = {"c_cpp": {"c", "cpp"}, "c++": {"cpp"}, "golang": {"go"}}
ZERO_FLAGS = {
    "training_allowed": False,
    "admission_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("\\", "/")
    text = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", text)
    text = re.sub(r"^git@github\.com:", "", text).removesuffix(".git").strip("/")
    if "__" in text and "/" not in text:
        text = text.replace("__", "/", 1)
    return text if text.count("/") == 1 else None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: expected object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_identity(row: dict[str, Any], dataset_file: str | None = None) -> tuple[str, str, str]:
    ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else row
    return (
        str(ref.get("instance_id") or ""),
        str(ref.get("trajectory_id") or ""),
        str(dataset_file or ref.get("dataset_file") or ""),
    )


def upstream_task_identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("source_adapter") or "Open-SWE-Traces"), str(row.get("instance_id") or "")


def changed_paths(diff: Any) -> list[str]:
    if not isinstance(diff, str):
        return []
    return sorted({path for pair in DIFF_HEADER_RE.findall(diff) for path in pair})


def derive_languages(paths: Iterable[str], verifier: dict[str, Any]) -> set[str]:
    languages = {EXT_LANGUAGE[Path(path).suffix.lower()] for path in paths if Path(path).suffix.lower() in EXT_LANGUAGE}
    argv = " ".join(str(item).lower() for item in verifier.get("argv", []) if isinstance(item, (str, int)))
    commands = {
        "cargo": "rust", "rustc": "rust", "go": "go", "pytest": "python", "python": "python",
        "node": "javascript", "npm": "javascript", "jest": "javascript", "mvn": "java", "gradle": "java",
    }
    first = argv.split(maxsplit=1)[0].rsplit("/", 1)[-1] if argv else ""
    if first in commands:
        languages.add(commands[first])
    return languages


def metadata_language_matches(metadata: Any, derived: set[str]) -> bool:
    label = str(metadata or "").strip().lower().replace("-", "_")
    expected = LANGUAGE_ALIASES.get(label, {label})
    return bool(label and derived and derived <= expected)


def _observation_valid(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("authoritative") is not True:
        return False
    argv = value.get("argv")
    cwd = value.get("cwd")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        return False
    if not isinstance(cwd, str) or not cwd or any(SHELL_CONTROL_RE.search(item) for item in argv):
        return False
    if argv[0].rsplit("/", 1)[-1] in {"sh", "bash", "zsh", "dash", "cmd", "powershell"}:
        return False
    markers = value.get("exit_markers")
    if not isinstance(markers, list) or len(markers) != 1 or not isinstance(markers[0], int):
        return False
    if value.get("exit_code") != markers[0]:
        return False
    output = value.get("output")
    return not isinstance(output, str) or len(EXIT_MARKER_RE.findall(output)) <= 1


def _base_record(preflight: dict[str, Any], source: dict[str, Any] | None, reasons: list[str]) -> dict[str, Any]:
    identity = source_identity(preflight)
    return {
        "record_type": "stage12550_source_native_replay_prefilter_v1",
        "candidate_id": preflight.get("candidate_id"),
        "source_native_identity": {"instance_id": identity[0], "trajectory_id": identity[1], "dataset_file": identity[2]},
        "source_row_sha256": stable_hash(source) if source is not None else None,
        "blocking_reasons": sorted(set(reasons)),
        "prefilter_only": True,
        **ZERO_FLAGS,
    }


def _full_digest(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or ""), re.I))


def trajectory_mutates_verifier_surface(source: dict[str, Any]) -> bool:
    trajectory = source.get("trajectory")
    if not isinstance(trajectory, list):
        return False
    for turn in trajectory:
        if not isinstance(turn, dict):
            continue
        texts: list[str] = []
        if isinstance(turn.get("content"), str):
            texts.append(turn["content"])
        calls = turn.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                arguments = function.get("arguments") if isinstance(function, dict) else None
                if isinstance(arguments, str):
                    texts.append(arguments)
        for text in texts:
            paths = changed_paths(text)
            if any(TEST_PATH_RE.search(path) or CONFIG_PATH_RE.search(path) for path in paths):
                return True
            if INLINE_RUST_TEST_RE.search(text):
                return True
    return False


def executor_bundle_valid(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    baseline = evidence.get("baseline_verifier")
    before = evidence.get("before")
    after = evidence.get("after")
    return bool(
        evidence.get("content_addressed") is True
        and isinstance(evidence.get("executor_id"), str) and evidence["executor_id"]
        and _full_digest(evidence.get("bundle_sha256"))
        and _full_digest(evidence.get("event_chain_sha256"))
        and isinstance(baseline, dict)
        and baseline.get("authoritative") is True
        and baseline.get("preexisting_at_base") is True
        and baseline.get("candidate_authored") is False
        and _full_digest(baseline.get("verifier_blob_sha256"))
        and _full_digest(baseline.get("verifier_closure_sha256"))
        and _observation_valid(before)
        and _observation_valid(after)
        and _full_digest(before.get("event_sha256") if isinstance(before, dict) else None)
        and _full_digest(after.get("event_sha256") if isinstance(after, dict) else None)
    )


def checkout_binding_valid(checkout: Any, base_commit: Any) -> bool:
    return bool(
        isinstance(checkout, dict)
        and checkout.get("exists") is True
        and checkout.get("commit_object_verified") is True
        and checkout.get("upstream_remote_verified") is True
        and checkout.get("commit") == base_commit
        and FULL_SHA_RE.fullmatch(str(checkout.get("commit", "")))
        and isinstance(checkout.get("repo_root"), str)
        and str(checkout["repo_root"]).startswith("/")
        and _full_digest(checkout.get("clean_tree_sha256"))
    )


def evaluate_candidate(
    preflight: dict[str, Any],
    source: dict[str, Any] | None,
    *,
    executor_evidence: dict[str, Any] | None = None,
    protected_identities: set[str] | None = None,
    protected_universe_available: bool = False,
    checkout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one source binding; semantic blockers outrank recoverable gaps."""
    recovery: list[str] = []
    reasons: list[str] = []
    if source is None:
        recovery.append("exact_source_parquet_row_unavailable")
        record = _base_record(preflight, source, recovery)
        record.update({"disposition": "recovery_only", "recovery_actions": recovery})
        return record

    if source_identity(preflight)[:2] != source_identity(source)[:2]:
        reasons.append("exact_source_row_identity_mismatch")
    if any(source.get(name) not in (None, False, "", {}, []) for name in (
        "replay", "ready", "causal_proof", "admission_allowed", "training_allowed",
    )):
        reasons.append("candidate_or_prior_stage_replay_claim_not_authoritative")

    base_commit = source.get("base_commit")
    if not isinstance(base_commit, str) or not FULL_SHA_RE.fullmatch(base_commit):
        recovery.append("authoritative_source_base_commit_missing")
    if not checkout_binding_valid(checkout, base_commit):
        recovery.append("local_checkout_or_commit_binding_missing")

    diff = source.get("model_patch")
    paths = changed_paths(diff)
    if not isinstance(diff, str) or not paths or not HUNK_RE.search(diff):
        reasons.append("complete_production_diff_missing")
    if any(TEST_PATH_RE.search(path) for path in paths) or (isinstance(diff, str) and INLINE_RUST_TEST_RE.search(diff)):
        reasons.append("test_fixture_snapshot_or_inline_test_mutation")
    if any(CONFIG_PATH_RE.search(path) for path in paths):
        reasons.append("build_manifest_lockfile_or_harness_config_mutation")
    if trajectory_mutates_verifier_surface(source):
        reasons.append("candidate_trajectory_mutates_verifier_surface")

    evidence = executor_evidence
    if evidence is None:
        recovery.append("content_addressed_executor_evidence_missing")
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
    elif not executor_bundle_valid(evidence):
        reasons.append("content_addressed_executor_evidence_invalid_or_self_attested")
        before = evidence.get("before") if isinstance(evidence.get("before"), dict) else {}
        after = evidence.get("after") if isinstance(evidence.get("after"), dict) else {}
    else:
        before = evidence["before"]
        after = evidence["after"]
        if before["argv"] != after["argv"] or before["cwd"] != after["cwd"]:
            reasons.append("canonical_direct_argv_or_cwd_mismatch")
        if before["exit_code"] == 0 or after["exit_code"] != 0:
            reasons.append("authoritative_fail_then_pass_not_observed")

    verifier = before if executor_bundle_valid(evidence) else {}
    derived = derive_languages(paths, verifier)
    if len(derived) != 1:
        reasons.append("changed_file_and_verifier_language_unresolved_or_conflicting")
    elif not metadata_language_matches(preflight.get("language_family"), derived):
        reasons.append("metadata_language_mismatch")

    task_key = "::".join(upstream_task_identity(source))
    if not protected_universe_available:
        recovery.append("protected_open_swe_swe_rebench_universe_unavailable")
    elif not protected_identities:
        reasons.append("protected_universe_identity_set_empty_or_missing")
    elif task_key in protected_identities:
        reasons.append("protected_universe_overlap_detected")

    all_reasons = sorted(set(reasons + recovery))
    record = _base_record(preflight, source, all_reasons)
    record.update({
        "source_metadata_language": source.get("language"),
        "preflight_language_family": preflight.get("language_family"),
        "derived_languages": sorted(derived),
        "changed_paths": paths,
        "canonical_repo": canonical_repo(source.get("repo")),
        "model_patch_sha256": hashlib.sha256(diff.encode()).hexdigest() if isinstance(diff, str) else None,
        "source_dataset_file_sha256": source.get("dataset_file_sha256"),
        "source_row_index_zero_based": source.get("source_row_index_zero_based"),
    })
    identity = record.get("source_native_identity")
    if isinstance(identity, dict):
        identity["dataset_file_sha256"] = source.get("dataset_file_sha256")
        identity["row_index_zero_based"] = source.get("source_row_index_zero_based")
    if recovery:
        record["recovery_actions"] = sorted(set(recovery))
    if reasons:
        record["disposition"] = "blocked"
        return record
    if recovery:
        record["disposition"] = "recovery_only"
        return record
    record["blocking_reasons"] = ["stage12551_authoritative_git_resolution_required"]
    record["recovery_actions"] = ["stage12551_authoritative_git_resolution_required"]
    record["disposition"] = "recovery_only"
    return record

def build_prefilter(
    preflight_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    *,
    executor_evidence: dict[tuple[str, str, str], dict[str, Any]] | None = None,
    protected_identities: set[str] | None = None,
    protected_universe_available: bool = False,
    checkouts: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    sources: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        sources[source_identity(row)].append(row)
    task_materializations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        task_materializations[upstream_task_identity(row)].append(row)

    eligible: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    recovery: list[dict[str, Any]] = []
    seen_tasks: set[tuple[str, str]] = set()
    for preflight in preflight_rows[:CAP]:
        identity = source_identity(preflight)
        matches = sources.get(identity, [])
        task = (str(preflight.get("source_adapter") or "Open-SWE-Traces"), identity[0])
        materializations = task_materializations.get(task, [])
        if task in seen_tasks:
            continue
        seen_tasks.add(task)
        if len(matches) != 1 or len(materializations) != 1:
            reason = "source_native_duplicate_conflicting_rows" if len({stable_hash(row) for row in materializations}) > 1 else "exact_source_row_match_count_not_one"
            row = _base_record(preflight, matches[0] if len(matches) == 1 else None, [reason])
            row["disposition"] = "blocked"
            blocked.append(row)
            continue
        source = matches[0]
        result = evaluate_candidate(
            preflight, source,
            executor_evidence=(executor_evidence or {}).get(identity),
            protected_identities=protected_identities,
            protected_universe_available=protected_universe_available,
            checkout=(checkouts or {}).get(task),
        )
        {"eligible_replay_request": eligible, "blocked": blocked, "recovery_only": recovery}[result["disposition"]].append(result)
    return {"eligible": eligible, "blocked": blocked, "recovery": recovery}


def _load_exact_source_rows(preflight_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in preflight_rows[:CAP]:
        instance, trajectory, dataset = source_identity(row)
        wanted[dataset].add((instance, trajectory))
    output: list[dict[str, Any]] = []
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        return output
    for filename, identities in wanted.items():
        path = Path(filename)
        if not path.is_file():
            continue
        parquet = pq.ParquetFile(path)
        dataset_digest = file_sha256(path)
        global_index = 0
        for group in range(parquet.num_row_groups):
            for row in parquet.read_row_group(group).to_pylist():
                if (str(row.get("instance_id") or ""), str(row.get("trajectory_id") or "")) in identities:
                    row["dataset_file"] = filename
                    row["dataset_file_sha256"] = dataset_digest
                    row["source_row_index_zero_based"] = global_index
                    output.append(row)
                global_index += 1
    return output


def main() -> int:
    preflight = read_jsonl(INPUT)[:CAP]
    sources = _load_exact_source_rows(preflight)
    # No candidate-authored or Stage12548 replay objects are loaded here.
    result = build_prefilter(preflight, sources)
    write_jsonl(ELIGIBLE_OUT, result["eligible"])
    write_jsonl(BLOCKED_OUT, result["blocked"])
    write_jsonl(RECOVERY_OUT, result["recovery"])
    counts = Counter(reason for kind in ("blocked", "recovery") for row in result[kind] for reason in row["blocking_reasons"])
    all_output = result["eligible"] + result["blocked"] + result["recovery"]
    dataset_counts = Counter(source_identity(row)[2] or "missing" for row in preflight)
    preflight_language_counts = Counter(str(row.get("language_family") or "missing") for row in preflight)
    derived_language_counts = Counter(
        "+".join(row.get("derived_languages") or ["unresolved"])
        for row in all_output
    )
    summary = {
        "stage": STAGE,
        "input_candidates_capped": len(preflight),
        "exact_source_rows_loaded": len(sources),
        "eligible_replay_request_count": len(result["eligible"]),
        "blocked_candidate_count": len(result["blocked"]),
        "recovery_worklist_count": len(result["recovery"]),
        "reason_counts": dict(sorted(counts.items())),
        "input_dataset_file_counts": dict(sorted(dataset_counts.items())),
        "input_unique_dataset_file_count": len(dataset_counts),
        "max_single_dataset_file_fraction": (
            max(dataset_counts.values()) / len(preflight) if preflight else 0.0
        ),
        "preflight_language_family_counts": dict(sorted(preflight_language_counts.items())),
        "derived_language_counts": dict(sorted(derived_language_counts.items())),
        "protected_universe_available": False,
        "candidate_or_stage12548_readiness_trusted": False,
        **ZERO_FLAGS,
    }
    write_json(OUT_SUMMARY, summary)
    write_json(SUMMARY, summary)
    print(SUMMARY.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
