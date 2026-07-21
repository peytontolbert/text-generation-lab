#!/usr/bin/env python3
"""Build Stage12548 non-BEARS external patch-effect intake artifacts.

This stage only inventories replay evidence already present in local artifacts.
It does not replay, admit, train on, or grant root/repair credit to candidates.
Every proof slot must be structural evidence on one input row; rows and sources
are never joined to complete a proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12548_non_bears_external_patch_effect_intake"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

READY_OUT = OUT / "ready_candidates.jsonl"
BLOCKED_OUT = OUT / "blocked_candidates.jsonl"
CAPACITY_OUT = OUT / "source_capacity_counters.json"

# Fixed inputs make repository runs reproducible and prevent Stage12548 from
# recursively ingesting its own output or arbitrary training projections.
SOURCE_FILES = {
    "stage12280_exact_verifier_candidates": ROOT / "runs/local/artifacts/stage12280_external_normalized_verifier_identity_selector/normalized_exact_verifier_candidates.jsonl",
    "stage12286_patch_effect_candidates": ROOT / "runs/local/artifacts/stage12286_external_repair_replay_smoke_executor/patch_effect_PE2_candidates.jsonl",
    "stage12288_patch_effect_candidates": ROOT / "runs/local/artifacts/stage12288_external_repair_replay_second_smoke_executor/patch_effect_PE2_candidates.jsonl",
    "stage12292_patch_effect_candidates": ROOT / "runs/local/artifacts/stage12292_after_pass_eligible_before_fail_patch_effect_replay/patch_effect_PE2_candidates.jsonl",
    "stage12386_candidate_only": ROOT / "runs/local/artifacts/stage12386_transition_local_event_joiner_gap_audit/candidate_only.jsonl",
    "stage12386_level3_control": ROOT / "runs/local/artifacts/stage12386_transition_local_event_joiner_gap_audit/level3_control_complete.jsonl",
    "stage12445_external_return": ROOT / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/returns/external_repair_trace_fail_to_pass_adapter.return.jsonl",
    "stage12445_level3_candidates": ROOT / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/admitted_level3_candidates.jsonl",
    "stage12468_accepted_refs": ROOT / "runs/local/artifacts/stage12468_non_bears_patch_effect_private_return_validator/accepted_return_ref_index.jsonl",
    "stage12468_rejected_refs": ROOT / "runs/local/artifacts/stage12468_non_bears_patch_effect_private_return_validator/rejected_return_ref_index.jsonl",
    "stage12514_causal_revalidation": ROOT / "runs/local/artifacts/stage12514_causal_proof_revalidation_gate/causal_proof_revalidation_records.jsonl",
}
CONTAMINATION_MANIFESTS = (
    ROOT / "runs/local/artifacts/stage12037_scratchpad_contamination_exclusion_audit/scratchpad_excluded_keys.jsonl",
    ROOT / "runs/local/artifacts/stage12040_training_data_scratchpad_contamination_gate/training_scratchpad_excluded_keys.jsonl",
    ROOT / "runs/local/artifacts/stage8672_locked_benchmark_pack_manifest/locked_benchmark_packs.jsonl",
    ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json",
    ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl",
)
LOCKED_MANIFEST_MARKERS = ("stage8672_", "stage9718_", "stage12105_")
SOURCE_PROVENANCE_CLASSES = {
    "stage12286_patch_effect_candidates": "direct_external_replay",
    "stage12288_patch_effect_candidates": "direct_external_replay",
    "stage12292_patch_effect_candidates": "direct_external_replay",
    "stage12514_causal_revalidation": "causal_revalidation_of_direct_external_replay",
    "unit_structural_external_trace": "test_only_structural_external_trace",
}

REQUIRED_SLOTS = (
    "immutable_repo_task_lineage",
    "real_patch_diff",
    "patch_apply_success",
    "identical_immutable_verifier",
    "immutable_test_tree",
    "patch_does_not_modify_tests",
    "observed_before_fail",
    "observed_after_pass",
    "revert_restores_failure",
    "chronological_same_source_linkage",
    "nonfixture_nonsynthetic_external_origin",
    "source_adapter_positive_provenance",
    "no_environment_or_dependency_failure",
    "contamination_manifest_clear",
)
TARGET_LANGUAGES = {"c_cpp", "rust"}
FAIL_VALUES = {"fail", "failed", "failing", "failure"}
PASS_VALUES = {"pass", "passed", "passing", "success"}
APPLY_SUCCESS_VALUES = {"applied", "pass", "passed", "success", "succeeded"}
PLACEHOLDERS = {"", "unknown", "none", "null", "todo", "tbd", "placeholder", "claimed", "n/a"}
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$", re.IGNORECASE)
DIFF_HEADER_RE = re.compile(r"(?m)^diff --git a/.+ b/.+$")
DIFF_HUNK_RE = re.compile(r"(?m)^@@ .+ @@")
DIFF_CHANGE_RE = re.compile(r"(?m)^[+-](?![+-]{2} ).+")


def norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def object_at(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def is_digest(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(SHA_RE.fullmatch(text) or re.fullmatch(r"[a-z][a-z0-9_]*_[0-9a-f]{20,64}", text, re.I))


def identity_group(name: str) -> str | None:
    lowered = name.lower().replace("-", "_")
    if "repo" in lowered or "repository" in lowered:
        return "repo"
    if "task" in lowered or "instance" in lowered or "request" in lowered:
        return "task"
    if "commit" in lowered or lowered in {"before", "after", "checkout_before", "checkout_after"}:
        return "commit"
    if "patch" in lowered or "diff" in lowered:
        return "patch"
    if "verifier" in lowered or "harness" in lowered or "test_id" in lowered:
        return "verifier"
    if "root" in lowered or "lineage" in lowered:
        return "root"
    if "row_id" in lowered:
        return "row"
    return None


def normalized_identity_values(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    values = {text}
    repo = text
    repo = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", repo)
    repo = re.sub(r"^git@github\.com:", "", repo)
    repo = repo.removesuffix(".git").strip("/")
    if repo != text:
        values.add(repo)
    for item in list(values):
        if "/" in item:
            values.add(item.replace("/", "__"))
        if "__" in item and item.count("__") == 1:
            values.add(item.replace("__", "/"))
    return values


def canonical_overlap_keys(name: str, value: Any) -> set[str]:
    group = identity_group(name)
    if group is None:
        return set()
    return {f"{group}:{item}" for item in normalized_identity_values(value)}


def normalize_explicit_overlap_key(value: Any) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set()
    if ":" not in text:
        return {f"opaque:{item}" for item in normalized_identity_values(text)}
    name, payload = text.split(":", 1)
    keys = canonical_overlap_keys(name, payload)
    return keys or {f"opaque:{item}" for item in normalized_identity_values(text)}


def normalize_manifest_key_set(values: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(normalize_explicit_overlap_key(value))
    return result


def language_of(row: dict[str, Any]) -> str:
    value = norm(first(row, "language_family", "language_family_label", "language"))
    aliases = {"cpp": "c_cpp", "c++": "c_cpp", "c": "c_cpp", "c_cpp": "c_cpp", "rust": "rust"}
    return aliases.get(value, value)


def immutable_lineage(row: dict[str, Any]) -> tuple[bool, str | None, dict[str, str]]:
    lineage = object_at(row, "lineage") or object_at(row, "source_lineage")
    repo = first(lineage, "repo_id", "repository_id", "repo_family_digest") or first(row, "repo_id", "repository_id", "repo_family_digest")
    task = first(lineage, "task_id", "task_id_hash", "request_id") or first(row, "task_id", "task_id_hash", "request_id")
    before = first(lineage, "before_commit", "commit_before", "commit_before_digest", "checkout_before") or first(row, "before_commit", "commit_before_digest")
    after = first(lineage, "after_commit", "commit_after", "commit_after_digest", "checkout_after") or first(row, "after_commit", "commit_after_digest")
    values = {"repo": str(repo or ""), "task": str(task or ""), "before": str(before or ""), "after": str(after or "")}
    ok = all(norm(value) not in PLACEHOLDERS for value in values.values()) and is_digest(repo) and is_digest(task) and is_digest(before) and is_digest(after) and before != after
    root = stable_hash({"repo": repo, "task": task}) if ok else None
    return ok, root, values


def real_diff(row: dict[str, Any]) -> bool:
    patch = object_at(row, "patch")
    diff = first(patch, "diff", "patch_diff") or first(row, "patch_diff", "diff")
    if not isinstance(diff, str):
        return False
    return bool(DIFF_HEADER_RE.search(diff) and DIFF_HUNK_RE.search(diff) and DIFF_CHANGE_RE.search(diff))


def event(row: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            return value
    return {}


def event_position(value: dict[str, Any]) -> tuple[str, Any] | None:
    index = first(value, "event_index", "sequence", "ordinal")
    if isinstance(index, (int, float)) and not isinstance(index, bool):
        return ("index", index)
    timestamp = first(value, "timestamp", "observed_at", "timestamp_utc")
    if isinstance(timestamp, str) and timestamp.strip():
        return ("timestamp", timestamp.strip())
    return None


def immutable_verifier_identity(value: dict[str, Any]) -> dict[str, str] | None:
    identity = object_at(value, "identity")
    if not identity:
        identity = value
    test_id = first(identity, "test_id_hash", "selected_test_digest")
    harness = first(identity, "harness_digest", "verifier_digest", "command_digest", "verifier_identity_hash")
    if not is_digest(test_id) or not is_digest(harness):
        return None
    return {"test_id_hash": str(test_id), "harness_digest": str(harness)}


def changed_paths_from_diff(row: dict[str, Any]) -> list[str]:
    patch = object_at(row, "patch")
    diff = first(patch, "diff", "patch_diff") or first(row, "patch_diff", "diff")
    if not isinstance(diff, str):
        return []
    return re.findall(r"(?m)^diff --git a/(.+?) b/(.+?)$", diff)


def patch_changes_tests(row: dict[str, Any]) -> bool:
    test_re = re.compile(r"(^|/)(tests?|testing|fixtures?|snapshots?)(/|$)|(?:^|/)test_[^/]+|_test\.", re.I)
    return any(test_re.search(path) for pair in changed_paths_from_diff(row) for path in pair)


def immutable_test_tree(row: dict[str, Any]) -> bool:
    before = first(row, "test_tree_before_hash", "immutable_test_tree_before_hash")
    after = first(row, "test_tree_after_hash", "immutable_test_tree_after_hash")
    return is_digest(before) and before == after


def provenance_passes(row: dict[str, Any]) -> bool:
    provenance = object_at(row, "provenance")
    source_kind = norm(first(provenance, "source_kind", "origin") or first(row, "source_kind", "origin"))
    external = provenance.get("external") is True or source_kind in {"external", "external_repository", "external_real_repository", "external_or_other_repo"}
    non_bears = provenance.get("bears") is False or row.get("is_bears") is False or norm(first(row, "benchmark", "source_benchmark")) not in {"bears", "bears_benchmark"}
    fixture_false = provenance.get("fixture") is False and provenance.get("synthetic") is False
    real_positive = provenance.get("real_repository") is True or source_kind in {"external_real_repository", "external_repository"}
    return external and non_bears and fixture_false and real_positive


def environment_passes(row: dict[str, Any]) -> bool:
    environment = object_at(row, "environment")
    return environment.get("failure") is False and environment.get("dependency_failure") is False


def candidate_contamination_keys(row: dict[str, Any], lineage_values: dict[str, str], root: str | None) -> set[str]:
    result: set[str] = set()
    keys = row.get("contamination_keys")
    if isinstance(keys, list):
        for value in keys:
            result.update(normalize_explicit_overlap_key(value))
    if root:
        result.update(canonical_overlap_keys("root_id", root))
    for name, value in lineage_values.items():
        if value:
            result.update(canonical_overlap_keys(name, value))
    for name in ("instance_id", "task_id", "repo", "repository", "patch_sha256", "verifier_identity_hash"):
        if row.get(name) not in (None, ""):
            result.update(canonical_overlap_keys(name, row[name]))
    return result


def evaluate_candidate(
    row: dict[str, Any],
    manifest_keys: set[str],
    manifest_loaded: bool = True,
    source_name: str = "unknown",
) -> dict[str, Any]:
    """Evaluate one structural bundle without importing evidence from another row."""
    lineage_ok, root, lineage_values = immutable_lineage(row)
    before = event(row, "verifier_before", "before_verifier")
    apply = event(row, "patch_apply", "apply_event") or object_at(object_at(row, "patch"), "apply")
    after = event(row, "verifier_after", "after_verifier")
    revert = event(row, "verifier_after_revert", "revert_verifier")

    before_identity = immutable_verifier_identity(before)
    after_identity = immutable_verifier_identity(after)
    revert_identity = immutable_verifier_identity(revert)
    same_verifier = before_identity is not None and before_identity == after_identity == revert_identity
    before_fail = before.get("observed") is True and norm(first(before, "status", "result")) in FAIL_VALUES
    after_pass = after.get("observed") is True and norm(first(after, "status", "result")) in PASS_VALUES
    revert_fail = revert.get("observed") is True and norm(first(revert, "status", "result")) in FAIL_VALUES
    apply_success = apply.get("observed") is True and norm(first(apply, "status", "result")) in APPLY_SUCCESS_VALUES

    positions = [event_position(value) for value in (before, apply, after, revert)]
    source_ids = [first(value, "source_id_hash", "trace_id_hash") for value in (before, apply, after, revert)]
    chronological = bool(
        all(position is not None for position in positions)
        and len({position[0] for position in positions if position}) == 1
        and positions[0][1] < positions[1][1] < positions[2][1] < positions[3][1]  # type: ignore[index]
        and all(is_digest(value) for value in source_ids)
        and len({str(value) for value in source_ids}) == 1
    )

    contamination_keys = candidate_contamination_keys(row, lineage_values, root)
    normalized_manifest_keys = normalize_manifest_key_set(manifest_keys) | set(manifest_keys)
    intersection = sorted(contamination_keys & normalized_manifest_keys)
    contamination_clear = manifest_loaded and bool(contamination_keys) and not intersection
    slots = {
        "immutable_repo_task_lineage": lineage_ok,
        "real_patch_diff": real_diff(row),
        "patch_apply_success": apply_success,
        "identical_immutable_verifier": same_verifier,
        "immutable_test_tree": immutable_test_tree(row),
        "patch_does_not_modify_tests": bool(changed_paths_from_diff(row)) and not patch_changes_tests(row),
        "observed_before_fail": before_fail,
        "observed_after_pass": after_pass,
        "revert_restores_failure": revert_fail,
        "chronological_same_source_linkage": chronological,
        "nonfixture_nonsynthetic_external_origin": provenance_passes(row),
        "source_adapter_positive_provenance": source_name in SOURCE_PROVENANCE_CLASSES,
        "no_environment_or_dependency_failure": environment_passes(row),
        "contamination_manifest_clear": contamination_clear,
    }
    missing = [slot for slot in REQUIRED_SLOTS if not slots[slot]]
    return {
        "canonical_root_id": root,
        "language_family": language_of(row),
        "ready": not missing,
        "proof_slots": slots,
        "missing_slots": missing,
        "contamination_key_count": len(contamination_keys),
        "contamination_manifest_intersection": intersection,
        "verifier_identity_hash": stable_hash(before_identity) if same_verifier else None,
        "training_allowed": False,
        "admission_allowed": False,
        "root_credit": 0,
    }


def _public_result(source: str, row_number: int, evaluated: dict[str, Any], duplicate_count: int) -> dict[str, Any]:
    return {
        "record_type": "stage12548_ready_candidate_v1" if evaluated["ready"] else "stage12548_blocked_candidate_v1",
        "candidate_ref": stable_hash({"source": source, "row": row_number}),
        "source_name": source,
        "source_row_number": row_number,
        "canonical_root_id": evaluated["canonical_root_id"],
        "canonical_root_materialization_count": duplicate_count,
        "language_family": evaluated["language_family"],
        "proof_slots": evaluated["proof_slots"],
        "missing_slots": evaluated["missing_slots"],
        "contamination_key_count": evaluated["contamination_key_count"],
        "contamination_manifest_intersection": evaluated["contamination_manifest_intersection"],
        "verifier_identity_hash": evaluated["verifier_identity_hash"],
        "replay_intake_only": True,
        "training_allowed": False,
        "admission_allowed": False,
        "root_credit": 0,
    }


def build_intake(sources: dict[str, list[dict[str, Any]]], manifest_keys: set[str], manifest_loaded: bool = True) -> dict[str, Any]:
    capacities: dict[str, Counter[str]] = defaultdict(Counter)
    grouped: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    for source, rows in sorted(sources.items()):
        capacities[source]["rows_seen"] = len(rows)
        for row_number, row in enumerate(rows, 1):
            language = language_of(row)
            if language not in TARGET_LANGUAGES:
                capacities[source]["non_target_language_rows"] += 1
                continue
            evaluated = evaluate_candidate(row, manifest_keys, manifest_loaded, source)
            capacities[source]["target_language_candidates"] += 1
            key = evaluated["canonical_root_id"] or f"unresolved:{source}:{row_number}"
            grouped[key].append((source, row_number, evaluated))

    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for key in sorted(grouped):
        options = sorted(grouped[key], key=lambda item: (len(item[2]["missing_slots"]), item[0], item[1]))
        source, row_number, evaluated = options[0]
        output = _public_result(source, row_number, evaluated, len(options))
        (ready if evaluated["ready"] else blocked).append(output)
        capacities[source]["ready_canonical_roots" if evaluated["ready"] else "blocked_canonical_roots"] += 1
        for duplicate_source, _, _ in options[1:]:
            capacities[duplicate_source]["duplicate_materializations"] += 1

    capacity_rows = []
    for source in sorted(sources):
        counts = capacities[source]
        capacity_rows.append({"source_name": source, **{key: counts[key] for key in (
            "rows_seen", "target_language_candidates", "non_target_language_rows",
            "ready_canonical_roots", "blocked_canonical_roots", "duplicate_materializations",
        )}})
    return {"ready": ready, "blocked": blocked, "capacity": capacity_rows}


def _manifest_objects(path: Path) -> list[Any]:
    if path.suffix == ".jsonl":
        return read_jsonl(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else [value]


def _collect_manifest_keys(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        for name, child in value.items():
            if isinstance(child, (str, int)) and child not in (None, ""):
                lowered = name.lower()
                if lowered == "exclusion_key":
                    keys.update(normalize_explicit_overlap_key(child))
                elif identity_group(name) is not None or "hash" in lowered or "digest" in lowered:
                    keys.update(canonical_overlap_keys(name, child))
            _collect_manifest_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _collect_manifest_keys(child, keys)


def load_contamination_manifest(paths: Iterable[Path]) -> tuple[set[str], list[str], list[str]]:
    keys: set[str] = set()
    loaded: list[str] = []
    locked_loaded: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        relative = str(path.relative_to(ROOT))
        loaded.append(relative)
        if any(marker in relative for marker in LOCKED_MANIFEST_MARKERS):
            locked_loaded.append(relative)
        for value in _manifest_objects(path):
            _collect_manifest_keys(value, keys)
    return keys, loaded, locked_loaded


def main() -> int:
    sources = {name: read_jsonl(path) for name, path in SOURCE_FILES.items()}
    manifest_keys, loaded_manifests, locked_manifests = load_contamination_manifest(CONTAMINATION_MANIFESTS)
    result = build_intake(sources, manifest_keys, bool(locked_manifests))
    write_jsonl(READY_OUT, result["ready"])
    write_jsonl(BLOCKED_OUT, result["blocked"])
    write_json(CAPACITY_OUT, {
        "record_type": "stage12548_source_capacity_counters_v1",
        "sources": result["capacity"],
        "totals": {
            "ready_canonical_roots": len(result["ready"]),
            "blocked_canonical_roots": len(result["blocked"]),
            "target_language_candidate_rows": sum(row["target_language_candidates"] for row in result["capacity"]),
        },
    })
    summary = {
        "stage": STAGE,
        "decision": "ready_candidates_materialized_replay_intake_only" if result["ready"] else "blocked_no_structurally_complete_replay_candidates",
        "ready_candidate_count": len(result["ready"]),
        "blocked_candidate_count": len(result["blocked"]),
        "required_proof_slots": list(REQUIRED_SLOTS),
        "contamination_manifests_loaded": loaded_manifests,
        "locked_or_sealed_manifests_loaded": locked_manifests,
        "contamination_manifest_key_count": len(manifest_keys),
        "cross_row_or_source_evidence_join_allowed": False,
        "canonical_root_dedupe_applied": True,
        "replay_performed_by_stage": False,
        "training_allowed": False,
        "admission_allowed": False,
        "root_credit": 0,
        "repair_credit": 0,
        "artifacts": {
            "ready_candidates": str(READY_OUT.relative_to(ROOT)),
            "blocked_candidates": str(BLOCKED_OUT.relative_to(ROOT)),
            "source_capacity_counters": str(CAPACITY_OUT.relative_to(ROOT)),
        },
    }
    write_json(SUMMARY, summary)
    print(SUMMARY.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
