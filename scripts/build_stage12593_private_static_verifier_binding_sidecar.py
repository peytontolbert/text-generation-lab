#!/usr/bin/env python3
"""Build fail-closed, non-executing Stage12593 verifier bindings."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12593_private_static_verifier_binding_sidecar"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REPOSITORY_BASE = Path("/arxiv/repositories")
S91_SCRIPT = ROOT / "scripts/build_stage12591_external_source_native_causal_replay_microbatch_preflight.py"
S91_UNIVERSE = ROOT / "runs/local/artifacts/stage12591_external_source_native_causal_replay_microbatch_preflight/static_universe.jsonl"
S47_LEDGER = ROOT / "runs/local/artifacts/stage12547_authoritative_independent_root_ledger/authoritative_independent_root_ledger.jsonl"
S47_SCRIPT = ROOT / "scripts/build_stage12547_authoritative_independent_root_ledger.py"
IDENTITY_GUARD = ROOT / "scripts/source_lineage_guard.py"
DENYLIST = ROOT / "configs/software_maintainer/future_eval_identity_denylist_v1.json"
PAIR_IDS = ("stage12591_pair_8f267d19b0a689e098db219f", "stage12591_pair_f70d9d0ce802945219904e1e")
TEST_MARKER = re.compile(r"(^|/)(test|tests|testing|spec|specs)(/|_)|\.(test|spec)\.", re.I)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SNAPSHOT_COMPONENTS = ("tracked", "untracked", "ignored", "paths", "types", "contents", "modes", "symlinks", "index", "submodules", "locks", "generated")
OUTCOMES = {
    "initial": [1, "EXPECTED_BEHAVIORAL_FAILURE"], "patched": [0, "PASS"],
    "final": [1, "EXPECTED_BEHAVIORAL_FAILURE"], "blocker_exit_codes": [2, 3, 4, 5],
    "initial_final_normalized_failure_fingerprint_equal": True,
}
FILESYSTEM_SPEC = {
    "version": "canonical_filesystem_closure_v2", "root": "exact_worktree_cwd",
    "entry_fields": ["path", "type", "mode", "content_sha256_or_symlink_target"],
    "volatile_fields_excluded": ["atime", "ctime", "mtime", "birthtime", "uid", "gid", "inode"],
    "git_evidence": ["status_porcelain_v2_z", "ls_files_stage_z", "untracked_z", "ignored_z", "submodule_status_recursive"],
    "required_components": list(SNAPSHOT_COMPONENTS), "final_digest_must_equal_initial": True,
}
FINGERPRINT_SPEC = {
    "version": "pytest_failure_fingerprint_v1", "digest": "sha256_canonical_json",
    "inputs": ["sorted_failed_node_ids", "exception_type", "normalized_failure_text"],
    "normalization": ["replace_execution_root", "replace_hex_addresses", "replace_durations", "normalize_newlines", "strip_trailing_space"],
}
PRIVATE_SPECS = {
    PAIR_IDS[0]: {"repo_name": "pytest", "after": "d2466e3a9655f75d25719bcc4510cdbcb39cf10d", "before": "4904d2ba80c3532037fc1d5360ac6faf30b93f2f", "production": "src/_pytest/_io/pprint.py", "test": "testing/io/test_pprint.py", "selector": "TestPformatLines", "python_suffix": "src", "module_prefixes": ("src/pytest/", "src/_pytest/"), "dependencies": ("pytest", "iniconfig", "packaging", "pluggy", "pygments"), "methods": ("test_no_budget_matches_pformat_splitlines", "test_under_budget_is_complete_and_a_prefix", "test_line_budget_stops_early", "test_char_budget_stops_early", "test_nested_element_respects_line_budget", "test_nested_dataclass_element_respects_line_budget", "test_sized_non_iterable_does_not_raise")},
    PAIR_IDS[1]: {"repo_name": "networkx", "after": "09d4ebed4fce80a6833017c9c2bdbb931a6fa87b", "before": "bc2ba5f087d291ead6c05568c12dc3551baada16", "production": "networkx/readwrite/pajek.py", "test": "networkx/readwrite/tests/test_pajek.py", "selector": "TestPajek::test_quotes_and_backslashes_roundtrip", "python_suffix": "", "module_prefixes": ("networkx/",), "dependencies": ("pytest",), "methods": ("test_quotes_and_backslashes_roundtrip",)},
}
TRUSTED_RUNNER_BLOCKERS = (
    "trusted_runner_recomputation_missing",
    "exact_patched_state_sole_delta_proof_missing",
    "measured_read_only_test_tree_checkpoint_missing",
    "per_node_pytest_report_and_raw_output_digest_missing",
    "phase_isolated_writable_state_closure_missing",
    "immediate_namespace_revalidation_missing",
)

class GateError(RuntimeError): pass
def sha256_bytes(v: bytes) -> str: return hashlib.sha256(v).hexdigest()
def sha256_file(p: Path) -> str: return sha256_bytes(p.read_bytes())
def stable_hash(v: Any) -> str: return sha256_bytes(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())
def opaque_ref(k: str, v: Any) -> str: return f"{k}_{stable_hash(v)[:24]}"

def no_claim_fields():
    return {
        "candidate_use_scope": "development_train_support_only",
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "authorizes_execution": False,
        "execution_performed": False,
        "execution_allowed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader: raise GateError(f"implementation_unavailable:{path.name}")
    module = importlib.util.module_from_spec(spec)
    had_previous = name in sys.modules
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if had_previous:
            sys.modules[name] = previous
        else:
            sys.modules.pop(name, None)
        raise
    return module

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict): raise GateError(f"non_object_jsonl:{path.name}:{number}")
            rows.append(row)
    return rows

def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text("".join(json.dumps(dict(r), sort_keys=True) + "\n" for r in rows))

def git(repo: Path, *args: str, binary=False):
    r = subprocess.run(("git", "-C", str(repo), *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if r.returncode: raise GateError(f"git_metadata_failure:{repo.name}:{args[0]}")
    return r.stdout if binary else r.stdout.decode().rstrip("\n")

def entry(repo: Path, commit: str, path: str):
    m = re.fullmatch(r"([0-7]{6}) (blob|tree) ([0-9a-f]{40,64})\t(.+)", str(git(repo, "ls-tree", commit, "--", path)))
    if not m or m.group(4) != path: raise GateError(f"missing_path:{repo.name}:{path}")
    return m.group(1), m.group(2), m.group(3)
def blob(repo: Path, oid: str) -> bytes: return bytes(git(repo, "cat-file", "blob", oid, binary=True))

def tree_manifest(repo: Path, commit: str, predicate) -> list[dict[str, Any]]:
    rows = []
    for item in bytes(git(repo, "ls-tree", "-rz", "-r", commit, binary=True)).rstrip(b"\0").split(b"\0"):
        if not item: continue
        meta, raw_path = item.split(b"\t", 1); mode, kind, oid = meta.decode().split(); path = raw_path.decode()
        if predicate(path):
            data = blob(repo, oid); rows.append({"path": path, "mode": mode, "type": kind, "blob_oid": oid, "sha256": sha256_bytes(data), "byte_count": len(data)})
    return sorted(rows, key=lambda r: r["path"].encode())

def file_fact(path: Path, display=None):
    p = path.resolve(strict=True); s = p.stat()
    return {"path": display or str(p), "resolved_path": str(p), "mode": f"{stat.S_IMODE(s.st_mode):04o}", "sha256": sha256_file(p), "byte_count": s.st_size}

def distribution_manifest(name: str):
    try: dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError as e: raise GateError(f"missing_distribution:{name}") from e
    if dist.files is None: raise GateError(f"dependency_manifest_unavailable:{name}")
    rows = []
    for rel in sorted(dist.files, key=lambda x: str(x).encode()):
        p = Path(dist.locate_file(rel))
        if p.is_symlink(): rows.append({"path": str(rel), "type": "symlink", "mode": f"{stat.S_IMODE(p.lstat().st_mode):04o}", "target": os.readlink(p)})
        elif p.is_file():
            f = file_fact(p, str(rel)); f.pop("resolved_path"); rows.append(f)
        else: raise GateError(f"dependency_file_unreadable:{name}:{rel}")
    return {"name": name.casefold(), "version": dist.version, "metadata_root": str(Path(dist._path).resolve()), "files": rows, "manifest_sha256": stable_hash(rows), "file_count": len(rows)}

def namespace_input_pins():
    s47, s91 = load_module("s47pins", S47_SCRIPT), load_module("s91pins", S91_SCRIPT)
    paths = {"stage12547_implementation": S47_SCRIPT, "stage12547_ledger": S47_LEDGER, "stage12591_implementation": S91_SCRIPT, "stage12591_static_universe": S91_UNIVERSE, "identity_guard": IDENTITY_GUARD, "future_denylist": DENYLIST}
    paths.update({f"stage12547_source:{k}": Path(v) for k, v in s47.SOURCE_FILES.items()}); paths.update({f"stage12547_materialized:{k}": Path(v) for k, v in s47.MATERIALIZED_FILES.items()}); paths.update({f"stage12591_input:{k}": Path(v) for k, v in s91.INPUTS.items()})
    rows = []
    for name, path in sorted(paths.items()):
        if not path.is_file(): raise GateError(f"namespace_input_missing:{name}")
        digest = sha256_file(path); key = name.removeprefix("stage12591_input:")
        if key in s91.PINNED_INPUT_SHA256 and digest != s91.PINNED_INPUT_SHA256[key]: raise GateError(f"stage12591_pin_drift:{key}")
        rows.append({"name": name, "path": str(path.resolve()), "sha256": digest})
    return {"files": rows, "file_count": len(rows), "manifest_sha256": stable_hash(rows)}

def namespace_data():
    s47, guard = load_module("s47identity", S47_SCRIPT), load_module("identity_guard", IDENTITY_GUARD)
    tokens, repo_hashes = set(), set()
    for row in read_jsonl(S47_LEDGER):
        roots, lineages = s47.identity_tokens(row); tokens.update(v.casefold() for v in roots + lineages)
        if row.get("canonical_identity"): tokens.add("canonical:" + str(row["canonical_identity"]).strip().casefold())
        if row.get("repo_family_hash") not in (None, "", "unknown"): repo_hashes.add(str(row["repo_family_hash"]).strip().casefold())
    try: deny = guard.load_future_eval_identity_denylist(DENYLIST)
    except ValueError as e: raise GateError("denylist_not_canonicalizable") from e
    return tokens, repo_hashes, {k: set(v) for k, v in deny.items()}, guard._normalize_identity

def clearance(repo: Path, before: str, after: str, ns, pins):
    tokens, repo_hashes, deny, normalize = ns
    family, source = normalize("repo_family", repo.name), normalize("source_path", str(repo.resolve()))
    roots = {normalize("root_identity", before), normalize("root_identity", after)}
    if not family or not source or any(not x for x in roots): raise GateError("identity_canonicalization_failed")
    candidates = {*(f"root:{x}" for x in roots), *(f"lineage:{x}" for x in roots), *(f"canonical:{x}" for x in roots)}
    forms = {sha256_bytes(family.encode())[:24], stable_hash(family)[:24]}
    overlaps, hash_overlaps = sorted(candidates & tokens), sorted(forms & repo_hashes)
    future = (["repo_family"] if family in deny.get("repo_family", set()) else []) + (["source_path"] if source in deny.get("source_path", set()) else []) + (["root_identity"] if roots & deny.get("root_identity", set()) else [])
    return {"normalizer_sha256": sha256_file(IDENTITY_GUARD), "canonical_repo_family": family, "canonical_source_path": source, "canonical_roots": sorted(roots), "candidate_tokens": sorted(candidates), "candidate_repo_hash_forms": sorted(forms), "stage12547_overlaps": overlaps, "stage12547_repository_hash_overlaps": hash_overlaps, "future_denylist_overlaps": future, "namespace_input_manifest_sha256": pins["manifest_sha256"], "clear": not (overlaps or hash_overlaps or future)}

def node_ids(data: bytes, fixture: str, selector: str, methods):
    parts = selector.split("::")
    if len(parts) not in (1, 2) or not all(parts): raise GateError("selector_malformed")
    class_name = parts[0]; classes = [n for n in ast.parse(data).body if isinstance(n, ast.ClassDef) and n.name == class_name]
    if len(classes) != 1: raise GateError("selector_class_not_unique")
    observed = [n.name for n in classes[0].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
    selected = observed
    if len(parts) == 2:
        method_name = parts[1]
        selected = [name for name in observed if name == method_name]
        if len(selected) != 1 or selected != list(methods): raise GateError("selected_method_drift")
    elif observed != list(methods):
        raise GateError("static_node_manifest_drift")
    return [f"{fixture}::{class_name}::{method}" for method in selected]

def protocol_rows(binding):
    p, ref = binding["binding_payload"], binding["binding_ref"]
    events = (("establish_network_disabled_mount_namespace", None), ("materialize_before_worktree_and_read_only_test_mounts", None), ("capture_initial_filesystem_digest", None), ("integrity_before_initial_verifier", "i"), ("run_initial_verifier", "initial"), ("integrity_after_initial_verifier", "i"), ("integrity_before_patch", "i"), ("apply_exact_production_patch", "p"), ("integrity_after_patch", "i"), ("integrity_before_patched_verifier", "i"), ("run_patched_verifier", "patched"), ("integrity_after_patched_verifier", "i"), ("integrity_before_revert", "i"), ("revert_exact_production_patch", "p"), ("integrity_after_revert", "i"), ("integrity_before_final_verifier", "i"), ("run_final_verifier", "final"), ("integrity_after_final_verifier", "i"), ("capture_final_filesystem_digest_and_compare", None))
    rows = []
    for order, (action, kind) in enumerate(events, 1):
        row = {"order": order, "action": action, "binding_ref": ref}
        if kind == "i": row.update({"test_manifest_sha256": p["frozen_tests"]["manifest_sha256"], "fixture_sha256": p["fixture"]["sha256"], "block_on_mismatch": True})
        elif kind == "p": row.update({"production_patch_sha256": p["production_patch"]["sha256"], "test_mounts_read_only": True})
        elif kind: row.update({"pytest_exit_code": OUTCOMES[kind][0], "classification": OUTCOMES[kind][1], "expected_node_count": p["expected_node_count"], "expected_node_ids_sha256": stable_hash(p["expected_node_ids"])})
        rows.append(row)
    return rows

def make_binding(pair_id, source, spec, ns, pins):
    repo, before, after = REPOSITORY_BASE / spec["repo_name"], spec["before"], spec["after"]
    if git(repo, "rev-parse", "HEAD") != after or git(repo, "show", "-s", "--format=%P", after).split() != [before]: raise GateError(f"checkout_or_parent_drift:{repo.name}")
    bt, at = git(repo, "show", "-s", "--format=%T", before), git(repo, "show", "-s", "--format=%T", after)
    lineage = source["lineage"]; checks = {"before_commit": sha256_bytes(before.encode()) == lineage["before_commit_sha256"], "after_commit": sha256_bytes(after.encode()) == lineage["after_commit_sha256"], "before_tree": sha256_bytes(bt.encode()) == lineage["before_tree_sha256"], "after_tree": sha256_bytes(at.encode()) == lineage["after_tree_sha256"]}
    if not all(checks.values()): raise GateError("stage12591_pin_mismatch")
    changed = [{"status": line.split("\t", 1)[0], "path": line.split("\t", 1)[1]} for line in git(repo, "diff-tree", "--no-commit-id", "--name-status", "-r", before, after).splitlines()]
    if {r["path"] for r in changed} != {spec["production"], spec["test"]} or any(r["status"] != "M" for r in changed): raise GateError("unexpected_commit_split")
    patch = bytes(git(repo, "diff", "--binary", before, after, "--", spec["production"], binary=True)); bp, ap = entry(repo, before, spec["production"]), entry(repo, after, spec["production"])
    tm, tk, toid = entry(repo, after, spec["test"]); test_data = blob(repo, toid); cb, ca = entry(repo, before, "pyproject.toml"), entry(repo, after, "pyproject.toml")
    if cb != ca or tk != "blob": raise GateError("fixture_or_config_not_immutable")
    frozen = tree_manifest(repo, before, lambda p: bool(TEST_MARKER.search(p))); modules = tree_manifest(repo, before, lambda p: any(p.startswith(x) for x in spec["module_prefixes"]))
    base = f"/tmp/{STAGE}/{pair_id}"; worktree, fixture_root = f"{base}/worktree", f"{base}/fixture"; fixture = f"{fixture_root}/{Path(spec['test']).name}"; selector = f"{fixture}::{spec['selector']}"; nodes = node_ids(test_data, fixture, spec["selector"], spec["methods"])
    python = Path(sys.executable).resolve(strict=True); bwrap, gitexe = shutil.which("bwrap"), shutil.which("git"); blockers = []
    if not bwrap: blockers.append("network_namespace_executable_missing")
    if not gitexe: blockers.append("git_executable_missing")
    deps = []
    try: deps = [distribution_manifest(x) for x in spec["dependencies"]]
    except GateError as e: blockers.append(str(e))
    py_path = worktree + (f"/{spec['python_suffix']}" if spec["python_suffix"] else "")
    if repo.name == "pytest":
        main = next((r for r in modules if r["path"] == "src/pytest/__main__.py"), None); resolved_module = ({"method": "PYTHONPATH_local", "path": f"{py_path}/pytest/__main__.py", "blob_oid": main["blob_oid"], "sha256": main["sha256"]} if main else {})
    else:
        found = importlib.util.find_spec("pytest"); resolved_module = file_fact(Path(found.origin)) if found and found.origin else {}
    if not resolved_module: blockers.append("pytest_module_unresolved_under_final_env")
    env = {"HOME": f"{base}/home", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PIP_NO_INDEX": "1", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1", "PYTHONPATH": py_path, "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TMPDIR": f"{base}/tmp", "XDG_CACHE_HOME": f"{base}/cache"}
    argv = [str(python), "-m", "pytest", "-p", "no:cacheprovider", "-c", f"{worktree}/pyproject.toml", "-q", selector]
    nargv = ([str(Path(bwrap).resolve()), "--unshare-net", "--die-with-parent", "--new-session", "--ro-bind", "/", "/", "--bind", worktree, worktree, "--ro-bind", fixture_root, fixture_root, "--chdir", worktree, "--clearenv"] + [x for k, v in sorted(env.items()) for x in ("--setenv", k, v)] + ["--"] + argv) if bwrap else []
    clear = clearance(repo, before, after, ns, pins)
    if not clear["clear"]: blockers.append("protected_namespace_overlap")
    dependency_ready = bool(deps) and not any(x.startswith(("missing_distribution", "dependency_")) for x in blockers); offline_ready = dependency_ready and bool(bwrap)
    if not dependency_ready: blockers.append("dependency_evidence_incomplete")
    if not offline_ready: blockers.append("offline_namespace_evidence_incomplete")
    executables = [file_fact(python)] + ([file_fact(Path(bwrap))] if bwrap else []) + ([file_fact(Path(gitexe))] if gitexe else [])
    payload = {"schema": "stage12593_canonical_immutable_binding_payload_v2", "candidate": {"candidate_ref": pair_id, "stage12591_row_sha256": stable_hash(source), "focused_verifier_ref": source["focused_verifier_ref"]}, "repository": {"path": str(repo.resolve()), "name": repo.name, "before_commit_oid": before, "after_commit_oid": after, "before_tree_oid": bt, "after_tree_oid": at, "pin_checks": checks, "changed_paths": changed}, "production_patch": {"path": spec["production"], "sha256": sha256_bytes(patch), "byte_count": len(patch), "before_blob": bp, "after_blob": ap, "paths": [spec["production"]]}, "frozen_tests": {"manifest": frozen, "manifest_sha256": stable_hash(frozen), "file_count": len(frozen), "mechanical_immutability": "read_only_bind_mounts"}, "fixture": {"source_path": spec["test"], "mode": tm, "blob_oid": toid, "sha256": sha256_bytes(test_data), "byte_count": len(test_data), "destination_path": fixture, "mechanical_immutability": "read_only_bind_mount"}, "selector": selector, "expected_node_ids": nodes, "expected_node_count": len(nodes), "invocation": {"argv": argv, "cwd": worktree, "clear_environment": True, "environment": env, "namespace_argv": nargv, "writable_external_paths": [env["HOME"], env["TMPDIR"], env["XDG_CACHE_HOME"]]}, "runtime": {"executables": executables, "resolved_pytest_module_under_final_environment": resolved_module, "local_module_files": modules, "local_module_manifest_sha256": stable_hash(modules), "config": {"path": f"{worktree}/pyproject.toml", "mode": cb[0], "blob_oid": cb[2], "sha256": sha256_bytes(blob(repo, cb[2]))}, "dependencies": deps, "dependency_manifest_sha256": stable_hash(deps)}, "outcome_contract": OUTCOMES, "failure_fingerprint_spec": FINGERPRINT_SPEC, "filesystem_digest_spec": FILESYSTEM_SPEC, "namespace_clearance": clear, "namespace_input_hashes": pins}
    ref = opaque_ref("binding", payload); blockers = sorted(set(blockers) | set(TRUSTED_RUNNER_BLOCKERS))
    return {"record_type": "stage12593_private_static_verifier_binding_v2", "candidate_ref": pair_id, "binding_ref": ref, "binding_payload_sha256": stable_hash(payload), "binding_payload": payload, "readiness_evidence": {"dependency_ready": dependency_ready, "offline_ready": offline_ready, "network_disabled_namespace": bool(bwrap)}, "blockers": blockers, "static_binding_ready": True, "execution_request_ready": False, "request_ready": False, **no_claim_fields()}

def validate_binding(binding):
    p = binding.get("binding_payload"); out = []
    if not isinstance(p, dict): return ["binding_payload_missing"]
    if stable_hash(p) != binding.get("binding_payload_sha256"): out.append("binding_payload_digest_mismatch")
    if opaque_ref("binding", p) != binding.get("binding_ref"): out.append("binding_ref_mismatch")
    return out

def validate_replay_attestation_structure(binding, a):
    out, p, inv = validate_binding(binding), binding["binding_payload"], binding["binding_payload"]["invocation"]
    checks = (("binding_ref", a.get("binding_ref"), binding["binding_ref"]), ("argv", a.get("argv"), inv["argv"]), ("cwd", a.get("cwd"), inv["cwd"]), ("environment", a.get("environment"), inv["environment"]), ("clear_environment", a.get("clear_environment"), True), ("namespace_argv", a.get("namespace_argv"), inv["namespace_argv"]), ("fixture_sha256", a.get("fixture_sha256"), p["fixture"]["sha256"]), ("test_manifest_sha256", a.get("test_manifest_sha256"), p["frozen_tests"]["manifest_sha256"]), ("production_patch_sha256", a.get("production_patch_sha256"), p["production_patch"]["sha256"]), ("node_ids", a.get("node_ids"), p["expected_node_ids"]), ("node_count", a.get("node_count"), p["expected_node_count"]))
    out += [f"{n}_mismatch" for n, got, want in checks if got != want]
    phases = a.get("phases")
    if not isinstance(phases, list) or len(phases) != 3: out.append("phase_evidence_malformed")
    else:
        for phase, name in zip(phases, ("initial", "patched", "final"), strict=True):
            if phase.get("name") != name: out.append(f"{name}_phase_name_mismatch")
            if phase.get("pytest_exit_code") != OUTCOMES[name][0]: out.append(f"{name}_exit_code_mismatch")
            if phase.get("classification") != OUTCOMES[name][1]: out.append(f"{name}_status_mismatch")
            if phase.get("node_ids") != p["expected_node_ids"]: out.append(f"{name}_node_ids_mismatch")
            if phase.get("node_count") != p["expected_node_count"]: out.append(f"{name}_node_count_mismatch")
        first, final = phases[0].get("normalized_failure_fingerprint"), phases[2].get("normalized_failure_fingerprint")
        if not isinstance(first, str) or not HEX64.fullmatch(first): out.append("initial_failure_fingerprint_invalid")
        if not isinstance(final, str) or not HEX64.fullmatch(final): out.append("final_failure_fingerprint_invalid")
        if first != final: out.append("initial_final_failure_fingerprint_mismatch")
        if phases[1].get("normalized_failure_fingerprint") not in (None, ""): out.append("patched_pass_has_failure_fingerprint")
    integrity = a.get("integrity_checks"); events = [s["action"] for s in protocol_rows(binding) if s["action"].startswith("integrity_")]
    if not isinstance(integrity, list) or [r.get("event") for r in integrity] != events: out.append("integrity_event_sequence_mismatch")
    elif any(r.get("fixture_sha256") != p["fixture"]["sha256"] or r.get("test_manifest_sha256") != p["frozen_tests"]["manifest_sha256"] for r in integrity): out.append("fixture_or_test_tree_integrity_mismatch")
    initial, final = a.get("initial_filesystem_digest"), a.get("final_filesystem_digest")
    if not isinstance(initial, str) or not HEX64.fullmatch(initial): out.append("initial_filesystem_digest_invalid")
    if not isinstance(final, str) or not HEX64.fullmatch(final): out.append("final_filesystem_digest_invalid")
    if initial != final: out.append("undeclared_residue")
    return {"record_type": "stage12593_non_authoritative_attestation_structure_v2", "structurally_valid": not out, "structural_errors": sorted(set(out)), **no_claim_fields()}

def binding_rows(private_rows):
    return [row for row in private_rows if isinstance(row.get("binding_payload"), dict)]

def string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from string_values(nested)

def public_leaks(value, private_rows):
    public_strings = list(string_values(value)); leaks = []
    for row in binding_rows(private_rows):
        p = row["binding_payload"]
        exact = str(p["repository"]["name"])
        if exact in public_strings: leaks.append(exact)
        for item in (p["repository"]["path"], p["repository"]["before_commit_oid"], p["repository"]["after_commit_oid"], p["production_patch"]["path"], p["fixture"]["source_path"], p["selector"], p["invocation"]["argv"][0]):
            if any(str(item) in public for public in public_strings): leaks.append(str(item))
    return sorted(set(leaks))

def public_file_paths(out=OUT, summary_path=SUMMARY):
    artifact_prefix = f"runs/local/artifacts/{STAGE}"
    return [
        (out / "nonexecuting_replay_blueprints.jsonl", f"{artifact_prefix}/nonexecuting_replay_blueprints.jsonl"),
        (out / "blocked_candidates.jsonl", f"{artifact_prefix}/blocked_candidates.jsonl"),
        (out / "blueprint_contract.json", f"{artifact_prefix}/blueprint_contract.json"),
        (out / "summary.json", f"{artifact_prefix}/summary.json"),
        (out / "public_leak_scan.json", f"{artifact_prefix}/public_leak_scan.json"),
        (summary_path, f"runs/summaries/{STAGE}.json"),
    ]

def scan_public(private_rows, private_path, out=OUT, summary_path=SUMMARY):
    files, leaks = [], []
    for path, display_path in public_file_paths(out, summary_path):
        if not path.is_file(): raise GateError(f"public_file_missing:{path.name}")
        value = read_jsonl(path) if path.suffix == ".jsonl" else json.loads(path.read_text()); found = public_leaks(value, private_rows); leaks += [f"{path.name}:{x}" for x in found]
        files.append({"path": display_path, "sha256": None if path.name == "public_leak_scan.json" else sha256_file(path), "leak_count": len(found)})
    canonical_private_path = f"runs/local/artifacts/{STAGE}/private/verifier_binding_sidecar.jsonl"
    report = {"record_type": "stage12593_public_leak_scan_v2", "public_files": files, "public_files_checked": len(files), "private_sidecar": {"path": canonical_private_path, "sha256": sha256_file(private_path)}, "linked_public_manifest_sha256": stable_hash(files), "leaks": sorted(leaks), "leak_count": len(leaks), "passed": not leaks, **no_claim_fields()}
    report["self_payload_sha256"] = stable_hash(report); return report

def blocker_code(error):
    if isinstance(error, GateError):
        return str(error).split(":", 1)[0] or "candidate_generation_failure"
    return "candidate_generation_internal_error"

def blocked_record(pair_id, error, static_binding_ready=False):
    return {
        "record_type": "stage12593_blocked_candidate_v2",
        "candidate_ref": pair_id,
        "blockers": [blocker_code(error)],
        "static_binding_ready": static_binding_ready,
        "execution_request_ready": False,
        "request_ready": False,
        **no_claim_fields(),
    }

def private_blocked_record(pair_id, error):
    row = blocked_record(pair_id, error)
    row["record_type"] = "stage12593_private_blocked_candidate_v2"
    row["blockers"] = sorted(set(row["blockers"]) | set(TRUSTED_RUNNER_BLOCKERS))
    row["failure_type"] = type(error).__name__
    row["failure_detail"] = str(error)
    return row

def publish(private, blocked, blueprints, contract, summary):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{STAGE}.", dir=OUT.parent))
    summary_fd, summary_name = tempfile.mkstemp(prefix=f".{STAGE}.", suffix=".json", dir=SUMMARY.parent)
    os.close(summary_fd)
    staged_summary = Path(summary_name)
    backup = OUT.parent / f".{STAGE}.previous"
    private_path = staging / "private/verifier_binding_sidecar.jsonl"
    try:
        write_jsonl(private_path, private)
        write_jsonl(staging / "nonexecuting_replay_blueprints.jsonl", blueprints)
        write_jsonl(staging / "blocked_candidates.jsonl", blocked)
        write_json(staging / "blueprint_contract.json", contract)
        write_json(staging / "summary.json", summary)
        write_json(staged_summary, summary)
        write_json(staging / "public_leak_scan.json", {"state": "pending", "positive_stop": False})
        report = scan_public(private, private_path, staging, staged_summary)
        write_json(staging / "public_leak_scan.json", report)
        final = scan_public(private, private_path, staging, staged_summary)
        if not final["passed"]: raise GateError("public_disk_rescan_failed")
        persisted = json.loads((staging / "public_leak_scan.json").read_text())
        digest = persisted.pop("self_payload_sha256")
        if stable_hash(persisted) != digest: raise GateError("leak_report_self_digest_mismatch")
        if backup.exists():
            shutil.rmtree(backup)
        had_previous = OUT.exists()
        if had_previous:
            os.replace(OUT, backup)
        try:
            os.replace(staging, OUT)
            os.replace(staged_summary, SUMMARY)
        except BaseException:
            if OUT.exists():
                shutil.rmtree(OUT)
            if had_previous and backup.exists():
                os.replace(backup, OUT)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if staged_summary.exists():
            staged_summary.unlink()

def build():
    sources = {str(row.get("candidate_id")): row for row in read_jsonl(S91_UNIVERSE)}
    setup_error = None
    try:
        pins, ns = namespace_input_pins(), namespace_data()
    except Exception as error:
        pins, ns, setup_error = None, None, error
    private, blocked = [], []
    for pair_id in PAIR_IDS:
        try:
            if setup_error is not None:
                raise setup_error
            if pair_id not in sources:
                raise GateError("candidate_missing")
            row = make_binding(pair_id, sources[pair_id], PRIVATE_SPECS[pair_id], ns, pins)
            row["blockers"] = sorted(set(row["blockers"] + validate_binding(row)) | set(TRUSTED_RUNNER_BLOCKERS))
            row.update({"static_binding_ready": True, "execution_request_ready": False, "request_ready": False, **no_claim_fields()})
            private.append(row)
            if row["blockers"]:
                public_blocked = blocked_record(pair_id, GateError(row["blockers"][0]), static_binding_ready=True)
                public_blocked["blockers"] = row["blockers"]
                blocked.append(public_blocked)
        except Exception as error:
            private_row = private_blocked_record(pair_id, error)
            private.append(private_row)
            public_blocked = blocked_record(pair_id, error)
            public_blocked["blockers"] = private_row["blockers"]
            blocked.append(public_blocked)
    blueprints = []
    for row in binding_rows(private):
        blueprints.append({"record_type": "stage12593_nonexecuting_replay_blueprint_v2", "candidate_ref": row["candidate_ref"], "blueprint_ref": opaque_ref("blueprint", [row["candidate_ref"], row["binding_ref"]]), "binding_ref": row["binding_ref"], "decision": "BLOCKED_TRUSTED_RUNNER_REQUIRED", "independent_candidate": True, "batch_readiness_required": False, "sibling_failure_has_no_effect": True, "static_binding_ready": True, "execution_request_ready": False, "production_only_change_required": True, "worktree_test_mutation_allowed": False, "undeclared_residue_allowed": False, "protocol": protocol_rows(row), **no_claim_fields()})
    counts = Counter(code for row in blocked for code in row["blockers"])
    static_ready_ids = [row["candidate_ref"] for row in binding_rows(private)]
    blocked_ids = [row["candidate_ref"] for row in blocked]
    contract = {"record_type": "stage12593_public_nonexecuting_blueprint_contract_v2", "stage": STAGE, "exact_candidate_refs": list(PAIR_IDS), "decision": "BLOCKED_TRUSTED_RUNNER_REQUIRED", "blueprint_count": len(blueprints), "static_binding_ready_count": len(static_ready_ids), "execution_request_ready_count": 0, "blocked_candidate_count": len(blocked), "candidates_are_independent": True, "batch_readiness_required": False, "sibling_failure_authorizes_other": False, "preexecution_status_known": False, "public_binding_material": "opaque_refs_only", "snapshot_components": list(SNAPSHOT_COMPONENTS), **no_claim_fields()}
    summary = {"record_type": "stage12593_public_static_binding_summary_v2", "stage": STAGE, "decision": "BLOCKED_TRUSTED_RUNNER_REQUIRED", "static_binding_ready_count": len(static_ready_ids), "static_binding_ready_candidate_refs": static_ready_ids, "execution_request_ready_count": 0, "execution_request_ready_candidate_refs": [], "nonexecuting_replay_blueprint_count": len(blueprints), "blocked_candidate_count": len(blocked), "blocked_candidate_refs": blocked_ids, "blocker_counts": dict(sorted(counts.items())), "private_sidecar_ref": opaque_ref("sidecar", private), "namespace_clearance_ref": opaque_ref("clearance", [row["binding_payload"]["namespace_clearance"] for row in binding_rows(private)]), "namespace_clearance_interpretation": "collision_check_only_not_novelty_or_eval_eligibility", **no_claim_fields()}
    if public_leaks({"blueprints": blueprints, "blocked": blocked, "contract": contract, "summary": summary}, private): raise GateError("public_private_leak")
    publish(private, blocked, blueprints, contract, summary)
    return summary

def main(): print(json.dumps(build(), sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
