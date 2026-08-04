#!/usr/bin/env python3
"""Build the Stage12591 static external causal-replay execution request."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12591_external_source_native_causal_replay_microbatch_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
PRIVATE_REPOSITORY_BASE = Path("/arxiv/repositories")

INPUTS = {
    "commit_seed_evidence": ROOT / "runs/local/artifacts/external_repo_commit_family_scale_v2/commit_episode_seeds.jsonl",
    "public_lane_worklist": ROOT / "runs/local/artifacts/stage12459_external_comparable_patch_effect_source_preflight/public_lane_ref_worklist.jsonl",
    "independent_root_ledger": ROOT / "runs/local/artifacts/stage12547_authoritative_independent_root_ledger/authoritative_independent_root_ledger.jsonl",
    "anti_collapse_contract": ROOT / "runs/local/artifacts/stage12489_anti_collapse_dataset_generation_contract/anti_collapse_dataset_generation_contract.json",
    "research_spine": ROOT / "runs/local/artifacts/stage12195_central_graph_integration/central_graph_integration_report.json",
    "future_eval_denylist": ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json",
    "stage12583_summary": ROOT / "runs/local/artifacts/stage12583_causal_episode_microfactory/summary.json",
    "stage12584_summary": ROOT / "runs/local/artifacts/stage12584_biome_causal_replay/summary.json",
}
PINNED_INPUT_SHA256 = {
    "commit_seed_evidence": "9f919b4cef72609b6ab2e065ddf77aa740c367cddcd64eed10b8fb95ddce0a20",
    "public_lane_worklist": "d3359b928de077bed56e48cda95c7021c38f7c8eff00e5a749cfd29e67a17239",
    "independent_root_ledger": "3c16c25fe2deb2d2b6deba1ed3bcf0066730ff757fe925c5b331d9cbb57a76bc",
    "anti_collapse_contract": "b7be39552342150eb11a9b37ce4a530c074ccdb2cb33c013934ce4a8260ceda0",
    "research_spine": "53e11976dae4cf81260dd914f7789959871fcbcb76efe2be1339353636652fdb",
    "future_eval_denylist": "1dc55b537a85f1033a842d337ff6bb6124fe0315e62aba520dea3ddc69f860a0",
    "stage12583_summary": "19ec339efd0d1abc3bd63e5d908eab5fc278062bf66bf8bc0da3dc5917aa9cd9",
    "stage12584_summary": "17856f3e9a5d43003d8740b2c7e4715ca910b830ddc97111475781b40216826d",
}

# Every declaration is an exact existing row in the pinned commit-seed evidence.
# The extra dirty declaration is retained to prove exclusion rather than padding.
DECLARATIONS = (
    ("rust_cpp", "Fuser", "dee9885fc6e108dea80d46d577e5a51579d99be5"),
    ("rust_cpp", "arrow", "9cb051b72326135b5094b82d1771a4331284541d"),
    ("rust_cpp", "benchmark", "2948b6a2e61ccabecc952c24794c6960d86c9ed6"),
    ("rust_cpp", "binaryen", "4b03c3a357a0dee7f39286db8b087ab9d9895847"),
    ("rust_cpp", "qdrant", "2db8e1c7ff6b4588082f370c9e8a56e8f44c49b6"),
    ("rust_cpp", "uv", "3723315ee615b1ae7fa9b136ca0df608c32d6092"),
    ("rust_cpp", "wasm-tools", "e6317b4f33aa5867ee902623f5e57cfea0733035"),
    ("rust_cpp", "axum", "5b52bcdcfa7143d755c27d0df43e19754a3f3a0d"),
    ("rust_cpp", "datafusion", "a27f030d5829a4460e87dbb8d2a6382c8f9ecd4f"),
    ("python", "pytest", "d2466e3a9655f75d25719bcc4510cdbcb39cf10d"),
    ("python", "flask", "06ea505ce2b2042af26e96d35ebf159af7c0869d"),
    ("python", "networkx", "09d4ebed4fce80a6833017c9c2bdbb931a6fa87b"),
    ("python", "scipy", "8bdcd4de49ef87f47c86ba8bbc5de3e07f8eaf67"),
    ("python", "django", "b461519bf5973d7fc149560d2f99acdba71a437d"),
    ("python", "sympy", "8381f0c42956f60caed72aedb2ca4e82420b9992"),
    ("python", "mctx", "b2e09add697294c2793506b8be074b128b166286"),
    ("python", "openai-agents-python", "09f0ed45e7177c340789f7946b2b14903b1c7d31"),
    ("js_ts_jvm", "angular", "a849b6fbfd8ee7e6122ca8d21b862096160e98c7"),
    ("js_ts_jvm", "axios", "a446b39b19c8b570214a4158520c5ddd5b020366"),
    ("js_ts_jvm", "eslint", "f291007cb73f55c09cf3c2aa3a405df379a5c594"),
    ("js_ts_jvm", "express", "18e5985b8a9d5e8423db0a9121f22bdaecd5b120"),
    ("js_ts_jvm", "jest", "55529e87d25e07849eadbba154846f4febac2902"),
    ("js_ts_jvm", "playwright", "32883517ffe7725ef45ac2dc020a63962c27d7a3"),
    ("js_ts_jvm", "promptfoo", "ad1ad354f87da934d763d4c937376a678aa3551c"),
    ("js_ts_jvm", "table", "516ab678183af3ebf80cda67d27f262dba549d39"),
)
TARGET_BUCKET_COUNTS = {"rust_cpp": 8, "python": 8, "js_ts_jvm": 8}
REQUEST_BUCKET_COUNTS = {"rust_cpp": 4, "python": 4, "js_ts_jvm": 4}

REQUEST_SLOTS = (
    "same_row_source_commit_tree_lineage",
    "frozen_before_state",
    "complete_filesystem_closure_before",
    "focused_verifier_fail",
    "exact_patch_apply",
    "identical_focused_verifier_pass",
    "after_state",
    "complete_filesystem_closure_after",
    "no_undeclared_mutation",
    "final_verifier_last_outcome_affecting_action",
    "changed_test_relevance",
    "environment_capture",
    "continue_disposition_unless_completion_separately_proved",
)
FILESYSTEM_SNAPSHOT_KINDS = (
    "tracked", "untracked", "ignored", "symlink", "mode", "index", "lock", "generated"
)
STOP_CODES = (
    "MAX_12_ATTEMPTS", "FEWER_THAN_3_OF_FIRST_6_PROOF_COMPLETE",
    "PROTECTED_IDENTITY_OVERLAP", "TWO_ENV_FAILURES_PER_ADAPTER", "NETWORK_REQUIRED",
    "VERIFIER_DRIFT", "HIDDEN_MUTATION", "CHANGED_TEST_IRRELEVANCE",
)
FORBIDDEN_KEYS = re.compile(
    r"(^|_)(admission|candidate_action|causal_candidate|observed_action|observed_outcome|result_based_rank|projection|rank_score|raw_path|training_row|authority)($|_)"
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TEST_MARKER = re.compile(r"(^|/)(test|tests|spec|specs)(/|_)|\.(test|spec)\.", re.I)
SOURCE_SUFFIXES = {
    "rust_cpp": (".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"),
    "python": (".py",),
    "js_ts_jvm": (".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts"),
}
MANIFEST_NAMES = {
    "rust_cpp": ("Cargo.toml", "CMakeLists.txt", "meson.build", "BUILD", "BUILD.bazel"),
    "python": ("pyproject.toml", "setup.cfg", "setup.py", "tox.ini"),
    "js_ts_jvm": ("package.json", "pom.xml", "build.gradle", "build.gradle.kts", "WORKSPACE", "WORKSPACE.bazel"),
}


class GateError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GateError(f"malformed_jsonl:{path.name}:{number}") from exc
            if not isinstance(row, dict):
                raise GateError(f"non_object_jsonl:{path.name}:{number}")
            yield row


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *args), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=30,
    )
    if check and result.returncode:
        raise GateError("git_metadata_unavailable")
    return result.stdout.rstrip("\n")


def pin_inputs() -> dict[str, str]:
    observed = {}
    for name, path in INPUTS.items():
        if not path.is_file():
            raise GateError(f"pinned_input_missing:{name}")
        observed[name] = sha256_bytes(path.read_bytes())
        if observed[name] != PINNED_INPUT_SHA256[name]:
            raise GateError(f"pinned_input_hash_mismatch:{name}")
    return observed


def source_rows() -> dict[tuple[str, str], tuple[dict[str, Any], str]]:
    wanted = {(repo, commit) for _, repo, commit in DECLARATIONS}
    found: dict[tuple[str, str], tuple[dict[str, Any], str]] = {}
    for row in iter_jsonl(INPUTS["commit_seed_evidence"]):
        key = (str(row.get("repo_id", "")), str(row.get("metadata", {}).get("commit_sha", "")))
        if key not in wanted:
            continue
        if key in found:
            raise GateError("duplicate_authoritative_seed_row")
        found[key] = (row, sha256_bytes(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()))
    if set(found) != wanted:
        raise GateError("declared_seed_row_missing")
    return found


def protected_identities() -> set[str]:
    deny = json.loads(INPUTS["future_eval_denylist"].read_text(encoding="utf-8"))["deny"]
    protected = {str(value).casefold() for values in deny.values() for value in values}
    for row in iter_jsonl(INPUTS["independent_root_ledger"]):
        for key in ("canonical_identity", "repo_family_hash"):
            if row.get(key):
                protected.add(str(row[key]).casefold())
        for key in ("root_aliases", "lineage_aliases"):
            protected.update(str(value).casefold() for value in row.get(key, []))
    return protected


def _repo_ref(repo: str) -> str:
    return "executor_repo_" + stable_hash(repo.casefold())[:24]


def _strip_seed_prefix(repo: str, path: str) -> str:
    prefix = repo + "/"
    return path[len(prefix):] if path.startswith(prefix) else path


def verifier_evidence(bucket: str, before: str, changed: Sequence[str], tree_files: set[str]) -> tuple[str, str]:
    test_files = sorted(
        path for path in changed if TEST_MARKER.search(path) and path.casefold().endswith(SOURCE_SUFFIXES[bucket])
    )
    baseline_tests = [path for path in test_files if path in tree_files]
    if not baseline_tests:
        raise GateError("focused_verifier_not_present_in_before_tree")
    manifests = sorted(path for path in tree_files if Path(path).name in MANIFEST_NAMES[bucket])
    if not manifests:
        raise GateError("repository_native_verifier_manifest_missing")
    adapter = {
        "rust_cpp": "cargo_or_native_build_focused_test_v1",
        "python": "python_pytest_focused_file_v1",
        "js_ts_jvm": "package_or_jvm_focused_test_v1",
    }[bucket]
    identity = stable_hash([adapter, before, baseline_tests[0], manifests[0]])
    return adapter, identity


def validate_declaration(
    declaration: tuple[str, str, str], seed: tuple[dict[str, Any], str], protected: set[str]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    bucket, repo_name, after = declaration
    reject_base = {
        "record_type": "stage12591_preflight_exclusion_v1",
        "repo_family": repo_name,
        "bucket": bucket,
        "source_evidence_ref": "seed_" + seed[1][:24],
        "training_allowed": False,
    }
    try:
        if repo_name.casefold() in {"agentkernel-seq2seq-text-lab", "parameter-golf"}:
            raise GateError("self_repo")
        repo = PRIVATE_REPOSITORY_BASE / repo_name
        if not repo.is_dir() or git(repo, "rev-parse", "--is-inside-work-tree") != "true":
            raise GateError("checkout_unavailable")
        if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
            raise GateError("checkout_dirty")
        parents = git(repo, "show", "-s", "--format=%P", after).split()
        if len(parents) != 1:
            raise GateError("merge_or_nonadjacent_commit")
        before = parents[0]
        before_tree = git(repo, "rev-parse", f"{before}^{{tree}}")
        after_tree = git(repo, "rev-parse", f"{after}^{{tree}}")
        if not all(HEX40.fullmatch(value) for value in (before, after, before_tree, after_tree)):
            raise GateError("commit_tree_lineage_missing")
        changed = sorted(filter(None, git(repo, "diff", "--name-only", before, after).splitlines()))
        seed_paths = {_strip_seed_prefix(repo_name, str(change["path"])) for change in seed[0].get("changes", [])}
        if not changed or set(changed) != seed_paths:
            raise GateError("seed_commit_diff_drift")
        tests = [path for path in changed if TEST_MARKER.search(path)]
        production = [
            path for path in changed
            if path.casefold().endswith(SOURCE_SUFFIXES[bucket]) and not TEST_MARKER.search(path)
        ]
        if not tests or not production:
            raise GateError("dependency_docs_generated_or_test_only_change")
        tree_files = set(git(repo, "ls-tree", "-r", "--name-only", before).splitlines())
        adapter, verifier_ref = verifier_evidence(bucket, before, changed, tree_files)
        identity = stable_hash([repo_name.casefold(), before, after, before_tree, after_tree])
        overlap_tokens = {repo_name.casefold(), before, after, identity}
        if overlap_tokens & protected:
            raise GateError("protected_or_stage12547_overlap")
        record = {
            "record_type": "stage12591_static_universe_candidate_v1",
            "candidate_id": "stage12591_pair_" + identity[:24],
            "repo_family": repo_name,
            "repo_executor_ref": _repo_ref(repo_name),
            "bucket": bucket,
            "source_evidence_ref": "seed_" + seed[1][:24],
            "lineage": {
                "before_commit_sha256": sha256_bytes(before.encode()),
                "after_commit_sha256": sha256_bytes(after.encode()),
                "before_tree_sha256": sha256_bytes(before_tree.encode()),
                "after_tree_sha256": sha256_bytes(after_tree.encode()),
                "adjacent_single_parent": True,
                "same_row_frozen": True,
            },
            "changed_file_count": len(changed),
            "changed_test_file_count": len(tests),
            "changed_production_file_count": len(production),
            "focused_verifier_adapter": adapter,
            "focused_verifier_ref": verifier_ref,
            "structural_priority": [len(changed), -len(tests), repo_name.casefold()],
            "pre_outcome_evidence_only": True,
            "training_allowed": False,
        }
        return record, None
    except (GateError, OSError, subprocess.TimeoutExpired) as exc:
        reject = dict(reject_base)
        reject["reason"] = str(exc) or type(exc).__name__
        return None, reject


def select_requests(universe: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    seen_repos: set[str] = set()
    for bucket in TARGET_BUCKET_COUNTS:
        rows = sorted(
            (row for row in universe if row["bucket"] == bucket),
            key=lambda row: (row["structural_priority"], row["candidate_id"]),
        )
        for row in rows:
            repo = str(row["repo_family"]).casefold()
            if repo in seen_repos:
                continue
            selected.append(row)
            seen_repos.add(repo)
            if sum(item["bucket"] == bucket for item in selected) == REQUEST_BUCKET_COUNTS[bucket]:
                break
    if len(selected) > 12:
        raise GateError("request_cap_exceeded")
    counts = Counter(str(row["bucket"]) for row in selected)
    expected = Counter(REQUEST_BUCKET_COUNTS)
    if counts != expected:
        raise GateError(f"exact_request_slots_unavailable:{dict(counts)}")
    requests = []
    for slot, row in enumerate(selected, 1):
        requests.append({
            "record_type": "stage12591_attempt_request_v1",
            "request_slot": slot,
            "request_id": f"stage12591_request_{slot:02d}",
            "candidate_id": row["candidate_id"],
            "repo_family": row["repo_family"],
            "repo_executor_ref": row["repo_executor_ref"],
            "bucket": row["bucket"],
            "source_evidence_ref": row["source_evidence_ref"],
            "lineage": row["lineage"],
            "focused_verifier_adapter": row["focused_verifier_adapter"],
            "focused_verifier_ref": row["focused_verifier_ref"],
            "required_return_slots": list(REQUEST_SLOTS),
            "filesystem_closure": {
                "snapshot_kinds": list(FILESYSTEM_SNAPSHOT_KINDS),
                "declared_cache_allowlist_required": True,
                "all_nonallowlisted_deltas_forbidden": True,
            },
            "repo_wide_tests_secondary_only": True,
            "repo_wide_tests_causal_credit": False,
            "generic_pass_to_pass_forbidden": True,
            "observed_action_imitation_forbidden": True,
            "sealed_pre_outcome_actions_required": True,
            "completion_default": "CONTINUE",
            "training_allowed": False,
        })
    return requests


def request_contract() -> dict[str, Any]:
    return {
        "record_type": "stage12591_microbatch_request_contract_v1",
        "mode": "PREFLIGHT_REQUEST_ONLY",
        "maximum_attempts": 12,
        "required_return_slots": list(REQUEST_SLOTS),
        "filesystem_closure": {
            "snapshot_kinds": list(FILESYSTEM_SNAPSHOT_KINDS),
            "declared_cache_allowlist_required": True,
            "tracked_index_and_worktree_compared": True,
            "symlink_target_and_mode_compared": True,
            "lock_and_generated_state_compared": True,
        },
        "stop_codes": list(STOP_CODES),
        "first_six_minimum_proof_complete": 3,
        "environment_failure_limit_per_adapter": 2,
        "network_allowed": False,
        "repo_wide_tests_secondary_only": True,
        "repo_wide_tests_causal_credit": False,
        "emit_attempt_requests_only": True,
        "completion_default": "CONTINUE",
        "training_allowed": False,
    }


def assert_public_schema(value: Any, key: str = "") -> None:
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            folded = str(child_key).casefold()
            if FORBIDDEN_KEYS.search(folded) or folded in {"command", "patch", "output", "source_path"}:
                raise GateError(f"forbidden_public_key:{child_key}")
            assert_public_schema(child, folded)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_public_schema(child, key)
    elif isinstance(value, str):
        if value.startswith("/") or "\\" in value or "://" in value:
            raise GateError(f"raw_public_value:{key}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(temporary, path)


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    observed_hashes = pin_inputs()
    seeds = source_rows()
    protected = protected_identities()
    universe, exclusions = [], []
    for declaration in DECLARATIONS:
        record, rejection = validate_declaration(declaration, seeds[(declaration[1], declaration[2])], protected)
        if record:
            universe.append(record)
        if rejection:
            exclusions.append(rejection)
    ids = [row["candidate_id"] for row in universe]
    repos = [str(row["repo_family"]).casefold() for row in universe]
    if len(ids) != len(set(ids)) or len(repos) != len(set(repos)):
        raise GateError("universe_dedupe_or_repo_cap_failed")
    bucket_counts = Counter(row["bucket"] for row in universe)
    deficits = {bucket: max(0, target - bucket_counts[bucket]) for bucket, target in TARGET_BUCKET_COUNTS.items()}
    requests = select_requests(universe) if not any(deficits.values()) else []
    summary = {
        "stage": STAGE,
        "status": "REQUEST_READY" if requests else "UNIVERSE_DEFICIT_NO_REQUEST",
        "mode": "PREFLIGHT_REQUEST_ONLY",
        "declared_evidence_rows": len(DECLARATIONS),
        "actual_universe_count": len(universe),
        "target_universe_count": 24,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "bucket_deficits": deficits,
        "repo_family_count": len(set(repos)),
        "minimum_nonself_repo_families": 12,
        "request_count": len(requests),
        "request_bucket_counts": dict(sorted(Counter(row["bucket"] for row in requests).items())),
        "excluded_count": len(exclusions),
        "excluded_reason_counts": dict(sorted(Counter(row["reason"] for row in exclusions).items())),
        "pinned_input_sha256": observed_hashes,
        "no_padding": True,
        "execution_performed": False,
        "network_performed": False,
        "repository_tests_performed": False,
        "training_allowed": False,
    }
    assert_public_schema([universe, exclusions, requests, request_contract(), summary])
    return universe, exclusions, requests, summary


def execute(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    universe, exclusions, requests, summary = build()
    write_jsonl(out / "static_universe.jsonl", universe)
    write_jsonl(out / "preflight_exclusions.jsonl", exclusions)
    write_jsonl(out / "attempt_requests.jsonl", requests)
    write_json(out / "request_contract.json", request_contract())
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(execute(), sort_keys=True))
