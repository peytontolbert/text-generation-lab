from __future__ import annotations

import collections
import hashlib
import importlib.util
import itertools
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12688_source_backed_multilingual_knowledge_corpus.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12688", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return result.stdout.strip()


def create_repo(source_root: Path, index: int) -> tuple[Path, str, str]:
    repo = source_root / f"repo-{index:03d}"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    origin = f"https://example.invalid/repo-{index:03d}.git"
    git(repo, "remote", "add", "origin", origin)
    files = {
        "LICENSE": (
            f"Internal fixture terms for repository {index}. Permission is hereby granted, free of charge.\n"
            "MIT License. THE SOFTWARE IS PROVIDED AS IS.\n"
        ),
        "src/main.py": (
            f"VALUE_{index} = {index}\n\n"
            f"def compute_{index}(value: int) -> int:\n"
            f"    adjusted_{index} = value + VALUE_{index}\n"
            f"    return adjusted_{index}\n"
        ),
        f"src/helper_{index}.py": (
            f"def helper_{index}(value: int) -> int:\n"
            f"    return value * {index + 2}\n"
        ),
        f"src/types_{index}.py": (
            f"TYPE_NAME_{index} = \"fixture_type_{index}\"\n"
            f"TYPE_VERSION_{index} = {index + 1}\n"
        ),
        "tests/main_test.ts": (
            f"import {{ compute{index} }} from '../src/main';\n"
            f"test('compute {index}', () => expect(compute{index}(2)).toBeGreaterThan(1));\n"
        ),
        "README.md": (
            f"# Repository {index}\n\n"
            f"This fixture repository demonstrates exact source reconstruction number {index}.\n"
        ),
        "Cargo.toml": (
            "[package]\n"
            f'name = "fixture-{index}"\n'
            'version = "0.1.0"\n'
        ),
        "config/settings.yaml": (
            f"service_name: fixture_{index}\n"
            f"worker_count: {index + 2}\n"
        ),
    }
    for relative, text in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", ".")
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_DATE": f"2021-02-{index % 28 + 1:02d}T00:00:00Z",
        "GIT_COMMITTER_DATE": f"2021-02-{index % 28 + 1:02d}T00:00:00Z",
    })
    git(repo, "commit", "-q", "-m", f"fixture {index}", env=env)
    return repo, origin, git(repo, "rev-parse", "HEAD")


def snapshot(module, *, blobs=None, split="train", lineage_keys=()):
    blobs = blobs or []
    return module.RepoSnapshot(
        local_path=Path("/unused"),
        repo_key="a" * 64,
        origin_url="https://example.invalid/source.git",
        revision="b" * 40,
        tree_oid="c" * 40,
        blobs=blobs,
        component_objects=tuple(("blob", blob.oid, blob.size) for blob in blobs),
        lineage_keys=lineage_keys,
        tree_entries=tuple(
            module.TreeEntry("100644", "blob", blob.oid, blob.size, blob.path)
            for blob in blobs
        ),
        component_key="d" * 64,
        split=split,
    )


@pytest.mark.parametrize(
    ("path", "language", "role"),
    [
        ("src/main.py", "python", "code"),
        ("src/main.js", "javascript_typescript", "code"),
        ("src/main.tsx", "javascript_typescript", "code"),
        ("cmd/main.go", "go", "code"),
        ("src/lib.rs", "rust", "code"),
        ("src/Main.java", "java", "code"),
        ("src/native.cc", "c_cpp", "code"),
        ("include/native.hpp", "c_cpp", "code"),
        ("tools/check.sh", "shell", "code"),
        ("README.md", "markdown", "documentation"),
        ("docs/guide.rst", "restructuredtext", "documentation"),
        ("config/app.json", "json", "config"),
        ("config/app.toml", "toml", "config"),
        ("config/app.yaml", "yaml", "config"),
        ("tests/main_test.py", "python", "test"),
        ("package.json", "json", "build"),
        ("Cargo.toml", "toml", "build"),
        ("go.mod", "go_module", "build"),
        ("pom.xml", "xml", "build"),
        ("CMakeLists.txt", "cmake", "build"),
        ("Makefile", "make", "build"),
        ("Dockerfile", "dockerfile", "build"),
    ],
)
def test_role_and_language_classification(path: str, language: str, role: str) -> None:
    module = load_module()
    assert module.classify_path(path) == module.FileKind(language, role)


def test_path_and_content_filters_fail_closed() -> None:
    module = load_module()
    assert module.classify_path("../escape.py") is None
    assert module.classify_path("/absolute.py") is None
    assert module.classify_path("src\\escape.py") is None
    assert module.classify_path("vendor/copied.rs") is None
    assert module.classify_path("src/generated/client.go") is None
    assert module.classify_path("package-lock.json") is None
    for malformed in (
        "src\nname.py", "src\tname.py", "src\x01name.py", "src\x7fname.py", "src\u0085name.py",
        "src//name.py", "src/name.py/", "./name.py", "src/../name.py",
    ):
        assert module.canonical_git_path(malformed) is False
        assert module.classify_path(malformed) is None
    assert module.classify_path("docs/test_guide.md") == module.FileKind("markdown", "test")
    for invalid_name in (
        "", ".", "..", "nested/name.py", "nested\\name.py", "bad\nname.py",
        "bad\tname.py", "bad\x00name.py", "TODO.py", module.DIRECTORY_ENTRY_MASK,
    ):
        assert module.canonical_entry_name(invalid_name) is False

    assert module.content_rejection_reason(b"x\x00y" + b" " * 30) == "binary"
    assert module.content_rejection_reason(b"\xff" * 30) == "malformed_utf8"
    assert module.content_rejection_reason(b"# automatically generated\n" + b"x = 1\n" * 5) == "generated"
    assert module.content_rejection_reason(b"token = AKIA1234567890ABCDEF\n") == "secret"
    assert module.content_rejection_reason(b"pass\n" + b" " * 30) == "stub_placeholder"
    assert module.content_rejection_reason(b"def complete(value):\n    return value + 1\n") is None

    for sentinel in ("COMMIT_PLACEHOLDER", "TITLE_PLACEHOLDER", "PLACEHOLDER"):
        payload = f"resolved_value = {sentinel}\n# enough source bytes for filtering\n".encode()
        assert module.UNRESOLVED_SENTINEL_RE.search(sentinel)
        assert module.content_rejection_reason(payload) == "unresolved_sentinel"
        assert all(
            sentinel not in payload[start:end].decode("utf-8")
            for start, end in module.candidate_spans(payload, "repo", "src/value.py")
        )
        assert module.canonical_entry_name(f"{sentinel}.py") is False

    for legitimate_term in (
        "ObjectPlaceholder.tsx",
        "PropertyPlaceholderAutoConfiguration",
        "TodoItem",
        "mockTodos",
        "autodoc",
        "placeholder UI parameters",
    ):
        assert module.rejected_target_marker(legitimate_term) is False

    legitimate = (
        "export const ObjectPlaceholder = () => null;\n"
        "class PropertyPlaceholderAutoConfiguration {}\n"
        "class TodoItem { constructor(public value: string) {} }\n"
        "const mockTodos = [new TodoItem(\"ship\")];\n"
        "const autodoc = true;\n"
        "const parameterHelp = \"placeholder UI parameters remain configurable\";\n"
    ).encode()
    assert module.content_rejection_reason(legitimate) is None
    assert len(module.candidate_spans(legitimate, "repo", "src/legitimate.tsx")) > 0
    assert module.classify_path("src/ObjectPlaceholder.tsx") == module.FileKind(
        "javascript_typescript", "code"
    )
    assert module.classify_path(
        "src/PropertyPlaceholderAutoConfiguration.java"
    ) == module.FileKind("java", "code")


def test_exact_span_reinsertion_and_target_mutation_independence() -> None:
    module = load_module()
    data = (
        b"const alpha = 17;\n"
        b"function compute(value) { return value + alpha; }\n"
        b"export { compute };\n"
    )
    blob_data = b"blob " + str(len(data)).encode() + b"\0" + data
    blob = module.Blob(hashlib.sha1(blob_data).hexdigest(), len(data), "src/main.js")
    snap = snapshot(module, blobs=[blob])
    kind = module.classify_path(blob.path)
    assert kind is not None
    spans = module.candidate_spans(data, snap.repo_key, blob.path)
    assert spans
    built = module.build_span_row(snap, blob, kind, data, spans[0])
    assert built is not None
    row, proof = built
    target = row["target"]["decoder_text"]
    assert row["input_text"].replace(module.MASK, target, 1).count(target) == 1
    assert proof["byte_exact_source_span_reinsertion_verified"] is True
    assert proof["exact_pinned_immediate_directory_entry_name_completion_verified"] is False
    assert module.normalized_without_whitespace(target) not in module.normalized_without_whitespace(row["input_text"])

    original_input = row["input_text"]
    mutated = json.loads(json.dumps(row))
    mutated["target"]["decoder_text"] = "a deliberately different exact target\n"
    assert mutated["input_text"] == original_input

    with pytest.raises(module.Stage12688Error, match="rejected_marker_in_final_target"):
        module._make_row_and_proof(
            snapshot=snap, blob=blob, kind=kind, input_text="safe encoder input",
            target="TITLE_PLACEHOLDER", objective="multilingual_exact_source_span_infilling",
            source_file_sha256="1" * 64, source_window_sha256="2" * 64,
            span_start=0, span_end=1, reinsertion_contract="test",
        )


def test_exact_immediate_directory_entry_name_completion_uses_real_git_tree(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo, _origin, _revision = create_repo(source_root, 31)
    snapshots, counters = module.discover_repositories(source_root, 10)
    assert counters["repositories_accepted"] == 1
    snap = snapshots[0]
    target_blob = next(blob for blob in snap.blobs if blob.path == "src/main.py")
    inventory = (snap.directory_inventories or {})["src"]
    built = module.build_directory_entry_row(snap, target_blob)
    assert built is not None
    row, proof = built
    target = row["target"]["decoder_text"]
    assert target == "main.py"
    assert "/" not in target and "src" not in target
    assert row["input_text"].count(module.DIRECTORY_ENTRY_MASK) == 1
    assert "parent_directory: src" in row["input_text"]
    assert "main.py" not in row["input_text"]
    assert "src/main.py" not in row["input_text"]
    assert "helper_31.py" in row["input_text"]
    assert "types_31.py" in row["input_text"]
    visible_names = row["input_text"].split(
        "<PINNED_IMMEDIATE_DIRECTORY_ENTRY_NAMES>\n", 1
    )[1].split("\n</PINNED_IMMEDIATE_DIRECTORY_ENTRY_NAMES>", 1)[0].splitlines()
    reconstructed = [target if name == module.DIRECTORY_ENTRY_MASK else name for name in visible_names]
    assert reconstructed == [entry.path for entry in inventory.entries]
    expected_tree_oid = git(repo, "rev-parse", "HEAD:src")
    target_entry = next(entry for entry in inventory.entries if entry.path == target)
    provenance = row["source_provenance"]
    assert inventory.tree_oid == expected_tree_oid
    assert provenance["revision"] == snap.revision
    assert provenance["parent_tree_oid"] == expected_tree_oid
    assert provenance["target_object_mode"] == target_entry.mode
    assert provenance["target_object_type"] == "blob"
    assert provenance["target_object_oid"] == target_blob.oid
    assert provenance["repository_relative_path"] == "src/main.py"
    assert proof["byte_exact_source_span_reinsertion_verified"] is False
    assert proof["exact_pinned_immediate_directory_entry_name_completion_verified"] is True
    original_input = row["input_text"]
    mutated = json.loads(json.dumps(row))
    mutated["target"]["decoder_text"] = "mutated.py"
    mutated["source_provenance"]["target_object_oid"] = "0" * 40
    mutated["source_provenance"]["parent_tree_oid"] = "1" * 40
    assert mutated["input_text"] == original_input


def test_single_shared_blob_does_not_union_but_exact_lineage_does() -> None:
    module = load_module()
    shared = ("blob", "9" * 40, 100)
    left = snapshot(module, blobs=[], lineage_keys=("root:shared",))
    left.repo_key = "1" * 64
    left.component_objects = (shared,)
    right = snapshot(module, blobs=[], lineage_keys=("root:other",))
    right.repo_key = "2" * 64
    right.component_objects = (shared,)
    module.assign_components([left, right])
    assert left.component_key != right.component_key

    third = snapshot(module, blobs=[], lineage_keys=("root:same-history",))
    third.repo_key = "3" * 64
    fourth = snapshot(module, blobs=[], lineage_keys=("root:same-history",))
    fourth.repo_key = "4" * 64
    module.assign_components([third, fourth])
    assert third.component_key == fourth.component_key
    assert third.split == fourth.split


def test_duplicate_examples_are_rejected() -> None:
    module = load_module()
    data = b"unique_configuration_value = 193\n"
    blob = module.Blob("7" * 40, len(data), "config/settings.toml")
    snap = snapshot(module, blobs=[blob])
    kind = module.classify_path(blob.path)
    assert kind is not None
    built = module.build_span_row(snap, blob, kind, data, (0, len(data)))
    assert built is not None
    row, proof = built
    rows: list[dict] = []
    proofs: list[dict] = []
    seen = {name: set() for name in ("id", "row", "input", "model", "semantic", "window")}
    counters: collections.Counter[str] = collections.Counter()
    kwargs = {
        "rows": rows,
        "proofs": proofs,
        "seen": seen,
        "digest_splits": {},
        "input_splits": {},
        "quarantined_file_digests": set(),
        "quarantined_file_instances": set(),
        "quarantined_objective_families": set(),
        "counters": counters,
    }
    assert module._validate_and_add(row, proof, **kwargs) is True
    assert module._validate_and_add(row, proof, **kwargs) is False
    assert counters["duplicate_row_or_example_rejected"] == 1
    assert counters["global_row_id_duplicate_rejected"] == 1
    assert counters["global_input_duplicate_rejected"] == 1
    assert counters["global_model_duplicate_rejected"] == 1
    assert counters["global_semantic_duplicate_rejected"] == 1
    assert counters["global_window_duplicate_rejected"] == 1


def test_identical_encoder_input_is_rejected_across_files_objectives_and_targets() -> None:
    module = load_module()
    left_blob = module.Blob("1" * 40, 80, "src/left.py")
    right_blob = module.Blob("2" * 40, 90, "docs/right.md")
    snap = snapshot(module, blobs=[left_blob, right_blob], split="train")
    left_kind = module.classify_path(left_blob.path)
    right_kind = module.classify_path(right_blob.path)
    assert left_kind is not None and right_kind is not None
    shared_input = "repository state with one deliberately ambiguous encoder input"
    left = module._make_row_and_proof(
        snapshot=snap, blob=left_blob, kind=left_kind, input_text=shared_input,
        target="left.py", objective="exact_pinned_immediate_directory_entry_name_completion",
        source_file_sha256="3" * 64, source_window_sha256="4" * 64,
        span_start=None, span_end=None, reinsertion_contract="test-layout",
    )
    right = module._make_row_and_proof(
        snapshot=snap, blob=right_blob, kind=right_kind, input_text=shared_input,
        target="different target text\n", objective="multilingual_exact_source_span_infilling",
        source_file_sha256="5" * 64, source_window_sha256="6" * 64,
        span_start=0, span_end=22, reinsertion_contract="test-span",
    )
    assert left[1]["encoder_input_sha256"] == right[1]["encoder_input_sha256"]
    assert left[1]["model_example_sha256"] != right[1]["model_example_sha256"]
    assert left[1]["semantic_example_sha256"] != right[1]["semantic_example_sha256"]
    rows: list[dict] = []
    proofs: list[dict] = []
    seen = {name: set() for name in ("id", "row", "input", "model", "semantic", "window")}
    counters: collections.Counter[str] = collections.Counter()
    kwargs = {
        "rows": rows, "proofs": proofs, "seen": seen,
        "digest_splits": {}, "input_splits": {},
        "quarantined_file_digests": set(),
        "quarantined_file_instances": set(),
        "quarantined_objective_families": set(),
        "counters": counters,
    }
    assert module._validate_and_add(*left, **kwargs) is True
    assert module._validate_and_add(*right, **kwargs) is False
    assert counters["global_input_duplicate_rejected"] == 1
    assert counters["global_model_duplicate_rejected"] == 0
    assert counters["global_semantic_duplicate_rejected"] == 0
    assert counters["global_window_duplicate_rejected"] == 0
    assert counters["public_duplicate_encoder_input_rows_quarantined"] == 1
    assert len(rows) == len({proof["encoder_input_sha256"] for proof in proofs}) == 1


def test_source_window_model_and_semantic_duplicates_remain_global_across_splits() -> None:
    module = load_module()
    data = b"global_duplicate_value = calculate_unique_value(29)\n"
    blob = module.Blob("8" * 40, len(data), "src/global.py")
    snap = snapshot(module, blobs=[blob], split="train")
    kind = module.classify_path(blob.path)
    assert kind is not None
    built = module.build_span_row(snap, blob, kind, data, (0, len(data)))
    assert built is not None
    row, proof = built
    rows: list[dict] = []
    proofs: list[dict] = []
    seen = {name: set() for name in ("id", "row", "input", "model", "semantic", "window")}
    digest_splits: dict[str, str] = {}
    input_splits: dict[str, str] = {}
    quarantined_digests: set[str] = set()
    quarantined_instances: set[str] = set()
    quarantined_objectives: set[str] = set()
    counters: collections.Counter[str] = collections.Counter()
    kwargs = {
        "rows": rows, "proofs": proofs, "seen": seen,
        "digest_splits": digest_splits,
        "input_splits": input_splits,
        "quarantined_file_digests": quarantined_digests,
        "quarantined_file_instances": quarantined_instances,
        "quarantined_objective_families": quarantined_objectives,
        "counters": counters,
    }
    assert module._validate_and_add(row, proof, **kwargs) is True
    duplicate_row = json.loads(json.dumps(row))
    duplicate_proof = json.loads(json.dumps(proof))
    duplicate_row["row_id"] = "different_row_id"
    duplicate_row["split"] = "eval"
    duplicate_proof["row_id"] = "different_row_id"
    duplicate_proof["row_sha256"] = "9" * 64
    duplicate_proof["split"] = "eval"
    duplicate_proof["source_file_sha256"] = "a" * 64
    assert module._validate_and_add(duplicate_row, duplicate_proof, **kwargs) is False
    assert counters["global_input_duplicate_rejected"] == 1
    assert counters["global_model_duplicate_rejected"] == 1
    assert counters["global_semantic_duplicate_rejected"] == 1
    assert counters["global_window_duplicate_rejected"] == 1
    assert counters["cross_split_source_file_digest_candidate_rows_rejected"] == 0
    assert quarantined_digests == set()


def test_common_license_content_is_quarantined_across_components_and_caps_refill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repositories = [create_repo(source_root, index)[0] for index in range(3)]
    common_content = (
        "# Shared internal license\n\n"
        "This exact policy text is intentionally common across unrelated repositories.\n"
    )
    for repo in repositories:
        license_path = repo / "docs" / "LICENSE.md"
        license_path.parent.mkdir(parents=True, exist_ok=True)
        license_path.write_text(common_content, encoding="utf-8")
        (repo / "docs" / f"guide_{repo.name}.md").write_text(
            f"# Guide for {repo.name}\n\nUnique guide material for directory context.\n",
            encoding="utf-8",
        )
        (repo / "docs" / f"reference_{repo.name}.md").write_text(
            f"# Reference for {repo.name}\n\nUnique reference material for layout refill.\n",
            encoding="utf-8",
        )
        git(repo, "add", "docs")
        git(repo, "commit", "-q", "-m", "add shared license fixture")

    discovered, _counters = module.discover_repositories(source_root, 10)
    assert len(discovered) == 3
    module.assign_components(discovered)
    assert len({snapshot.repo_key for snapshot in discovered}) == 3
    assert len({snapshot.component_key for snapshot in discovered}) == 3

    def forced_split_assignment(snapshots, requested_rows=None):
        split_by_name = {"repo-000": "train", "repo-001": "eval", "repo-002": "strict_eval"}
        prefix_by_split = {"train": "a", "eval": "b", "strict_eval": "c"}
        for item in snapshots:
            item.split = split_by_name[item.local_path.name]
            item.component_key = prefix_by_split[item.split] + module.stable([item.repo_key])[1:]
            item.blobs.sort(key=lambda blob: (blob.path != "docs/LICENSE.md", blob.path))
        return {
            "estimated_split_cap_feasible": True,
            "contract_version": module.FORK_GROUPING_CONTRACT_VERSION,
            "thresholds": {},
            "whole_component_assignment": True,
            "allocation_method": "test_forced",
            "allocation_search_budget_exhausted": False,
            "residual": "test fixture",
        }

    monkeypatch.setattr(module, "assign_components", forced_split_assignment)
    real_layout_builder = module.build_directory_entry_row

    def inject_ambiguous_layout_candidate(item, blob, source_file_sha256=""):
        if item.split == "train" and blob.path in {"Cargo.toml", "README.md"}:
            kind = module.classify_path(blob.path)
            assert kind is not None
            is_cargo = blob.path == "Cargo.toml"
            return module._make_row_and_proof(
                snapshot=item, blob=blob, kind=kind,
                input_text="identical ambiguous encoder input across files and objectives",
                target="cargo-choice" if is_cargo else "readme-choice\n",
                objective=(
                    "exact_pinned_immediate_directory_entry_name_completion"
                    if is_cargo else "multilingual_exact_source_span_infilling"
                ),
                source_file_sha256=source_file_sha256,
                source_window_sha256=module.stable(["ambiguous", blob.path]),
                span_start=None if is_cargo else 0,
                span_end=None if is_cargo else 14,
                reinsertion_contract="ambiguous-input-refill-test",
            )
        return real_layout_builder(item, blob, source_file_sha256)

    monkeypatch.setattr(
        module, "build_directory_entry_row", inject_ambiguous_layout_candidate
    )
    summary = module.build(
        source_root, tmp_path / "output", tmp_path / "summary.json",
        max_repos=10, max_rows=10,
    )
    assert summary["public_split_counts"] == {"eval": 1, "train": 8}
    assert summary["unresolved_sentinel_target_rows"] == 0
    assert summary["distinct_encoder_input_hashes"] == summary["materialized_model_row_count"]
    assert summary["encoder_input_hashes_equal_materialized_rows"] is True
    assert summary["public_duplicate_encoder_input_rows_quarantined"] >= 1
    quarantine = summary["public_cross_split_source_file_quarantine"]
    assert quarantine["quarantined_distinct_source_file_digest_count"] == 1
    assert quarantine["quarantined_file_instance_count"] == 3
    assert quarantine["candidate_row_rejection_count"] >= 2
    assert quarantine["finalized_train_eval_file_digest_overlap_zero"] is True
    assert quarantine["exact_public_split_caps_refilled"] is True
    assert len(quarantine["quarantined_source_file_digest_commitment_sha256"]) == 64
    assert set(quarantine["quarantined_objective_families"]) == {
        "multilingual_exact_source_span_infilling",
        "exact_pinned_immediate_directory_entry_name_completion",
    }
    assert summary["train_eval_file_digest_overlap"] == 0
    assert summary["public_split_overlap_metrics"]["file_digest"]["overlap_count"] == 0


def test_secure_publication_rejects_temp_collision_and_symlink_parent(tmp_path: Path) -> None:
    module = load_module()
    target = tmp_path / "artifact.jsonl"
    data = b"protected\n"
    temporary = tmp_path / f".{target.name}.tmp.{os.getpid()}.{module.sha256_bytes(data)[:12]}"
    victim = tmp_path / "victim"
    victim.write_text("unchanged", encoding="utf-8")
    temporary.symlink_to(victim)
    with pytest.raises(FileExistsError):
        module.secure_atomic_write(target, data, mode=0o600)
    assert victim.read_text(encoding="utf-8") == "unchanged"

    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        module.open_directory_nofollow(linked)


def test_full_build_materializes_only_train_eval_and_freezes_strict_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    for index in range(12):
        repo, _origin, _revision = create_repo(source_root, index)
        if index < 8:
            sentinel = "COMMIT_PLACEHOLDER" if index % 2 == 0 else "TITLE_PLACEHOLDER"
            sentinel_path = repo / "docs" / f"unresolved_{index}.md"
            sentinel_path.parent.mkdir(parents=True, exist_ok=True)
            sentinel_path.write_text(
                f"# Unresolved fixture {index}\n\nvalue: {sentinel}\n", encoding="utf-8"
            )
            git(repo, "add", str(sentinel_path.relative_to(repo)))
            git(repo, "commit", "-q", "-m", f"add unresolved fixture {index}")

    failed_output = tmp_path / "transaction-failure"
    failed_summary = tmp_path / "must-not-publish-summary.json"
    real_rename = module.rename_noreplace
    def reject_generation_rename(*args, **kwargs):
        raise OSError("injected generation rename failure")
    monkeypatch.setattr(module, "rename_noreplace", reject_generation_rename)
    with pytest.raises(OSError, match="injected generation rename failure"):
        module.build(source_root, failed_output, failed_summary, max_repos=100, max_rows=20)
    assert not failed_summary.exists()
    assert not (failed_output / "summary.json").exists()
    assert all(path.name.startswith(".pending-") for path in (failed_output / "private").iterdir())
    monkeypatch.setattr(module, "rename_noreplace", real_rename)

    output = tmp_path / "artifacts"
    summary_path = tmp_path / "summary.json"
    real_prepare = module.prepare_release
    captured = []

    def capture_prepared(*args, **kwargs):
        prepared = real_prepare(*args, **kwargs)
        captured.append(prepared)
        return prepared

    monkeypatch.setattr(module, "prepare_release", capture_prepared)
    summary = module.build(source_root, output, summary_path, max_repos=100, max_rows=20)
    assert len(captured) == 1
    prepared = captured[0]
    assert summary["public_split_counts"] == {"eval": 2, "train": 16}
    assert "row_count" not in summary
    assert summary["materialized_model_row_count"] == 18
    assert summary["distinct_encoder_input_hashes"] == 18
    assert summary["encoder_input_hashes_equal_materialized_rows"] is True
    assert summary["reserved_unmaterialized_strict_row_count"] == 2
    assert len(summary["strict_eval_commitment_sha256"]) == 64
    strict_top_level_keys = {key for key in summary if "strict" in key}
    assert strict_top_level_keys == {
        "reserved_unmaterialized_strict_row_count",
        "strict_eval_commitment_sha256",
    }
    forbidden_strict_detail = {
        "frozen_per_language_retention_commitments",
        "frozen_retention_language_count",
        "strict_retention_sufficient",
        "strict_retention_status",
        "strict_nonrequired_language_counts",
        "strict_objective_family_counts",
        "strict_eval_plaintext_materialized",
        "strict_eval_rebuild_required_for_release_review",
        "reserved_unmaterialized_strict_source_catalog_rows",
        "counters",
    }
    assert forbidden_strict_detail.isdisjoint(summary)
    assert summary["all_tree_object_inventory_audit"]["retained"] is True
    grouping = summary["practical_fork_grouping_contract"]
    assert grouping["contract_version"] == module.FORK_GROUPING_CONTRACT_VERSION
    assert grouping["whole_component_assignment"] is True
    assert grouping["estimated_split_cap_feasible"] is True
    assert "estimated_split_row_capacities" not in grouping
    assert "estimated_split_capacity_fractions" not in grouping
    assert "requested_split_row_caps" not in grouping
    assert summary["training_eligible_rows"] == 0
    assert all(value is False for value in summary["authority"].values())
    assert summary["stub_or_placeholder_target_rows"] == 0
    assert summary["unresolved_sentinel_target_rows"] == 0
    assert summary["input_target_whitespace_normalized_overlap_rows"] == 0
    assert "license_and_training_permission_review_required" not in summary["release_blockers"]
    assert "retention_eligibility_not_established" in summary["release_blockers"]
    assert summary["near_duplicate_rerooted_residual"]["status"] == "UNRESOLVED_REVIEW_REQUIRED"
    assert all(
        metric["computed_from_finalized_rows"] is True and metric["overlap_count"] == 0
        for metric in summary["public_split_overlap_metrics"].values()
    )

    generation = output / summary["generation_relative_path"]
    assert generation.stat().st_mode & 0o777 == 0o500
    authoritative_summary = generation / "summary.json"
    assert authoritative_summary.exists()
    assert authoritative_summary.stat().st_mode & 0o777 == 0o400
    assert summary["authoritative_summary_relative_path"] == (
        summary["generation_relative_path"] + "/summary.json"
    )
    assert summary["generation_and_authoritative_summary_transactional"] is True
    assert summary["external_summary_mirrors_are_nonauthoritative"] is True
    assert not any("strict" in path.name for path in generation.iterdir())
    manifest = [
        json.loads(line)
        for line in (generation / "multilingual_train_eval_manifest.jsonl").read_text().splitlines()
    ]
    provenance = [
        json.loads(line)
        for line in (generation / "train_eval_source_provenance_ledger.jsonl").read_text().splitlines()
    ]
    catalog = [
        json.loads(line)
        for line in (generation / "train_eval_source_catalog.jsonl").read_text().splitlines()
    ]
    assert len(manifest) == 18
    assert len({
        module.sha256_bytes(row["input_text"].encode("utf-8")) for row in manifest
    }) == len(manifest) == summary["distinct_encoder_input_hashes"]
    proof_by_row_id = {proof["row_id"]: proof for proof in provenance}
    assert all(
        proof_by_row_id[row["row_id"]]["encoder_input_sha256"]
        == module.sha256_bytes(row["input_text"].encode("utf-8"))
        for row in manifest
    )
    assert {row["split"] for row in manifest} <= {"train", "eval"}
    assert all(
        row["source_provenance"]["origin_url_trust"]
        == "untrusted_mutable_metadata_not_used_for_identity_or_split"
        for row in manifest
    )
    assert all(
        row["source_provenance"]["origin_url_sha256"]
        == module.sha256_bytes(row["source_provenance"]["origin_url"].encode("utf-8"))
        for row in manifest
    )
    assert all(
        row["origin_url_trust"] == "untrusted_mutable_metadata_not_used_for_identity_or_split"
        for row in catalog
    )
    assert all(
        row["origin_url_sha256"]
        == module.sha256_bytes(row["origin_url"].encode("utf-8"))
        for row in catalog
    )
    remote_contract = summary["mutable_remote_metadata_contract"]
    assert all(remote_contract.values())
    assert summary["near_duplicate_rerooted_residual"][
        "mutable_remote_metadata_hard_grouping"
    ] is False
    assert all(row["all_tree_object_count"] > 0 for row in catalog)
    assert all(
        proof["immediate_directory_inventory_sha256"] and proof["parent_tree_oid"]
        for proof in provenance
        if proof["objective_family"] == "exact_pinned_immediate_directory_entry_name_completion"
    )
    assert all(
        module.normalized_without_whitespace(row["target"]["decoder_text"])
        not in module.normalized_without_whitespace(row["input_text"])
        for row in manifest
    )
    for name, contract in summary["artifact_contract"].items():
        path = output / contract["relative_path"]
        assert module.file_sha256(path) == contract["sha256"]
        assert path.stat().st_mode & 0o777 == 0o400
    expected_generation_id = module.stable([
        "stage12688_generation_v4_public_artifacts_and_strict_commitment",
        summary["artifact_schema_version"],
        sorted(
            (name, contract["rows"], contract["sha256"])
            for name, contract in summary["artifact_contract"].items()
        ),
        summary["reserved_unmaterialized_strict_row_count"],
        summary["strict_eval_commitment_sha256"],
    ])[:24]
    assert summary["generation_id"] == expected_generation_id

    assert summary_path.read_bytes() == (output / "summary.json").read_bytes()
    assert summary_path.read_bytes() == authoritative_summary.read_bytes()
    assert summary == prepared.summary
    assert len(prepared.rows) == len(prepared.proofs) == 20
    proof_by_row_id = {proof["row_id"]: proof for proof in prepared.proofs}
    catalog_split = {
        entry["repository_key_sha256"]: entry["split"] for entry in prepared.catalog
    }
    assert all(
        row["split"] == proof_by_row_id[row["row_id"]]["split"]
        == catalog_split[row["source_provenance"]["repository_key_sha256"]]
        for row in prepared.rows
    )
    strict_rows = [row for row in prepared.rows if row["split"] == "strict_eval"]
    strict_proofs = [
        proof for proof in prepared.proofs if proof["split"] == "strict_eval"
    ]
    assert len(strict_rows) == len(strict_proofs) == summary[
        "reserved_unmaterialized_strict_row_count"
    ]
    assert module.stable(sorted(proof["row_sha256"] for proof in strict_proofs)) == summary[
        "strict_eval_commitment_sha256"
    ]
    for name, payload in prepared.public_payloads.items():
        assert (generation / name).read_bytes() == payload
    with pytest.raises(module.Stage12688Error, match="immutable_generation_exists"):
        module.build(source_root, output, summary_path, max_repos=100, max_rows=20)

    real_private = tmp_path / "real-private"
    real_private.mkdir()
    linked_output = tmp_path / "linked-output"
    linked_output.mkdir()
    (linked_output / "private").symlink_to(real_private, target_is_directory=True)
    with pytest.raises(module.Stage12688Error, match="symlinked_private_root"):
        module.build(source_root, linked_output, tmp_path / "linked-summary.json", max_repos=100, max_rows=20)


@pytest.mark.parametrize("max_rows", [0, 9, 11, 12])
def test_invalid_max_rows_rejected_before_discovery_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_rows: int
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    output = tmp_path / "output"
    discovery_called = False

    def forbidden_discovery(*_args, **_kwargs):
        nonlocal discovery_called
        discovery_called = True
        raise AssertionError("discovery must not run")

    monkeypatch.setattr(module, "discover_repositories", forbidden_discovery)
    with pytest.raises(module.Stage12688Error, match="invalid_max_rows_exact_80_10_10_required"):
        module.build(
            source_root, output, tmp_path / "summary.json",
            max_repos=10, max_rows=max_rows,
        )
    assert discovery_called is False
    assert not output.exists()


def test_any_finalized_cross_split_overlap_aborts_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    for index in range(12):
        create_repo(source_root, index)
    output = tmp_path / "output"
    summary_path = tmp_path / "summary.json"

    def injected_overlap(_proofs, field):
        return {
            "field": field,
            "overlap_count": 1,
            "overlap_value_commitment_sha256": "f" * 64,
            "computed_from_finalized_rows": True,
        }

    monkeypatch.setattr(module, "finalized_cross_split_overlap", injected_overlap)
    with pytest.raises(module.Stage12688Error, match="finalized_cross_split_overlap_detected"):
        module.build(
            source_root, output, summary_path, max_repos=100, max_rows=20
        )
    assert not output.exists()
    assert not summary_path.exists()


def test_finalized_overlap_metrics_detect_real_overlap() -> None:
    module = load_module()
    proofs = [
        {"split": "train", "repository_key_sha256": "shared"},
        {"split": "eval", "repository_key_sha256": "shared"},
        {"split": "strict_eval", "repository_key_sha256": "strict-only"},
    ]
    metric = module.finalized_cross_split_overlap(proofs, "repository_key_sha256")
    assert metric["computed_from_finalized_rows"] is True
    assert metric["overlap_count"] == 1
    assert len(metric["overlap_value_commitment_sha256"]) == 64


def test_shallow_repository_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    create_repo(source_root, 1)
    real_git = module.git

    def shallow_git(repo: Path, *args: str, timeout: int = 60) -> bytes:
        if args == ("rev-parse", "--is-shallow-repository"):
            return b"true\n"
        return real_git(repo, *args, timeout=timeout)

    monkeypatch.setattr(module, "git", shallow_git)
    snapshots, counters = module.discover_repositories(source_root, 10)
    assert snapshots == []
    assert counters["shallow_repository_rejected"] == 1


def test_noncanonical_immediate_directory_entry_is_rejected() -> None:
    module = load_module()
    target = module.Blob("1" * 40, 80, "src/main.py")
    snap = snapshot(module, blobs=[target])
    snap.directory_inventories = {
        "src": module.DirectoryInventory(
            "src",
            "3" * 40,
            (
                module.TreeEntry("100644", "blob", target.oid, target.size, "main.py"),
                module.TreeEntry("100644", "blob", "2" * 40, 10, "bad\nentry.py"),
                module.TreeEntry("040000", "tree", "4" * 40, None, "nested"),
            ),
        )
    }
    with pytest.raises(module.Stage12688Error, match="noncanonical_immediate_directory_inventory"):
        module.build_directory_entry_row(snap, target)


def test_discovery_rejects_repository_with_noncanonical_tree_path(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo, _origin, _revision = create_repo(source_root, 2)
    (repo / "bad\nname.py").write_text("value = 17\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "add malformed path")
    snapshots, counters = module.discover_repositories(source_root, 10)
    assert snapshots == []
    assert counters["noncanonical_tree_path_rejected"] == 1


def test_ls_tree_parses_blobs_submodules_and_trees_and_groups_all_objects() -> None:
    module = load_module()
    blob_oid = "1" * 40
    submodule_oid = "2" * 40
    tree_oid = "3" * 40
    raw = (
        f"100644 blob {blob_oid} 17\tsrc/main.py\0"
        f"160000 commit {submodule_oid} -\tthird_party/tool\0"
        f"040000 tree {tree_oid} -\tdocs\0"
    ).encode("ascii")
    entries = module.parse_ls_tree(raw)
    assert entries == [
        module.TreeEntry("100644", "blob", blob_oid, 17, "src/main.py"),
        module.TreeEntry("160000", "commit", submodule_oid, None, "third_party/tool"),
        module.TreeEntry("040000", "tree", tree_oid, None, "docs"),
    ]
    rendered = [module.render_tree_entry(entry) for entry in entries]
    assert rendered[0] == f"100644 blob {blob_oid} 17\tsrc/main.py"
    assert rendered[1] == f"160000 commit {submodule_oid} -\tthird_party/tool"
    assert rendered[2] == f"040000 tree {tree_oid} -\tdocs"

    shared_submodule = ("commit", submodule_oid, None)
    left = snapshot(module, blobs=[])
    left.repo_key = "a" * 64
    left.component_objects = (shared_submodule,)
    right = snapshot(module, blobs=[])
    right.repo_key = "b" * 64
    right.component_objects = (shared_submodule,)
    module.assign_components([left, right])
    assert left.component_key != right.component_key


def test_identical_mutable_remote_does_not_union_or_change_identity_and_splits(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    left_repo, _left_origin, _left_revision = create_repo(source_root, 77)
    right_repo, _right_origin, _right_revision = create_repo(source_root, 78)
    shared_remote = "https://mutable.invalid/shared/location.git"
    git(left_repo, "remote", "set-url", "origin", shared_remote)
    git(right_repo, "remote", "set-url", "origin", shared_remote)

    before, _before_counters = module.discover_repositories(source_root, 10)
    assert len(before) == 2
    module.assign_components(before)
    assert {snapshot.origin_url for snapshot in before} == {shared_remote}
    assert len({snapshot.repo_key for snapshot in before}) == 2
    assert len({snapshot.component_key for snapshot in before}) == 2
    assert all(
        not any(key.startswith("remote_content:") for key in snapshot.lineage_keys)
        for snapshot in before
    )
    before_identity = {
        snapshot.local_path.name: (
            snapshot.repo_key, snapshot.component_key, snapshot.split,
            snapshot.revision, snapshot.tree_oid, snapshot.estimated_row_capacity,
        )
        for snapshot in before
    }

    git(left_repo, "remote", "set-url", "origin", "ssh://moved.invalid/left.git")
    git(right_repo, "remote", "remove", "origin")
    after, _after_counters = module.discover_repositories(source_root, 10)
    assert len(after) == 2
    module.assign_components(after)
    after_identity = {
        snapshot.local_path.name: (
            snapshot.repo_key, snapshot.component_key, snapshot.split,
            snapshot.revision, snapshot.tree_oid, snapshot.estimated_row_capacity,
        )
        for snapshot in after
    }
    assert before_identity == after_identity
    assert {snapshot.origin_url for snapshot in after} == {"ssh://moved.invalid/left.git", ""}
    assert len({snapshot.component_key for snapshot in after}) == 2


def test_foundational_trainer_allowlist_excludes_target_provenance_and_oracles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    data = b"unique_runtime_value = calculate_runtime_value(17)\n"
    blob = module.Blob("7" * 40, len(data), "src/runtime.py")
    snap = snapshot(module, blobs=[blob])
    kind = module.classify_path(blob.path)
    assert kind is not None
    built = module.build_span_row(snap, blob, kind, data, (0, len(data)))
    assert built is not None
    row, _proof = built

    types = __import__("types")
    fake_torch = types.ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    training_path = ROOT / "legacy_src/agentkernel_lite/training_data.py"
    spec = importlib.util.spec_from_file_location("stage12688_training_data", training_path)
    assert spec and spec.loader
    training_data = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = training_data
    spec.loader.exec_module(training_data)

    baseline_text = training_data._foundational_row_text(row)
    tokenizer = training_data.ByteTokenizer()
    baseline_tokens = tokenizer.encode(baseline_text, max_length=2048)
    mutated = json.loads(json.dumps(row))
    mutated.update({
        "row_id": "oracle-derived-row-id",
        "split": "strict_eval",
        "language_family": "oracle-language",
        "objective_family": "oracle-objective",
        "target": {"decoder_text": "oracle target", "label": "gold"},
        "loss_mask": {"decoder_ce": False, "oracle": True},
        "source_provenance": {
            "target_sha256": "0" * 64,
            "repository_relative_path": "oracle/path.py",
            "revision": "f" * 40,
            "correct_candidate_position": 999,
            "positive_chunk_ids": ["oracle-chunk"],
        },
        "authority": {"training_admitted": True},
        "positive_chunk_ids": ["oracle-top-level"],
        "gold_answer": "oracle",
    })
    assert training_data._foundational_row_text(mutated) == baseline_text
    assert tokenizer.encode(
        training_data._foundational_row_text(mutated), max_length=2048
    ) == baseline_tokens


def test_private_root_parent_swap_is_detected_before_generation_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_root = tmp_path / "artifact" / "private"
    moved_root = tmp_path / "artifact" / "private-original"
    real_revalidate = module.revalidate_directory_identity
    observed = {"swapped": False}

    def swap_then_revalidate(path: Path, fd: int, expected: tuple[int, int]) -> None:
        os.rename(path, moved_root)
        path.mkdir(mode=0o700)
        observed["swapped"] = True
        real_revalidate(path, fd, expected)

    monkeypatch.setattr(module, "revalidate_directory_identity", swap_then_revalidate)
    with pytest.raises(module.Stage12688Error, match="private_root_identity_changed"):
        module.publish_generation(
            private_root,
            "a" * 24,
            {"manifest.jsonl": b'{"row":1}\n'},
            {"authority": dict(module.AUTHORITY)},
        )
    assert observed["swapped"] is True
    assert not (private_root / ("a" * 24)).exists()
    assert any(path.name.startswith(".pending-") for path in moved_root.iterdir())


def test_pending_generation_substitution_race_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_root = tmp_path / "pending-substitution" / "private"
    generation_id = "b" * 24
    real_revalidate = module.revalidate_directory_identity
    calls = 0

    def substitute_pending(path: Path, fd: int, expected: tuple[int, int]) -> None:
        nonlocal calls
        real_revalidate(path, fd, expected)
        calls += 1
        if calls == 1:
            pending = next(
                entry for entry in path.iterdir()
                if entry.name.startswith(".pending-")
            )
            pending.rename(path / f"{pending.name}.original")
            pending.mkdir(mode=0o700)

    monkeypatch.setattr(module, "revalidate_directory_identity", substitute_pending)
    with pytest.raises(
        module.Stage12688Error,
        match="pending_generation_inode_mismatch",
    ):
        module.publish_generation(
            private_root,
            generation_id,
            {"manifest.jsonl": b'{"row":1}\n'},
            {"authority": dict(module.AUTHORITY)},
        )
    assert not (private_root / generation_id).exists()


def test_destination_collision_race_does_not_replace_existing_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_root = tmp_path / "destination-collision" / "private"
    generation_id = "c" * 24
    real_rename = module.rename_noreplace

    def create_collision(
        parent_fd: int, source_name: str, destination_name: str
    ) -> None:
        destination = private_root / destination_name
        destination.mkdir()
        (destination / "race-owner").write_text("unchanged", encoding="utf-8")
        real_rename(parent_fd, source_name, destination_name)

    monkeypatch.setattr(module, "rename_noreplace", create_collision)
    with pytest.raises(OSError) as collision:
        module.publish_generation(
            private_root,
            generation_id,
            {"manifest.jsonl": b'{"row":1}\n'},
            {"authority": dict(module.AUTHORITY)},
        )
    assert collision.value.errno == module.errno.EEXIST
    assert (private_root / generation_id / "race-owner").read_text(encoding="utf-8") == "unchanged"
    assert any(entry.name.startswith(".pending-") for entry in private_root.iterdir())


def test_post_rename_inode_and_same_name_same_size_artifact_substitution_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    inode_root = tmp_path / "destination-substitution" / "private"
    inode_generation = "d" * 24
    real_rename = module.rename_noreplace

    def substitute_destination(
        parent_fd: int, source_name: str, destination_name: str
    ) -> None:
        real_rename(parent_fd, source_name, destination_name)
        destination = inode_root / destination_name
        destination.rename(inode_root / f"{destination_name}.original")
        destination.mkdir()

    monkeypatch.setattr(module, "rename_noreplace", substitute_destination)
    with pytest.raises(
        module.Stage12688Error,
        match="published_generation_inode_mismatch",
    ):
        module.publish_generation(
            inode_root,
            inode_generation,
            {"manifest.jsonl": b'{"row":1}\n'},
            {"authority": dict(module.AUTHORITY)},
        )

    summary_root = tmp_path / "summary-substitution" / "private"
    summary_generation = "e" * 24

    replacement_sizes: list[tuple[int, int]] = []

    def replace_summary_same_size(
        parent_fd: int, source_name: str, destination_name: str
    ) -> None:
        real_rename(parent_fd, source_name, destination_name)
        destination = summary_root / destination_name
        destination.chmod(0o700)
        summary_path = destination / "summary.json"
        original = summary_path.read_bytes()
        summary_path.rename(destination / "summary.original")
        summary_path.write_bytes(original)
        replacement_sizes.append((len(original), summary_path.stat().st_size))

    monkeypatch.setattr(module, "rename_noreplace", replace_summary_same_size)
    with pytest.raises(
        module.Stage12688Error,
        match="published_generation_artifact_identity_mismatch:summary.json",
    ):
        module.publish_generation(
            summary_root,
            summary_generation,
            {"manifest.jsonl": b'{"row":1}\n'},
            {"authority": dict(module.AUTHORITY)},
        )
    assert replacement_sizes and replacement_sizes[0][0] == replacement_sizes[0][1]


def synthetic_grouping_snapshot(
    module,
    key: str,
    objects: tuple[tuple[str, str, int | None], ...],
    *,
    placements: tuple[tuple[tuple[str, str, int | None], str, str], ...] = (),
    lineage: tuple[str, ...] = (),
    capacity: int = 10,
):
    return module.RepoSnapshot(
        local_path=Path(f"/synthetic/{key}"),
        repo_key=module.stable(["synthetic", key]),
        origin_url="",
        revision=(module.stable(["revision", key])[:40]),
        tree_oid=(module.stable(["tree", key])[:40]),
        blobs=[],
        component_objects=tuple(sorted(objects)),
        lineage_keys=lineage,
        supported_placements=tuple(sorted(placements)),
        estimated_row_capacity=capacity,
    )


def test_common_license_empty_and_submodule_objects_do_not_union() -> None:
    module = load_module()
    license_object = ("blob", "1" * 40, 1_024)
    empty_object = ("blob", "2" * 40, 0)
    submodule_object = ("commit", "3" * 40, None)
    snapshots = []
    for index in range(10):
        unique = ("blob", f"{index + 100:040x}", 4_096)
        snapshots.append(synthetic_grouping_snapshot(
            module,
            f"common-{index}",
            (license_object, empty_object, submodule_object, unique),
        ))
    report = module.assign_components(snapshots)
    assert len({snapshot.component_key for snapshot in snapshots}) == 10
    assert report["object_df_common_threshold"] == 8
    assert report["nonseeding_common_object_count"] >= 3
    assert report["nonseeding_empty_or_submodule_object_count"] >= 2
    assert report["fork_union_count"] == 0


def test_rerooted_superset_passes_practical_fork_contract() -> None:
    module = load_module()
    shared = tuple(
        ("blob", f"{index + 1:040x}", 4_096)
        for index in range(module.MIN_SHARED_SEEDING_OBJECTS)
    )
    extras = (
        ("blob", "a" * 40, 4_096),
        ("blob", "b" * 40, 4_096),
    )
    placements = tuple(
        (identity, f"src/module_{index}.py", "code")
        for index, identity in enumerate(shared)
    )
    left = synthetic_grouping_snapshot(
        module, "reroot-left", shared, placements=placements
    )
    right = synthetic_grouping_snapshot(
        module, "reroot-superset", shared + extras, placements=placements
    )
    report = module.assign_components([left, right])
    assert left.component_key == right.component_key
    assert left.split == right.split
    assert report["candidate_pair_count"] == 1
    assert report["fork_union_count"] == 1
    assert report["thresholds"]["minimum_shared_seeding_objects"] == 8
    assert report["thresholds"]["minimum_shared_seeding_bytes"] == 32 * 1024


def test_grouping_and_capacity_assignment_are_permutation_stable() -> None:
    module = load_module()

    def make_snapshots():
        shared = tuple(
            ("blob", f"{index + 20:040x}", 4_096)
            for index in range(module.MIN_SHARED_SEEDING_OBJECTS)
        )
        placements = tuple(
            (identity, f"tests/test_{index}.py", "test")
            for index, identity in enumerate(shared)
        )
        return [
            synthetic_grouping_snapshot(module, "stable-a", shared, placements=placements, capacity=20),
            synthetic_grouping_snapshot(module, "stable-b", shared, placements=placements, capacity=20),
            *[
                synthetic_grouping_snapshot(
                    module,
                    f"stable-independent-{index}",
                    (("blob", f"{index + 500:040x}", 8_192),),
                    capacity=10,
                )
                for index in range(12)
            ],
        ]

    forward = make_snapshots()
    reverse = list(reversed(make_snapshots()))
    forward_report = module.assign_components(forward, requested_rows=100)
    reverse_report = module.assign_components(reverse, requested_rows=100)
    forward_state = {
        snapshot.repo_key: (snapshot.component_key, snapshot.split)
        for snapshot in forward
    }
    reverse_state = {
        snapshot.repo_key: (snapshot.component_key, snapshot.split)
        for snapshot in reverse
    }
    assert forward_state == reverse_state
    assert forward_report["estimated_split_row_capacities"] == reverse_report["estimated_split_row_capacities"]


def test_601_repositories_with_one_common_blob_do_not_collapse() -> None:
    module = load_module()
    common = ("blob", "f" * 40, 2_048)
    snapshots = [
        synthetic_grouping_snapshot(
            module,
            f"scale-{index:03d}",
            (common, ("blob", f"{index + 10_000:040x}", 4_096)),
            capacity=1,
        )
        for index in range(601)
    ]
    report = module.assign_components(snapshots)
    assert report["object_df_common_threshold"] == 13
    assert report["maximum_seeding_posting_size"] == 1
    assert report["candidate_pair_count"] == 0
    assert report["fork_union_count"] == 0
    assert report["component_count"] == 601
    assert len({snapshot.component_key for snapshot in snapshots}) == 601


def test_whole_component_capacity_assignment_hits_exact_80_10_10_feasibility() -> None:
    module = load_module()
    snapshots = [
        synthetic_grouping_snapshot(
            module,
            f"capacity-{index:02d}",
            (("blob", f"{index + 20_000:040x}", 4_096),),
            capacity=10,
        )
        for index in range(20)
    ]
    report = module.assign_components(snapshots, requested_rows=200)
    assert report["estimated_split_row_capacities"] == {
        "eval": 20,
        "strict_eval": 20,
        "train": 160,
    }
    assert report["requested_split_row_caps"] == {
        "train": 160,
        "eval": 20,
        "strict_eval": 20,
    }
    assert report["estimated_split_cap_feasible"] is True
    assert report["component_digest_computation_count"] == report["component_count"]
    component_splits: dict[str, set[str]] = collections.defaultdict(set)
    for snapshot in snapshots:
        component_splits[snapshot.component_key].add(snapshot.split)
    assert all(len(splits) == 1 for splits in component_splits.values())


def test_exact_capacity_assignment_handles_greedy_counterexample_and_permutations() -> None:
    module = load_module()

    def run(order: tuple[int, ...]):
        capacities = (6, 2, 1, 1)
        snapshots = [
            synthetic_grouping_snapshot(
                module,
                f"exact-capacity-{index}",
                (("blob", f"{index + 40_000:040x}", 4_096),),
                capacity=capacities[index],
            )
            for index in order
        ]
        report = module.assign_components(snapshots, requested_rows=10)
        assignment = {snapshot.repo_key: snapshot.split for snapshot in snapshots}
        assigned = collections.Counter()
        for snapshot in snapshots:
            assigned[snapshot.split] += snapshot.estimated_row_capacity
        return report, assignment, dict(assigned)

    baseline_report, baseline_assignment, baseline_capacities = run((0, 1, 2, 3))
    assert baseline_report["estimated_split_cap_feasible"] is True
    assert baseline_report["allocation_method"] == "deterministic_iterative_bounded_exact"
    assert baseline_report["allocation_search_status"] == "feasible"
    assert baseline_report["allocation_search_states"] > 0
    assert baseline_report["allocation_search_exhaustive_infeasible"] is False
    assert baseline_report["allocation_search_budget_exhausted"] is False
    assert baseline_capacities == {"train": 8, "eval": 1, "strict_eval": 1}
    for order in ((3, 2, 1, 0), (1, 3, 0, 2), (2, 0, 3, 1)):
        report, assignment, capacities = run(order)
        assert assignment == baseline_assignment
        assert capacities == baseline_capacities
        assert report["allocation_method"] == "deterministic_iterative_bounded_exact"


def test_exact_capacity_assignment_matches_bounded_brute_force_oracle() -> None:
    module = load_module()
    rng = random.Random(12688)
    splits = ("train", "eval", "strict_eval")

    def oracle(capacities: tuple[int, ...], caps: dict[str, int]) -> bool:
        for choices in itertools.product(range(3), repeat=len(capacities)):
            totals = [0, 0, 0]
            for capacity, choice in zip(capacities, choices):
                totals[choice] += capacity
            if all(totals[index] >= caps[split] for index, split in enumerate(splits)):
                return True
        return False

    cases = [((6, 2, 1, 1), {"train": 8, "eval": 1, "strict_eval": 1})]
    for _ in range(120):
        capacities = tuple(rng.randint(1, 8) for _ in range(rng.randint(1, 7)))
        total = sum(capacities)
        caps = {
            "train": rng.randint(0, total + 2),
            "eval": rng.randint(0, total + 2),
            "strict_eval": rng.randint(0, total + 2),
        }
        cases.append((capacities, caps))

    for case_index, (capacities, caps) in enumerate(cases):
        components = [
            {"digest": f"{index:064x}", "capacity": capacity, "snapshots": []}
            for index, capacity in enumerate(capacities)
        ]
        result = module.exact_component_capacity_assignment(
            components, caps
        )
        expected_feasible = oracle(capacities, caps)
        assignment = result["assignment"]
        assert (result["status"] == "feasible") is expected_feasible, case_index
        assert result["status"] in {"feasible", "proven_infeasible"}
        assert result["explored_states"] > 0
        if assignment is not None:
            totals = collections.Counter()
            for component in components:
                totals[assignment[component["digest"]]] += component["capacity"]
            assert all(totals[split] >= cap for split, cap in caps.items())


def test_exact_capacity_assignment_proves_infeasible_before_reporting() -> None:
    module = load_module()
    snapshots = [
        synthetic_grouping_snapshot(
            module,
            f"infeasible-{index}",
            (("blob", f"{index + 50_000:040x}", 4_096),),
            capacity=capacity,
        )
        for index, capacity in enumerate((7, 3))
    ]
    report = module.assign_components(snapshots, requested_rows=10)
    assert report["estimated_split_cap_feasible"] is False
    assert report["allocation_method"] == "deterministic_exact_memoized_exhaustive_infeasible"
    assert report["allocation_search_status"] == "proven_infeasible"
    assert report["allocation_search_states"] > 0
    assert report["allocation_search_exhaustive_infeasible"] is True
    assert report["allocation_search_budget_exhausted"] is False


@pytest.mark.parametrize("component_count", [479, 800, 1000])
def test_iterative_exact_allocator_handles_adversarial_component_counts(
    component_count: int,
) -> None:
    module = load_module()
    components = [
        {
            "digest": hashlib.sha256(f"large-{index}".encode()).hexdigest(),
            "capacity": (index * 37) % 11 + 1,
            "snapshots": [],
        }
        for index in range(component_count)
    ]
    total_capacity = sum(component["capacity"] for component in components)
    caps = {
        "train": total_capacity * 8 // 10,
        "eval": total_capacity // 10,
        "strict_eval": total_capacity - total_capacity * 8 // 10 - total_capacity // 10,
    }
    result = module.exact_component_capacity_assignment(components, caps)
    assert result["status"] == "feasible"
    assert result["assignment"] is not None
    assert len(result["assignment"]) == component_count
    assert result["explored_states"] <= component_count + 1
    assert result["work_items"] <= component_count + 1


def test_iterative_exact_allocator_returns_unknown_on_forced_budget_exhaustion() -> None:
    module = load_module()
    components = [
        {"digest": f"{index:064x}", "capacity": capacity, "snapshots": []}
        for index, capacity in enumerate((6, 2, 1, 1))
    ]
    result = module.exact_component_capacity_assignment(
        components,
        {"train": 8, "eval": 1, "strict_eval": 1},
        state_budget=1,
        memory_budget=10,
        work_budget=10,
    )
    assert result["status"] == "search_budget_exhausted"
    assert result["assignment"] is None
    assert result["explored_states"] == 1


def test_assign_components_reports_budget_exhaustion_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()

    def exhausted(*_args, **_kwargs):
        return {
            "status": "search_budget_exhausted",
            "assignment": None,
            "explored_states": 7,
            "memoized_dead_states": 3,
            "work_items": 11,
            "state_budget": 7,
            "memory_budget": 7,
            "work_budget": 11,
        }

    monkeypatch.setattr(module, "exact_component_capacity_assignment", exhausted)
    snapshots = [
        synthetic_grouping_snapshot(
            module,
            f"budget-{index}",
            (("blob", f"{index + 60_000:040x}", 4_096),),
            capacity=1,
        )
        for index in range(10)
    ]
    report = module.assign_components(snapshots, requested_rows=10)
    assert report["estimated_split_cap_feasible"] is False
    assert report["allocation_search_status"] == "search_budget_exhausted"
    assert report["allocation_search_exhaustive_infeasible"] is False
    assert report["allocation_search_budget_exhausted"] is True
    assert report["allocation_search_states"] == 7
    assert report["allocation_search_memoized_states"] == 3
    assert report["allocation_search_work_items"] == 11



def test_actual_candidate_capacity_infeasible_fails_closed() -> None:
    module = load_module()
    snapshots = [
        synthetic_grouping_snapshot(
            module, f"actual-infeasible-{index}",
            (("blob", f"{index + 70_000:040x}", 4_096),),
        )
        for index in range(3)
    ]
    for index, item in enumerate(snapshots):
        item.component_key = module.stable(["actual-component", index])
    inventory = [
        module.InventoryCandidate(item, {}, {}, (item.component_key, offset))
        for item, count in zip(snapshots, (5, 1, 1), strict=True)
        for offset in range(count)
    ]
    with pytest.raises(
        module.Stage12688Error, match="actual_component_split_capacity_infeasible",
    ):
        module.assign_actual_candidate_capacities(
            snapshots, inventory, {}, {"train": 8, "eval": 1, "strict_eval": 1},
        )


def test_actual_candidate_assignment_is_permutation_stable() -> None:
    module = load_module()

    def run(reverse: bool):
        capacities = (6, 2, 1, 1)
        snapshots = [
            synthetic_grouping_snapshot(
                module, f"actual-stable-{index}",
                (("blob", f"{index + 71_000:040x}", 4_096),),
            )
            for index in range(len(capacities))
        ]
        for index, item in enumerate(snapshots):
            item.component_key = module.stable(["actual-stable-component", index])
        inventory = [
            module.InventoryCandidate(item, {}, {}, (item.component_key, offset))
            for item, count in zip(snapshots, capacities, strict=True)
            for offset in range(count)
        ]
        if reverse:
            snapshots.reverse()
            inventory.reverse()
        contract = {}
        module.assign_actual_candidate_capacities(
            snapshots, inventory, contract,
            {"train": 8, "eval": 1, "strict_eval": 1},
        )
        return (
            {item.repo_key: item.split for item in snapshots},
            contract["estimated_split_row_capacities"],
        )

    assert run(False) == run(True)


def test_candidate_inventory_applies_per_repository_cap_before_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    blob = module.Blob("7" * 40, 1, "src/capped.py")
    item = snapshot(module, blobs=[blob])
    item.component_key = module.stable(["capped-component"])
    monkeypatch.setattr(module, "cat_blobs", lambda _repo, _blobs: {blob.path: b"x"})
    monkeypatch.setattr(module, "content_rejection_reason", lambda _data: None)
    monkeypatch.setattr(module, "build_directory_entry_row", lambda *_args: None)
    monkeypatch.setattr(
        module, "candidate_spans",
        lambda *_args: [(index, index + 1) for index in range(241)],
    )

    def build_candidate(_item, _blob, _kind, _data, span, _source_digest):
        index = span[0]
        digest = module.stable(["candidate", index])
        row = {
            "row_id": f"row-{index}",
            "objective_family": "multilingual_exact_source_span_infilling",
            "source_provenance": {"repository_relative_path": blob.path},
        }
        proof = {
            "span_start_byte": index,
            "span_end_byte": index + 1,
            "target_sha256": digest,
            "source_file_sha256": "8" * 64,
            "repository_relative_path_sha256": module.stable([blob.path]),
            "row_sha256": digest,
            "encoder_input_sha256": module.stable(["input", index]),
            "model_example_sha256": module.stable(["model", index]),
            "semantic_example_sha256": module.stable(["semantic", index]),
            "source_window_sha256": module.stable(["window", index]),
        }
        return row, proof

    monkeypatch.setattr(module, "build_span_row", build_candidate)
    counters = collections.Counter()
    inventory, *_ = module.materialize_candidate_inventory([item], counters)
    assert len(inventory) == module.MAX_ROWS_PER_REPO == 240
    assert counters["per_repository_candidate_rows_capped"] == 1


def test_budget_exhaustion_blocks_actual_capacity_assignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    snapshot_row = synthetic_grouping_snapshot(
        module,
        "blocked-build",
        (("blob", "9" * 40, 4_096),),
        capacity=10,
    )
    monkeypatch.setattr(
        module,
        "discover_repositories",
        lambda *_args, **_kwargs: ([snapshot_row], collections.Counter()),
    )

    def grouped(snapshots, requested_rows=None):
        assert requested_rows is None
        for snapshot in snapshots:
            snapshot.component_key = module.stable(["actual-capacity", snapshot.repo_key])
            snapshot.split = "train"
        return {
            "contract_version": module.FORK_GROUPING_CONTRACT_VERSION,
            "thresholds": {},
            "whole_component_assignment": True,
            "residual": "fixture",
        }

    monkeypatch.setattr(module, "assign_components", grouped)
    monkeypatch.setattr(
        module,
        "exact_component_capacity_assignment",
        lambda *_args, **_kwargs: {
            "status": "search_budget_exhausted",
            "assignment": None,
            "explored_states": 7,
            "memoized_dead_states": 3,
            "work_items": 11,
        },
    )
    output_dir = tmp_path / "output"
    summary_path = tmp_path / "summary.json"
    with pytest.raises(
        module.Stage12688Error,
        match="component_split_allocation_search_budget_exhausted",
    ):
        module.build(
            source_root,
            output_dir,
            summary_path,
            max_repos=1,
            max_rows=10,
        )
    assert not output_dir.exists()
    assert not summary_path.exists()


def test_directory_context_bound_exact_heap_spans_and_digest_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    entries = tuple(
        module.TreeEntry(
            "100644", "blob", f"{index + 30_000:040x}", 100,
            f"very_long_repository_name_{index:03d}_" + "x" * 40 + ".py",
        )
        for index in range(80)
    )
    target = module.Blob(entries[0].oid, 100, "src/" + entries[0].path)
    snap = snapshot(module, blobs=[target])
    snap.directory_inventories = {
        "src": module.DirectoryInventory("src", "4" * 40, entries)
    }
    assert module.build_directory_entry_row(snap, target) is None

    data = b"".join(f"unique_line_{index} = {index}\n".encode("ascii") for index in range(12))
    spans = []
    cursor = 0
    for line in data.splitlines(keepends=True):
        spans.append((cursor, cursor + len(line)))
        cursor += len(line)
    expected = sorted(
        spans,
        key=lambda span: (
            module.stable(["repo", "src/many.py", span[0], span[1]]),
            span,
        ),
    )[: module.MAX_ROWS_PER_FILE]
    assert module.candidate_spans(data, "repo", "src/many.py") == expected

    digest_calls = 0
    real_sha256 = module.sha256_bytes
    def counting_sha256(payload: bytes) -> str:
        nonlocal digest_calls
        digest_calls += 1
        return real_sha256(payload)
    monkeypatch.setattr(module, "sha256_bytes", counting_sha256)
    cache: dict[str, str] = {}
    first = module.cached_blob_sha256(cache, "shared-oid", data)
    second = module.cached_blob_sha256(cache, "shared-oid", data)
    assert first == second
    assert digest_calls == 1
