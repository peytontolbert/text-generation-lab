from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12691_source_backed_python_api_doc_links.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage12691", SCRIPT)
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
    git(repo, "remote", "add", "origin", f"https://example.invalid/api-doc-{index}.git")
    (repo / "src/pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "src/pkg/__init__.py").write_text(
        f"# repository fixture {index}\n", encoding="utf-8"
    )
    (repo / "src/pkg/core.py").write_text(
        f"# repository fixture {index}\n"
        "def alpha(value: int, *, scale: int = 1) -> int:\n"
        "    return value * scale\n\n"
        "def beta(value: int) -> int:\n    return value + 2\n\n"
        "def gamma(value: int) -> int:\n    return value + 3\n\n"
        f"class Delta:\n    marker = {index}\n",
        encoding="utf-8",
    )
    calls = {
        "alpha": f"alpha({index + 1}, scale={index + 2})",
        "beta": f"beta({index + 3})",
        "gamma": f"gamma({index + 4})",
        "Delta": "Delta()",
    }
    for symbol, expression in calls.items():
        (repo / f"tests/test_{symbol.lower()}.py").write_text(
            f"from pkg.core import {symbol}\n\n"
            f"def test_{symbol.lower()}():\n    assert {expression} is not None\n"
            f"# repository fixture {index}\n",
            encoding="utf-8",
        )
    (repo / "tests/test_rejected.py").write_text(
        f"# repository fixture {index}\n"
        "from pkg.core import *\n"
        "from ..pkg.core import alpha\n"
        "from pkg.core import beta as rebound\n"
        "rebound = lambda value: value\n"
        "def dynamic(values, kwargs):\n"
        "    return alpha(*values, **kwargs) + rebound(1)\n",
        encoding="utf-8",
    )
    (repo / "docs/api.rst").write_text(
        f".. repository fixture {index}\n\n"
        "API\n===\n\n"
        "Use :func:`pkg.core.alpha`, :func:`~pkg.core.beta`, and "
        ":class:`pkg.core.Delta`.\n"
        "Reject :meth:`pkg.core.gamma` and plain pkg.core.gamma proximity.\n",
        encoding="utf-8",
    )
    if ambiguous:
        conflict = repo / "vendor/src/pkg/core.py"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("def alpha(value):\n    return value\n#" + "x" * 260_000, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "add explicit API documentation and tests")
    return repo


def snapshot_fixture(module, repo: Path):
    snapshots, counters = module.stage12690.discover_repositories(repo.parent, 1)
    assert counters["repositories_accepted"] == 1
    snapshot = snapshots[0]
    snapshot.split = "train"
    parsed, parse_counts = module.stage12690.parse_snapshot(snapshot)
    relations, relation_counts = module.stage12690.extract_relations(
        parsed, snapshot.module_path_index
    )
    docs, doc_counts = module.load_doc_blobs(snapshot)
    return snapshot, parsed, relations, docs, parse_counts + relation_counts + doc_counts


def test_exact_unique_keyword_name_is_source_backed_and_oracle_free(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 1)
    snapshot, parsed, relations, _docs, _ = snapshot_fixture(module, repo)
    examples, counters = module.api_examples(parsed, relations)
    assert counters["api_keyword_name_examples"] == 1
    assert len(examples) == 1
    example = examples[0]
    assert example.relation.source.symbol == "alpha"
    assert example.target == "scale"
    assert module.SIGNATURE_PARAMETER_MASK in example.masked_definition_signature
    assert module.KEYWORD_MASK in example.masked_call_text
    assert "scale=" not in example.masked_call_text
    assert str(1 + 2) in example.masked_call_text
    assert example.original_definition_signature == "def alpha(value: int, *, scale: int = 1) -> int"
    assert module.reconstruct_single_mask(
        example.masked_definition_signature, module.SIGNATURE_PARAMETER_MASK, example.target
    ) == example.original_definition_signature
    assert module.reconstruct_single_mask(
        example.masked_call_text, module.KEYWORD_MASK, example.target
    ) == example.original_call_text
    test_bytes = (repo / example.relation.test_path).read_bytes()
    assert test_bytes[example.keyword_start_byte:example.keyword_end_byte] == b"scale"

    rows, proofs, build_counts = module.build_rows(snapshot, parsed, relations, [])
    assert build_counts["api_keyword_name_rows"] == 1
    assert rows[0]["objective_family"] == "python_api_keyword_name_completion"
    assert rows[0]["target"]["decoder_text"] == "scale"
    assert proofs[0]["candidate_count"] == 0
    assert proofs[0]["unique_remaining_keyword_parameter_verified"] is True
    assert proofs[0]["signature_reconstruction_verified"] is True
    assert proofs[0]["call_reconstruction_verified"] is True
    assert proofs[0]["reconstructed_signature_sha256"] == proofs[0]["original_signature_sha256"]
    assert proofs[0]["reconstructed_call_sha256"] == proofs[0]["original_call_sha256"]
    assert proofs[0]["normalized_identifier_target_absent_from_full_input"] is True
    assert "scale" not in module.normalized_identifier_tokens(rows[0]["input_text"])
    assert all(value is False for row in rows for value in row["authority"].values())

    import types
    fake_torch = types.ModuleType("torch")
    previous_torch = sys.modules.get("torch")
    sys.modules["torch"] = fake_torch
    try:
        training_path = ROOT / "legacy_src/agentkernel_lite/training_data.py"
        spec = importlib.util.spec_from_file_location("stage12691_training_data", training_path)
        assert spec and spec.loader
        training_data = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = training_data
        spec.loader.exec_module(training_data)
        baseline_row = training_data._row_text(rows[0])
        baseline_foundational = training_data._foundational_row_text(rows[0])
        mutated = json.loads(json.dumps(rows[0]))
        mutated["target"]["decoder_text"] = "oracle mutation"
        mutated["source_provenance"] = {"target": "oracle provenance"}
        mutated["authority"] = {"training_admitted": True}
        assert training_data._row_text(mutated) == baseline_row
        assert training_data._foundational_row_text(mutated) == baseline_foundational
    finally:
        if previous_torch is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = previous_torch


def test_invalid_calls_classes_values_and_conflicts_do_not_generate(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 2)
    with (repo / "src/pkg/core.py").open("a", encoding="utf-8") as handle:
        handle.write(
            "\ndef epsilon(value: int, *, option: int = 1, mode: int = 2) -> int:\n"
            "    return value + option + mode\n"
            "\ndef zeta(required: int, *, flag: bool) -> int:\n"
            "    return required if flag else 0\n"
        )
    fixtures = {
        "test_bogus.py": "from pkg.core import alpha\ndef test_bogus():\n    return alpha(1, bogus=2)\n",
        "test_wrong_type.py": "from pkg.core import alpha\ndef test_wrong_type():\n    return alpha('wrong', scale=2)\n",
        "test_arbitrary.py": "from pkg.core import alpha\ndef test_arbitrary():\n    return alpha(object(), scale=2)\n",
        "test_conflict.py": "from pkg.core import alpha\ndef test_conflict():\n    alpha(1, scale=2)\n    return alpha(3, scale=4)\n",
        "test_class_keyword.py": "from pkg.core import Delta\ndef test_class_keyword():\n    return Delta(bogus=1)\n",
        "test_nonunique.py": "from pkg.core import epsilon\ndef test_nonunique():\n    return epsilon(1, option=2)\n",
        "test_missing_required.py": "from pkg.core import zeta\ndef test_missing_required():\n    return zeta(flag=True)\n",
        "test_dynamic_star.py": "from pkg.core import alpha\ndef test_dynamic_star(values):\n    return alpha(1, *values)\n",
        "test_dynamic_kwargs.py": "from pkg.core import alpha\ndef test_dynamic_kwargs(kwargs):\n    return alpha(1, **kwargs)\n",
        "test_attribute.py": "from pkg.core import Delta\ndef test_attribute():\n    return Delta.build(mode=1)\n",
    }
    for name, content in fixtures.items():
        (repo / "tests" / name).write_text(content, encoding="utf-8")
    git(repo, "add", "src/pkg/core.py", "tests")
    git(repo, "commit", "-q", "-m", "add rejected keyword binding adversaries")
    _snapshot, parsed, relations, _docs, _ = snapshot_fixture(module, repo)
    examples, counters = module.api_examples(parsed, relations)
    assert [example.relation.test_path for example in examples] == ["tests/test_alpha.py"]
    assert all(example.target == "scale" for example in examples)
    assert counters["unknown_keyword_rejected"] >= 1
    assert counters["statically_wrong_argument_type_rejected"] >= 2
    assert counters["conflicting_direct_calls_rejected"] >= 1
    assert counters["nonfunction_or_missing_call_rejected"] >= 1
    assert counters["keyword_not_uniquely_inferable_rejected"] >= 1
    assert counters["required_binding_invalid_rejected"] >= 1
    assert counters["star_argument_call_rejected"] >= 1
    assert counters["dynamic_keyword_unpack_call_rejected"] >= 1
    assert not any(relation.test_path == "tests/test_attribute.py" for relation in relations)
    assert not any(relation.test_path == "tests/test_rejected.py" for relation in relations)


def test_full_input_normalized_identifier_leak_rejects_exact_token_not_substrings(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 6)
    with (repo / "src/pkg/core.py").open("a", encoding="utf-8") as handle:
        handle.write(
            "\ndef oracle(value: int, *, scale: scale = 1) -> int:\n"
            "    return value * scale\n"
            "\ndef scaler(scale_factor: int, *, scale: int = 1) -> int:\n"
            "    return scale_factor * scale\n"
        )
    (repo / "tests/test_oracle_annotation.py").write_text(
        "from pkg.core import oracle\ndef test_oracle_annotation():\n    return oracle(1, scale=2)\n",
        encoding="utf-8",
    )
    (repo / "tests/test_scaler_collision.py").write_text(
        "from pkg.core import scaler\ndef test_scaler_collision():\n    return scaler(1, scale=2)\n",
        encoding="utf-8",
    )
    git(repo, "add", "src/pkg/core.py", "tests")
    git(repo, "commit", "-q", "-m", "add identifier leakage adversaries")
    snapshot, parsed, relations, _docs, _ = snapshot_fixture(module, repo)
    examples, _ = module.api_examples(parsed, relations)
    assert {
        example.relation.test_path for example in examples
        if example.target == "scale"
    } >= {
        "tests/test_oracle_annotation.py",
        "tests/test_scaler_collision.py",
    }
    rows, _proofs, counters = module.build_rows(snapshot, parsed, relations, [])
    api_rows = [
        row for row in rows
        if row["objective_family"] == "python_api_keyword_name_completion"
    ]
    paths = {row["source_provenance"]["test_path"] for row in api_rows}
    assert "tests/test_oracle_annotation.py" not in paths
    assert "tests/test_scaler_collision.py" in paths
    assert counters["full_input_normalized_identifier_leak_rejected"] >= 1
    assert all(
        "scale" not in module.normalized_identifier_tokens(row["input_text"])
        for row in api_rows if row["target"]["decoder_text"] == "scale"
    )


def test_explicit_sphinx_role_requires_unique_same_definition_test_relation(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 3)
    (repo / "tests/test_alpha_second.py").write_text(
        "from pkg.core import alpha\ndef test_alpha_second():\n    return alpha(41)\n",
        encoding="utf-8",
    )
    git(repo, "add", "tests/test_alpha_second.py")
    git(repo, "commit", "-q", "-m", "add second test for the same definition")
    snapshot, parsed, relations, docs, _ = snapshot_fixture(module, repo)
    examples, counters = module.doc_examples(docs, relations, snapshot.module_path_index)
    assert {(example.role, example.qualified_name) for example in examples} == {
        ("func", "pkg.core.alpha"),
        ("func", "pkg.core.beta"),
        ("class", "pkg.core.Delta"),
    }
    assert counters["sphinx_method_role_rejected"] == 1
    assert all(module.DOC_MASK in example.doc_context for example in examples)
    assert all(example.qualified_name not in example.doc_context for example in examples)
    rows, proofs, build_counts = module.build_rows(snapshot, parsed, relations, docs)
    doc_rows = [row for row in rows if row["objective_family"] == "python_sphinx_doc_code_test_relationship"]
    doc_proofs = [proof for proof in proofs if proof["objective_family"] == "python_sphinx_doc_code_test_relationship"]
    assert build_counts["doc_rows"] == 3
    assert len(doc_rows) == len(doc_proofs) == 3
    assert all(proof["candidate_count"] >= 3 for proof in doc_proofs)
    assert all(proof["same_definition_test_relation_verified"] for proof in doc_proofs)
    assert all(
        proof["proof_contract"] == "absolute_sphinx_role_text_plus_syntactic_repository_module_path_plus_unique_top_level_definition_plus_test_import_direct_call_chain"
        for proof in doc_proofs
    )
    assert all(row["source_provenance"]["sphinx_domain_resolution_claimed"] is False for row in doc_rows)


def test_doc_full_input_rejects_nfkc_target_leak_but_allows_components(
    tmp_path: Path,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 7)
    source_path = repo / "src/pkg/core.py"
    source = source_path.read_text(encoding="utf-8")
    source = source.replace(
        "def alpha(value: int, *, scale: int = 1) -> int:\n    return value * scale",
        "def alpha(value: int, *, scale: int = 1) -> int:\n"
        "    \"\"\"Reviewer saw ｐｋｇ．ｃｏｒｅ．ａｌｐｈａ directly.\"\"\"\n"
        "    return value * scale",
    )
    source = source.replace(
        "def beta(value: int) -> int:\n    return value + 2",
        "def beta(value: int) -> int:\n"
        "    \"\"\"Separated semantic components: pkg / core / beta.\"\"\"\n"
        "    return value + 2",
    )
    source_path.write_text(source, encoding="utf-8")
    git(repo, "add", "src/pkg/core.py")
    git(repo, "commit", "-q", "-m", "add reviewer docstring leakage fixture")
    snapshot, parsed, relations, docs, _ = snapshot_fixture(module, repo)
    rows, proofs, counters = module.build_rows(snapshot, parsed, relations, docs)
    doc_rows = [
        row for row in rows
        if row["objective_family"] == "python_sphinx_doc_code_test_relationship"
    ]
    targets = {row["target"]["decoder_text"] for row in doc_rows}
    assert "pkg.core.alpha" not in targets
    assert {"pkg.core.beta", "pkg.core.Delta"}.issubset(targets)
    assert counters[
        "doc_full_input_normalized_fully_qualified_target_leak_rejected"
    ] >= 1
    beta_row = next(
        row for row in doc_rows if row["target"]["decoder_text"] == "pkg.core.beta"
    )
    assert "pkg / core / beta" in beta_row["input_text"]
    for row in doc_rows:
        normalized_target = module.unicodedata.normalize(
            "NFKC", row["target"]["decoder_text"]
        )
        normalized_input = module.unicodedata.normalize("NFKC", row["input_text"])
        assert normalized_target not in normalized_input
    doc_proofs = [
        proof for proof in proofs
        if proof["objective_family"] == "python_sphinx_doc_code_test_relationship"
    ]
    assert all(
        proof["normalized_fully_qualified_target_absent_from_full_input"] is True
        for proof in doc_proofs
    )


def test_all_path_module_ambiguity_rejects_links_even_outside_parse_cap(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 4, ambiguous=True)
    snapshot, parsed, relations, docs, _ = snapshot_fixture(module, repo)
    assert snapshot.module_path_index["pkg.core"] == (
        "src/pkg/core.py", "vendor/src/pkg/core.py"
    )
    assert relations == []
    api, _ = module.api_examples(parsed, relations)
    linked, counters = module.doc_examples(docs, relations, snapshot.module_path_index)
    assert api == []
    assert linked == []
    assert counters["missing_or_ambiguous_doc_test_relation_rejected"] >= 3


def test_doc_filters_generated_secret_and_nonexplicit_mentions(tmp_path: Path) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    repo = create_repo(source_root, 5)
    (repo / "docs/generated.rst").write_text(
        "This file is generated. Do not edit.\n:func:`pkg.core.alpha`\n", encoding="utf-8"
    )
    (repo / "docs/secret.rst").write_text(
        "password = 'correct horse battery staple'\n:func:`pkg.core.alpha`\n", encoding="utf-8"
    )
    (repo / "docs/plain.rst").write_text("pkg.core.alpha without a role\n", encoding="utf-8")
    git(repo, "add", "docs")
    git(repo, "commit", "-q", "-m", "add rejected documentation fixtures")
    snapshot, _parsed, relations, docs, _ = snapshot_fixture(module, repo)
    paths = {doc.path for doc in docs}
    assert "docs/generated.rst" not in paths
    assert "docs/secret.rst" not in paths
    examples, _ = module.doc_examples(docs, relations, snapshot.module_path_index)
    assert all(example.doc.path != "docs/plain.rst" for example in examples)


def synthetic_records(module, splits=("train",)):
    rows, proofs, catalog = [], [], []
    for index, split in enumerate(splits):
        rows.append({
            "split": split,
            "objective_family": "python_api_keyword_name_completion",
            "source_provenance": {},
        })
        proofs.append({
            "split": split,
            "row_sha256": f"{index + 1:064x}",
            "objective_family": "python_api_keyword_name_completion",
            "repository_key_sha256": f"{index + 11:064x}",
            "content_component_sha256": f"{index + 21:064x}",
            "source_file_sha256": f"{index + 31:064x}",
            "test_file_sha256": f"{index + 41:064x}",
            "model_input_sha256": f"{index + 51:064x}",
            "candidate_evidence_sha256s": [],
            "correct_candidate_position": -1,
        })
        catalog.append({
            "split": split,
            "repository_key_sha256": f"{index + 11:064x}",
        })
    return rows, proofs, catalog


def test_publication_excludes_strict_and_keeps_all_authority_false(tmp_path: Path) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_records(module, ("train", "strict_eval"))
    output = tmp_path / "out"
    summary = module.publish(output, tmp_path / "summary.json", rows, proofs, catalog, {})
    generation = output / summary["generation_relative_path"]
    manifest = (generation / "api_doc_train_eval_manifest.jsonl").read_text()
    assert "strict_eval" not in manifest
    assert summary["strict_eval_plaintext_materialized"] is False
    assert summary["reserved_unmaterialized_strict_row_count"] == 1
    assert summary["multilanguage_api_claimed"] is False
    assert summary["sphinx_domain_resolution_claimed"] is False
    assert {
        "unresolved_methods_and_attribute_calls_not_materialized",
        "multilanguage_api_not_materialized",
        "stage12691_trainer_adapter_not_materialized",
    }.issubset(summary["release_blockers"])
    assert all(value is False for value in summary["authority"].values())
    assert generation.stat().st_mode & 0o777 == 0o500
    assert not any("strict" in path.name for path in generation.iterdir())


def test_strict_rows_cannot_leak_through_public_stats_or_generation_identity(
    tmp_path: Path,
) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_records(
        module, ("train", "eval", "strict_eval")
    )
    output = tmp_path / "shared-output"
    baseline = module.publish(
        output, tmp_path / "baseline.json",
        rows, proofs, catalog, {"strict_secret_counter": 999},
    )

    changed_rows = json.loads(json.dumps(rows))
    changed_proofs = json.loads(json.dumps(proofs))
    changed_catalog = json.loads(json.dumps(catalog))
    changed_rows[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE"
    changed_proofs[-1]["objective_family"] = "STRICT_SECRET_OBJECTIVE"
    changed_proofs[-1]["correct_candidate_position"] = 987
    changed_proofs[-1]["row_sha256"] = "f" * 64
    changed_catalog[-1]["strict_secret_catalog_field"] = "STRICT_SECRET_CATALOG"
    changed = module.publish(
        output, tmp_path / "changed.json",
        changed_rows, changed_proofs, changed_catalog,
        {"STRICT_SECRET_COUNTER": 123456},
    )

    assert baseline["strict_eval_commitment_sha256"] != changed[
        "strict_eval_commitment_sha256"
    ]
    assert baseline["generation_id"] != changed["generation_id"]
    assert len(baseline["generation_id"]) == len(changed["generation_id"]) == 64

    def without_allowed_generation_changes(summary):
        projected = json.loads(json.dumps(summary))
        for key in (
            "generation_id",
            "generation_relative_path",
            "authoritative_summary_relative_path",
            "strict_eval_commitment_sha256",
        ):
            projected.pop(key)
        for artifact in projected["artifact_contract"].values():
            artifact.pop("relative_path")
        return projected

    assert without_allowed_generation_changes(baseline) == (
        without_allowed_generation_changes(changed)
    )
    assert baseline["split_counts"] == changed["split_counts"] == {
        "eval": 1, "train": 1,
    }
    assert "987" not in {
        position
        for positions in changed["candidate_position_counts"].values()
        for position in positions
    }
    assert "counters" not in baseline and "counters" not in changed
    assert baseline["reserved_unmaterialized_strict_row_count"] == 1
    assert changed["reserved_unmaterialized_strict_row_count"] == 1
    overlap_fields = {
        key: value for key, value in changed.items()
        if key.startswith("cross_split_")
    }
    assert overlap_fields and set(overlap_fields.values()) == {0}

    baseline_generation = output / baseline["generation_relative_path"]
    changed_generation = output / changed["generation_relative_path"]
    assert baseline_generation.is_dir()
    assert changed_generation.is_dir()
    artifact_names = {
        "api_doc_train_eval_manifest.jsonl",
        "train_eval_source_provenance_ledger.jsonl",
        "train_eval_source_catalog.jsonl",
    }
    assert {
        name: (baseline_generation / name).read_bytes() for name in artifact_names
    } == {
        name: (changed_generation / name).read_bytes() for name in artifact_names
    }
    assert json.loads((baseline_generation / "summary.json").read_text()) == baseline
    assert json.loads((changed_generation / "summary.json").read_text()) == changed

    serialized = json.dumps(changed, sort_keys=True)
    assert "STRICT_SECRET_OBJECTIVE" not in serialized
    assert "STRICT_SECRET_CATALOG" not in serialized
    assert "STRICT_SECRET_COUNTER" not in serialized
    with pytest.raises(module.Stage12691Error, match="immutable_generation_exists"):
        module.publish(
            output, tmp_path / "duplicate.json",
            changed_rows, changed_proofs, changed_catalog, {},
        )
    assert not (tmp_path / "duplicate.json").exists()


@pytest.mark.parametrize("max_rows", [0, 1, 9, 11, 19, 21])
def test_invalid_max_rows_rejected_before_discovery_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_rows: int,
) -> None:
    module = load_module()
    discovered = False

    def forbidden_discovery(*_args, **_kwargs):
        nonlocal discovered
        discovered = True
        raise AssertionError("discovery must not run")

    monkeypatch.setattr(
        module.stage12690, "discover_repositories", forbidden_discovery
    )
    output = tmp_path / f"out-{max_rows}"
    summary_path = tmp_path / f"summary-{max_rows}.json"
    with pytest.raises(
        module.Stage12691Error,
        match="max_rows_must_be_multiple_of_10_and_at_least_10",
    ):
        module.build(
            tmp_path / "missing-source",
            output,
            summary_path,
            max_repos=1,
            max_rows=max_rows,
        )
    assert discovered is False
    assert not output.exists()
    assert not summary_path.exists()


def test_reserved_split_caps_and_build_allocate_exactly_80_10_10(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    from types import SimpleNamespace

    splits = ["train"] * 8 + ["eval", "strict_eval"]
    snapshots = [
        SimpleNamespace(
            split=split,
            component_key=f"component-{index:02d}",
            repo_key=f"repo-{index:02d}",
            module_path_index={},
        )
        for index, split in enumerate(splits)
    ]
    monkeypatch.setattr(
        module.stage12690,
        "discover_repositories",
        lambda _source, _limit: (snapshots, module.collections.Counter()),
    )
    monkeypatch.setattr(
        module,
        "source_catalog_entry",
        lambda snapshot: {
            "split": snapshot.split,
            "repository_key_sha256": module.stable(snapshot.repo_key),
        },
    )
    monkeypatch.setattr(
        module.stage12690,
        "parse_snapshot",
        lambda _snapshot: ([], module.collections.Counter()),
    )
    monkeypatch.setattr(
        module.stage12690,
        "extract_relations",
        lambda _parsed, _index: ([], module.collections.Counter()),
    )
    monkeypatch.setattr(
        module,
        "load_doc_blobs",
        lambda _snapshot: ([], module.collections.Counter()),
    )

    def one_row(snapshot, _parsed, _relations, _docs):
        row = {
            "split": snapshot.split,
            "objective_family": "synthetic_publication_only",
        }
        proof = {
            "split": snapshot.split,
            "model_input_sha256": module.stable(snapshot.repo_key),
        }
        return [row], [proof], module.collections.Counter()

    monkeypatch.setattr(module, "build_rows", one_row)
    captured = {}

    def capture_publish(_output, _summary, rows, proofs, catalog, counters):
        captured.update(
            rows=rows, proofs=proofs, catalog=catalog, counters=counters
        )
        return {"split_counts": dict(module.collections.Counter(
            row["split"] for row in rows
        ))}

    monkeypatch.setattr(module, "publish", capture_publish)
    source_root = tmp_path / "repos"
    source_root.mkdir()
    summary = module.build(
        source_root, tmp_path / "out", tmp_path / "summary.json",
        max_repos=10, max_rows=10,
    )
    assert module.MAX_ROWS == 300
    assert module.reserved_split_caps(10) == {
        "train": 8, "eval": 1, "strict_eval": 1,
    }
    assert summary["split_counts"] == {
        "train": 8, "eval": 1, "strict_eval": 1,
    }
    assert len(captured["rows"]) == len(captured["proofs"]) == 10


@pytest.mark.parametrize(
    "shared_field",
    [
        "repository_key_sha256",
        "content_component_sha256",
        "source_file_sha256",
        "test_file_sha256",
        "doc_file_sha256",
        "model_input_sha256",
        "candidate_evidence_sha256s",
    ],
)
def test_every_final_overlap_key_merges_allocation_components(shared_field: str) -> None:
    module = load_module()
    records = {}
    for index, component in enumerate(("component-a", "component-b")):
        proof = {
            "repository_key_sha256": f"repo-{index}",
            "content_component_sha256": f"content-{index}",
            "source_file_sha256": f"source-{index}",
            "test_file_sha256": f"test-{index}",
            "doc_file_sha256": f"doc-{index}",
            "model_input_sha256": f"input-{index}",
            "candidate_evidence_sha256s": [f"candidate-{index}"],
        }
        proof[shared_field] = (
            ["shared"] if shared_field == "candidate_evidence_sha256s"
            else "shared"
        )
        records[component] = [(None, {}, proof)]
    grouped, component_to_group, members = (
        module.merge_overlap_evidence_components(records)
    )
    assert len(grouped) == 1
    assert len(set(component_to_group.values())) == 1
    assert next(iter(members.values())) == ("component-a", "component-b")


def test_uneven_sparse_capacity_allocation_is_deterministic_and_whole_component() -> None:
    module = load_module()
    capacities = {"large": 17, "medium": 4, "sparse": 2, "tail": 1}
    caps = module.reserved_split_caps(20)
    first = module.allocate_component_splits(capacities, caps)
    second = module.allocate_component_splits(dict(reversed(list(capacities.items()))), caps)
    assert first == second
    assert set(first) == set(capacities)
    assigned_capacity = {
        split: sum(
            capacities[component]
            for component, assigned_split in first.items()
            if assigned_split == split
        )
        for split in caps
    }
    assert all(assigned_capacity[split] >= caps[split] for split in caps)


def test_sparse_capacity_failure_is_generic() -> None:
    module = load_module()
    with pytest.raises(module.Stage12691Error) as caught:
        module.allocate_component_splits(
            {"single-component": 9}, module.reserved_split_caps(10)
        )
    assert str(caught.value) == "reserved_split_caps_unfilled"
    assert not any(character.isdigit() for character in str(caught.value))


def test_nonzero_overlap_and_same_name_artifact_replacement_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    overlap_fields = (
        "repository_key_sha256",
        "content_component_sha256",
        "source_file_sha256",
        "test_file_sha256",
        "doc_file_sha256",
        "model_input_sha256",
        "candidate_evidence_sha256s",
    )
    for field in overlap_fields:
        rows, proofs, catalog = synthetic_records(module, ("train", "eval"))
        shared = ["shared-evidence"] if field == "candidate_evidence_sha256s" else "d" * 64
        proofs[0][field] = shared
        proofs[1][field] = shared
        output = tmp_path / f"overlap-{field}"
        with pytest.raises(module.Stage12691Error) as caught:
            module.publish(
                output, tmp_path / f"overlap-{field}.json",
                rows, proofs, catalog, {},
            )
        disclosure = str(caught.value)
        assert disclosure == "cross_split_overlap_nonzero"
        assert field not in disclosure
        assert "=1" not in disclosure
        assert ":" not in disclosure
        assert not output.exists()

    rows, proofs, catalog = synthetic_records(module)
    output = tmp_path / "substitution"
    real_rename = module.stage12690.rename_noreplace

    def substitute(parent_fd: int, source: str, destination: str) -> None:
        real_rename(parent_fd, source, destination)
        generation = output / "private" / destination
        generation.chmod(0o700)
        original = (generation / "summary.json").read_bytes()
        (generation / "summary.json").rename(generation / "old-summary.json")
        (generation / "summary.json").write_bytes(original)

    monkeypatch.setattr(module.stage12690, "rename_noreplace", substitute)
    with pytest.raises(
        module.stage12690.Stage12690Error,
        match="published_generation_artifact_identity_mismatch:summary.json",
    ):
        module.publish(output, tmp_path / "substitution.json", rows, proofs, catalog, {})
    assert not (tmp_path / "substitution.json").exists()


def test_full_build_is_bounded_python_only_and_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    source_root = tmp_path / "repos"
    source_root.mkdir()
    for index in range(10, 30):
        create_repo(source_root, index)
    real_discover = module.stage12690.discover_repositories

    def discover_with_reserved_splits(source, limit):
        snapshots, counters = real_discover(source, limit)
        ordered = sorted(
            snapshots, key=lambda value: (value.component_key, value.repo_key)
        )
        for index, snapshot in enumerate(ordered):
            snapshot.split = (
                "train" if index < 16 else "eval" if index < 18 else "strict_eval"
            )
        return snapshots, counters

    monkeypatch.setattr(
        module.stage12690, "discover_repositories", discover_with_reserved_splits
    )
    output = tmp_path / "release"
    summary_path = tmp_path / "summary.json"
    summary = module.build(source_root, output, summary_path, max_repos=20, max_rows=10)
    assert summary["row_count"] == 10
    assert summary["materialized_model_row_count"] == 9
    assert summary["reserved_unmaterialized_strict_row_count"] == 1
    assert summary["split_counts"] == {"eval": 1, "train": 8}
    assert summary["objective_counts"]["python_api_keyword_name_completion"] >= 1
    assert summary["objective_counts"]["python_sphinx_doc_code_test_relationship"] >= 3
    generation = output / summary["generation_relative_path"]
    rows = [json.loads(line) for line in (generation / "api_doc_train_eval_manifest.jsonl").read_text().splitlines()]
    assert rows and {row["language_family"] for row in rows} == {"python"}
    assert not any("placeholder" in row["target"]["decoder_text"].lower() for row in rows)
    with pytest.raises(module.Stage12691Error, match="immutable_generation_exists"):
        module.build(source_root, output, summary_path, max_repos=20, max_rows=10)

def test_prepare_release_preserves_splits_commitment_and_public_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    rows, proofs, catalog = synthetic_records(
        module, ("train", "eval", "strict_eval")
    )
    original_splits = [row["split"] for row in rows]
    monkeypatch.setattr(
        module,
        "materialize",
        lambda *args, **kwargs: (
            rows,
            proofs,
            catalog,
            module.collections.Counter(),
            {},
        ),
    )
    source_root = tmp_path / "source"
    source_root.mkdir()
    prepared = module.prepare_release(
        source_root, max_repos=3, max_rows=10
    )
    assert [row["split"] for row in prepared.rows] == original_splits
    assert prepared.summary["reserved_unmaterialized_strict_row_count"] == 1
    strict_rows = [row for row in rows if row["split"] == "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    strict_catalog = [
        entry for entry in catalog if entry["split"] == "strict_eval"
    ]
    assert prepared.summary["strict_eval_commitment_sha256"] == module.stable({
        "contract": "stage12691_strict_eval_v2",
        "row_sha256s": sorted(module.stable(row) for row in strict_rows),
        "proof_sha256s": sorted(module.stable(proof) for proof in strict_proofs),
        "catalog_sha256s": sorted(
            module.stable(entry) for entry in strict_catalog
        ),
    })

    output = tmp_path / "output-prepared"
    published = module.publish(
        output,
        tmp_path / "prepared-summary.json",
        rows,
        proofs,
        catalog,
        {},
    )
    assert published == prepared.summary
    generation = output / published["generation_relative_path"]
    for name, expected in prepared.public_payloads.items():
        assert (generation / name).read_bytes() == expected
