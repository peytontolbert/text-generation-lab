from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12690_source_backed_symbol_api_test_links.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12690", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def create_repo(source_root: Path, index: int, *, ambiguous: bool = False) -> Path:
    repo = source_root / f"repo-{index:03d}"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "remote", "add", "origin", f"https://example.com/relation-{index:03d}.git")
    (repo / "src/pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src/pkg/__init__.py").write_text(f"PACKAGE_{index} = 'fixture-{index}'\n", encoding="utf-8")
    (repo / "src/pkg/core.py").write_text(
        f"# café repository {index}\nREPOSITORY_INDEX_{index} = {index}\n\n"
        f"def alpha(value: int) -> int:\n    return value + {index * 10 + 1}\n\n"
        f"def beta(value: int) -> int:\n    return value + {index * 10 + 2}\n\n"
        f"def gamma(value: int) -> int:\n    return value + {index * 10 + 3}\n\n"
        f"def delta(value: int) -> int:\n    return value + {index * 10 + 4}\n",
        encoding="utf-8",
    )
    for number, symbol in enumerate(("alpha", "beta", "gamma", "delta")):
        (repo / f"tests/test_{symbol}.py").write_text(
            f"# café repository fixture {index}\nfrom pkg.core import {symbol}\n\n"
            f"def test_{symbol}():\n"
            f"    observed = {symbol}({index * 10 + number})\n"
            f"    assert observed == {number + number + 1}\n",
            encoding="utf-8",
        )
    (repo / "tests/test_rejections.py").write_text(
        f"# repository fixture {index}\n"
        "from pkg.core import *\n"
        "from ..escape import alpha\n",
        encoding="utf-8",
    )
    if ambiguous:
        (repo / "pkg").mkdir()
        (repo / "pkg/core.py").write_text(
            "def alpha(value: int) -> int:\n    return value - 1\n",
            encoding="utf-8",
        )
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "source-backed relation fixture")
    return repo


def parsed_fixture(module, repo: Path):
    revision = git(repo, "rev-parse", "HEAD")
    origin = git(repo, "config", "--get", "remote.origin.url")
    all_entries = module.parse_ls_tree(module.stage12687.git(repo, "ls-tree", "-r", "-l", "-z", revision))
    entries = [entry for entry in all_entries if module.path_allowed(entry)]
    snapshot = module.Snapshot(
        local_path=repo,
        repo_key=module.stable([origin, revision]),
        origin_url=origin,
        revision=revision,
        blobs=entries,
        component_blobs=tuple(sorted((entry.oid, entry.size) for entry in entries)),
        lineage_keys=(f"root:{revision}",),
        module_path_index=module.repository_module_path_index(all_entries),
        component_key="c" * 64,
        split="train",
    )
    parsed, counters = module.parse_snapshot(snapshot)
    return snapshot, parsed, counters


def test_filters_module_mapping_and_tree_parser_fail_closed() -> None:
    module = load_module()
    raw = b"100644 blob " + b"a" * 40 + b" 123\tsrc/pkg/core.py\0"
    assert module.parse_ls_tree(raw) == [module.GitBlob("100644", "a" * 40, 123, "src/pkg/core.py")]
    assert module.module_names_for_path("src/pkg/core.py") == ("src.pkg.core", "pkg.core")
    assert module.module_names_for_path("src/pkg/__init__.py") == ("src.pkg", "pkg")
    assert module.path_allowed(module.GitBlob("100644", "a" * 40, 10, "src/pkg/core.py"))
    assert not module.path_allowed(module.GitBlob("120000", "a" * 40, 10, "src/pkg/link.py"))
    assert not module.path_allowed(module.GitBlob("100644", "a" * 40, 10, "vendor/pkg/core.py"))
    assert not module.path_allowed(module.GitBlob("100644", "a" * 40, 10, "src/pkg/core.pyi"))
    assert not module.path_allowed(module.GitBlob("100644", "a" * 40, 10, "tests/fixtures/data.py"))
    assert module.is_test_path("tests/test_core.py")
    assert module.is_test_path("pkg/core_test.py")
    assert not module.is_test_path("src/pkg/core.py")
    with pytest.raises(module.Stage12690Error, match="malformed_ls_tree_record"):
        module.parse_ls_tree(b"broken\0")


def test_exact_ast_relations_and_ambiguous_imports_are_rejected(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 1)
    snapshot, parsed, parse_counts = parsed_fixture(module, repo)
    assert parse_counts["python_files_parsed"] == 7
    relations, counters = module.extract_relations(parsed, snapshot.module_path_index)
    assert len(relations) == 4
    assert counters["star_import_rejected"] == 1
    assert counters["relative_or_empty_import_rejected"] == 1
    assert {relation.imported_symbol for relation in relations} == {"alpha", "beta", "gamma", "delta"}
    for relation in relations:
        assert relation.source.path == "src/pkg/core.py"
        assert relation.test_path == f"tests/test_{relation.imported_symbol}.py"
        assert relation.test_evidence
        assert relation.source.evidence
        assert relation.source.evidence.startswith("def ")
        assert "<MASKED_IMPORT_ALIAS>" in relation.test_evidence
        assert "<MASKED_CALL_NAME>" in relation.test_evidence
        assert relation.imported_symbol not in relation.test_evidence
        assert relation.local_name not in relation.test_evidence
        assert relation.call_span_end_byte > relation.call_span_start_byte

    ambiguous_repo = create_repo(source_root, 2, ambiguous=True)
    ambiguous_snapshot, ambiguous_parsed, _counts = parsed_fixture(module, ambiguous_repo)
    ambiguous_relations, ambiguous_counts = module.extract_relations(ambiguous_parsed, ambiguous_snapshot.module_path_index)
    assert ambiguous_relations == []
    assert ambiguous_counts["ambiguous_or_missing_syntactic_module_rejected"] == 4


def test_rows_have_real_candidates_balanced_positions_and_target_independence(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 3)
    snapshot, parsed, _ = parsed_fixture(module, repo)
    relations, _ = module.extract_relations(parsed, snapshot.module_path_index)
    definitions = [
        definition for parsed_file in parsed if not parsed_file.is_test
        for definition in module.top_level_definitions(parsed_file)
    ]
    rows, proofs, counters = module.build_relation_rows(snapshot, relations, definitions)
    assert counters["symbol_reference_rows"] == 4
    assert counters["test_association_rows"] == 4
    assert len(rows) == len(proofs) == 8
    assert {row["objective_family"] for row in rows} == {
        "python_symbol_reference_prediction", "python_test_file_association"
    }
    for row, proof in zip(rows, proofs, strict=True):
        assert row["target"]["decoder_text"] == f"candidate_{proof['correct_candidate_position']}"
        assert row["input_text"].count("<candidate_") == proof["candidate_count"]
        assert len(set(proof["candidate_evidence_sha256s"])) == proof["candidate_count"]
        assert all(value is False for value in row["authority"].values())
        assert row["source_provenance"]["revision"] == snapshot.revision
        assert row["source_provenance"]["test_git_blob_oid"]
        assert row["source_provenance"]["source_git_blob_oid"]
        before = row["input_text"]
        mutated = json.loads(json.dumps(row))
        mutated["target"]["decoder_text"] = "candidate_mutated"
        assert mutated["input_text"] == before

    positions = {
        module.deterministic_candidates(
            "correct", ["n1", "n2", "n3"], identity=lambda value: value,
            seed=["balance", index],
        )[1]
        for index in range(256)
    }
    assert positions == {0, 1, 2, 3}


def test_full_build_securely_excludes_strict_plaintext(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    split_repo_counts = {"train": 0, "eval": 0, "strict_eval": 0}
    for index in range(120):
        repo = create_repo(source_root, index)
        revision = git(repo, "rev-parse", "HEAD")
        origin = git(repo, "config", "--get", "remote.origin.url")
        repo_key = module.stable([origin, revision])
        component = module.stable([repo_key])
        bucket = int(component[:8], 16) % 20
        split = "train" if bucket < 16 else "eval" if bucket < 18 else "strict_eval"
        split_repo_counts[split] += 1
        if (
            split_repo_counts["train"] >= 4
            and split_repo_counts["eval"] >= 1
            and split_repo_counts["strict_eval"] >= 1
        ):
            break
    assert split_repo_counts["train"] >= 4
    assert split_repo_counts["eval"] >= 1
    assert split_repo_counts["strict_eval"] >= 1

    output = tmp_path / "artifact"
    summary_path = tmp_path / "summary.json"
    summary = module.build(source_root, output, summary_path, max_repos=120, max_rows=40)
    assert summary["row_count"] == 40
    assert summary["split_counts"] == {"train": 32, "eval": 4, "strict_eval": 4}
    assert summary["objective_counts"]["python_symbol_reference_prediction"] > 0
    assert summary["objective_counts"]["python_test_file_association"] > 0
    assert summary["strict_eval_plaintext_materialized"] is False
    assert summary["training_eligible_rows"] == 0
    assert all(value is False for value in summary["authority"].values())
    generation = output / summary["generation_relative_path"]
    assert not any("strict" in path.name for path in generation.iterdir())
    manifest_path = generation / "symbol_test_train_eval_manifest.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text().splitlines()]
    assert rows and all(row["split"] != "strict_eval" for row in rows)
    authoritative_summary = output / summary["authoritative_summary_relative_path"]
    assert authoritative_summary.read_bytes() == summary_path.read_bytes()
    assert authoritative_summary.stat().st_mode & 0o777 == 0o400
    assert summary_path.read_bytes() == (output / "summary.json").read_bytes()
    for key in (
        "cross_split_repository_overlap",
        "cross_split_component_overlap",
        "cross_split_source_file_digest_overlap",
        "cross_split_test_file_digest_overlap",
        "cross_split_model_input_overlap",
        "cross_split_candidate_evidence_overlap",
    ):
        assert isinstance(summary[key], int)
    assert summary["cross_split_repository_overlap"] == 0
    assert summary["cross_split_component_overlap"] == 0
    assert generation.stat().st_mode & 0o777 == 0o500
    for contract in summary["artifact_contract"].values():
        path = output / contract["relative_path"]
        assert module.stage12687.file_sha256(path) == contract["sha256"]
        assert path.stat().st_mode & 0o777 == 0o400

    with pytest.raises(module.Stage12690Error, match="immutable_generation_exists"):
        module.build(source_root, output, summary_path, max_repos=120, max_rows=40)


def test_scope_aware_binding_exact_masks_and_full_inventory(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 70)
    (repo / "tests/test_scope.py").write_text(
        "from pkg.core import alpha as module_alpha\n\n"
        "def nested():\n"
        "    return module_alpha(1)\n\n"
        "def shadowed(module_alpha):\n"
        "    return module_alpha(2)\n\n"
        "def local():\n"
        "    from pkg.core import beta as local_beta\n"
        "    return local_beta(3)\n\n"
        "def outer():\n"
        "    from pkg.core import gamma as outer_gamma\n"
        "    def inner():\n"
        "        return outer_gamma(4)\n"
        "    return inner\n",
        encoding="utf-8",
    )
    (repo / "tests/test_module_rebind.py").write_text(
        "from pkg.core import delta as module_delta\n"
        "module_delta = lambda value: value\n"
        "def call_rebound():\n"
        "    return module_delta(5)\n",
        encoding="utf-8",
    )
    git(repo, "add", "tests/test_scope.py", "tests/test_module_rebind.py")
    git(repo, "commit", "-q", "-m", "scope adversary")
    snapshot, parsed, _ = parsed_fixture(module, repo)
    relations, counters = module.extract_relations(parsed, snapshot.module_path_index)
    scoped = [relation for relation in relations if relation.test_path == "tests/test_scope.py"]
    assert {(relation.imported_symbol, relation.import_scope_kind, relation.call_scope_kind) for relation in scoped} == {
        ("alpha", "module", "function"),
        ("beta", "function", "function"),
    }
    assert all(relation.imported_symbol not in relation.test_evidence for relation in scoped)
    assert all(relation.local_name not in relation.test_evidence for relation in scoped)
    assert counters["unbound_ambiguous_or_rebound_call_rejected"] >= 2

    full_inventory = dict(snapshot.module_path_index)
    full_inventory["pkg.core"] = ("src/pkg/core.py", "unparsed/pkg/core.py")
    rejected, rejected_counts = module.extract_relations(parsed, full_inventory)
    assert rejected == []
    assert rejected_counts["ambiguous_or_missing_syntactic_module_rejected"] >= 1


def test_same_definition_negatives_are_excluded_and_renderer_is_allowlisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 71)
    (repo / "tests/test_alpha_alias.py").write_text(
        "from pkg.core import alpha as selected\n\n"
        "def check_alias():\n"
        "    return selected(9)\n",
        encoding="utf-8",
    )
    git(repo, "add", "tests/test_alpha_alias.py")
    git(repo, "commit", "-q", "-m", "same definition adversary")
    snapshot, parsed, _ = parsed_fixture(module, repo)
    relations, _ = module.extract_relations(parsed, snapshot.module_path_index)
    definitions = [
        definition for parsed_file in parsed if not parsed_file.is_test
        for definition in module.top_level_definitions(parsed_file)
    ]
    rows, proofs, counters = module.build_relation_rows(snapshot, relations, definitions)
    assert counters["test_association_rows"] >= 5
    for proof in proofs:
        if proof["objective_family"] != "python_test_file_association":
            continue
        assert proof["candidate_source_definition_keys"].count(
            proof["correct_source_definition_key"]
        ) == 1

    types = __import__("types")
    fake_torch = types.ModuleType("torch")
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    training_path = ROOT / "legacy_src/agentkernel_lite/training_data.py"
    spec = importlib.util.spec_from_file_location("stage12690_training_data", training_path)
    assert spec and spec.loader
    training_data = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = training_data
    spec.loader.exec_module(training_data)

    row = rows[0]
    baseline = training_data._row_text(row)
    mutated = json.loads(json.dumps(row))
    mutated["row_id"] = "target-derived-id"
    mutated["target"]["decoder_text"] = "candidate_mutated"
    mutated["source_provenance"] = {
        "revision": "target-derived-revision",
        "correct_candidate_position": 999,
        "target_sha256": "target-derived-hash",
    }
    mutated["authority"] = {"training_admitted": True}
    assert training_data._row_text(mutated) == baseline
    assert training_data._foundational_row_text(mutated) == training_data._foundational_row_text(row)


def test_overlap_counter_and_publication_race_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    rename_parent = tmp_path / "rename-parent"
    rename_parent.mkdir()
    (rename_parent / "pending").mkdir()
    (rename_parent / "pending" / "new-owner").write_text("new", encoding="utf-8")
    (rename_parent / "generation").mkdir()
    (rename_parent / "generation" / "old-owner").write_text("old", encoding="utf-8")
    parent_fd = module.stage12687.open_directory_nofollow(rename_parent)
    try:
        with pytest.raises(OSError) as collision:
            module.rename_noreplace(parent_fd, "pending", "generation")
        assert collision.value.errno == module.errno.EEXIST
    finally:
        module.os.close(parent_fd)
    assert (rename_parent / "pending" / "new-owner").read_text(encoding="utf-8") == "new"
    assert (rename_parent / "generation" / "old-owner").read_text(encoding="utf-8") == "old"

    assert module.cross_split_overlap_count(
        [
            {"split": "train", "values": ["shared", "train-only"]},
            {"split": "eval", "values": ["shared", "eval-only"]},
            {"split": "strict_eval", "values": ["strict-only"]},
        ],
        lambda record: record["values"],
    ) == 1

    row = {
        "split": "train",
        "objective_family": "python_symbol_reference_prediction",
        "source_provenance": {
            "source_file_sha256": "a" * 64,
            "test_file_sha256": "b" * 64,
        },
    }
    proof = {
        "split": "train",
        "row_sha256": "c" * 64,
        "objective_family": "python_symbol_reference_prediction",
        "correct_candidate_position": 0,
        "repository_key_sha256": "d" * 64,
        "content_component_sha256": "e" * 64,
        "model_input_sha256": "f" * 64,
        "candidate_evidence_sha256s": ["1" * 64, "2" * 64, "3" * 64],
    }
    catalog = [{
        "split": "train",
        "repository_key_sha256": "d" * 64,
    }]
    output = tmp_path / "race-artifact"
    summary_path = tmp_path / "race-summary.json"

    def racing_rename(parent_fd: int, source_name: str, destination_name: str) -> None:
        destination = output / "private" / destination_name
        destination.mkdir()
        (destination / "race-owner").write_text("untouched", encoding="utf-8")
        raise FileExistsError(module.errno.EEXIST, "simulated publication race", destination_name)

    monkeypatch.setattr(module, "rename_noreplace", racing_rename)
    with pytest.raises(FileExistsError):
        module.publish(output, summary_path, [row], [proof], catalog, {})
    generation_dirs = [
        path for path in (output / "private").iterdir()
        if not path.name.startswith(".pending-")
    ]
    assert len(generation_dirs) == 1
    assert (generation_dirs[0] / "race-owner").read_text(encoding="utf-8") == "untouched"
    assert not summary_path.exists()
    assert not (output / "summary.json").exists()


def synthetic_publication_records(module, splits: tuple[str, ...] = ("train",)):
    rows = []
    proofs = []
    catalog = []
    for index, split in enumerate(splits):
        rows.append({
            "split": split,
            "objective_family": "python_symbol_reference_prediction",
            "source_provenance": {
                "source_file_sha256": f"{index + 1:064x}",
                "test_file_sha256": f"{index + 101:064x}",
            },
        })
        proofs.append({
            "split": split,
            "row_sha256": f"{index + 201:064x}",
            "objective_family": "python_symbol_reference_prediction",
            "correct_candidate_position": index % 3,
            "repository_key_sha256": f"{index + 301:064x}",
            "content_component_sha256": f"{index + 401:064x}",
            "model_input_sha256": f"{index + 501:064x}",
            "candidate_evidence_sha256s": [
                f"{index * 10 + offset + 601:064x}" for offset in range(3)
            ],
        })
        catalog.append({
            "split": split,
            "repository_key_sha256": f"{index + 301:064x}",
        })
    return rows, proofs, catalog



def publication_generation_id_for_records(module, rows, proofs, catalog):
    train_eval_rows = [row for row in rows if row["split"] != "strict_eval"]
    train_eval_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    train_eval_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    encoded_values = {
        "symbol_test_train_eval_manifest.jsonl": module.jsonl_bytes(train_eval_rows),
        "train_eval_source_provenance_ledger.jsonl": module.jsonl_bytes(train_eval_proofs),
        "train_eval_source_catalog.jsonl": module.jsonl_bytes(train_eval_catalog),
    }
    strict_commitment = module.stable(sorted(
        proof["row_sha256"] for proof in proofs
        if proof["split"] == "strict_eval"
    ))
    return module.publication_generation_id(
        artifact_schema_version=module.ARTIFACT_SCHEMA_VERSION,
        strict_eval_commitment_sha256=strict_commitment,
        artifact_sha256s={
            name: module.sha256_bytes(value) for name, value in encoded_values.items()
        },
    )

def test_complete_tree_module_ambiguity_includes_oversized_excluded_blob(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 72)
    conflict = repo / "vendor/src/pkg/core.py"
    conflict.parent.mkdir(parents=True)
    conflict.write_text(
        "def alpha(value):\n    return value\n#" + "x" * module.MAX_FILE_BYTES,
        encoding="utf-8",
    )
    git(repo, "add", "vendor/src/pkg/core.py")
    git(repo, "commit", "-q", "-m", "oversized excluded module conflict")

    snapshots, counters = module.discover_repositories(source_root, 1)
    assert counters["repositories_accepted"] == 1
    snapshot = snapshots[0]
    assert conflict.relative_to(repo).as_posix() not in {blob.path for blob in snapshot.blobs}
    assert snapshot.module_path_index["pkg.core"] == (
        "src/pkg/core.py",
        "vendor/src/pkg/core.py",
    )
    parsed, _ = module.parse_snapshot(snapshot)
    relations, relation_counts = module.extract_relations(parsed, snapshot.module_path_index)
    assert relations == []
    assert relation_counts["ambiguous_or_missing_syntactic_module_rejected"] == 4


def test_pending_collision_symlink_and_private_inode_swap_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_publication_records(module)
    generation_id = publication_generation_id_for_records(module, rows, proofs, catalog)
    pending_name = f".pending-{generation_id}-{module.os.getpid()}"

    collision_output = tmp_path / "pending-collision"
    collision_private = collision_output / "private"
    collision_private.mkdir(parents=True)
    (collision_private / pending_name).mkdir()
    with pytest.raises(FileExistsError):
        module.publish(
            collision_output,
            tmp_path / "collision-summary.json",
            rows,
            proofs,
            catalog,
            {},
        )
    assert not (collision_private / generation_id).exists()

    symlink_output = tmp_path / "pending-symlink"
    symlink_private = symlink_output / "private"
    symlink_private.mkdir(parents=True)
    victim = tmp_path / "pending-victim"
    victim.mkdir()
    (victim / "owner").write_text("untouched", encoding="utf-8")
    (symlink_private / pending_name).symlink_to(victim, target_is_directory=True)
    with pytest.raises(FileExistsError):
        module.publish(
            symlink_output,
            tmp_path / "symlink-summary.json",
            rows,
            proofs,
            catalog,
            {},
        )
    assert (victim / "owner").read_text(encoding="utf-8") == "untouched"
    assert list(victim.iterdir()) == [victim / "owner"]

    swap_output = tmp_path / "private-swap"
    real_write = module.write_file_at
    writes = 0

    def swap_parent_after_first_write(
        directory_fd: int,
        name: str,
        data: bytes,
        *,
        mode: int,
    ):
        nonlocal writes
        identity = real_write(directory_fd, name, data, mode=mode)
        writes += 1
        if writes == 1:
            (swap_output / "private").rename(swap_output / "private-original")
            (swap_output / "private").mkdir()
        return identity

    with monkeypatch.context() as scoped:
        scoped.setattr(module, "write_file_at", swap_parent_after_first_write)
        with pytest.raises(module.Stage12690Error, match="private_root_inode_changed"):
            module.publish(
                swap_output,
                tmp_path / "swap-summary.json",
                rows,
                proofs,
                catalog,
                {},
            )
    assert not (swap_output / "private" / generation_id).exists()
    assert any(
        path.name.startswith(".pending-")
        for path in (swap_output / "private-original").iterdir()
    )
    assert not (tmp_path / "swap-summary.json").exists()


def test_nonzero_final_overlap_fails_before_generation_write(tmp_path: Path) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_publication_records(module, ("train", "eval"))
    proofs[1]["candidate_evidence_sha256s"][0] = proofs[0]["candidate_evidence_sha256s"][0]
    output = tmp_path / "overlap-output"
    with pytest.raises(
        module.Stage12690Error,
        match="^cross_split_overlap_nonzero$",
    ):
        module.publish(
            output,
            tmp_path / "overlap-summary.json",
            rows,
            proofs,
            catalog,
            {},
        )
    assert not output.exists()
    assert not (tmp_path / "overlap-summary.json").exists()


def test_exception_and_structural_pattern_bindings_shadow_imports(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 73)
    binding_test = repo / "tests/test_binding_forms.py"
    binding_test.write_text(
        "from pkg.core import alpha as except_bound\n"
        "from pkg.core import beta as nested_bound\n"
        "from pkg.core import gamma as star_bound\n"
        "from pkg.core import delta as rest_bound\n\n"
        "def exception_case():\n"
        "    try:\n"
        "        raise ValueError('x')\n"
        "    except ValueError as except_bound:\n"
        "        pass\n"
        "    return except_bound(1)\n\n"
        "def nested_pattern_case(value):\n"
        "    match value:\n"
        "        case {'payload': [nested_bound]}:\n"
        "            pass\n"
        "    return nested_bound(2)\n\n"
        "def star_pattern_case(value):\n"
        "    match value:\n"
        "        case [*star_bound]:\n"
        "            pass\n"
        "    return star_bound(3)\n\n"
        "def mapping_rest_case(value):\n"
        "    match value:\n"
        "        case {'known': _, **rest_bound}:\n"
        "            pass\n"
        "    return rest_bound(4)\n",
        encoding="utf-8",
    )
    git(repo, "add", "tests/test_binding_forms.py")
    git(repo, "commit", "-q", "-m", "lexical binding adversaries")
    snapshot, parsed, _ = parsed_fixture(module, repo)
    parsed_binding_test = next(
        value for value in parsed if value.blob.path == "tests/test_binding_forms.py"
    )
    analyzer = module.ScopeAnalyzer(parsed_binding_test.tree)
    collected_bindings = set().union(
        *(record.bindings for record in analyzer.records.values())
    )
    assert {
        "except_bound",
        "nested_bound",
        "star_bound",
        "rest_bound",
    }.issubset(collected_bindings)

    relations, counters = module.extract_relations(parsed, snapshot.module_path_index)
    assert [
        relation for relation in relations
        if relation.test_path == "tests/test_binding_forms.py"
    ] == []
    assert counters["unbound_ambiguous_or_rebound_call_rejected"] >= 4


def test_pending_and_published_generation_substitution_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_publication_records(module)
    generation_id = publication_generation_id_for_records(module, rows, proofs, catalog)

    pending_output = tmp_path / "pending-substitution"
    real_revalidate = module.revalidate_private_root
    revalidations = 0

    def substitute_pending(
        private_root: Path,
        private_fd: int,
        expected,
    ) -> None:
        nonlocal revalidations
        real_revalidate(private_root, private_fd, expected)
        revalidations += 1
        if revalidations == 1:
            pending = next(
                path for path in private_root.iterdir()
                if path.name.startswith(".pending-")
            )
            pending.rename(private_root / f"{pending.name}.original")
            pending.mkdir()

    with monkeypatch.context() as scoped:
        scoped.setattr(module, "revalidate_private_root", substitute_pending)
        with pytest.raises(
            module.Stage12690Error,
            match="pending_generation_inode_mismatch",
        ):
            module.publish(
                pending_output,
                tmp_path / "pending-substitution-summary.json",
                rows,
                proofs,
                catalog,
                {},
            )
    assert not (pending_output / "private" / generation_id).exists()
    assert not (tmp_path / "pending-substitution-summary.json").exists()

    destination_output = tmp_path / "destination-substitution"
    real_rename = module.rename_noreplace

    def substitute_destination(
        parent_fd: int,
        source_name: str,
        destination_name: str,
    ) -> None:
        real_rename(parent_fd, source_name, destination_name)
        destination = destination_output / "private" / destination_name
        destination.rename(destination_output / "private" / f"{destination_name}.original")
        destination.mkdir()

    with monkeypatch.context() as scoped:
        scoped.setattr(module, "rename_noreplace", substitute_destination)
        with pytest.raises(
            module.Stage12690Error,
            match="published_generation_inode_mismatch",
        ):
            module.publish(
                destination_output,
                tmp_path / "destination-substitution-summary.json",
                rows,
                proofs,
                catalog,
                {},
            )
    assert not (tmp_path / "destination-substitution-summary.json").exists()

    artifact_output = tmp_path / "artifact-substitution"

    def substitute_required_artifact(
        parent_fd: int,
        source_name: str,
        destination_name: str,
    ) -> None:
        real_rename(parent_fd, source_name, destination_name)
        generation = artifact_output / "private" / destination_name
        generation.chmod(0o700)
        original_bytes = (generation / "summary.json").read_bytes()
        (generation / "summary.json").rename(generation / "summary.original")
        (generation / "summary.json").write_bytes(original_bytes)

    with monkeypatch.context() as scoped:
        scoped.setattr(module, "rename_noreplace", substitute_required_artifact)
        with pytest.raises(
            module.Stage12690Error,
            match="published_generation_artifact_identity_mismatch:summary.json",
        ):
            module.publish(
                artifact_output,
                tmp_path / "artifact-substitution-summary.json",
                rows,
                proofs,
                catalog,
                {},
            )
    assert not (tmp_path / "artifact-substitution-summary.json").exists()


def fake_split_snapshot(module, index: int, split: str):
    return module.Snapshot(
        local_path=Path("/unused"),
        repo_key=f"{index + 1:064x}",
        origin_url=f"https://example.com/split-{index}.git",
        revision=f"{index + 101:040x}",
        blobs=[],
        component_blobs=(),
        lineage_keys=(f"root:{index + 201:040x}",),
        module_path_index={},
        component_key=f"{index + 301:064x}",
        split=split,
    )


def install_split_selection_fakes(
    module,
    monkeypatch: pytest.MonkeyPatch,
    snapshots,
    *,
    rows_per_snapshot: int = 20,
):
    processed: list[str] = []

    monkeypatch.setattr(
        module,
        "discover_repositories",
        lambda source_root, max_repos: (snapshots[:max_repos], module.collections.Counter()),
    )
    monkeypatch.setattr(
        module,
        "parse_snapshot",
        lambda snapshot: ([], module.collections.Counter()),
    )
    monkeypatch.setattr(
        module,
        "extract_relations",
        lambda parsed, module_index: ([], module.collections.Counter()),
    )

    def fake_rows(snapshot, relations, definitions):
        processed.append(snapshot.split)
        rows = []
        proofs = []
        for row_index in range(rows_per_snapshot):
            identity = f"{snapshot.repo_key}:{row_index}"
            rows.append({
                "split": snapshot.split,
                "objective_family": "python_symbol_reference_prediction",
            })
            proofs.append({
                "split": snapshot.split,
                "model_input_sha256": module.sha256_bytes(identity.encode("ascii")),
                "candidate_evidence_sha256s": [
                    module.sha256_bytes((identity + ":evidence").encode("ascii")),
                ],
            })
        return rows, proofs, module.collections.Counter()

    monkeypatch.setattr(module, "build_relation_rows", fake_rows)
    return processed


def test_cross_component_candidate_evidence_rows_are_quarantined() -> None:
    module = load_module()
    snapshot_a = fake_split_snapshot(module, 30, "train")
    snapshot_b = fake_split_snapshot(module, 31, "eval")
    shared = "a" * 64
    same_component = "b" * 64
    safe_b = "c" * 64

    def record(snapshot, row_id, evidence):
        return (
            snapshot,
            {"row_id": row_id},
            {"row_id": row_id, "candidate_evidence_sha256s": evidence},
        )

    records = {
        snapshot_a.component_key: [
            record(snapshot_a, "a-shared", [shared]),
            record(snapshot_a, "a-local-1", [same_component]),
            record(snapshot_a, "a-local-2", [same_component]),
        ],
        snapshot_b.component_key: [
            record(snapshot_b, "b-shared", [shared]),
            record(snapshot_b, "b-safe", [safe_b]),
        ],
    }
    counters = module.collections.Counter()
    retained = module.quarantine_cross_component_candidate_evidence(records, counters)
    assert [record[1]["row_id"] for record in retained[snapshot_a.component_key]] == [
        "a-local-1",
        "a-local-2",
    ]
    assert [record[1]["row_id"] for record in retained[snapshot_b.component_key]] == [
        "b-safe",
    ]
    assert counters["cross_component_candidate_evidence_rows_quarantined"] == 2


def test_candidate_evidence_quarantine_precedes_deterministic_capacity_estimation() -> None:
    module = load_module()
    snapshots = [fake_split_snapshot(module, index, "train") for index in range(40, 44)]
    shared = "d" * 64
    records = {}
    for index, snapshot in enumerate(snapshots):
        component_records = []
        for row_index in range(4):
            evidence = shared if row_index == 0 and index < 2 else f"{index * 10 + row_index + 1:064x}"
            component_records.append((
                snapshot,
                {"row_id": f"{index}:{row_index}"},
                {"candidate_evidence_sha256s": [evidence]},
            ))
        records[snapshot.component_key] = component_records

    retained = module.quarantine_cross_component_candidate_evidence(
        records, module.collections.Counter()
    )
    reversed_retained = module.quarantine_cross_component_candidate_evidence(
        dict(reversed(list(records.items()))), module.collections.Counter()
    )
    capacities = module.estimate_component_relation_capacities(retained)
    assert capacities == module.estimate_component_relation_capacities(reversed_retained)
    assert sorted(capacities.values()) == [3, 3, 4, 4]
    allocation = module.allocate_component_splits(capacities, module.reserved_split_caps(10))
    assert allocation == module.allocate_component_splits(
        dict(reversed(list(capacities.items()))), module.reserved_split_caps(10)
    )


def test_capacity_estimator_and_allocator_balance_uneven_whole_components() -> None:
    module = load_module()
    assert module.MAX_ROWS == 13_000
    records_by_component = {
        "component-a": [(None, {}, {})] * 600,
        "component-b": [(None, {}, {})] * 250,
        "component-c": [(None, {}, {})] * 150,
        "component-d": [(None, {}, {})] * 100,
        "component-e": [(None, {}, {})] * 50,
        "empty-component": [],
    }
    capacities = module.estimate_component_relation_capacities(records_by_component)
    assert capacities == {
        "component-a": 600,
        "component-b": 250,
        "component-c": 150,
        "component-d": 100,
        "component-e": 50,
    }
    split_caps = module.reserved_split_caps(1_000)
    allocation = module.allocate_component_splits(capacities, split_caps)
    reverse_order = module.allocate_component_splits(
        dict(reversed(list(capacities.items()))), split_caps
    )
    assert allocation == reverse_order
    assert set(allocation) == set(capacities)
    assigned_capacity = module.collections.Counter()
    for component_key, split in allocation.items():
        assigned_capacity[split] += capacities[component_key]
    assert assigned_capacity["train"] >= 800
    assert assigned_capacity["eval"] >= 100
    assert assigned_capacity["strict_eval"] >= 100
    assert all(split in {"train", "eval", "strict_eval"} for split in allocation.values())


def test_split_caps_continue_past_early_train_rows_to_eval_and_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    source_root = tmp_path / "source"
    source_root.mkdir()
    snapshots = [
        fake_split_snapshot(module, 0, "train"),
        fake_split_snapshot(module, 1, "train"),
        fake_split_snapshot(module, 2, "eval"),
        fake_split_snapshot(module, 3, "strict_eval"),
    ]
    processed = install_split_selection_fakes(module, monkeypatch, snapshots)
    captured = {}

    def capture_publish(output_dir, summary_path, rows, proofs, catalog, counters):
        captured["counts"] = dict(module.collections.Counter(row["split"] for row in rows))
        captured["row_count"] = len(rows)
        return {"split_counts": captured["counts"], "row_count": len(rows)}

    monkeypatch.setattr(module, "publish", capture_publish)
    result = module.build(
        source_root,
        tmp_path / "output",
        tmp_path / "summary.json",
        max_repos=4,
        max_rows=10,
    )
    assert result["row_count"] == 10
    assert result["split_counts"] == {"train": 8, "eval": 1, "strict_eval": 1}
    assert processed == ["train", "train", "eval", "strict_eval"]
    assert not (tmp_path / "output").exists()


def test_unfilled_strict_cap_fails_before_any_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    source_root = tmp_path / "source"
    source_root.mkdir()
    snapshots = [
        fake_split_snapshot(module, 10, "train"),
        fake_split_snapshot(module, 11, "eval"),
    ]
    install_split_selection_fakes(module, monkeypatch, snapshots, rows_per_snapshot=4)
    monkeypatch.setattr(
        module,
        "publish",
        lambda *args, **kwargs: pytest.fail("publish must not run with an unfilled strict cap"),
    )
    output = tmp_path / "output"
    summary = tmp_path / "summary.json"
    with pytest.raises(
        module.Stage12690Error,
        match="^reserved_split_caps_unfilled$",
    ) as error:
        module.build(
            source_root,
            output,
            summary,
            max_repos=2,
            max_rows=10,
        )
    assert str(error.value) == "reserved_split_caps_unfilled"
    assert not output.exists()
    assert not summary.exists()


@pytest.mark.parametrize("max_rows", [11, 19, 21])
def test_nonmultiple_max_rows_rejected_before_discovery_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_rows: int,
) -> None:
    module = load_module()
    source_root = tmp_path / "source"
    source_root.mkdir()
    monkeypatch.setattr(
        module,
        "discover_repositories",
        lambda *args, **kwargs: pytest.fail("discovery must not run"),
    )
    output = tmp_path / "output"
    summary = tmp_path / "summary.json"
    with pytest.raises(
        module.Stage12690Error,
        match="max_rows_must_be_multiple_of_10_and_at_least_10",
    ):
        module.build(
            source_root,
            output,
            summary,
            max_repos=1,
            max_rows=max_rows,
        )
    assert not output.exists()
    assert not summary.exists()


def test_one_strict_row_exposes_only_count_and_single_commitment(
    tmp_path: Path,
) -> None:
    module = load_module()
    rows_a, proofs_a, catalog_a = synthetic_publication_records(
        module, ("train", "eval", "strict_eval")
    )
    rows_b = json.loads(json.dumps(rows_a))
    proofs_b = json.loads(json.dumps(proofs_a))
    catalog_b = json.loads(json.dumps(catalog_a))

    rows_a[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE_A"
    proofs_a[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE_A"
    proofs_a[-1]["correct_candidate_position"] = 97
    proofs_a[-1]["row_sha256"] = module.sha256_bytes(b"strict-secret-a")
    rows_b[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE_B"
    proofs_b[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE_B"
    proofs_b[-1]["correct_candidate_position"] = 98
    proofs_b[-1]["row_sha256"] = module.sha256_bytes(b"strict-secret-b")

    output = tmp_path / "output"
    summary_a = module.publish(
        output,
        tmp_path / "summary-a.json",
        rows_a,
        proofs_a,
        catalog_a,
        {"strict_secret_counter_a": 1},
    )
    summary_b = module.publish(
        output,
        tmp_path / "summary-b.json",
        rows_b,
        proofs_b,
        catalog_b,
        {"strict_secret_counter_b": 1},
    )

    assert summary_a["reserved_unmaterialized_strict_row_count"] == 1
    assert summary_a["strict_eval_plaintext_materialized"] is False
    assert summary_a["generation_id"] != summary_b["generation_id"]
    assert summary_a["objective_counts"] == {
        "python_symbol_reference_prediction": 2,
    }
    assert summary_a["candidate_position_counts"] == {
        "python_symbol_reference_prediction": {"0": 1, "1": 1},
    }
    assert "language_counts" not in summary_a
    assert "counters" not in summary_a

    public_a = json.dumps(summary_a, sort_keys=True)
    public_b = json.dumps(summary_b, sort_keys=True)
    for secret in (
        "STRICT_SECRET_OBJECTIVE_A",
        "STRICT_SECRET_OBJECTIVE_B",
        "strict_secret_counter_a",
        "strict_secret_counter_b",
    ):
        assert secret not in public_a
        assert secret not in public_b

    commitment_a = summary_a["strict_eval_commitment_sha256"]
    commitment_b = summary_b["strict_eval_commitment_sha256"]
    assert commitment_a != commitment_b
    generation_a = output / summary_a["generation_relative_path"]
    generation_b = output / summary_b["generation_relative_path"]
    assert generation_a.is_dir()
    assert generation_b.is_dir()
    authoritative_a = output / summary_a["authoritative_summary_relative_path"]
    authoritative_b = output / summary_b["authoritative_summary_relative_path"]
    assert authoritative_a.read_bytes() == module.json_bytes(summary_a)
    assert authoritative_b.read_bytes() == module.json_bytes(summary_b)

    normalized_a = json.loads(json.dumps(summary_a))
    normalized_b = json.loads(json.dumps(summary_b))
    for normalized in (normalized_a, normalized_b):
        normalized.pop("generation_id")
        normalized.pop("generation_relative_path")
        normalized.pop("authoritative_summary_relative_path")
        normalized.pop("strict_eval_commitment_sha256")
        for contract in normalized["artifact_contract"].values():
            contract.pop("relative_path")
    assert normalized_a == normalized_b

    with pytest.raises(module.Stage12690Error, match="immutable_generation_exists"):
        module.publish(
            output,
            tmp_path / "duplicate-summary.json",
            rows_a,
            proofs_a,
            catalog_a,
            {},
        )
    assert not (tmp_path / "duplicate-summary.json").exists()

def test_prepare_release_preserves_splits_commitment_and_public_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_publication_records(
        module, ("train", "eval", "strict_eval")
    )
    original_splits = [row["split"] for row in rows]
    monkeypatch.setattr(
        module,
        "materialize",
        lambda *args, **kwargs: (
            rows, proofs, catalog, module.collections.Counter()
        ),
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    prepared = module.prepare_release(
        source_root, max_repos=3, max_rows=10
    )
    assert [row["split"] for row in prepared.rows] == original_splits
    assert prepared.summary["reserved_unmaterialized_strict_row_count"] == 1
    assert prepared.summary["strict_eval_commitment_sha256"] == module.stable(
        sorted(
            proof["row_sha256"]
            for proof in proofs
            if proof["split"] == "strict_eval"
        )
    )

    output = tmp_path / "output"
    published = module.publish(
        output,
        tmp_path / "summary.json",
        rows,
        proofs,
        catalog,
        {},
    )
    assert published == prepared.summary
    generation = output / published["generation_relative_path"]
    for name, expected in prepared.public_payloads.items():
        assert (generation / name).read_bytes() == expected
