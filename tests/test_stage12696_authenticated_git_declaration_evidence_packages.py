from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_stage12696_authenticated_git_declaration_evidence_packages.py"
SPEC = importlib.util.spec_from_file_location("stage12696_tested", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = S
SPEC.loader.exec_module(S)


def test_dependency_loader_executes_hashed_bytes_without_path_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    name = "stage12696_loader_race_fixture"
    raw = b"VALUE = \"trusted\"\n"
    monkeypatch.setitem(S.DEPENDENCY_SHA256, name, hashlib.sha256(raw).hexdigest())
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.name == "race_fixture.py":
            return raw
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    module = S._load(name, "race_fixture.py")
    assert module.VALUE == "trusted"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], env={**os.environ, "LC_ALL": "C"}).decode().strip()


def repository(tmp_path: Path, source: bytes = b'[package]\nname = "demo"\n') -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / "Cargo.toml").write_bytes(source)
    git(repo, "add", "Cargo.toml")
    git(repo, "commit", "-qm", "initial")
    return repo, git(repo, "rev-parse", "HEAD")


def catalog(repo_key: str, revision: str, repo: Path) -> dict:
    component_objects = []
    for line in git(repo, "ls-tree", "-r", "-l", revision).splitlines():
        header, _path = line.split("\t", 1)
        _mode, object_type, oid, raw_size = header.split()
        component_objects.append((
            object_type, oid, None if raw_size == "-" else int(raw_size),
        ))
    component_objects.sort()
    type_counts = {}
    for object_type, _oid, _size in component_objects:
        type_counts[object_type] = type_counts.get(object_type, 0) + 1
    roots = sorted(git(repo, "rev-list", "--max-parents=0", revision).splitlines())
    return {
        "repository_key_sha256": repo_key,
        "revision": revision,
        "head_commit_git_oid": revision,
        "git_tree_oid": git(repo, "rev-parse", revision + "^{tree}"),
        "root_commit_git_oids": roots,
        "all_tree_object_count": len(component_objects),
        "all_tree_object_identity_inventory_sha256": (
            S.S92.stage12688.stable(component_objects)
        ),
        "tree_object_type_counts": dict(sorted(type_counts.items())),
        "caller_root_count": 999,
    }


def declaration(repo_key: str, revision: str, repo: Path) -> tuple[dict, dict]:
    source = (repo / "Cargo.toml").read_bytes()
    oid = git(repo, "rev-parse", "HEAD:Cargo.toml")
    row = S.S92.extract_cargo_toml_rows(
        source, repository_key_sha256=repo_key, revision=revision,
        source_blob_oid=oid, source_path="Cargo.toml",
    )[0]
    row["source_provenance"].update({"content_component_sha256": "c" * 64, "tree_oid": git(repo, "rev-parse", "HEAD^{tree}")})
    row["split"] = "train"
    proof = {
        "row_id": row["row_id"], "row_sha256": S.S92.stage12688.stable(row),
        "repository_key_sha256": repo_key, "revision": revision,
        "source_path": "Cargo.toml", "source_file_sha256": hashlib.sha256(source).hexdigest(),
    }
    return row, proof


def declaration_for_file(repo_key: str, revision: str, repo: Path, name: str) -> tuple[dict, dict]:
    source = (repo / name).read_bytes()
    oid = git(repo, "rev-parse", f"HEAD:{name}")
    adapter = S.S92._adapter_for_path(name)
    kwargs = {"repository_key_sha256": repo_key, "revision": revision}
    if adapter is S.S92.extract_package_json_rows:
        rows = adapter(source, package_blob_oid=oid, package_path=name, **kwargs)
    else:
        rows = adapter(source, source_blob_oid=oid, source_path=name, **kwargs)
    assert rows
    row = rows[0]
    provenance = row["source_provenance"]
    provenance.update({
        "source_path": provenance.get("source_path", provenance.get("package_path")),
        "source_git_blob_oid": provenance.get("source_git_blob_oid", provenance.get("package_git_blob_oid")),
        "source_file_sha256": provenance.get("source_file_sha256", provenance.get("package_file_sha256")),
        "content_component_sha256": "c" * 64,
        "tree_oid": git(repo, "rev-parse", "HEAD^{tree}"),
    })
    row["split"] = "train"
    proof = {
        "row_id": row["row_id"], "row_sha256": S.S92.stage12688.stable(row),
        "repository_key_sha256": repo_key, "revision": revision,
        "source_path": name, "source_file_sha256": hashlib.sha256(source).hexdigest(),
    }
    return row, proof


def membership(root: Path, name: str, records: list[dict]) -> S.AuthenticatedJsonl:
    raw = b"".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for item in records
    )
    (root / name).write_bytes(raw)
    return S.authenticate_jsonl(root, name, hashlib.sha256(raw).hexdigest(), S.PackageLimits())


def load_fixture_generation(tmp_path: Path, monkeypatch) -> dict[str, S.AuthenticatedJsonl]:
    paths = {
        "stage12688_catalog": "s88.jsonl",
        "stage12692_rows": "rows.jsonl",
        "stage12692_catalog": "catalog92.jsonl",
        "stage12692_ledger": "proofs.jsonl",
    }
    hashes = {role: hashlib.sha256((tmp_path / path).read_bytes()).hexdigest() for role, path in paths.items()}
    monkeypatch.setattr(S, "ACCEPTED_ARTIFACT_RELATIVE_PATHS", paths)
    monkeypatch.setattr(S, "ACCEPTED_ARTIFACT_SHA256S", hashes)
    return S.load_accepted_artifact_memberships(tmp_path)


def inventory_kwargs(tmp_path: Path, monkeypatch) -> dict:
    repo, revision = repository(tmp_path)
    key = "1" * 64
    row, proof = declaration(key, revision, repo)
    declaration_catalog = {
        **catalog(key, revision, repo),
        "tree_oid": row["source_provenance"]["tree_oid"],
        "content_component_sha256": row["source_provenance"]["content_component_sha256"],
    }
    membership(tmp_path, "s88.jsonl", [catalog(key, revision, repo)])
    membership(tmp_path, "rows.jsonl", [row])
    membership(tmp_path, "catalog92.jsonl", [declaration_catalog])
    membership(tmp_path, "proofs.jsonl", [proof])
    accepted = load_fixture_generation(tmp_path, monkeypatch)
    return {
        **accepted,
        "repository_root": tmp_path,
        "repository_paths": {key: "repo"},
    }


def test_git_evidence_is_derived_not_caller_labeled(tmp_path: Path):
    repo, revision = repository(tmp_path)
    key = "1" * 64
    evidence = S.derive_git_head_evidence(catalog(key, revision, repo), "2" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))
    assert evidence.root_commit_oids == (revision,)
    assert evidence.commit_objects_inspected == 1
    assert evidence.commit_oids == (revision,)
    assert evidence.tree_count == 1
    assert evidence.blob_count == 1
    assert evidence.total_object_count == 3
    assert len(evidence.component_objects) == 1
    assert evidence.component_objects[0][0] == "blob"
    assert evidence.component_objects[0][2] == (repo / "Cargo.toml").stat().st_size
    assert [entry[4] for entry in evidence.component_tree_entry_identities] == ["Cargo.toml"]



def test_git_evidence_commit_inventory_covers_every_merge_parent(tmp_path: Path):
    repo, root = repository(tmp_path)
    main_branch = git(repo, "branch", "--show-current")
    git(repo, "checkout", "-qb", "side")
    (repo / "side.txt").write_text("side\n", encoding="utf-8")
    git(repo, "add", "side.txt")
    git(repo, "commit", "-qm", "side")
    side = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", main_branch)
    (repo / "main.txt").write_text("main\n", encoding="utf-8")
    git(repo, "add", "main.txt")
    git(repo, "commit", "-qm", "main")
    main = git(repo, "rev-parse", "HEAD")
    git(repo, "merge", "--no-ff", "-qm", "merge", "side")
    head = git(repo, "rev-parse", "HEAD")
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, head, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()),
        (root, side, main, head),
    )
    assert set(evidence.commit_oids) == {root, side, main, head}
    assert evidence.commit_objects_inspected == 4


def test_lineage_target_object_must_be_reachable_from_head(tmp_path: Path):
    repo, head = repository(tmp_path)
    main_branch = git(repo, "branch", "--show-current")
    git(repo, "checkout", "--orphan", "unrelated")
    for path in repo.iterdir():
        if path.name != ".git" and path.is_file():
            path.unlink()
    (repo / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "unrelated")
    unrelated = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", main_branch)
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, head, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()), (unrelated,),
    )
    assert unrelated not in evidence.commit_oids
    assert evidence.commit_oids == (head,)


def test_head_component_inventory_preserves_repeated_blob_placements(
    tmp_path: Path,
) -> None:
    repo, _revision = repository(tmp_path)
    (repo / "Cargo-copy.toml").write_bytes((repo / "Cargo.toml").read_bytes())
    git(repo, "add", "Cargo-copy.toml")
    git(repo, "commit", "-qm", "repeat blob placement")
    revision = git(repo, "rev-parse", "HEAD")
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()),
    )

    assert len(evidence.component_objects) == 2
    assert evidence.component_objects[0] == evidence.component_objects[1]



def test_head_component_inventory_preserves_nested_repeated_symlink_subtrees(
    tmp_path: Path,
) -> None:
    repo, _revision = repository(tmp_path)
    for name in ("one", "two"):
        directory = repo / name
        directory.mkdir()
        (directory / "shared.txt").write_bytes(b"shared\n")
        os.symlink("shared.txt", directory / "link")
    git(repo, "add", "one", "two")
    git(repo, "commit", "-qm", "repeat nested symlink subtree")
    revision = git(repo, "rev-parse", "HEAD")
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()),
    )

    regular_oid = git(repo, "rev-parse", "HEAD:one/shared.txt")
    symlink_oid = git(repo, "rev-parse", "HEAD:one/link")
    assert [item[1] for item in evidence.component_objects].count(regular_oid) == 2
    assert [item[1] for item in evidence.component_objects].count(symlink_oid) == 2
    assert {item[2] for item in evidence.component_objects if item[1] == symlink_oid} == {
        len(b"shared.txt"),
    }


def test_head_component_inventory_excludes_historical_only_blob(
    tmp_path: Path,
) -> None:
    repo, _revision = repository(tmp_path)
    historical_oid = git(repo, "rev-parse", "HEAD:Cargo.toml")
    (repo / "Cargo.toml").write_bytes(b"[package]\nname = \"new\"\n")
    git(repo, "add", "Cargo.toml")
    git(repo, "commit", "-qm", "replace historical blob")
    revision = git(repo, "rev-parse", "HEAD")
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()),
    )

    assert historical_oid not in {oid for _kind, oid, _size in evidence.component_objects}
    assert historical_oid not in {
        entry[3] for entry in evidence.tree_entry_identities
    }
    current_oid = git(repo, "rev-parse", "HEAD:Cargo.toml")
    assert current_oid in {oid for _kind, oid, _size in evidence.component_objects}
    assert evidence.commit_oids == (revision,)
    assert evidence.root_commit_oids != evidence.commit_oids
    assert historical_oid not in {
        entry[3] for entry in evidence.component_tree_entry_identities
    }
    assert current_oid in {entry[3] for entry in evidence.component_tree_entry_identities}


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("all_tree_object_count", 999, "catalog_component_object_count_mismatch"),
        ("all_tree_object_identity_inventory_sha256", "f" * 64,
         "catalog_component_object_inventory_mismatch"),
        ("tree_object_type_counts", {"commit": 1},
         "catalog_component_object_type_counts_mismatch"),
    ],
)
def test_component_inventory_catalog_forgery_rejected(
    tmp_path: Path, field: str, value: object, reason: str,
) -> None:
    repo, revision = repository(tmp_path)
    forged = catalog("1" * 64, revision, repo)
    forged[field] = value
    with pytest.raises(S.Stage12696Error, match=reason):
        S.derive_git_head_evidence(
            forged, "2" * 64, tmp_path, "repo",
            S.WorkBudget(S.PackageLimits()),
        )


def test_component_inventory_blob_size_forgery_rejected(tmp_path: Path) -> None:
    repo, revision = repository(tmp_path)
    forged = catalog("1" * 64, revision, repo)
    oid = git(repo, "rev-parse", "HEAD:Cargo.toml")
    forged["all_tree_object_identity_inventory_sha256"] = (
        S.S92.stage12688.stable([("blob", oid, 1)])
    )
    with pytest.raises(
        S.Stage12696Error, match="catalog_component_object_inventory_mismatch",
    ):
        S.derive_git_head_evidence(
            forged, "2" * 64, tmp_path, "repo",
            S.WorkBudget(S.PackageLimits()),
        )


def test_component_inventory_sizes_large_blob_without_reading_payload(
    tmp_path: Path, monkeypatch,
) -> None:
    repo, _revision = repository(tmp_path)
    (repo / "large.bin").write_bytes(b"x" * 128)
    git(repo, "add", "large.bin")
    git(repo, "commit", "-qm", "large metadata-only blob")
    revision = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(S.S93, "MAX_BLOB_OBJECT_BYTES", 64)
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo",
        S.WorkBudget(S.PackageLimits()),
    )
    large_oid = git(repo, "rev-parse", "HEAD:large.bin")
    assert ("blob", large_oid, 128) in evidence.component_objects


def test_batch_blob_metadata_parser_accepts_exact_output():
    first, second = "1" * 40, "2" * 40

    result = S._parse_batch_blob_sizes(
        (first, second), f"{first} blob 7\n{second} blob 11\n".encode(),
    )
    assert result == {first: 7, second: 11}


def test_batch_blob_metadata_parser_rejects_wrong_oid():
    requested = "1" * 40

    with pytest.raises(S.Stage12696Error, match="batch_blob_metadata_mismatch"):
        S._parse_batch_blob_sizes(
            (requested,), f"{'2' * 40} blob 7\n".encode(),
        )


@pytest.mark.parametrize("payload", [
    b"",
    (("1" * 40) + " tree 7\n").encode(),
    (("1" * 40) + " blob 07\n").encode(),
    (("1" * 40) + " blob nope\n").encode(),
    b"\xff",
])
def test_batch_blob_metadata_parser_rejects_malformed_output(payload: bytes):
    with pytest.raises(S.Stage12696Error):
        S._parse_batch_blob_sizes(("1" * 40,), payload)


def test_stage12696_single_object_git_disables_lazy_fetch(monkeypatch):
    observed = {}

    class Process:
        returncode = 0
        pid = 123

        def communicate(self, timeout):
            assert timeout == 60
            return b"commit\n", b""

    def popen(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return Process()

    monkeypatch.setattr(S.subprocess, "Popen", popen)
    output = S._git_no_lazy_fetch(
        SimpleNamespace(repo_fd=10, git_fd=11),
        "cat-file", "-t", "1" * 40, max_stdout_bytes=16,
    )
    assert output == b"commit\n"
    assert observed["kwargs"]["env"]["GIT_NO_LAZY_FETCH"] == "1"
    assert observed["kwargs"]["pass_fds"] == (10, 11)
    assert observed["kwargs"]["start_new_session"] is True


def test_coordinated_forged_catalog_cannot_override_raw_git(tmp_path: Path):
    repo, revision = repository(tmp_path)
    forged = {**catalog("1" * 64, revision, repo), "revision": "f" * 40, "head_commit_git_oid": "f" * 40}
    with pytest.raises(S.Stage12696Error, match="pinned_revision_mismatch"):
        S.derive_git_head_evidence(forged, "2" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))


def test_resealed_derived_catalog_labels_are_rejected(tmp_path: Path):
    repo, revision = repository(tmp_path)
    forged = {**catalog("1" * 64, revision, repo), "root_commit_git_oids": ["f" * 40]}
    with pytest.raises(S.Stage12696Error, match="catalog_git_derivation_mismatch"):
        S.derive_git_head_evidence(forged, "2" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))


def test_each_gitlink_placement_is_counted_even_when_oid_is_history_commit(tmp_path: Path):
    repo, parent = repository(tmp_path)
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{parent},deps/one")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{parent},deps/two")
    git(repo, "commit", "-qm", "add gitlinks")
    revision = git(repo, "rev-parse", "HEAD")
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits())
    )
    assert evidence.commit_objects_inspected == 2
    assert evidence.submodule_count == 2
    assert [item[1:] for item in evidence.gitlink_identities] == [
        ("160000", "commit", parent, "deps/one"),
        ("160000", "commit", parent, "deps/two"),
    ]
    assert evidence.total_object_count >= (
        len(evidence.commit_oids) + evidence.submodule_count
    )


def test_repository_replacement_after_pin_is_rejected(tmp_path: Path):
    repo, revision = repository(tmp_path)
    with pytest.raises(S.Stage12696Error, match="repository_path_replaced"):
        with S.pin_repository_at_root(tmp_path, "repo") as pinned:
            moved = tmp_path / "moved"
            repo.rename(moved)
            repo.mkdir()
            assert S.S93.read_commit(pinned, revision).oid == revision


def test_git_environment_ignores_replace_and_global_config(tmp_path: Path, monkeypatch):
    repo, revision = repository(tmp_path)
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/forged")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "forged-config"))
    evidence = S.derive_git_head_evidence(catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))
    assert evidence.revision == revision


def test_declaration_replays_parser_and_span(tmp_path: Path):
    repo, revision = repository(tmp_path)
    key = "1" * 64
    row, proof = declaration(key, revision, repo)
    evidence = S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))
    assert evidence.parser_adapter == "stdlib_tomllib_cargo"
    assert evidence.source_bytes == (repo / "Cargo.toml").read_bytes()
    assert evidence.source_size == len(evidence.source_bytes)
    assert evidence.source_bytes not in repr(evidence).encode()


@pytest.mark.parametrize("name,source", [
    ("package.json", b'{"scripts":{"build":"tsc","lint":"eslint .","test":"pytest","docs":"sphinx","ci":"npm run test"}}\n'),
    ("tox.ini", b"[tox]\nenvlist=py, lint, docs, type\n[testenv:py]\ncommands=pytest\n[testenv:lint]\ncommands=ruff check .\n[testenv:docs]\ncommands=sphinx-build docs out\n[testenv:type]\ncommands=mypy src\n[testenv:ci]\ncommands=tox -e py\n"),
    ("pyproject.toml", b"[tool.ruff]\nline-length = 88\n"),
    ("Makefile", b"build:\n\techo build\nlint:\n\techo lint\ntest:\n\techo test\ndocs:\n\techo docs\nci:\n\tmake test\n"),
])
def test_every_supported_strict_adapter_is_replayed(tmp_path: Path, name: str, source: bytes):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / name).write_bytes(source)
    git(repo, "add", name)
    git(repo, "commit", "-qm", "initial")
    revision = git(repo, "rev-parse", "HEAD")
    row, proof = declaration_for_file("1" * 64, revision, repo, name)
    evidence = S.authenticate_declaration_row(
        row, proof, "3" * 64, "4" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits())
    )
    assert evidence.row_id == row["row_id"]


def test_parser_mutation_rejected(tmp_path: Path):
    repo, revision = repository(tmp_path)
    row, proof = declaration("1" * 64, revision, repo)
    row["source_provenance"]["parser_adapter"]["name"] = "stdlib_tomllib_pyproject"
    proof["row_sha256"] = S.S92.stage12688.stable(row)
    with pytest.raises(S.Stage12696Error, match="parser_adapter_path_mismatch"):
        S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))


def test_span_or_target_forgery_rejected_even_when_resealed(tmp_path: Path):
    repo, revision = repository(tmp_path)
    row, proof = declaration("1" * 64, revision, repo)
    row["source_provenance"]["target_start_byte"] += 1
    row["target"]["decoder_text"] = "forged"
    proof["row_sha256"] = S.S92.stage12688.stable(row)
    with pytest.raises(S.Stage12696Error, match="declaration_row_not_reproduced"):
        S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))


def test_blob_bytes_must_match_revision_not_worktree(tmp_path: Path):
    repo, revision = repository(tmp_path)
    row, proof = declaration("1" * 64, revision, repo)
    (repo / "Cargo.toml").write_bytes(b'[package]\nname = "forged"\n')
    evidence = S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", S.WorkBudget(S.PackageLimits()))
    assert evidence.source_file_sha256 != hashlib.sha256((repo / "Cargo.toml").read_bytes()).hexdigest()
    assert evidence.source_bytes != (repo / "Cargo.toml").read_bytes()
    assert hashlib.sha256(evidence.source_bytes).hexdigest() == evidence.source_file_sha256


@pytest.mark.parametrize("field", ["commits", "trees", "tree_entries", "object_reads", "blob_bytes", "declaration_rows"])
def test_resource_limits_fail_closed(tmp_path: Path, field: str):
    repo, revision = repository(tmp_path)
    limits = S.PackageLimits(**{**S.PackageLimits().__dict__, field: 1})
    budget = S.WorkBudget(limits)
    if field == "blob_bytes":
        row, proof = declaration("1" * 64, revision, repo)
        with pytest.raises(S.Stage12696Error, match="resource_limit_exceeded"):
            S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", budget)
    elif field == "declaration_rows":
        row, proof = declaration("1" * 64, revision, repo)
        S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", budget)
        with pytest.raises(S.Stage12696Error, match="resource_limit_exceeded"):
            S.authenticate_declaration_row(row, proof, "3" * 64, "4" * 64, tmp_path, "repo", budget)
    else:
        if field in {"commits", "trees", "tree_entries"}:
            budget.charge(field)
        with pytest.raises(S.Stage12696Error, match="resource_limit_exceeded"):
            S.derive_git_head_evidence(catalog("1" * 64, revision, repo), "2" * 64, tmp_path, "repo", budget)


def test_inventory_wide_tree_entry_bound_accepts_measured_footprint_and_fails_above_limit():
    limits = S.PackageLimits()
    assert limits.tree_entries == 2_100_000

    accepted = S.WorkBudget(limits)
    accepted.charge("tree_entries", 2_027_908)
    assert accepted.tree_entries == 2_027_908

    exceeded = S.WorkBudget(limits)
    with pytest.raises(
        S.Stage12696Error, match="resource_limit_exceeded:tree_entries",
    ):
        exceeded.charge("tree_entries", 2_100_001)


def test_jsonl_authentication_rejects_symlink_and_digest_mutation(tmp_path: Path):
    record = {"a": 1}
    raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path = tmp_path / "records.jsonl"
    path.write_bytes(raw)
    authenticated = S.authenticate_jsonl(tmp_path, "records.jsonl", hashlib.sha256(raw).hexdigest(), S.PackageLimits())
    assert authenticated.records == (record,)
    link = tmp_path / "link.jsonl"
    link.symlink_to(path)
    with pytest.raises(S.Stage12696Error, match="descriptor_relative_open_failed"):
        S.authenticate_jsonl(tmp_path, "link.jsonl", hashlib.sha256(raw).hexdigest(), S.PackageLimits())
    with pytest.raises(S.Stage12696Error, match="commitment_mismatch"):
        S.authenticate_jsonl(tmp_path, "records.jsonl", "f" * 64, S.PackageLimits())


def test_symlinked_artifact_parent_and_root_are_rejected(tmp_path: Path):
    actual = tmp_path / "actual"
    actual.mkdir()
    raw = b'{"a":1}\n'
    (actual / "records.jsonl").write_bytes(raw)
    (tmp_path / "alias").symlink_to(actual, target_is_directory=True)
    with pytest.raises(S.Stage12696Error, match="descriptor_relative_open_failed"):
        S.authenticate_jsonl(tmp_path, "alias/records.jsonl", hashlib.sha256(raw).hexdigest(), S.PackageLimits())
    with pytest.raises(S.Stage12696Error, match="descriptor_root_pin_failed"):
        S.authenticate_jsonl(tmp_path / "alias", "records.jsonl", hashlib.sha256(raw).hexdigest(), S.PackageLimits())


def test_symlinked_repository_parent_is_rejected(tmp_path: Path):
    repos = tmp_path / "repos"
    repos.mkdir()
    repository(repos)
    (tmp_path / "repo_alias").symlink_to(repos, target_is_directory=True)
    with pytest.raises(S.Stage12696Error, match="descriptor_relative_open_failed"):
        S.derive_git_head_evidence(
            catalog("1" * 64, git(repos / "repo", "rev-parse", "HEAD"), repos / "repo"),
            "2" * 64, tmp_path, "repo_alias/repo", S.WorkBudget(S.PackageLimits()),
        )


def test_build_rejects_caller_fabricated_membership(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    kwargs["stage12688_catalog"] = replace(kwargs["stage12688_catalog"], _seal=object())
    with pytest.raises(S.Stage12696Error, match="accepted_artifact_role_path_or_digest_mismatch"):
        S.build_package_inventory(**kwargs)


def test_build_failure_names_immutable_repository_identity(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    record = kwargs["stage12688_catalog"].records[0]
    monkeypatch.setattr(
        S, "_derive_git_head_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            S.Stage12696Error("malformed_commit_headers")
        ),
    )
    expected = (
        "git_head_evidence_failed:"
        + record["repository_key_sha256"] + ":" + record["revision"]
        + ":malformed_commit_headers"
    )
    with pytest.raises(S.Stage12696Error, match=expected):
        S.build_package_inventory(**kwargs)


def test_build_rejects_valid_but_nonaccepted_authenticated_files(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    generic = membership(tmp_path, "generic.jsonl", list(kwargs["stage12688_catalog"].records))
    kwargs["stage12688_catalog"] = generic
    with pytest.raises(S.Stage12696Error, match="accepted_generation_token_missing_or_mixed"):
        S.build_package_inventory(**kwargs)


def test_build_rejects_duplicate_role_and_swapped_path(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    kwargs["stage12692_rows"] = kwargs["stage12688_catalog"]
    with pytest.raises(S.Stage12696Error, match="accepted_artifact_role_path_or_digest_mismatch"):
        S.build_package_inventory(**kwargs)


def test_build_rejects_nonaccepted_digest_before_reauthentication(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    kwargs["stage12692_rows"] = replace(kwargs["stage12692_rows"], file_sha256="f" * 64)
    with pytest.raises(S.Stage12696Error, match="accepted_artifact_role_path_or_digest_mismatch"):
        S.build_package_inventory(**kwargs)


def test_missing_and_extra_artifact_arguments_reject(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    missing = dict(kwargs)
    missing.pop("stage12692_ledger")
    with pytest.raises(TypeError):
        S.build_package_inventory(**missing)
    with pytest.raises(TypeError):
        S.build_package_inventory(**kwargs, unexpected_role=kwargs["stage12692_ledger"])


def test_coordinated_recomputed_package_cannot_forge_loader_token(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    forged_token = object()
    for role in (
        "stage12688_catalog", "stage12692_rows", "stage12692_catalog", "stage12692_ledger"
    ):
        original = kwargs[role]
        forged = membership(
            tmp_path, f"forged-{role}.jsonl", list(original.records),
        )
        kwargs[role] = replace(
            forged,
            relative_path=S.ACCEPTED_ARTIFACT_RELATIVE_PATHS[role],
            file_sha256=S.ACCEPTED_ARTIFACT_SHA256S[role],
            _accepted_role=role,
            _generation_token=forged_token,
        )
    with pytest.raises(S.Stage12696Error, match="accepted_generation_token_not_issued"):
        S.build_package_inventory(**kwargs)


def test_build_rejects_same_content_artifact_replacement(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    path = tmp_path / "s88.jsonl"
    raw = path.read_bytes()
    replacement = tmp_path / "replacement.jsonl"
    replacement.write_bytes(raw)
    replacement.replace(path)
    with pytest.raises(S.Stage12696Error, match="authenticated_membership_replaced"):
        S.build_package_inventory(**kwargs)


def test_closed_generation_rejects_even_when_fd_number_is_reused(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    memberships = {
        role: kwargs[role] for role in (
            "stage12688_catalog", "stage12692_rows", "stage12692_catalog", "stage12692_ledger"
        )
    }
    token = memberships["stage12688_catalog"]._generation_token
    handle = S._ISSUED_GENERATION_TOKENS[token][0]
    closed_fd = handle.fd
    S.close_accepted_artifact_memberships(memberships)
    S.close_accepted_artifact_memberships(memberships)
    source_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    reused_fd = os.dup2(source_fd, closed_fd)
    try:
        assert reused_fd == closed_fd
        with pytest.raises(S.Stage12696Error, match="accepted_generation_root_closed"):
            S.build_package_inventory(**kwargs)
    finally:
        os.close(reused_fd)
        if source_fd != reused_fd:
            os.close(source_fd)


def test_externally_closed_fd_reused_for_same_root_inode_rejects(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    token = kwargs["stage12688_catalog"]._generation_token
    handle = S._ISSUED_GENERATION_TOKENS[token][0]
    closed_fd = handle.fd
    os.close(closed_fd)
    source_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    os.lseek(source_fd, handle.offset_cookie, os.SEEK_SET)
    reused_fd = os.dup2(source_fd, closed_fd)
    try:
        with pytest.raises(S.Stage12696Error, match="accepted_generation_root_fd_invalid_or_reused"):
            S.build_package_inventory(**kwargs)
    finally:
        os.close(reused_fd)
        if source_fd != reused_fd:
            os.close(source_fd)
        handle.fd = -1
        handle.close()


def test_dup2_from_guard_preserves_original_open_file_description(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    token = kwargs["stage12688_catalog"]._generation_token
    handle = S._ISSUED_GENERATION_TOKENS[token][0]
    os.dup2(handle.guard_fd, handle.fd)
    # This is not replacement: both descriptors still reference the loader's
    # original pinned open-file description and all root/path/inode checks hold.
    inventory = S.build_package_inventory(**kwargs)
    assert inventory.capacity["authenticated_unique_repositories"] == 1


def test_nonseekable_reused_root_fd_rejects(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    token = kwargs["stage12688_catalog"]._generation_token
    handle = S._ISSUED_GENERATION_TOKENS[token][0]
    read_fd, write_fd = os.pipe()
    os.dup2(read_fd, handle.fd)
    try:
        with pytest.raises(S.Stage12696Error, match="accepted_generation_root_fd_invalid_or_reused"):
            S.build_package_inventory(**kwargs)
    finally:
        os.close(read_fd)
        os.close(write_fd)
        handle.fd = -1
        handle.close()


def test_live_offset_challenge_is_concurrent_and_restores_position(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    token = kwargs["stage12688_catalog"]._generation_token
    handle = S._ISSUED_GENERATION_TOKENS[token][0]

    def challenge_many(_worker: int) -> None:
        for _ in range(25):
            handle.revalidate()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(challenge_many, range(8)))
    assert os.lseek(handle.fd, 0, os.SEEK_CUR) == handle.offset_cookie
    assert os.lseek(handle.guard_fd, 0, os.SEEK_CUR) == handle.offset_cookie
    assert S.build_package_inventory(**kwargs).capacity["authenticated_git_heads"] == 1


def test_hard_linked_accepted_leaf_rejects(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    os.link(tmp_path / "s88.jsonl", tmp_path / "s88-hardlink.jsonl")
    with pytest.raises(S.Stage12696Error, match="descriptor_leaf_hard_link_rejected"):
        S.build_package_inventory(**kwargs)


def test_generation_root_replacement_before_inventory_rejects(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    moved = tmp_path.parent / f"{tmp_path.name}-pinned"
    tmp_path.rename(moved)
    tmp_path.mkdir()
    with pytest.raises(S.Stage12696Error, match="accepted_generation_root_path_replaced"):
        S.build_package_inventory(**kwargs)


def test_generation_root_replacement_race_rejects_after_descriptor_work(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    moved = tmp_path.parent / f"{tmp_path.name}-raced"
    original = S._derive_git_head_evidence
    raced = False

    def replace_root_during_inventory(*args, **inner_kwargs):
        nonlocal raced
        if not raced:
            raced = True
            tmp_path.rename(moved)
            tmp_path.mkdir()
        return original(*args, **inner_kwargs)

    monkeypatch.setattr(S, "_derive_git_head_evidence", replace_root_during_inventory)
    with pytest.raises(S.Stage12696Error, match="accepted_generation_root_path_replaced"):
        S.build_package_inventory(**kwargs)
    assert raced


def test_unique_repository_budget_is_shared_across_lanes(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    one_repo_limits = S.PackageLimits(**{**S.PackageLimits().__dict__, "repositories": 1})
    inventory = S.build_package_inventory(**kwargs, limits=one_repo_limits)
    assert inventory.capacity["authenticated_unique_repositories"] == 1

    second_key = "2" * 64
    second_catalog = {"repository_key_sha256": second_key, "revision": "f" * 40}
    membership(tmp_path, "catalog92.jsonl", [second_catalog])
    accepted = load_fixture_generation(tmp_path, monkeypatch)
    kwargs.update(accepted)
    kwargs["repository_paths"] = {"1" * 64: "repo", second_key: "missing"}
    with pytest.raises(S.Stage12696Error, match="resource_limit_exceeded:repositories"):
        S.build_package_inventory(**kwargs, limits=one_repo_limits)



def test_artifact_and_repository_roots_are_independently_pinned(
    tmp_path: Path, monkeypatch,
) -> None:
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    repository_root = tmp_path / "repositories"
    repository_root.mkdir()
    (tmp_path / "repo").rename(repository_root / "repo")
    kwargs["repository_root"] = repository_root

    inventory = S.build_package_inventory(**kwargs)

    assert inventory.capacity["authenticated_unique_repositories"] == 1
    assert inventory.git_heads[0].component_objects


def test_separate_repository_root_replacement_race_rejects(
    tmp_path: Path, monkeypatch,
) -> None:
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    repository_root = tmp_path / "repositories"
    repository_root.mkdir()
    (tmp_path / "repo").rename(repository_root / "repo")
    kwargs["repository_root"] = repository_root
    moved = tmp_path / "repositories-pinned"
    original = S._derive_git_head_evidence
    raced = False

    def replace_repository_root(*args, **inner_kwargs):
        nonlocal raced
        if not raced:
            raced = True
            repository_root.rename(moved)
            repository_root.mkdir()
        return original(*args, **inner_kwargs)

    monkeypatch.setattr(S, "_derive_git_head_evidence", replace_repository_root)
    with pytest.raises(
        S.Stage12696Error, match="accepted_generation_root_path_replaced",
    ):
        S.build_package_inventory(**kwargs)
    assert raced


def test_inventory_commitment_is_deterministic_and_authority_closed(tmp_path: Path, monkeypatch):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    first = S.build_package_inventory(**kwargs)
    second = S.build_package_inventory(**kwargs)
    assert first.package_manifest_sha256 == second.package_manifest_sha256
    assert first.capacity == {"authenticated_git_heads": 1, "authenticated_declaration_rows": 1, "unique_declaration_blobs": 1, "authenticated_unique_repositories": 1, "training_eligible_rows": 0}
    assert not any(first.authority.values())
    assert not hasattr(S, "publish")


def _two_repository_inventory_kwargs(tmp_path: Path, monkeypatch) -> dict:
    first_repo, first_revision = repository(tmp_path)
    second_parent = tmp_path / "second"
    second_parent.mkdir()
    second_repo, second_revision = repository(second_parent)
    records = []
    rows = []
    catalogs = []
    proofs = []
    paths = {}
    for key, revision, repo, relative_path in (
        ("1" * 64, first_revision, first_repo, "repo"),
        ("2" * 64, second_revision, second_repo, "second/repo"),
    ):
        row, proof = declaration(key, revision, repo)
        records.append(catalog(key, revision, repo))
        catalogs.append({
            **catalog(key, revision, repo),
            "tree_oid": row["source_provenance"]["tree_oid"],
            "content_component_sha256":
                row["source_provenance"]["content_component_sha256"],
        })
        rows.append(row)
        proofs.append(proof)
        paths[key] = relative_path
    membership(tmp_path, "s88.jsonl", records)
    membership(tmp_path, "rows.jsonl", rows)
    membership(tmp_path, "catalog92.jsonl", catalogs)
    membership(tmp_path, "proofs.jsonl", proofs)
    return {
        **load_fixture_generation(tmp_path, monkeypatch),
        "repository_root": tmp_path,
        "repository_paths": paths,
    }


def test_inventory_bounds_active_repository_descriptors_and_readers(
    tmp_path: Path, monkeypatch,
):
    kwargs = _two_repository_inventory_kwargs(tmp_path, monkeypatch)
    original_pin = S.pin_repository_at_fd
    original_reader = S._BatchObjectReader
    active_repositories = 0
    active_readers = 0
    maximum_repositories = 0
    maximum_readers = 0
    reader_starts = 0

    @contextmanager
    def tracked_pin(*args, **inner_kwargs):
        nonlocal active_repositories, maximum_repositories
        active_repositories += 1
        maximum_repositories = max(maximum_repositories, active_repositories)
        try:
            with original_pin(*args, **inner_kwargs) as repo:
                yield repo
        finally:
            active_repositories -= 1

    class TrackedReader:
        def __init__(self, *args, **inner_kwargs):
            self.inner = original_reader(*args, **inner_kwargs)

        def __enter__(self):
            nonlocal active_readers, maximum_readers, reader_starts
            active_readers += 1
            reader_starts += 1
            maximum_readers = max(maximum_readers, active_readers)
            try:
                return self.inner.__enter__()
            except BaseException:
                active_readers -= 1
                raise

        def __exit__(self, *args):
            nonlocal active_readers
            try:
                return self.inner.__exit__(*args)
            finally:
                active_readers -= 1

    monkeypatch.setattr(S, "pin_repository_at_fd", tracked_pin)
    monkeypatch.setattr(S, "_BatchObjectReader", TrackedReader)
    inventory = S.build_package_inventory(**kwargs)

    assert inventory.capacity["authenticated_unique_repositories"] == 2
    assert maximum_repositories == 1
    assert maximum_readers == 1
    assert reader_starts == 2
    assert active_repositories == active_readers == 0


def test_production_scale_inventory_lifecycle_proxy(
    tmp_path: Path, monkeypatch,
):
    repository_count = 479
    declaration_count = 1692
    metadata_records = []
    catalog_records = []
    rows = []
    proofs = []
    repository_paths = {}
    for index in range(repository_count):
        key = hashlib.sha256(f"repo:{index}".encode()).hexdigest()
        revision = f"{index + 1:040x}"
        tree = f"{index + 1000:040x}"
        component = hashlib.sha256(f"component:{index}".encode()).hexdigest()
        metadata_records.append({
            "repository_key_sha256": key, "revision": revision,
        })
        catalog_records.append({
            "repository_key_sha256": key, "revision": revision,
            "tree_oid": tree, "content_component_sha256": component,
        })
        repository_paths[key] = f"repo-{index:03d}"
    for index in range(declaration_count):
        repository_index = index % repository_count
        catalog_record = catalog_records[repository_index]
        row_id = f"row:{index}"
        row = {
            "row_id": row_id,
            "source_provenance": {
                "repository_key_sha256":
                    catalog_record["repository_key_sha256"],
                "revision": catalog_record["revision"],
                "tree_oid": catalog_record["tree_oid"],
                "content_component_sha256":
                    catalog_record["content_component_sha256"],
            },
        }
        rows.append(row)
        proofs.append({"row_id": row_id})
    membership(tmp_path, "s88.jsonl", metadata_records)
    membership(tmp_path, "rows.jsonl", rows)
    membership(tmp_path, "catalog92.jsonl", catalog_records)
    membership(tmp_path, "proofs.jsonl", proofs)
    accepted = load_fixture_generation(tmp_path, monkeypatch)
    active_repositories = 0
    active_readers = 0
    maximum_repositories = 0
    maximum_readers = 0
    reader_starts = 0

    @contextmanager
    def fake_pin(_root, _root_fd, relative_path):
        nonlocal active_repositories, maximum_repositories
        active_repositories += 1
        maximum_repositories = max(maximum_repositories, active_repositories)
        try:
            yield SimpleNamespace(relative_path=relative_path)
        finally:
            active_repositories -= 1

    class FakeReader:
        def __init__(self, _repo, _budget):
            pass

        def __enter__(self):
            nonlocal active_readers, maximum_readers, reader_starts
            active_readers += 1
            reader_starts += 1
            maximum_readers = max(maximum_readers, active_readers)
            return self

        def __exit__(self, *_args):
            nonlocal active_readers
            active_readers -= 1

    def fake_head(record, _line_hash, _repo, _budget, _lineage):
        return SimpleNamespace(
            evidence_commitment_sha256=hashlib.sha256(
                record["repository_key_sha256"].encode()
            ).hexdigest(),
        )

    def fake_declaration(row, _proof, _row_hash, _proof_hash, _repo, _budget,
                         _blob_cache, _parser_cache):
        return SimpleNamespace(
            revision=row["source_provenance"]["revision"],
            source_blob_oid=hashlib.sha1(row["row_id"].encode()).hexdigest(),
            evidence_commitment_sha256=hashlib.sha256(
                row["row_id"].encode()
            ).hexdigest(),
        )

    monkeypatch.setattr(S, "pin_repository_at_fd", fake_pin)
    monkeypatch.setattr(S, "_BatchObjectReader", FakeReader)
    monkeypatch.setattr(S, "_derive_git_head_evidence", fake_head)
    monkeypatch.setattr(S, "_authenticate_declaration_row", fake_declaration)

    inventory = S.build_package_inventory(
        **accepted,
        repository_root=tmp_path,
        repository_paths=repository_paths,
    )

    assert inventory.capacity == {
        "authenticated_git_heads": repository_count,
        "authenticated_declaration_rows": declaration_count,
        "unique_declaration_blobs": declaration_count,
        "authenticated_unique_repositories": repository_count,
        "training_eligible_rows": 0,
    }
    assert reader_starts == repository_count
    assert maximum_repositories == maximum_readers == 1
    assert active_repositories == active_readers == 0


def test_nested_tree_reads_use_one_persistent_object_process(
    tmp_path: Path, monkeypatch,
):
    repo, _revision = repository(tmp_path)
    for index in range(40):
        path = repo / "nested" / f"d{index:03d}"
        path.mkdir(parents=True)
        (path / "value.txt").write_text(str(index), encoding="ascii")
    git(repo, "add", "nested")
    git(repo, "commit", "-qm", "nested tree proxy")
    revision = git(repo, "rev-parse", "HEAD")
    launches = []
    batch_environments = []
    original_popen = S.subprocess.Popen

    def tracked_popen(command, *args, **kwargs):
        launches.append(tuple(command))
        if tuple(command[-2:]) == ("cat-file", "--batch"):
            batch_environments.append(dict(kwargs.get("env", {})))
        return original_popen(command, *args, **kwargs)

    monkeypatch.setattr(S.subprocess, "Popen", tracked_popen)
    started = time.monotonic()
    evidence = S.derive_git_head_evidence(
        catalog("1" * 64, revision, repo), "2" * 64,
        tmp_path, "repo", S.WorkBudget(S.PackageLimits()),
    )
    object_batches = [
        command for command in launches
        if command[-2:] == ("cat-file", "--batch")
    ]
    batch_checks = [
        command for command in launches
        if command[-1].startswith("--batch-check=")
    ]
    direct_tree_reads = [
        command for command in launches
        if len(command) >= 3 and command[-3:-1] == ("cat-file", "tree")
    ]
    elapsed = time.monotonic() - started
    assert evidence.tree_count >= 41
    assert elapsed < 15
    assert len(object_batches) == 1
    assert len(batch_checks) == 1
    assert batch_environments[0]["GIT_NO_LAZY_FETCH"] == "1"
    assert direct_tree_reads == []


def test_declaration_blob_and_parser_cache_are_reused_and_nonforgeable(
    tmp_path: Path, monkeypatch,
):
    repo, revision = repository(tmp_path)
    row, proof = declaration("1" * 64, revision, repo)
    find_calls = 0
    parser_calls = 0
    original_find = S._find_blob
    original_adapter = S._adapter_rows

    def tracked_find(*args, **kwargs):
        nonlocal find_calls
        find_calls += 1
        return original_find(*args, **kwargs)

    def tracked_adapter(*args, **kwargs):
        nonlocal parser_calls
        parser_calls += 1
        return original_adapter(*args, **kwargs)

    monkeypatch.setattr(S, "_find_blob", tracked_find)
    monkeypatch.setattr(S, "_adapter_rows", tracked_adapter)
    budget = S.WorkBudget(S.PackageLimits())
    budget.begin_repository()
    blob_cache = {}
    parser_cache = {}
    with S.pin_repository_at_root(tmp_path, "repo") as pinned:
        with S._BatchObjectReader(pinned, budget) as reader:
            pinned._stage12696_object_reader = reader
            first = S._authenticate_declaration_row(
                row, proof, "3" * 64, "4" * 64, pinned, budget,
                blob_cache, parser_cache,
            )
            second = S._authenticate_declaration_row(
                row, proof, "3" * 64, "4" * 64, pinned, budget,
                blob_cache, parser_cache,
            )
            forged = json.loads(json.dumps(row))
            forged["target"]["decoder_text"] = "forged"
            forged_proof = dict(proof)
            forged_proof["row_sha256"] = S.S92.stage12688.stable(forged)
            with pytest.raises(S.Stage12696Error, match="declaration_row_not_reproduced"):
                S._authenticate_declaration_row(
                    forged, forged_proof, "3" * 64, "4" * 64,
                    pinned, budget, blob_cache, parser_cache,
                )
    assert first == second
    assert find_calls == 1
    assert parser_calls == 1
    assert len(blob_cache) == len(parser_cache) == 1


def test_accepted_member_replacement_during_repository_work_rejects(
    tmp_path: Path, monkeypatch,
):
    kwargs = inventory_kwargs(tmp_path, monkeypatch)
    original = S._derive_git_head_evidence
    replaced = False

    def replace_member(*args, **inner_kwargs):
        nonlocal replaced
        result = original(*args, **inner_kwargs)
        if not replaced:
            replaced = True
            accepted = tmp_path / "s88.jsonl"
            replacement = tmp_path / "s88-replacement.jsonl"
            replacement.write_bytes(accepted.read_bytes())
            replacement.replace(accepted)
        return result

    monkeypatch.setattr(S, "_derive_git_head_evidence", replace_member)
    with pytest.raises(S.Stage12696Error, match="authenticated_membership_replaced"):
        S.build_package_inventory(**kwargs)
    assert replaced


def _reader_protocol_fixture(monkeypatch, data: bytes = b"payload"):
    budget = S.WorkBudget(S.PackageLimits())
    budget.begin_repository()
    reader = S._BatchObjectReader(
        SimpleNamespace(repo_fd=10, git_fd=11), budget,
    )
    reader.process = SimpleNamespace(poll=lambda: None)
    oid = S.S93._git_object_oid("blob", data, 40)
    monkeypatch.setattr(reader, "_write", lambda _payload, _deadline: None)
    return reader, oid, data


def test_batch_reader_rejects_malformed_wrong_identity_and_oversize_headers(
    monkeypatch,
):
    cases = (
        (b"malformed", "batch_object_identity_mismatch"),
        ((("f" * 40) + " blob 7").encode(), "batch_object_identity_mismatch"),
        (None, "batch_object_identity_mismatch"),
        (None, "batch_object_size_exceeded"),
        (b"\xff", "batch_object_header_invalid"),
    )
    for index, (header, expected) in enumerate(cases):
        reader, oid, data = _reader_protocol_fixture(monkeypatch)
        if index == 2:
            header = f"{oid} tree {len(data)}".encode()
        elif index == 3:
            header = f"{oid} blob {S.MAX_BATCH_RESPONSE_BYTES + 1}".encode()
        monkeypatch.setattr(reader, "_line", lambda _deadline, value=header: value)
        monkeypatch.setattr(
            reader, "_exact", lambda _size, _deadline, value=data: value + b"\n",
        )
        with pytest.raises(S.Stage12696Error, match=expected):
            reader.read(oid, "blob")


def test_batch_reader_rejects_bad_framing_and_digest_mismatch(monkeypatch):
    reader, oid, data = _reader_protocol_fixture(monkeypatch)
    monkeypatch.setattr(
        reader, "_line", lambda _deadline: f"{oid} blob {len(data)}".encode(),
    )
    monkeypatch.setattr(reader, "_exact", lambda _size, _deadline: data + b"x")
    with pytest.raises(S.Stage12696Error, match="batch_object_framing_invalid"):
        reader.read(oid, "blob")

    reader, oid, data = _reader_protocol_fixture(monkeypatch)
    monkeypatch.setattr(
        reader, "_line", lambda _deadline: f"{oid} blob {len(data)}".encode(),
    )
    monkeypatch.setattr(
        reader, "_exact", lambda _size, _deadline: b"x" * len(data) + b"\n",
    )
    with pytest.raises(S.Stage12696Error, match="batch_object_digest_mismatch"):
        reader.read(oid, "blob")


def test_batch_reader_timeout_and_request_exhaustion(monkeypatch):
    reader, oid, _data = _reader_protocol_fixture(monkeypatch)
    monkeypatch.setattr(
        reader, "_write",
        lambda *_args: (_ for _ in ()).throw(
            S.Stage12696Error("batch_object_reader_timeout")
        ),
    )
    with pytest.raises(S.Stage12696Error, match="batch_object_reader_timeout"):
        reader.read(oid, "blob")

    reader, _oid, _data = _reader_protocol_fixture(monkeypatch)
    reader._write = S._BatchObjectReader._write.__get__(
        reader, S._BatchObjectReader,
    )
    reader.request_bytes = S.MAX_BATCH_REQUEST_BYTES
    with pytest.raises(S.Stage12696Error, match="request_bytes_exceeded"):
        reader._write(b"x", time.monotonic() + 1)


def test_batch_reader_broken_pipe_eof_and_response_exhaustion(monkeypatch):
    budget = S.WorkBudget(S.PackageLimits())
    budget.begin_repository()
    reader = S._BatchObjectReader(SimpleNamespace(repo_fd=10, git_fd=11), budget)
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    writer = os.fdopen(write_fd, "wb", buffering=0)
    reader.process = SimpleNamespace(stdin=writer)
    with pytest.raises(S.Stage12696Error, match="reader_write_failed"):
        reader._write(b"x", time.monotonic() + 1)
    writer.close()

    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    reader.process = SimpleNamespace(stdout=os.fdopen(read_fd, "rb", buffering=0))
    with pytest.raises(S.Stage12696Error, match="unexpected_eof"):
        reader._fill(time.monotonic() + 1)
    reader.process.stdout.close()

    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"x")
    os.close(write_fd)
    reader.process = SimpleNamespace(stdout=os.fdopen(read_fd, "rb", buffering=0))
    reader.response_bytes = S.MAX_BATCH_RESPONSE_BYTES
    with pytest.raises(S.Stage12696Error, match="response_bytes_exceeded"):
        reader._fill(time.monotonic() + 1)
    reader.process.stdout.close()


def test_batch_reader_timeout_cleans_process_group(monkeypatch):
    budget = S.WorkBudget(S.PackageLimits())
    budget.begin_repository()
    reader = S._BatchObjectReader(SimpleNamespace(repo_fd=10, git_fd=11), budget)

    class Stream:
        closed = False

        def close(self):
            self.closed = True

    class Process:
        pid = 4321
        stdin = Stream()
        stdout = Stream()

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("git", timeout)

    process = Process()
    reader.process = process
    cleaned = []
    monkeypatch.setattr(S, "_kill_process_group", lambda value: cleaned.append(value))
    with pytest.raises(S.Stage12696Error, match="reader_exit_failed"):
        reader.__exit__(None, None, None)
    assert cleaned == [process]
    assert process.stdout.closed


def test_work_budget_deadlines_are_cumulative_and_minimum(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(S.time, "monotonic", lambda: clock[0])
    limits = S.PackageLimits(
        object_read_seconds=5.0, repository_seconds=10.0,
        inventory_seconds=20.0,
    )
    budget = S.WorkBudget(limits)
    budget.begin_repository()
    assert budget.operation_deadline() == 105.0
    clock[0] = 107.0
    assert budget.operation_deadline() == 110.0
    clock[0] = 110.0
    with pytest.raises(S.Stage12696Error, match="repository_deadline_exceeded"):
        budget.operation_deadline()

    clock[0] = 200.0
    budget = S.WorkBudget(S.PackageLimits(
        object_read_seconds=50.0, repository_seconds=50.0,
        inventory_seconds=10.0,
    ))
    budget.begin_repository()
    assert budget.operation_deadline() == 210.0
    clock[0] = 210.0
    with pytest.raises(S.Stage12696Error, match="inventory_deadline_exceeded"):
        budget.operation_deadline()


def test_batch_reader_uses_budget_capped_deadline(monkeypatch):
    clock = [50.0]
    monkeypatch.setattr(S.time, "monotonic", lambda: clock[0])
    budget = S.WorkBudget(S.PackageLimits(
        object_read_seconds=8.0, repository_seconds=5.0,
        inventory_seconds=20.0,
    ))
    budget.begin_repository()
    reader = S._BatchObjectReader(SimpleNamespace(repo_fd=10, git_fd=11), budget)
    reader.process = SimpleNamespace(poll=lambda: None)
    data = b"payload"
    oid = S.S93._git_object_oid("blob", data, 40)
    observed = []
    monkeypatch.setattr(
        reader, "_write", lambda _payload, deadline: observed.append(deadline),
    )
    monkeypatch.setattr(
        reader, "_line", lambda deadline: (
            observed.append(deadline) or f"{oid} blob {len(data)}".encode()
        ),
    )
    monkeypatch.setattr(
        reader, "_exact", lambda _size, deadline: (
            observed.append(deadline) or data + b"\n"
        ),
    )
    assert reader.read(oid, "blob") == data
    assert observed == [55.0, 55.0, 55.0]


def test_no_stage12695_dependency_or_output_path():
    text = SCRIPT.read_text()
    assert "stage12695" not in text.lower()
    assert "output-dir" not in text
    assert "write_text" not in text and "write_bytes" not in text


def test_accepted_artifact_hashes_are_sha256_and_generation_pinned():
    assert set(S.ACCEPTED_ARTIFACT_SHA256S) == {
        "stage12688_catalog", "stage12692_rows", "stage12692_catalog", "stage12692_ledger"
    }
    assert all(len(value) == 64 for value in S.ACCEPTED_ARTIFACT_SHA256S.values())
    assert S.ACCEPTED_STAGE12688_GENERATION == "23cac72b1c420605413d0f77"
    assert S.ACCEPTED_STAGE12692_GENERATION.startswith("0251bea687f8")
