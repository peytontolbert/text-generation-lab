from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12693_source_backed_historical_old_language_retention.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12693", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    return result.stdout.strip()


def commit(repo: Path, message: str, timestamp: str) -> str:
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp})
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD")


def make_history(tmp_path: Path) -> tuple[Path, str, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    source = repo / "old.py"
    source.write_bytes("# café\r\ndef old_value():\r\n    return '雪'\r\n".encode())
    root = commit(repo, "historical root", "2014-08-03T00:00:00+0530")
    source.write_bytes("# café\r\ndef old_value():\r\n    return '雪-v2'\r\n".encode())
    child = commit(repo, "historical child", "2018-08-03T00:00:00-0400")
    source.unlink()
    (repo / "current.py").write_text("def current():\n    return 3\n", encoding="utf-8")
    head = commit(repo, "current head", "2025-08-03T00:00:00Z")
    return repo, root, child, head


def test_pin_head_verified_objects_and_descriptor_command_allowlist(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, _child, head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        assert pinned.head_oid == head
        raw = module.read_verified_object(pinned, head, "commit")
        assert module.read_commit(pinned, head).oid == head
        assert module.verify_object_oid(head, "commit", raw)
        with pytest.raises(module.Stage12693Error, match="disallowed"):
            pinned.git("status")
        with pytest.raises(module.Stage12693Error, match="disallowed"):
            pinned.git("cat-file", "--filters", head)
    with pytest.raises(module.Stage12693Error, match="closed"):
        pinned.git("rev-parse", "HEAD")


def test_repository_path_replacement_cannot_change_pinned_head(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, _child, original_head = make_history(tmp_path)
    pinned = module.pin_repository(repo.resolve())
    try:
        moved = tmp_path / "moved-original"
        repo.rename(moved)
        replacement = tmp_path / "repo"
        replacement.mkdir()
        git(replacement, "init", "-q")
        git(replacement, "config", "user.email", "fixture@example.invalid")
        git(replacement, "config", "user.name", "Fixture")
        (replacement / "replacement.py").write_text("replacement = True\n", encoding="utf-8")
        replacement_head = commit(replacement, "replacement", "2025-08-03T00:00:00Z")
        assert replacement_head != original_head
        assert pinned.head_oid == original_head
        assert module.read_commit(pinned, original_head).oid == original_head
        assert module.build_current_head_exclusion_inventory(pinned).pinned_head_oid == original_head
    finally:
        pinned.close()


def test_relative_repo_and_git_symlink_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    with pytest.raises(module.Stage12693Error, match="absolute"):
        module.pin_repository(Path("relative"))
    actual = tmp_path / "actual"
    actual.mkdir()
    git(actual, "init", "-q")
    wrapper = tmp_path / "wrapper"
    wrapper.mkdir()
    (wrapper / ".git").symlink_to(actual / ".git", target_is_directory=True)
    with pytest.raises(module.Stage12693Error, match="pin_failed"):
        module.pin_repository(wrapper.resolve())


def test_raw_commit_strictness_tamper_and_timestamp(tmp_path: Path) -> None:
    module = load_module()
    repo, root, _child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        raw = module.read_verified_object(pinned, root, "commit")
        parsed = module.parse_raw_commit(raw, root)
        assert parsed.committer_timezone == "+0530"
        assert not module.verify_object_oid(root, "commit", raw + b"tamper")
    tree = b"1" * 40
    base = b"tree " + tree + b"\nauthor A <a@b> 1 +0000\ncommitter A <a@b> 1 +0000\n\nx"
    assert module.parse_raw_commit(base).tree_oid == "1" * 40
    malformed = (
        base.replace(b"tree ", b"tree " + tree + b"\ntree ", 1),
        base.replace(b"committer ", b"committer A <a@b> 1 +0000\ncommitter ", 1),
        base.replace(b"+0000", b"+1460"),
        base.replace(b"\n\n", b"\r\n\r\n"),
    )
    for value in malformed:
        with pytest.raises(module.Stage12693Error):
            module.parse_raw_commit(value)


def test_commit_parser_accepts_cr_message_and_generic_signed_headers() -> None:
    module = load_module()
    tree = b"1" * 40
    parent = b"2" * 40
    raw = (
        b"tree " + tree + b"\nparent " + parent
        + b"\nauthor A <a@b> 1 +0000"
        + b"\ngpgsig -----BEGIN SIGNATURE-----\n signed-line\r"
        + b"\nmergetag object " + parent + b"\n type commit\n tag v1"
        + b"\ncommitter A <a@b> 1 +0000\n\nlegal\rmessage\r\nbody"
    )
    parsed = module.parse_raw_commit(raw)
    assert parsed.tree_oid == tree.decode()
    assert parsed.parent_oids == (parent.decode(),)
    with pytest.raises(
        module.Stage12693Error, match="critical_commit_header_continuation"
    ):
        module.parse_raw_commit(
            b"tree " + tree + b"\n forged\n"
            b"committer A <a@b> 1 +0000\n\nx"
        )


def test_repository_cache_reuses_only_same_pinned_repo_and_scope(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, _child, _head = make_history(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q")
    git(other, "config", "user.email", "fixture@example.invalid")
    git(other, "config", "user.name", "Fixture")
    (other / "other.py").write_text("other = 1\n", encoding="utf-8")
    commit(other, "other", "2025-08-03T00:00:00Z")
    root_fd = module._open_directory(tmp_path.resolve())
    try:
        with module.cumulative_work_scope() as budget:
            with module.pin_repository_at(root_fd, "repo", tmp_path.resolve()) as first:
                module.read_commit(first, first.head_oid)
                before = (
                    budget.object_reads,
                    budget.total_blob_bytes_read,
                    dict(first.cache.counters),
                )
                module.read_commit(first, first.head_oid)
                assert budget.object_reads == before[0]
                assert budget.total_blob_bytes_read == before[1]
                first_cache = first.cache
            with module.pin_repository_at(root_fd, "repo", tmp_path.resolve()) as reopened:
                assert reopened.cache is first_cache
                assert reopened.cache.counters["repository_cache_reused"] >= 1
            with module.pin_repository_at(root_fd, "other", tmp_path.resolve()) as distinct:
                assert distinct.cache is not first_cache
    finally:
        os.close(root_fd)


def test_verified_reader_rejects_tampered_git_payload(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repo, _root, _child, head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        original = pinned.git

        def tampered(
            *args: str, timeout: int = 60, max_stdout_bytes: int = 256
        ) -> bytes:
            data = original(
                *args, timeout=timeout, max_stdout_bytes=max_stdout_bytes
            )
            return data + b"tamper" if args == ("cat-file", "commit", head) else data

        monkeypatch.setattr(pinned, "git", tampered)
        pinned.cache.raw_objects.pop((head, "commit"))
        with pytest.raises(module.Stage12693Error, match="identity_mismatch"):
            module.read_verified_object(pinned, head, "commit")


def test_exact_age_boundaries() -> None:
    module = load_module()
    utc = dt.timezone.utc

    def epoch(year: int) -> int:
        return int(dt.datetime(year, 8, 3, tzinfo=utc).timestamp())

    assert module.age_bucket(epoch(2024) + 1) is None
    assert module.age_bucket(epoch(2024)) == "historical_2_to_5_years"
    assert module.age_bucket(epoch(2021) + 1) == "historical_2_to_5_years"
    assert module.age_bucket(epoch(2021)) == "historical_5_to_10_years"
    assert module.age_bucket(epoch(2016) + 1) == "historical_5_to_10_years"
    assert module.age_bucket(epoch(2016)) == "historical_10_plus_years"
    with pytest.raises(module.Stage12693Error, match="naive"):
        module.age_bucket(epoch(2016), dt.datetime(2026, 8, 3))


def test_deterministic_single_parent_edges_exclude_root_and_merge(tmp_path: Path) -> None:
    module = load_module()
    repo, root, child, _head = make_history(tmp_path)
    git(repo, "checkout", "-q", "-b", "side", child)
    (repo / "side.py").write_text("side = True\n", encoding="utf-8")
    commit(repo, "side", "2020-08-03T00:00:00Z")
    git(repo, "checkout", "-q", "master")
    git(repo, "merge", "-q", "--no-ff", "side", "-m", "merge side")
    merge_oid = git(repo, "rev-parse", "HEAD")
    with module.pin_repository(repo.resolve()) as pinned:
        first = module.enumerate_single_parent_edges(pinned)
        assert first == module.enumerate_single_parent_edges(pinned)
        assert tuple(sorted(first, key=lambda edge: (edge.child_oid, edge.parent_oid))) == first
        assert root not in {edge.child_oid for edge in first}
        assert merge_oid not in {edge.child_oid for edge in first}
        assert child in {edge.child_oid for edge in first}


def test_tree_inventory_historical_exclusion_and_exact_bytes(tmp_path: Path) -> None:
    module = load_module()
    repo, root, child, head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        head_commit = module.read_commit(pinned, head)
        immediate = module.list_tree_immediate(pinned, head_commit.tree_oid)
        recursive = module.list_tree_recursive(pinned, head_commit.tree_oid)
        assert [entry.path for entry in immediate] == ["current.py"]
        assert [entry.path for entry in recursive] == ["current.py"]
        inventory = module.build_current_head_exclusion_inventory(pinned)
        current_data = module.read_verified_object(pinned, recursive[0].oid, "blob")
        assert recursive[0].oid in inventory.blob_oids
        assert hashlib.sha256(current_data).hexdigest() in inventory.file_sha256s
        assert head_commit.tree_oid in inventory.tree_oids
        edge = next(edge for edge in module.enumerate_single_parent_edges(pinned) if edge.child_oid == child)
        candidates = module.select_historical_blobs_absent_from_current_head(pinned, edge, inventory)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.parent_commit_oid == root
        assert candidate.path == "old.py"
        assert candidate.language_family == "python"
        assert candidate.data == "# café\r\ndef old_value():\r\n    return '雪'\r\n".encode()
        assert candidate.file_sha256 not in inventory.file_sha256s


def test_same_blob_or_same_bytes_at_head_are_excluded(tmp_path: Path) -> None:
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    shared = b"def retained():\n    return 1\n"
    (repo / "old.py").write_bytes(shared)
    root = commit(repo, "root", "2014-08-03T00:00:00Z")
    (repo / "old.py").unlink()
    (repo / "renamed.py").write_bytes(shared)
    child = commit(repo, "rename", "2018-08-03T00:00:00Z")
    (repo / "next.py").write_text("value = 2\n", encoding="utf-8")
    commit(repo, "head", "2025-08-03T00:00:00Z")
    with module.pin_repository(repo.resolve()) as pinned:
        inventory = module.build_current_head_exclusion_inventory(pinned)
        edge = next(edge for edge in module.enumerate_single_parent_edges(pinned) if edge.child_oid == child)
        assert edge.parent_oid == root
        assert module.select_historical_blobs_absent_from_current_head(pinned, edge, inventory) == ()


def test_stage12688_filters_languages_and_uppercase_sentinels() -> None:
    module = load_module()
    paths = {
        "a.py": "python", "a.ts": "javascript_typescript", "a.go": "go",
        "a.rs": "rust", "A.java": "java", "a.cpp": "c_cpp", "a.sh": "shell",
        "README.md": "markdown", "a.rst": "restructuredtext", "a.json": "json",
        "a.toml": "toml", "a.yaml": "yaml",
    }
    observed = {path: module.classify_required_language(path).language_family for path in paths}
    assert observed == paths
    assert module.historical_content_rejection_reason(b"safe = 1\n" * 4) is None
    assert module.historical_content_rejection_reason(b"COMMIT_PLACEHOLDER\n" * 4) == "unresolved_sentinel"
    assert module.historical_content_rejection_reason(b"TITLE_PLACEHOLDER\n" * 4) == "unresolved_sentinel"
    generated = b"# This file is automatically generated\nvalue = 1\n"
    assert module.historical_content_rejection_reason(generated) == "generated"
    assert module.historical_content_rejection_reason(b"token = 'AKIA1234567890ABCDEF'\n") == "secret"


def test_edge_and_inventory_tampering_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        inventory = module.build_current_head_exclusion_inventory(pinned)
        edge = next(edge for edge in module.enumerate_single_parent_edges(pinned) if edge.child_oid == child)
        bad_edge = module.HistoryEdge(
            edge.child_oid, edge.child_tree_oid, "0" * len(edge.parent_oid), edge.parent_tree_oid,
            edge.parent_committer_epoch, edge.parent_committer_timezone, edge.age_bucket,
        )
        with pytest.raises(module.Stage12693Error):
            module.select_historical_blobs_absent_from_current_head(pinned, bad_edge, inventory)
        bad_inventory = module.CurrentHeadExclusionInventory(
            "0" * len(pinned.head_oid), inventory.head_tree_oid, inventory.blob_oids,
            inventory.tree_oids, inventory.file_sha256s, inventory.inventory_sha256,
        )
        with pytest.raises(module.Stage12693Error, match="inventory"):
            module.select_historical_blobs_absent_from_current_head(pinned, edge, bad_inventory)


def test_forged_inventory_with_matching_head_fails(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        inventory = module.build_current_head_exclusion_inventory(pinned)
        edge = next(edge for edge in module.enumerate_single_parent_edges(pinned) if edge.child_oid == child)
        forged = module.CurrentHeadExclusionInventory(
            inventory.pinned_head_oid, inventory.head_tree_oid, frozenset(),
            inventory.tree_oids, inventory.file_sha256s, "0" * 64,
        )
        with pytest.raises(module.Stage12693Error, match="forged_or_stale"):
            module.select_historical_blobs_absent_from_current_head(pinned, edge, forged)


def test_raw_history_ignores_replace_grafts_and_shallow_environment(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    repo, root, child, head = make_history(tmp_path)
    info = repo / ".git" / "info"
    info.mkdir(exist_ok=True)
    (info / "grafts").write_text(head + "\n", encoding="ascii")
    git(repo, "replace", child, root)
    fake_shallow = tmp_path / "fake-shallow"
    fake_shallow.write_text(head + "\n", encoding="ascii")
    monkeypatch.setenv("GIT_SHALLOW_FILE", str(fake_shallow))
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/replace/")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "attacker-config"))
    with module.pin_repository(repo.resolve()) as pinned:
        edges = module.enumerate_single_parent_edges(pinned)
        identities = {(edge.child_oid, edge.parent_oid) for edge in edges}
        assert (head, child) in identities
        assert (child, root) in identities


def test_historical_symlink_named_as_source_is_not_candidate(tmp_path: Path) -> None:
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    os.symlink("real.py", repo / "symlink.py")
    root = commit(repo, "root", "2014-08-03T00:00:00Z")
    (repo / "symlink.py").unlink()
    child = commit(repo, "remove link", "2018-08-03T00:00:00Z")
    (repo / "current.py").write_text("current = True\n", encoding="utf-8")
    commit(repo, "head", "2025-08-03T00:00:00Z")
    with module.pin_repository(repo.resolve()) as pinned:
        inventory = module.build_current_head_exclusion_inventory(pinned)
        edge = next(edge for edge in module.enumerate_single_parent_edges(pinned) if edge.child_oid == child)
        assert edge.parent_oid == root
        assert module.select_historical_blobs_absent_from_current_head(
            pinned, edge, inventory
        ) == ()


def _raw_tree_entry(mode: bytes, name: bytes, fill: int) -> bytes:
    return mode + b" " + name + b"\0" + bytes([fill]) * 20


def test_tree_order_size_and_width_limits(monkeypatch) -> None:
    module = load_module()
    unsorted = (
        _raw_tree_entry(b"100644", b"z.py", 1)
        + _raw_tree_entry(b"100644", b"a.py", 2)
    )
    with pytest.raises(module.Stage12693Error, match="noncanonical_git_tree_order"):
        module.parse_raw_tree(unsorted, 40)
    ordered = (
        _raw_tree_entry(b"100644", b"a.py", 1)
        + _raw_tree_entry(b"100644", b"z.py", 2)
    )
    monkeypatch.setattr(module, "MAX_TREE_ENTRIES_PER_TREE", 1)
    with pytest.raises(module.Stage12693Error, match="tree_entry_limit"):
        module.parse_raw_tree(ordered, 40)
    monkeypatch.setattr(module, "MAX_TREE_ENTRIES_PER_TREE", 100)
    monkeypatch.setattr(module, "MAX_TREE_OBJECT_BYTES", 1)
    with pytest.raises(module.Stage12693Error, match="tree_size_limit"):
        module.parse_raw_tree(ordered, 40)


def test_stdout_blob_history_and_depth_limits(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repo, _root, _child, _head = make_history(tmp_path)
    nested = repo / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "deep.py").write_text("deep = True\n", encoding="utf-8")
    commit(repo, "deep head", "2025-08-04T00:00:00Z")
    with module.pin_repository(repo.resolve()) as pinned:
        with pytest.raises(module.Stage12693Error, match="stdout_limit"):
            pinned.git("rev-parse", "--verify", "HEAD^{commit}", max_stdout_bytes=1)

        head = module.read_commit(pinned, pinned.head_oid)
        entries = module.list_tree_recursive(pinned, head.tree_oid)
        blob_oid = next(entry.oid for entry in entries if entry.object_type == "blob")
        monkeypatch.setattr(module, "MAX_BLOB_OBJECT_BYTES", 1)
        pinned.cache.raw_objects.pop((blob_oid, "blob"), None)
        pinned.cache.object_metadata.pop((blob_oid, "blob"), None)
        with pytest.raises(module.Stage12693Error, match="blob_size_limit"):
            module.read_verified_object(pinned, blob_oid, "blob")

        monkeypatch.setattr(module, "MAX_BLOB_OBJECT_BYTES", 32 * 1024 * 1024)
        monkeypatch.setattr(module, "MAX_TREE_DEPTH", 1)
        with pytest.raises(module.Stage12693Error, match="tree_depth_limit"):
            module.list_tree_recursive(pinned, head.tree_oid)

        monkeypatch.setattr(module, "MAX_TREE_DEPTH", 64)
        monkeypatch.setattr(module, "MAX_HISTORY_COMMITS", 1)
        with pytest.raises(module.Stage12693Error, match="history_commit_limit"):
            module.enumerate_single_parent_edges(pinned)


def make_retention_history(tmp_path: Path) -> tuple[Path, str, str, str]:
    repo = tmp_path / "retention-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "old.py").write_bytes(
        "# café\r\ndef old_value():\r\n    return '雪'\r\n".encode()
    )
    (repo / "alpha.py").write_text(
        "def alpha_value():\n    return 'historical alpha value'\n", encoding="utf-8",
    )
    (repo / "beta.py").write_text(
        "def beta_value():\n    return 'historical beta value'\n", encoding="utf-8",
    )
    root = commit(repo, "historical root", "2014-08-03T00:00:00+0530")
    (repo / "old.py").write_bytes(
        "# café\r\ndef old_value():\r\n    return '雪-v2'\r\n".encode()
    )
    child = commit(repo, "historical child", "2018-08-03T00:00:00-0400")
    for name in ("old.py", "alpha.py", "beta.py"):
        (repo / name).unlink()
    (repo / "current.py").write_text(
        "def current_value():\n    return 'current only'\n", encoding="utf-8",
    )
    head = commit(repo, "current head", "2025-08-03T00:00:00Z")
    return repo, root, child, head


def test_historical_rows_exact_crlf_multibyte_directory_and_provenance(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, root, child, _head = make_retention_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        edge = next(
            edge for edge in module.enumerate_single_parent_edges(pinned)
            if edge.child_oid == child
        )
        material = module.construct_revision_material(pinned, "repo-key", edge)
        module.assign_historical_components([material])
        exclusion = module.build_current_head_example_exclusion(pinned, "repo-key")
        built = module.construct_historical_revision_rows(
            pinned, material, exclusion,
        )
        assert built.rows
        assert {
            row["objective_family"] for row in built.rows
        } == set(module.HISTORICAL_OBJECTIVES.values())
        span_row = next(
            row for row in built.rows
            if "雪" in row["target"]["decoder_text"]
        )
        provenance = span_row["source_provenance"]
        root_data = module.read_verified_object(
            pinned, provenance["git_blob_oid"], "blob"
        )
        start, end = provenance["span_start_byte"], provenance["span_end_byte"]
        assert root_data[start:end] == span_row["target"]["decoder_text"].encode()
        assert "\r\n" in span_row["target"]["decoder_text"]
        assert span_row["input_text"].count(module.S88.MASK) == 1
        assert root not in span_row["input_text"]
        assert provenance["historical_age_bucket"] not in span_row["input_text"]
        assert provenance["source_recorded_committer_timezone"] not in span_row["input_text"]
        assert provenance["exact_reconstruction_verified"]
        assert not any(span_row["authority"].values())


def test_target_mutation_rebuild_keeps_encoder_input(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, child, _head = make_retention_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        edge = next(
            edge for edge in module.enumerate_single_parent_edges(pinned)
            if edge.child_oid == child
        )
        inventory = module.build_current_head_exclusion_inventory(pinned)
        candidate = next(
            candidate for candidate in module.select_historical_blobs_absent_from_current_head(
                pinned, edge, inventory,
            )
            if candidate.path == "old.py"
        )
        span = next(
            span for span in module.S88.candidate_spans(
                candidate.data, "repo-key", candidate.path,
            )
            if "雪" in candidate.data[span[0]:span[1]].decode()
        )
        blob = module.S88.Blob(candidate.blob_oid, len(candidate.data), candidate.path)
        snapshot = module.S88.RepoSnapshot(
            local_path=repo, repo_key="repo-key", origin_url="",
            revision=edge.parent_oid, tree_oid=edge.parent_tree_oid,
            blobs=[blob], component_objects=(), lineage_keys=(),
        )
        kind = module.S88.classify_path(candidate.path)
        original = module.S88.build_span_row(
            snapshot, blob, kind, candidate.data, span, candidate.file_sha256,
        )
        changed_target = candidate.data[span[0]:span[1]].replace(
            "雪".encode(), "火".encode()
        )
        changed_data = (
            candidate.data[:span[0]] + changed_target + candidate.data[span[1]:]
        )
        changed = module.S88.build_span_row(
            snapshot, blob, kind, changed_data, span,
            module._sha256(changed_data),
        )
        assert original and changed
        assert original[0]["input_text"] == changed[0]["input_text"]
        assert original[0]["target"] != changed[0]["target"]


def test_current_head_comparable_example_duplicates_are_rejected(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = tmp_path / "duplicate-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    lines = [
        f"value_{index:02d} = '{index:02d}-" + ("x" * 180) + "'\n"
        for index in range(20)
    ]
    (repo / "shared.py").write_text("".join(lines), encoding="utf-8")
    root = commit(repo, "root", "2014-08-03T00:00:00Z")
    (repo / "marker.txt").write_text("child marker\n", encoding="utf-8")
    child_lines = list(lines)
    child_lines[-1] = child_lines[-1].replace("19-", "CHILD-")
    (repo / "shared.py").write_text("".join(child_lines), encoding="utf-8")
    child = commit(repo, "child", "2018-08-03T00:00:00Z")
    lines[-1] = lines[-1].replace("19-", "ZZ-")
    (repo / "shared.py").write_text("".join(lines), encoding="utf-8")
    commit(repo, "head", "2025-08-03T00:00:00Z")
    with module.pin_repository(repo.resolve()) as pinned:
        edge = next(
            edge for edge in module.enumerate_single_parent_edges(pinned)
            if edge.child_oid == child
        )
        material = module.construct_revision_material(pinned, "repo-key", edge)
        module.assign_historical_components([material])
        exclusion = module.build_current_head_example_exclusion(pinned, "repo-key")
        raw_candidates = module.select_historical_blobs_absent_from_current_head(
            pinned, edge, exclusion.base_inventory,
        )
        raw_pairs = module._construct_comparable_pairs(
            pinned, "repo-key", root, edge.parent_tree_oid,
            raw_candidates, material.component_key,
        )
        built = module.construct_historical_revision_rows(
            pinned, material, exclusion,
        )
        assert raw_pairs
        assert len(built.rows) < len(raw_pairs)
        assert all(
            proof["encoder_input_sha256"] not in exclusion.encoder_input_sha256s
            and proof["model_example_sha256"] not in exclusion.model_example_sha256s
            and proof["semantic_example_sha256"] not in exclusion.semantic_example_sha256s
            and proof["source_window_sha256"] not in exclusion.source_window_sha256s
            for proof in built.proofs
        )


def test_metadata_inventory_never_loads_huge_irrelevant_blob_payload(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo = tmp_path / "metadata-only"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "source.py").write_text("value = 1\n" * 4, encoding="utf-8")
    (repo / "irrelevant.bin").write_bytes(b"z" * (2 * 1024 * 1024))
    commit(repo, "head", "2025-08-03T00:00:00Z")
    huge_oid = git(repo, "rev-parse", "HEAD:irrelevant.bin")

    with module.pin_repository(repo.resolve()) as pinned:
        original = pinned.git
        payload_reads: list[str] = []

        def instrumented(
            *args: str, timeout: int = 60, max_stdout_bytes: int = 256,
        ) -> bytes:
            if args == ("cat-file", "blob", huge_oid):
                payload_reads.append(huge_oid)
            return original(
                *args, timeout=timeout, max_stdout_bytes=max_stdout_bytes,
            )

        monkeypatch.setattr(pinned, "git", instrumented)
        head = module.read_commit(pinned, pinned.head_oid)
        entries = module.list_tree_metadata_recursive(pinned, head.tree_oid)
        exclusion = module.build_current_head_example_exclusion(
            pinned, "fixture-repository-key",
        )

        assert any(entry.oid == huge_oid for entry in entries)
        assert huge_oid in exclusion.base_inventory.blob_oids
        assert payload_reads == []
        assert (huge_oid, "blob") not in pinned.cache.raw_objects


def test_changed_supported_blob_payload_is_loaded_exactly_once(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo, root, child, _head = make_history(tmp_path)
    root_blob_oid = git(repo, "rev-parse", f"{root}:old.py")
    with module.pin_repository(repo.resolve()) as pinned:
        edge = next(
            edge for edge in module.enumerate_single_parent_edges(pinned)
            if edge.child_oid == child
        )
        inventory = module.build_current_head_exclusion_inventory(pinned)
        original = pinned.git
        payload_reads: list[str] = []

        def instrumented(
            *args: str, timeout: int = 60, max_stdout_bytes: int = 256,
        ) -> bytes:
            if args == ("cat-file", "blob", root_blob_oid):
                payload_reads.append(root_blob_oid)
            return original(
                *args, timeout=timeout, max_stdout_bytes=max_stdout_bytes,
            )

        monkeypatch.setattr(pinned, "git", instrumented)
        first = module.select_historical_blobs_absent_from_current_head(
            pinned, edge, inventory,
        )
        second = module.select_historical_blobs_absent_from_current_head(
            pinned, edge, inventory,
        )

        assert first == second and len(first) == 1
        assert payload_reads == [root_blob_oid]


def test_metadata_inventory_rejects_corrupt_tree_identity_and_path(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo, _root, _child, _head = make_history(tmp_path)
    with pytest.raises(module.Stage12693Error, match="noncanonical_tree_name"):
        module.parse_raw_tree(
            _raw_tree_entry(b"100644", b"bad/name.py", 1), 40,
        )
    with module.pin_repository(repo.resolve()) as pinned:
        tree_oid = module.read_commit(pinned, pinned.head_oid).tree_oid
        pinned.cache.raw_objects.pop((tree_oid, "tree"), None)
        pinned.cache.parsed_trees.pop(tree_oid, None)
        original = pinned.git

        def corrupt(
            *args: str, timeout: int = 60, max_stdout_bytes: int = 256,
        ) -> bytes:
            data = original(
                *args, timeout=timeout, max_stdout_bytes=max_stdout_bytes,
            )
            if args == ("cat-file", "tree", tree_oid):
                return data + b"corrupt"
            return data

        monkeypatch.setattr(pinned, "git", corrupt)
        with pytest.raises(module.Stage12693Error, match="tree_identity_mismatch"):
            module.list_tree_metadata_recursive(pinned, tree_oid)


def test_oid_aware_diff_skips_identical_subtree_parsing(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo = tmp_path / "subtree-skip"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "stable").mkdir()
    (repo / "stable" / "kept.py").write_text("kept = 1\n" * 4)
    (repo / "changed.py").write_text("value = 1\n" * 4)
    parent = commit(repo, "parent", "2018-08-03T00:00:00Z")
    (repo / "changed.py").write_text("value = 2\n" * 4)
    child = commit(repo, "child", "2020-08-03T00:00:00Z")
    stable_oid = git(repo, "rev-parse", f"{parent}:stable")
    assert stable_oid == git(repo, "rev-parse", f"{child}:stable")

    with module.pin_repository(repo.resolve()) as pinned:
        parsed: list[str] = []
        original = module._parsed_tree_entries

        def instrumented(pinned_repo, tree_oid):
            parsed.append(tree_oid)
            return original(pinned_repo, tree_oid)

        monkeypatch.setattr(module, "_parsed_tree_entries", instrumented)
        changed = module.changed_supported_parent_tree_entries(
            pinned,
            module.read_commit(pinned, child).tree_oid,
            module.read_commit(pinned, parent).tree_oid,
        )
        assert [entry.path for entry in changed] == ["changed.py"]
        assert stable_oid not in parsed


def test_metadata_tree_visits_charge_again_on_cache_hits(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, _child, head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        tree_oid = module.read_commit(pinned, head).tree_oid
        limits = module.RepositoryWorkLimits(tree_visits=100)
        with module.repository_work_scope(limits) as budget:
            module.list_tree_metadata_recursive(pinned, tree_oid)
            first = budget.tree_visits
            module.list_tree_metadata_recursive(pinned, tree_oid)
            second = budget.tree_visits
        assert first > 0
        assert second == first * 2


def test_wrong_blob_type_rejects_without_payload_read(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo, _root, _child, head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        tree_oid = module.read_commit(pinned, head).tree_oid
        payload_reads: list[str] = []
        original_git = pinned.git

        def instrumented_git(
            *args: str, timeout: int = 60, max_stdout_bytes: int = 256,
        ) -> bytes:
            if args == ("cat-file", "blob", tree_oid):
                payload_reads.append(tree_oid)
            return original_git(
                *args, timeout=timeout, max_stdout_bytes=max_stdout_bytes,
            )

        monkeypatch.setattr(pinned, "git", instrumented_git)
        monkeypatch.setattr(
            module,
            "_parsed_tree_entries",
            lambda _repo, _oid: (
                module.GitTreeEntry("100644", "blob", tree_oid, "wrong.py"),
            ),
        )
        with pytest.raises(module.Stage12693Error, match="metadata_mismatch"):
            module._typed_metadata_tree_entries(pinned, tree_oid)
        assert payload_reads == []


def _planning_pair(module, index: int, component: str):
    input_text = f"repository_relative_path: file_{index}.py\n<MASKED_EXACT_SPAN>"
    target = f"value_{index}"
    base_objective = "multilingual_exact_source_span_infilling"
    target_sha = module._sha256(target.encode())
    row = {
        "row_id": f"stage12693_manual_{index}",
        "split": "",
        "language_family": "python",
        "objective_family": module.HISTORICAL_OBJECTIVES[base_objective],
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": {
            "content_component_sha256": component,
            "target_sha256": target_sha,
        },
        "authority": dict(module.AUTHORITY),
    }
    proof = {
        "selection_key_sha256": module.S88.stable(["evidence", index]),
        "encoder_input_sha256": module._sha256(input_text.encode()),
        "model_example_sha256": module.S88.stable([input_text, target]),
        "semantic_example_sha256": module.S88.stable([
            base_objective,
            module.S88.normalized_without_whitespace(input_text),
            module.S88.normalized_without_whitespace(target),
        ]),
        "target_sha256": target_sha,
        "base_comparison_objective_family": base_objective,
        "content_component_sha256": component,
        "historical_age_bucket": "historical_10_plus_years",
        "repository_key_sha256": f"repo-{component}",
        "source_window_sha256": module.S88.stable(["window", index]),
        "source_file_sha256": module.S88.stable(["file", index]),
        "git_blob_oid": f"{index + 1:040x}",
    }
    return row, proof


def _trusted_planning_fixture(module, tmp_path: Path):
    pinned_repositories = []
    materials = []
    exclusions = []
    try:
        for repo_index in range(3):
            repo = tmp_path / f"planner-repo-{repo_index}"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "fixture@example.invalid")
            git(repo, "config", "user.name", "Fixture")
            for file_index in range(10):
                (repo / f"legacy_{repo_index}_{file_index}.py").write_text(
                    "".join(
                        f"value_{repo_index}_{file_index}_{line} = {1000 + line}\n"
                        for line in range(5)
                    ),
                    encoding="utf-8",
                )
            commit(repo, "historical root", "2014-08-03T00:00:00Z")
            for file_index in range(10):
                path = repo / f"legacy_{repo_index}_{file_index}.py"
                path.write_text(
                    path.read_text(encoding="utf-8")
                    + f"revision_{repo_index}_{file_index} = 2000\n",
                    encoding="utf-8",
                )
            child = commit(repo, "historical child", "2018-08-03T00:00:00Z")
            for path in tuple(repo.glob("legacy_*.py")):
                path.unlink()
            (repo / f"current_{repo_index}.py").write_text(
                f"current_{repo_index} = 3000\n", encoding="utf-8",
            )
            commit(repo, "current head", "2025-08-03T00:00:00Z")

            pinned = module.pin_repository(repo.resolve())
            pinned_repositories.append(pinned)
            edge = next(
                edge for edge in module.enumerate_single_parent_edges(pinned)
                if edge.child_oid == child
            )
            materials.append(module.construct_revision_material(
                pinned, f"planner_repository_{repo_index}", edge,
            ))
            exclusions.append(module.build_current_head_example_exclusion(
                pinned, f"planner_repository_{repo_index}",
            ))

        module.assign_historical_components(materials)
        revisions = [
            module.construct_historical_revision_rows(
                pinned, material, exclusion,
            )
            for pinned, material, exclusion in zip(
                pinned_repositories, materials, exclusions, strict=True,
            )
        ]
        counts = (8, 1, 1)
        selected = []
        seen = {
            name: set()
            for name in ("row", "encoder", "model", "semantic", "window")
        }
        for revision, count in zip(revisions, counts, strict=True):
            retained = 0
            for row, proof in zip(
                revision.rows, revision.proofs, strict=True,
            ):
                identities = {
                    "row": row["row_id"],
                    "encoder": proof["encoder_input_sha256"],
                    "model": proof["model_example_sha256"],
                    "semantic": proof["semantic_example_sha256"],
                    "window": proof["source_window_sha256"],
                }
                if any(
                    value in seen[name] for name, value in identities.items()
                ):
                    continue
                for name, value in identities.items():
                    seen[name].add(value)
                selected.append((row, proof, revision.material))
                retained += 1
                if retained == count:
                    break
            assert retained == count
        rows = tuple(row for row, _proof, _material in selected)
        proofs = tuple(proof for _row, proof, _material in selected)
        trusted = tuple(
            (module.historical_planning_identity(row, proof), material)
            for row, proof, material in selected
        )
        return rows, proofs, trusted
    finally:
        for pinned in pinned_repositories:
            pinned.close()


def test_global_dedup_repository_cap_component_grouping_and_split_plan(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, child, head = make_retention_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        edges = module.enumerate_single_parent_edges(pinned)
        first = module.construct_revision_material(
            pinned, "same-repository", next(edge for edge in edges if edge.child_oid == child),
        )
        second = module.construct_revision_material(
            pinned, "same-repository", next(edge for edge in edges if edge.child_oid == head),
        )
        groups = module.assign_historical_components([first, second])
        assert len(groups) == 1
        assert first.component_key == second.component_key
        exclusion = module.build_current_head_example_exclusion(
            pinned, "same-repository",
        )
        revision = module.construct_historical_revision_rows(
            pinned, first, exclusion,
        )
        assert len(revision.rows) >= 2

    dedup_rows, dedup_proofs = module.globally_deduplicate_historical_rows(
        [revision, revision], repository_cap=2,
    )
    assert len(dedup_rows) == len(dedup_proofs) == 2
    assert len({proof["encoder_input_sha256"] for proof in dedup_proofs}) == 2

    untrusted_rows, untrusted_proofs = _synthetic_planning_rows(
        module, revision.rows[0], revision.proofs[0],
    )
    with pytest.raises(
        module.Stage12693Error, match="missing_trusted_historical_material"
    ):
        module.plan_historical_component_splits(
            untrusted_rows, untrusted_proofs, 10,
        )

    rows, proofs, trusted_materials = _trusted_planning_fixture(
        module, tmp_path,
    )
    bucket = proofs[0]["historical_age_bucket"]
    gates = module.RetentionPlanningGates(
        required_languages=("python",),
        required_age_buckets=(bucket,),
        min_rows_per_language_per_split=1,
        min_rows_per_age_bucket_per_split=1,
    )
    plan = module.plan_historical_component_splits(
        rows, proofs, 10, gates, trusted_materials=trusted_materials,
    )
    assert len(plan.train_rows) == 8
    assert len(plan.eval_rows) == 1
    assert plan.strict_planned_count == 1
    assert len(plan.strict_commitment_sha256) == 64
    assert not hasattr(plan, "strict_rows")
    assert not any(plan.authority.values())
    assert len({split for _component, split in plan.component_splits}) == 2
    assert all(split != "strict_eval" for _component, split in plan.component_splits)
    assert sorted(
        capacity for _component, capacity
        in module.historical_component_capacities(proofs)
    ) == [1, 1, 8]
    with pytest.raises(module.Stage12693Error, match="language_gate"):
        module.plan_historical_component_splits(
            rows, proofs, 10,
            module.RetentionPlanningGates(
                required_languages=("rust",),
                min_rows_per_language_per_split=1,
            ),
            trusted_materials=trusted_materials,
        )

    mutated_rows = copy.deepcopy(rows)
    mutated_proofs = copy.deepcopy(proofs)
    mutated_rows[0]["target"]["decoder_text"] = "replacement_value"
    replacement = mutated_rows[0]["target"]["decoder_text"]
    mutated_proofs[0]["target_sha256"] = module._sha256(replacement.encode())
    mutated_rows[0]["source_provenance"]["target_sha256"] = mutated_proofs[0]["target_sha256"]
    mutated_proofs[0]["model_example_sha256"] = module.S88.stable([
        mutated_rows[0]["input_text"], replacement,
    ])
    mutated_proofs[0]["semantic_example_sha256"] = module.S88.stable([
        mutated_proofs[0]["base_comparison_objective_family"],
        module.S88.normalized_without_whitespace(mutated_rows[0]["input_text"]),
        module.S88.normalized_without_whitespace(replacement),
    ])
    replacement_row_id = "stage12693_" + module.S88.stable([
        mutated_proofs[0]["selection_key_sha256"],
        mutated_proofs[0]["target_sha256"],
    ])[:24]
    mutated_rows[0]["row_id"] = replacement_row_id
    mutated_proofs[0]["row_id"] = replacement_row_id
    mutated_proofs[0]["row_sha256"] = module.S88.stable(mutated_rows[0])
    mutated_proofs[0]["immutable_evidence_binding_sha256"] = (
        module.immutable_row_evidence_binding(mutated_rows[0], mutated_proofs[0])
    )
    mutated_identity = module.historical_planning_identity(
        mutated_rows[0], mutated_proofs[0],
    )
    mutated_trusted_materials = (
        (mutated_identity, trusted_materials[0][1]),
        *trusted_materials[1:],
    )
    with pytest.raises(
        module.Stage12693Error, match="material_binding_mismatch"
    ):
        module.plan_historical_component_splits(
            mutated_rows,
            mutated_proofs,
            10,
            gates,
            trusted_materials=mutated_trusted_materials,
        )


def test_bounded_scope_and_authority() -> None:
    module = load_module()
    assert module.REQUIRED_LANGUAGES == tuple(module.S88.REQUIRED_RETENTION_LANGUAGES)
    assert module.AUTHORITY and not any(module.AUTHORITY.values())
    module.assert_bounded_core_only()
    source = SCRIPT.read_text(encoding="utf-8")
    assert "def publish" not in source
    assert "def build_row" not in source
    assert "assign_split" not in source
    assert '"rev-list"' not in source
    assert "dict(os.environ)" not in source
    assert "--no-replace-objects" in source


def _materialized_fixture_rows(module, repo: Path, child: str):
    pinned = module.pin_repository(repo.resolve())
    inventory = module.build_current_head_example_exclusion(
        pinned, "fixture_repository_key",
    )
    edge = next(
        edge for edge in module.enumerate_single_parent_edges(pinned)
        if edge.child_oid == child
    )
    material = module.construct_revision_material(
        pinned, "fixture_repository_key", edge,
    )
    module.assign_historical_components([material])
    revision = module.construct_historical_revision_rows(
        pinned, material, inventory,
    )
    return pinned, inventory, revision


def test_constructs_exact_stage12688_compatible_historical_rows(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    pinned, exclusion, revision = _materialized_fixture_rows(module, repo, child)
    try:
        assert revision.rows
        assert len(revision.rows) == len(revision.proofs)
        for row, proof in zip(revision.rows, revision.proofs):
            assert row["objective_family"] in module.HISTORICAL_OBJECTIVES.values()
            assert proof["base_comparison_objective_family"] in module.HISTORICAL_OBJECTIVES
            assert row["source_provenance"]["source_stage"] == module.STAGE
            assert row["source_provenance"]["current_head_example_exclusion_sha256"] == (
                exclusion.commitment_sha256
            )
            assert not any(row["authority"].values())
            assert not module.S88.rejected_target_marker(
                row["target"]["decoder_text"]
            )
            assert module.S88.normalized_without_whitespace(
                row["target"]["decoder_text"]
            ) not in module.S88.normalized_without_whitespace(row["input_text"])
    finally:
        pinned.close()


def test_changed_historical_file_at_current_head_path_is_retained_when_evidence_differs(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    source = repo / "retained.py"
    source.write_text("value = 1001\nvalue = 1002\nvalue = 1003\n", encoding="utf-8")
    commit(repo, "old", "2014-08-03T00:00:00Z")
    source.write_text("value = 2001\nvalue = 2002\nvalue = 2003\n", encoding="utf-8")
    child = commit(repo, "middle", "2018-08-03T00:00:00Z")
    source.write_text("value = 3001\nvalue = 3002\nvalue = 3003\n", encoding="utf-8")
    commit(repo, "head", "2025-08-03T00:00:00Z")
    pinned, exclusion, revision = _materialized_fixture_rows(module, repo, child)
    try:
        assert not hasattr(exclusion, "repository_relative_path_sha256s")
        assert revision.rows
        assert revision.proofs
        assert all(
            proof["encoder_input_sha256"] not in exclusion.encoder_input_sha256s
            and proof["model_example_sha256"] not in exclusion.model_example_sha256s
            and proof["semantic_example_sha256"] not in exclusion.semantic_example_sha256s
            and proof["source_window_sha256"] not in exclusion.source_window_sha256s
            for proof in revision.proofs
        )
    finally:
        pinned.close()


def test_current_head_exclusion_enumerates_all_eligible_spans(tmp_path: Path) -> None:
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    lines = [f"value_{index} = {1000 + index}\n" for index in range(9)]
    (repo / "current.py").write_text("".join(lines), encoding="utf-8")
    commit(repo, "head", "2025-08-03T00:00:00Z")
    with module.pin_repository(repo.resolve()) as pinned:
        exclusion = module.build_current_head_example_exclusion(
            pinned, "fixture_repository_key",
        )
        assert len(exclusion.encoder_input_sha256s) >= len(lines)
        # All masks reconstruct the same short verified source window.
        assert len(exclusion.source_window_sha256s) == 1
        assert len(exclusion.semantic_example_sha256s) >= len(lines)


def test_global_input_and_evidence_dedup_is_position_independent(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    pinned, _exclusion, revision = _materialized_fixture_rows(module, repo, child)
    try:
        rows, proofs = module.globally_deduplicate_historical_rows(
            [revision, revision],
        )
        unique_windows = {
            proof["source_window_sha256"] for proof in revision.proofs
        }
        assert len(rows) == len(unique_windows)
        assert len(proofs) == len(unique_windows)

        reversed_rows, reversed_proofs = module.globally_deduplicate_historical_rows(
            [
                module.HistoricalRevisionRows(
                    revision.material,
                    tuple(reversed(revision.rows)),
                    tuple(reversed(revision.proofs)),
                ),
                revision,
            ],
        )
        assert tuple(row["row_id"] for row in reversed_rows) == tuple(
            row["row_id"] for row in rows
        )
        assert reversed_proofs == proofs
    finally:
        pinned.close()


def _synthetic_planning_rows(module, row, proof):
    rows = []
    proofs = []
    for component, count in (("component_a", 8), ("component_b", 1), ("component_c", 1)):
        for index in range(count):
            candidate_row = copy.deepcopy(row)
            candidate_proof = copy.deepcopy(proof)
            input_text = row["input_text"] + f"\nplanning_nonce: {component}:{index}"
            provenance = candidate_row["source_provenance"]
            provenance["content_component_sha256"] = component
            synthetic_position = (
                {"component_a": 1000, "component_b": 2000, "component_c": 3000}[component]
                + index
            )
            provenance["span_start_byte"] = synthetic_position
            provenance["span_end_byte"] = synthetic_position + 1
            selection_key = module.S88.stable([
                "stage12693_target_independent_row_selection_v1",
                provenance["repository_key_sha256"],
                provenance["sampling_child_commit_git_oid"],
                provenance["historical_parent_commit_git_oid"],
                provenance["repository_relative_path"],
                candidate_proof["base_comparison_objective_family"],
                provenance["span_start_byte"],
                provenance["span_end_byte"],
                provenance["git_blob_oid"],
                provenance["parent_tree_oid"],
            ])
            target = candidate_row["target"]["decoder_text"]
            row_id = "stage12693_" + module.S88.stable([
                selection_key,
                module._sha256(target.encode("utf-8")),
            ])[:24]
            candidate_row["row_id"] = row_id
            candidate_row["input_text"] = input_text
            candidate_proof["row_id"] = row_id
            candidate_proof["selection_key_sha256"] = selection_key
            candidate_proof["encoder_input_sha256"] = hashlib.sha256(
                input_text.encode("utf-8")
            ).hexdigest()
            target = candidate_row["target"]["decoder_text"]
            candidate_proof["model_example_sha256"] = module.S88.stable(
                [input_text, target]
            )
            candidate_proof["semantic_example_sha256"] = module.S88.stable([
                candidate_proof["base_comparison_objective_family"],
                module.S88.normalized_without_whitespace(input_text),
                module.S88.normalized_without_whitespace(target),
            ])
            candidate_proof["content_component_sha256"] = component
            source_window_sha256 = module.S88.stable(
                ["verified_window", component, index]
            )
            candidate_proof["source_window_sha256"] = source_window_sha256
            candidate_row["source_provenance"]["source_window_sha256"] = (
                source_window_sha256
            )
            candidate_proof["row_sha256"] = module.S88.stable(candidate_row)
            candidate_proof["immutable_evidence_binding_sha256"] = (
                module.immutable_row_evidence_binding(
                    candidate_row, candidate_proof,
                )
            )
            rows.append(candidate_row)
            proofs.append(candidate_proof)
    return tuple(rows), tuple(proofs)


def test_exact_whole_component_plan_and_age_language_accounting(
    tmp_path: Path,
) -> None:
    module = load_module()
    rows, proofs, trusted_materials = _trusted_planning_fixture(
        module, tmp_path,
    )
    bucket = proofs[0]["historical_age_bucket"]
    language = rows[0]["language_family"]
    plan = module.plan_historical_component_splits(
        rows,
        proofs,
        10,
        module.RetentionPlanningGates(
            required_languages=(language,),
            required_age_buckets=(bucket,),
            min_rows_per_language_per_split=1,
            min_rows_per_age_bucket_per_split=1,
        ),
        trusted_materials=trusted_materials,
    )
    assert len(plan.train_rows) == 8
    assert len(plan.eval_rows) == 1
    assert plan.strict_planned_count == 1
    assert sorted(split for _component, split in plan.component_splits) == [
        "eval", "train",
    ]
    assert all(split != "strict_eval" for _component, split in plan.component_splits)
    assert plan.language_counts_by_split == {
        "train": {language: 8},
        "eval": {language: 1},
    }
    assert plan.age_bucket_counts_by_split == {
        "train": {bucket: 8},
        "eval": {bucket: 1},
    }
    assert not any(plan.authority.values())
    assert all(not any(row["authority"].values()) for row in plan.train_rows)
    assert all(not any(row["authority"].values()) for row in plan.eval_rows)


def test_planner_requires_exact_authenticated_material_map_and_rejects_full_reseal(
    tmp_path: Path,
) -> None:
    module = load_module()
    rows, proofs, trusted = _trusted_planning_fixture(module, tmp_path)
    gates = module.RetentionPlanningGates(
        required_languages=("python",),
        required_age_buckets=(proofs[0]["historical_age_bucket"],),
        min_rows_per_language_per_split=1,
        min_rows_per_age_bucket_per_split=1,
    )

    with pytest.raises(module.Stage12693Error, match="missing_trusted"):
        module.plan_historical_component_splits(rows, proofs, 10, gates)
    with pytest.raises(module.Stage12693Error, match="duplicate_trusted"):
        module.plan_historical_component_splits(
            rows, proofs, 10, gates,
            trusted_materials=(*trusted, trusted[0]),
        )
    with pytest.raises(module.Stage12693Error, match="missing_trusted"):
        module.plan_historical_component_splits(
            rows, proofs, 10, gates,
            trusted_materials=trusted[:-1],
        )
    with pytest.raises(module.Stage12693Error, match="unused_trusted"):
        module.plan_historical_component_splits(
            rows, proofs, 10, gates,
            trusted_materials=(*trusted, ("f" * 64, trusted[0][1])),
        )

    mismatched = list(trusted)
    mismatched[0] = (mismatched[0][0], trusted[8][1])
    with pytest.raises(module.Stage12693Error, match="material_binding_mismatch"):
        module.plan_historical_component_splits(
            rows, proofs, 10, gates,
            trusted_materials=tuple(mismatched),
        )

    forged_material = copy.deepcopy(trusted[0][1])
    forged = ((trusted[0][0], forged_material), *trusted[1:])
    with pytest.raises(module.Stage12693Error, match="untrusted_or_forged"):
        module.plan_historical_component_splits(
            rows, proofs, 10, gates, trusted_materials=forged,
        )

    forged_rows = copy.deepcopy(rows)
    forged_proofs = copy.deepcopy(proofs)
    row = forged_rows[0]
    proof = forged_proofs[0]
    provenance = row["source_provenance"]
    provenance["repository_relative_path"] = "fully_resealed.rs"
    row["language_family"] = proof["language_family"] = "rust"
    proof["repository_relative_path_sha256"] = module._sha256(
        provenance["repository_relative_path"].encode("utf-8")
    )
    proof["selection_key_sha256"] = module.S88.stable([
        "stage12693_target_independent_row_selection_v1",
        provenance["repository_key_sha256"],
        provenance["sampling_child_commit_git_oid"],
        provenance["historical_parent_commit_git_oid"],
        provenance["repository_relative_path"],
        proof["base_comparison_objective_family"],
        provenance["span_start_byte"],
        provenance["span_end_byte"],
        provenance["git_blob_oid"],
        provenance["parent_tree_oid"],
    ])
    row_id = "stage12693_" + module.S88.stable([
        proof["selection_key_sha256"], proof["target_sha256"],
    ])[:24]
    row["row_id"] = proof["row_id"] = row_id
    proof["row_sha256"] = module.S88.stable(row)
    proof["immutable_evidence_binding_sha256"] = (
        module.immutable_row_evidence_binding(row, proof)
    )
    resealed_identity = module.historical_planning_identity(row, proof)
    resealed_trusted = ((resealed_identity, trusted[0][1]), *trusted[1:])
    with pytest.raises(module.Stage12693Error, match="material_binding_mismatch"):
        module.plan_historical_component_splits(
            forged_rows,
            forged_proofs,
            10,
            module.RetentionPlanningGates(),
            trusted_materials=resealed_trusted,
        )


def test_direct_traversal_and_material_entries_enforce_low_budgets(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        edges = module.enumerate_single_parent_edges(pinned)
        edge = next(edge for edge in edges if edge.child_oid == child)
        head = module.read_commit(pinned, pinned.head_oid)
        entries = module.list_tree_recursive(pinned, head.tree_oid)
        blob_oid = next(entry.oid for entry in entries if entry.object_type == "blob")
        inventory = module.build_current_head_exclusion_inventory(pinned)

        def reset_cache() -> None:
            pinned.cache = module.RepositoryEvidenceCache(
                pinned.cache.identity
            )
            pinned.cache.bind_head(pinned.head_oid)

        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_object_reads_limit"
        ):
            module.enumerate_single_parent_edges(
                pinned,
                work_limits=module.Stage12693WorkLimits(object_reads=1),
            )
        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_tree_work_limit"
        ):
            module.list_tree_recursive(
                pinned,
                head.tree_oid,
                work_limits=module.Stage12693WorkLimits(tree_work=1),
            )
        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_object_reads_limit"
        ):
            module.construct_revision_material(
                pinned,
                "fixture_repository_key",
                edge,
                work_limits=module.Stage12693WorkLimits(object_reads=1),
            )
        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_total_blob_bytes_read_limit"
        ):
            module.read_verified_object(
                pinned,
                blob_oid,
                "blob",
                work_limits=module.Stage12693WorkLimits(
                    total_blob_bytes_read=1,
                ),
            )
        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_retained_head_evidence_limit"
        ):
            module.build_current_head_exclusion_inventory(
                pinned,
                work_limits=module.Stage12693WorkLimits(
                    retained_head_evidence=1,
                ),
            )
        reset_cache()
        with pytest.raises(
            module.Stage12693Error, match="cumulative_object_reads_limit"
        ):
            module.select_historical_blobs_absent_from_current_head(
                pinned,
                edge,
                inventory,
                work_limits=module.Stage12693WorkLimits(object_reads=1),
            )


def _reseal_refreshed_hashes(module, row, proof) -> None:
    proof["row_sha256"] = module.S88.stable(row)
    proof["immutable_evidence_binding_sha256"] = (
        module.immutable_row_evidence_binding(row, proof)
    )


def test_row_gate_and_historical_provenance_forgery_rejects_after_rehash(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, child, _head = make_history(tmp_path)
    pinned, _exclusion, revision = _materialized_fixture_rows(module, repo, child)
    try:
        source_row = revision.rows[0]
        source_proof = revision.proofs[0]

        row, proof = copy.deepcopy(source_row), copy.deepcopy(source_proof)
        row["row_id"] = proof["row_id"] = "stage12693_" + "f" * 24
        _reseal_refreshed_hashes(module, row, proof)
        with pytest.raises(module.Stage12693Error, match="field_mismatch"):
            module.validate_historical_row_proof(row, proof, revision.material)

        row, proof = copy.deepcopy(source_row), copy.deepcopy(source_proof)
        row["language_family"] = proof["language_family"] = "rust"
        _reseal_refreshed_hashes(module, row, proof)
        with pytest.raises(module.Stage12693Error, match="field_mismatch"):
            module.validate_historical_row_proof(row, proof, revision.material)

        row, proof = copy.deepcopy(source_row), copy.deepcopy(source_proof)
        wrong_objective = next(
            objective for objective in module.HISTORICAL_OBJECTIVES.values()
            if objective != row["objective_family"]
        )
        row["objective_family"] = proof["objective_family"] = wrong_objective
        _reseal_refreshed_hashes(module, row, proof)
        with pytest.raises(module.Stage12693Error, match="field_mismatch"):
            module.validate_historical_row_proof(row, proof, revision.material)

        row, proof = copy.deepcopy(source_row), copy.deepcopy(source_proof)
        forged_bucket = (
            "historical_5_to_10_years"
            if proof["historical_age_bucket"] != "historical_5_to_10_years"
            else "historical_10_plus_years"
        )
        row["source_provenance"]["historical_age_bucket"] = forged_bucket
        proof["historical_age_bucket"] = forged_bucket
        _reseal_refreshed_hashes(module, row, proof)
        with pytest.raises(module.Stage12693Error, match="field_mismatch"):
            module.validate_historical_row_proof(row, proof, revision.material)

        for provenance_field, proof_field, forged_value in (
            ("repository_key_sha256", "repository_key_sha256", "forged_repository"),
            ("content_component_sha256", "content_component_sha256", "f" * 64),
            (
                "historical_parent_commit_git_oid",
                "historical_parent_commit_git_oid",
                "f" * len(revision.material.edge.parent_oid),
            ),
        ):
            row, proof = copy.deepcopy(source_row), copy.deepcopy(source_proof)
            row["source_provenance"][provenance_field] = forged_value
            proof[proof_field] = forged_value
            selection_provenance = row["source_provenance"]
            proof["selection_key_sha256"] = module.S88.stable([
                "stage12693_target_independent_row_selection_v1",
                selection_provenance["repository_key_sha256"],
                selection_provenance["sampling_child_commit_git_oid"],
                selection_provenance["historical_parent_commit_git_oid"],
                selection_provenance["repository_relative_path"],
                proof["base_comparison_objective_family"],
                selection_provenance["span_start_byte"],
                selection_provenance["span_end_byte"],
                selection_provenance["git_blob_oid"],
                selection_provenance["parent_tree_oid"],
            ])
            row_id = "stage12693_" + module.S88.stable([
                proof["selection_key_sha256"], proof["target_sha256"],
            ])[:24]
            row["row_id"] = proof["row_id"] = row_id
            _reseal_refreshed_hashes(module, row, proof)
            with pytest.raises(
                module.Stage12693Error, match="material_binding_mismatch"
            ):
                module.validate_historical_row_proof(
                    row, proof, revision.material,
                )
    finally:
        pinned.close()


def test_cumulative_work_limits_fail_closed_before_unbounded_growth(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo, _root, _child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        for field in (
            "total_blob_bytes_read",
            "object_reads",
            "tree_work",
            "eligible_spans_considered",
            "comparable_examples",
            "retained_head_evidence",
        ):
            pinned.cache = module.RepositoryEvidenceCache(
                pinned.cache.identity
            )
            pinned.cache.bind_head(pinned.head_oid)
            limits = module.Stage12693WorkLimits(**{field: 1})
            with pytest.raises(
                module.Stage12693Error,
                match=f"cumulative_{field}_limit_exceeded",
            ):
                module.build_current_head_example_exclusion(
                    pinned,
                    "fixture_repository_key",
                    work_limits=limits,
                )


def test_comparable_example_budget_rejects_before_next_row_constructor(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    repo, _root, child, _head = make_retention_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        edge = next(
            edge for edge in module.enumerate_single_parent_edges(pinned)
            if edge.child_oid == child
        )
        inventory = module.build_current_head_exclusion_inventory(pinned)
        candidates = module.select_historical_blobs_absent_from_current_head(
            pinned, edge, inventory,
        )
        assert candidates

        constructor_calls: list[str] = []
        original_directory = module.S88.build_directory_entry_row
        original_span = module.S88.build_span_row

        def instrumented_directory(*args, **kwargs):
            constructor_calls.append("directory")
            return original_directory(*args, **kwargs)

        def instrumented_span(*args, **kwargs):
            constructor_calls.append("span")
            return original_span(*args, **kwargs)

        monkeypatch.setattr(
            module.S88, "build_directory_entry_row", instrumented_directory,
        )
        monkeypatch.setattr(module.S88, "build_span_row", instrumented_span)

        with module.cumulative_work_scope(
            module.Stage12693WorkLimits(comparable_examples=1)
        ):
            with pytest.raises(
                module.Stage12693Error,
                match="cumulative_comparable_examples_limit_exceeded",
            ):
                module._construct_comparable_pairs(
                    pinned,
                    "fixture_repository_key",
                    edge.parent_oid,
                    edge.parent_tree_oid,
                    candidates,
                    "fixture_component",
                )

        assert constructor_calls == ["directory"]


def test_forged_current_head_example_exclusion_fails_closed(tmp_path: Path) -> None:
    module = load_module()
    repo, _root, _child, _head = make_history(tmp_path)
    with module.pin_repository(repo.resolve()) as pinned:
        exclusion = module.build_current_head_example_exclusion(
            pinned, "fixture_repository_key",
        )
        forged = module.CurrentHeadExampleExclusion(
            exclusion.base_inventory,
            frozenset(),
            exclusion.model_example_sha256s,
            exclusion.semantic_example_sha256s,
            exclusion.source_window_sha256s,
            exclusion.commitment_sha256,
        )
        with pytest.raises(module.Stage12693Error, match="forged_or_stale"):
            module.validate_current_head_example_exclusion(
                pinned, "fixture_repository_key", forged,
            )


def _synthetic_material(module, seed: int, shared_blobs: frozenset[str]):
    oid = f"{seed:040x}"
    edge = module.HistoryEdge(
        f"{seed + 1:040x}",
        f"{seed + 2:040x}",
        f"{seed + 3:040x}",
        f"{seed + 4:040x}",
        1,
        "+0000",
        "historical_10_plus_years",
    )
    return module.HistoricalRevisionMaterial(
        repository_key_sha256=f"repository_{seed}",
        pinned_head_oid=oid,
        edge=edge,
        lineage_commit_oids=frozenset({f"{seed + 5:040x}"}),
        tree_oids=frozenset({f"{seed + 6:040x}"}),
        blob_oids=shared_blobs,
    )


def test_component_grouping_uses_exact_lineage_not_shared_blob_heuristic() -> None:
    module = load_module()
    shared = frozenset({"a" * 40, "b" * 40})
    left = _synthetic_material(module, 100, shared)
    right = _synthetic_material(module, 200, shared)
    components = module.assign_historical_components([left, right])
    assert len(components) == 2

    right.lineage_commit_oids = left.lineage_commit_oids
    components = module.assign_historical_components([left, right])
    assert len(components) == 1


def test_copied_tree_alone_does_not_union_unrelated_repositories() -> None:
    module = load_module()
    left = _synthetic_material(module, 300, frozenset())
    right = _synthetic_material(module, 400, frozenset())
    right.tree_oids = left.tree_oids

    components = module.assign_historical_components([left, right])

    assert len(components) == 2
    assert left.component_key != right.component_key


def _make_capacity_scan_repository(
    source_root: Path, name: str, seed: int,
) -> Path:
    repo = source_root / name
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    for index in range(3):
        (repo / f"legacy_{seed}_{index}.py").write_text(
            "".join(
                f"value_{seed}_{index}_{line} = {seed * 1000 + line}\n"
                for line in range(5)
            ),
            encoding="utf-8",
        )
    commit(repo, "historical root", "2014-08-03T00:00:00Z")
    for index in range(3):
        path = repo / f"legacy_{seed}_{index}.py"
        path.write_text(
            path.read_text(encoding="utf-8")
            + f"revision_{seed}_{index} = {seed * 2000}\n",
            encoding="utf-8",
        )
    commit(repo, "historical child", "2018-08-03T00:00:00Z")
    for path in tuple(repo.glob("legacy_*.py")):
        path.unlink()
    (repo / f"current_{seed}.py").write_text(
        f"current_{seed} = {seed * 3000}\n", encoding="utf-8",
    )
    commit(repo, "current head", "2025-08-03T00:00:00Z")
    return repo


def _capacity_scan_fixture(tmp_path: Path):
    module = load_module()
    source_root = tmp_path / "repositories"
    source_root.mkdir()
    repositories = (
        _make_capacity_scan_repository(source_root, "alpha", 11),
        _make_capacity_scan_repository(source_root, "beta", 22),
    )
    records = []
    private_identities = []
    for index, repo in enumerate(repositories):
        with module.pin_repository(repo.resolve()) as pinned:
            head = module.read_commit(pinned, pinned.head_oid)
            repository_key = hashlib.sha256(
                f"fixture-repository-{index}".encode("ascii")
            ).hexdigest()
            records.append({
                "head_commit_git_oid": pinned.head_oid,
                "git_tree_oid": head.tree_oid,
                "repository_key_sha256": repository_key,
                "split": "train" if index == 0 else "eval",
            })
            private_identities.extend(
                (pinned.head_oid, head.tree_oid, repository_key)
            )
    catalog_path = tmp_path / "accepted_catalog.jsonl"
    catalog_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    return module, source_root, catalog_path, tuple(private_identities)


def _fixture_scan_summary(module, source_root: Path, catalog_path: Path):
    catalog_path = catalog_path.resolve()
    return module.run_capacity_scan(
        source_root.resolve(),
        catalog_path,
        max_local_directories=10,
        max_repositories=2,
        max_materials=4,
        max_materials_per_repository=2,
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(),
        expected_catalog_path=catalog_path,
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )


def test_source_catalog_requires_exact_authoritative_path_and_sha(
    tmp_path: Path,
) -> None:
    module = load_module()
    authoritative = module.AUTHORITATIVE_STAGE12688_CATALOG
    assert hashlib.sha256(authoritative.read_bytes()).hexdigest() == (
        module.AUTHORITATIVE_STAGE12688_CATALOG_SHA256
    )
    substitute = tmp_path / "catalog.jsonl"
    substitute.write_bytes(authoritative.read_bytes())
    with pytest.raises(module.Stage12693Error, match="unauthorized"):
        module.load_accepted_source_catalog(substitute.resolve())
    with pytest.raises(module.Stage12693Error, match="sha256_mismatch"):
        module.load_accepted_source_catalog(
            substitute.resolve(),
            expected_path=substitute.resolve(),
            expected_sha256="0" * 64,
        )


def test_capacity_scan_cli_refuses_default_and_stdout_is_hash_bound(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    defaults = module.parse_capacity_scan_args(["--capacity-scan"])
    assert defaults.source_root == module.DEFAULT_SCAN_SOURCE_ROOT
    assert defaults.source_catalog is None
    assert defaults.max_commits_per_repository == 512
    assert defaults.max_secondary_parents_per_repository == 32
    assert defaults.max_rows_per_repository == module.S88.MAX_ROWS_PER_REPO
    assert module.resolve_default_source_catalog(
        module.DEFAULT_STAGE12688_SUMMARY
    ) == (
        ROOT
        / "runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus"
        / "private/23cac72b1c420605413d0f77/train_eval_source_catalog.jsonl"
    )
    refused = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert "explicit --capacity-scan is required" in refused.stderr

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--capacity-scan",
            "--source-root", str(source_root.resolve()),
            "--max-local-directories", "10",
            "--max-repositories", "2",
            "--max-materials", "4",
            "--max-materials-per-repository", "2",
            "--requested-rows", "10",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["decision"] == "READ_ONLY_CAPACITY_SCAN_NO_PUBLICATION"
    binding = summary["summary_artifact_binding"]
    assert binding["aggregate_only"] is True
    assert not any(binding["authority"].values())
    assert all(len(binding[field]) == 64 for field in (
        "builder_sha256", "catalog_sha256", "config_sha256",
        "summary_body_sha256", "binding_sha256",
    ))


def test_summary_output_path_symlink_collision_hash_and_privacy(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    output_root = (tmp_path / "capacity_summaries").resolve()
    output_root.mkdir()
    monkeypatch.setattr(module, "STAGE12693_SUMMARY_OUTPUT_ROOT", output_root)
    summary = {
        "decision": "READ_ONLY_CAPACITY_SCAN_NO_PUBLICATION",
        "privacy": {"aggregate_counts_only": True, "rows_emitted": 0},
        "authority": dict(module.AUTHORITY),
        "counts": {"deduplicated_candidates": 7},
    }
    payload, binding = module._build_bound_summary_payload(
        summary, "a" * 64, "b" * 64,
    )
    path = module._write_persisted_summary(output_root, payload, binding)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    artifact = persisted.pop("summary_artifact_binding")
    body = json.dumps(
        persisted, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    assert artifact["summary_body_sha256"] == hashlib.sha256(body).hexdigest()
    assert artifact["binding_sha256"] == binding
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "row_id" not in payload.decode("utf-8")
    assert not any(artifact["authority"].values())
    with pytest.raises(module.Stage12693Error, match="collision"):
        module._write_persisted_summary(output_root, payload, binding)

    unauthorized = (tmp_path / "unauthorized").resolve()
    unauthorized.mkdir()
    with pytest.raises(module.Stage12693Error, match="not_authorized"):
        module._write_persisted_summary(unauthorized, payload, binding)
    link = tmp_path / "summary-link"
    link.symlink_to(output_root, target_is_directory=True)
    monkeypatch.setattr(module, "STAGE12693_SUMMARY_OUTPUT_ROOT", link.absolute())
    with pytest.raises(module.Stage12693Error, match="not_authorized"):
        module._write_persisted_summary(link.absolute(), payload, binding)


def test_capacity_scan_fixture_is_deterministic_bounded_and_aggregate_only(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, private = _capacity_scan_fixture(
        tmp_path,
    )
    first = _fixture_scan_summary(module, source_root, catalog_path)
    second = _fixture_scan_summary(module, source_root, catalog_path)
    assert first == second
    assert first["completeness"]["complete"] is True
    assert (
        first["completeness"]["catalog_identity_selection_complete"]
        is True
    )
    assert first["completeness"]["catalog_identities_not_verified"] == 0
    assert (
        first["completeness"]["catalog_identity_availability_claim"]
        == "all_catalog_identities_verified"
    )
    assert first["catalog"]["unverified_repository_identities"] == 0
    assert first["counts"]["repositories_scanned"] == 2
    assert first["counts"]["snapshots_scanned"] == 2
    assert first["counts"]["repositories_attempted"] == 2
    assert first["counts"]["repositories_completed"] == 2
    assert first["counts"]["repositories_partial"] == 0
    assert first["counts"]["repositories_error"] == 0
    assert first["counts"]["commits_verified"] == (
        first["verification_counters"]["parsed_commits"]
    )
    assert first["verification_counters"]["raw_object_cache_hits"] > 0
    assert first["verification_counters"][
        "repository_cache_peak_raw_bytes"
    ] < first["verification_counters"]["repository_cached_raw_bytes"]
    assert first["counts"]["materials_constructed"] == 2
    assert first["counts"]["raw_candidates_after_head_exclusion"] >= (
        first["counts"]["deduplicated_candidates"]
    )
    assert first["counts"]["deduplicated_candidates"] > 0
    assert first["language_capacity"]["python"] > 0
    assert sum(first["age_bucket_capacity"].values()) == (
        first["counts"]["deduplicated_candidates"]
    )
    assert first["component_capacity"]["component_count"] == 2
    assert first["requested_split_feasibility"]["complete_corpus_status"] != (
        "unknown_incomplete_scan"
    )
    assert first["privacy"] == {
        "rows_emitted": 0,
        "row_or_repository_identifiers_emitted": False,
        "strict_plaintext_emitted": False,
        "strict_component_identities_emitted": False,
        "aggregate_counts_only": True,
    }
    assert first["authority"] and not any(first["authority"].values())
    encoded = json.dumps(first, sort_keys=True)
    assert all(identity not in encoded for identity in private)
    assert "alpha" not in encoded and "beta" not in encoded



def test_repository_bound_does_not_claim_unexamined_catalog_missing(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    catalog_path = catalog_path.resolve()
    summary = module.run_capacity_scan(
        source_root.resolve(),
        catalog_path,
        max_local_directories=10,
        max_repositories=1,
        max_materials=2,
        max_materials_per_repository=2,
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(),
        expected_catalog_path=catalog_path,
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )

    assert summary["completeness"]["repository_bound_reached"] is True
    assert (
        summary["completeness"]["catalog_identity_selection_complete"]
        is False
    )
    assert summary["completeness"]["catalog_identities_not_verified"] == 1
    assert (
        summary["completeness"]["catalog_identity_availability_claim"]
        == "unknown_outside_bounded_scan"
    )
    assert summary["catalog"]["unverified_repository_identities"] == 1
    assert "catalog_repositories_not_matched_locally" not in (
        summary["quarantines"]["by_reason"]
    )




def test_capacity_scan_deduplicates_local_checkout_identity(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    subprocess.run(
        [
            "git", "clone", "-q", "--no-hardlinks",
            str(source_root / "alpha"), str(source_root / "alpha-copy"),
        ],
        check=True,
    )
    summary = _fixture_scan_summary(module, source_root, catalog_path)

    assert summary["counts"]["repositories_attempted"] == 3
    assert summary["counts"]["repositories_catalog_matched"] == 2
    assert summary["counts"]["repositories_catalog_unmatched"] == 0
    assert (
        summary["counts"]["repositories_catalog_duplicate_identity"] == 1
    )
    assert summary["counts"]["repository_lifecycle_total"] == 2
    assert summary["quarantines"]["by_reason"] == {
        "duplicate_local_catalog_identity": 1,
    }


def test_capacity_scan_quarantines_controlled_stage12688_repository_error(
    tmp_path: Path, monkeypatch,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    original = module.build_current_head_example_exclusion
    calls = 0

    def fail_first_repository(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise module.S88.Stage12688Error(
                "noncanonical_immediate_directory_inventory"
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(
        module, "build_current_head_example_exclusion", fail_first_repository,
    )
    summary = _fixture_scan_summary(module, source_root, catalog_path)

    assert summary["errors"]["by_reason"] == {
        "noncanonical_immediate_directory_inventory": 1,
    }
    assert summary["counts"]["repositories_partial"] == 1
    assert summary["counts"]["repositories_completed"] == 1
    assert summary["counts"]["repository_lifecycle_total"] == 2
    assert summary["counts"]["deduplicated_candidates"] > 0


def test_streaming_scan_constructs_before_history_generator_completes(
    tmp_path: Path, monkeypatch,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    events: list[str] = []
    original_iter = module._iter_bounded_history_edges
    original_construct = module.construct_streaming_revision_material

    def instrumented_iter(*args, **kwargs):
        try:
            for edge in original_iter(*args, **kwargs):
                events.append("edge")
                yield edge
        finally:
            events.append("history_complete")

    def instrumented_construct(*args, **kwargs):
        events.append("construct")
        return original_construct(*args, **kwargs)

    monkeypatch.setattr(module, "_iter_bounded_history_edges", instrumented_iter)
    monkeypatch.setattr(
        module, "construct_streaming_revision_material",
        instrumented_construct,
    )
    summary = _fixture_scan_summary(module, source_root, catalog_path)

    assert summary["counts"]["deduplicated_candidates"] > 0
    assert events.index("construct") < events.index("history_complete")


def test_streaming_material_cap_is_a_hard_upper_bound(tmp_path: Path) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    catalog_path = catalog_path.resolve()
    summary = module.run_capacity_scan(
        source_root.resolve(),
        catalog_path,
        max_local_directories=10,
        max_repositories=2,
        max_materials=2,
        max_materials_per_repository=1,
        max_commits_per_repository=8,
        max_secondary_parents_per_repository=0,
        max_rows_per_repository=20,
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(),
        expected_catalog_path=catalog_path,
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )
    assert summary["counts"]["materials_constructed"] == 2
    assert summary["counts"]["materials_constructed"] <= (
        summary["counts"]["repositories_catalog_matched"]
        * summary["bounds"]["max_materials_per_repository"]
    )


def test_bounded_streaming_history_never_expands_huge_history(
    tmp_path: Path,
) -> None:
    module = load_module()
    repo = tmp_path / "long-history"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    path = repo / "legacy.py"
    for index in range(40):
        path.write_text(f"value = {index}\n", encoding="utf-8")
        commit(repo, f"revision {index}", "2018-08-03T00:00:00Z")

    with module.pin_repository(repo.resolve()) as pinned:
        report = module.collections.Counter()
        edges = tuple(module._iter_bounded_history_edges(
            pinned,
            max_commits=5,
            max_secondary_parents=0,
            report=report,
        ))

    assert report["bounded_commits_verified"] == 5
    assert report["commit_bound_reached"] == 1
    assert len(edges) < 40


def test_global_limit_reconciles_every_queued_repository_lifecycle(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    catalog_path = catalog_path.resolve()
    summary = module.run_capacity_scan(
        source_root.resolve(),
        catalog_path,
        max_local_directories=10,
        max_repositories=2,
        max_materials=4,
        max_materials_per_repository=2,
        max_commits_per_repository=8,
        max_secondary_parents_per_repository=0,
        max_rows_per_repository=20,
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(
            total_blob_bytes_read=1,
        ),
        expected_catalog_path=catalog_path,
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )
    counts = summary["counts"]
    lifecycle_sum = sum(counts[field] for field in (
        "repositories_completed",
        "repositories_partial",
        "repositories_error",
        "repositories_not_started_due_global_limit",
    ))
    assert counts["repositories_catalog_matched"] == 2
    assert counts["repository_lifecycle_total"] == lifecycle_sum == 2
    assert counts["repositories_partial"] == 1
    assert counts["repositories_not_started_due_global_limit"] == 1


def test_repository_quota_marks_partial_and_continues_next_repo(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    catalog_path = catalog_path.resolve()
    summary = module.run_capacity_scan(
        source_root.resolve(), catalog_path,
        max_local_directories=10,
        max_repositories=2,
        max_materials=4,
        max_materials_per_repository=2,
        max_commits_per_repository=8,
        max_secondary_parents_per_repository=0,
        max_rows_per_repository=20,
        repository_work_limits=module.RepositoryWorkLimits(
            blob_payload_bytes=1,
            raw_object_bytes=64 * 1024 * 1024,
            tree_visits=10_000,
            commits=8,
            eligible_spans_considered=10_000,
        ),
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(),
        expected_catalog_path=catalog_path,
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )
    counts = summary["counts"]
    assert counts["repository_lifecycle_total"] == 2
    assert counts["repositories_partial"] == 2
    assert counts["repositories_not_started_due_global_limit"] == 0
    assert summary["errors"]["by_reason"] == {
        "repository_blob_payload_bytes_quota_exceeded": 2,
    }


def test_capacity_scan_descriptor_symlink_and_path_replacement_protection(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    symlink_root = tmp_path / "repository-link"
    symlink_root.symlink_to(source_root, target_is_directory=True)
    with pytest.raises(module.Stage12693Error, match="not_canonical"):
        module.run_capacity_scan(
            symlink_root.absolute(),
            catalog_path.resolve(),
            max_local_directories=10,
            max_repositories=2,
            max_materials=4,
            max_materials_per_repository=2,
                requested_rows=10,
                work_limits=module.Stage12693WorkLimits(),
                expected_catalog_path=catalog_path.resolve(),
                expected_catalog_sha256=hashlib.sha256(
                    catalog_path.read_bytes()
                ).hexdigest(),
        )

    catalog_link = tmp_path / "catalog-link.jsonl"
    catalog_link.symlink_to(catalog_path)
    with pytest.raises(module.Stage12693Error, match="not_canonical"):
        module.run_capacity_scan(
            source_root.resolve(),
            catalog_link.absolute(),
            max_local_directories=10,
            max_repositories=2,
            max_materials=4,
            max_materials_per_repository=2,
            requested_rows=10,
            work_limits=module.Stage12693WorkLimits(),
            expected_catalog_path=catalog_link.absolute(),
            expected_catalog_sha256=hashlib.sha256(
                catalog_path.read_bytes()
            ).hexdigest(),
        )

    root_fd = module._open_directory(source_root.resolve())
    try:
        pinned = module.pin_repository_at(
            root_fd, "alpha", source_root.resolve(),
        )
        original_head = pinned.head_oid
        displaced = tmp_path / "displaced-alpha"
        (source_root / "alpha").rename(displaced)
        replacement = _make_capacity_scan_repository(
            source_root, "alpha", 99,
        )
        assert replacement.is_dir()
        assert pinned.head_oid == original_head
        assert module.read_commit(pinned, original_head).oid == original_head
        pinned.close()
    finally:
        os.close(root_fd)


def test_capacity_scan_reports_controlled_direct_resource_exhaustion(
    tmp_path: Path,
) -> None:
    module, source_root, catalog_path, _private = _capacity_scan_fixture(
        tmp_path,
    )
    summary = module.run_capacity_scan(
        source_root.resolve(),
        catalog_path.resolve(),
        max_local_directories=10,
        max_repositories=2,
        max_materials=4,
        max_materials_per_repository=2,
        requested_rows=10,
        work_limits=module.Stage12693WorkLimits(object_reads=1),
        expected_catalog_path=catalog_path.resolve(),
        expected_catalog_sha256=hashlib.sha256(
            catalog_path.read_bytes()
        ).hexdigest(),
    )
    assert summary["completeness"]["complete"] is False
    assert summary["completeness"]["resource_termination"] == (
        "cumulative_object_reads_limit_exceeded"
    )
    assert summary["requested_split_feasibility"]["complete_corpus_status"] == (
        "unknown_incomplete_scan"
    )
    assert summary["requested_split_feasibility"][
        "observed_capacity_status"
    ].startswith("partial_observed_")
    assert summary["errors"]["by_reason"] == {
        "cumulative_object_reads_limit_exceeded": 1,
    }
    assert summary["privacy"]["aggregate_counts_only"] is True
    assert not any(summary["authority"].values())


def test_component_material_bound_and_dedup_count_mismatch_fail_closed(
    tmp_path: Path, monkeypatch,
) -> None:
    module = load_module()
    materials = [
        _synthetic_material(module, 100, frozenset()),
        _synthetic_material(module, 200, frozenset()),
    ]
    monkeypatch.setattr(module, "MAX_REVISION_MATERIALS", 1)
    with pytest.raises(module.Stage12693Error, match="material_limit"):
        module.assign_historical_components(materials)

    repo, _root, child, _head = make_history(tmp_path)
    pinned, _exclusion, revision = _materialized_fixture_rows(module, repo, child)
    try:
        malformed = module.HistoricalRevisionRows(
            revision.material, revision.rows, revision.proofs[:-1],
        )
        with pytest.raises(module.Stage12693Error, match="count_mismatch"):
            module.globally_deduplicate_historical_rows([malformed])
    finally:
        pinned.close()
