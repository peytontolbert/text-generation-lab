from __future__ import annotations

import importlib.util
import collections
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12683_precise_link_semantic_repair_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12683", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_python_import_extraction_is_semantic_and_bounded() -> None:
    rows = M.python_imports("from package.module import Widget as LocalWidget\nimport ignored\n")
    assert rows == [{"module": "package.module", "level": 0, "name": "Widget", "alias_used": True, "line": 1}]


def test_ambiguous_definition_names_are_quarantined() -> None:
    file_a = {"rel": "a.py", "role": "code", "language_family": "python", "suffix_token": ".py", "stem_token": "a", "path_depth_bucket": "root", "definitions": [{"name": "Shared", "kind": "class", "line": 1, "method": "python_ast_definition"}], "definition_names": {"Shared"}, "tokens": set(), "imports": [], "module_aliases": {"a"}}
    file_b = {**file_a, "rel": "b.py", "stem_token": "b", "module_aliases": {"b"}}
    scanned = {"repo": {"repo": {}, "files": [file_a, file_b]}}
    rows, stats = M.materialize_drafts(scanned, {"repo": "train"})
    assert rows == []
    assert stats["ambiguous_symbol_keys_quarantined"] == 1


def test_finalize_deduplicates_and_rejects_conflicting_inputs() -> None:
    base = M.draft_row("repo", "train", "objective", {"feature": "x"}, "yes", {"extraction_method": "parser", "occurrence_proof_digest": "proof_a"})
    duplicate = json.loads(json.dumps(base))
    conflict = json.loads(json.dumps(base))
    conflict["expected_output"] = {"relationship": "no"}
    conflict["evidence"]["occurrence_proof_digest"] = "proof_b"
    rows, stats = M.finalize_rows([base, duplicate, conflict])
    assert rows == []
    assert stats["semantic_duplicate_excess_rows_removed"] == 1
    assert stats["conflicting_input_groups_quarantined"] == 1


def test_forbidden_source_context_is_quarantined() -> None:
    row = M.draft_row("repo", "train", "objective", {"symbol_name": "placeholder"}, "yes", {"extraction_method": "parser", "occurrence_proof_digest": "proof"})
    rows, stats = M.finalize_rows([row])
    assert rows == []
    assert stats["forbidden_lexical_candidates_quarantined"] == 1


def test_real_packet_has_grounded_non_leaky_rows() -> None:
    summary, audit, checks, rows = M.build_packet()
    assert summary["decision"] == "PRECISE_LINK_SEMANTIC_REPAIR_MATERIALIZED_INDEPENDENT_REVIEW_REQUIRED"
    assert summary["materialized_rows"] == len(rows) >= 20_000
    assert set(summary["objective_counts"]) == {
        "python_ast_symbol_definition_relation",
        "language_pattern_symbol_definition_relation",
        "doc_build_literal_symbol_association",
        "python_absolute_import_symbol_resolution",
    }
    assert summary["target_leak_rows"] == 0
    assert summary["cross_split_file_digest_groups"] == 0
    assert summary["semantic_duplicate_excess_rows"] == 0
    assert summary["identical_input_multiple_target_groups"] == 0
    assert audit["semantic_claim_policy"]["doc_build_relations"].startswith("literal_association_only")
    assert summary["materialized_rows"] == 2 * summary["contrast_pairs_materialized"]
    pair_counts = collections.Counter(row["evidence"]["contrast_pair_digest"] for row in rows)
    assert set(pair_counts.values()) == {2}
    import_rows = [row for row in rows if row["objective_family"] == "python_absolute_import_symbol_resolution"]
    assert import_rows and all(row["input_state"]["imported_module"] for row in import_rows)
    assert all(row["input_state"]["relative_import_level_bucket"] == "zero" for row in import_rows)
    definition_rows = [row for row in rows if "symbol_definition_relation" in row["objective_family"]]
    assert definition_rows and all(row["input_state"]["declaration_shape"] for row in definition_rows)
    assert all(row["input_state"]["declaration_line_bucket"] != "zero" for row in definition_rows)
    assert {item["status"] for item in checks} == {"passed", "blocked"}
    for row in rows:
        assert not (M.scalar_values(row["expected_output"]) & (M.scalar_values(row["input_state"]) | M.scalar_values(row["evidence"])))
        assert all(value is False for value in row["authority"].values())


def test_build_writes_digest_bound_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifact"
    summary_path = tmp_path / "summary.json"
    summary = M.build(out, summary_path)
    rows = M.read_jsonl(out / "private/precise_link_semantic_repair_rows.jsonl")
    contract = M.read_json(out / "contract.json")
    pointer = M.read_json(out / "digest_pointer.json")
    assert summary_path.exists()
    assert contract["rows_sha256"] == M.stable_hash(rows)
    assert pointer["rows_sha256"] == contract["rows_sha256"]
    assert pointer["summary_sha256"] == M.stable_hash(summary)


def test_all_public_and_private_authority_gates_remain_closed() -> None:
    summary, audit, _checks, _rows = M.build_packet()
    for record in (summary, audit):
        assert all(record[field] is False for field in M.FALSE_FIELDS)
    assert summary["training_source_rows_admitted"] == 0
    assert summary["recommended_next_stage"] == "stage12684_precise_link_semantic_repair_independent_review_only"
