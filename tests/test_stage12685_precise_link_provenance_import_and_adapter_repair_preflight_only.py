from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12685_precise_link_provenance_import_and_adapter_repair_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12685", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_ast_occurrence_span_is_exact_and_digest_bound(tmp_path: Path) -> None:
    source = "def alpha(value):\n    return value\n"
    path = tmp_path / "module.py"
    path.write_text(source, encoding="utf-8")
    file = {"rel": "module.py", "digest": M.sha(source.encode("utf-8"))}
    span = M.occurrence_span(tmp_path, file, "alpha", 1, "python_ast_definition")
    assert span is not None
    assert (span["line"], span["column"], span["end_line"]) == (1, 0, 2)
    assert span["snippet_sha256"] == M.sha(ast.get_source_segment(source, ast.parse(source).body[0]).encode("utf-8"))


def test_pattern_occurrence_span_is_bounded(tmp_path: Path) -> None:
    source = "before\nfunction target() {}\nafter\n"
    path = tmp_path / "module.js"
    path.write_text(source, encoding="utf-8")
    file = {"rel": "module.js", "digest": M.sha(source.encode("utf-8"))}
    span = M.occurrence_span(tmp_path, file, "target", 2, "language_definition_pattern")
    assert span is not None
    assert (span["line"], span["column"], span["end_column"]) == (2, 9, 15)
    assert span["occurrence_count"] == 1


def test_real_packet_repairs_provenance_metadata_and_shortcuts() -> None:
    summary, audit, checks, rows, provenance = M.build_packet()
    assert summary["decision"] == "PRECISE_LINK_PROVENANCE_AND_PAIR_ADAPTER_MATERIALIZED_INDEPENDENT_REVIEW_REQUIRED"
    assert len(rows) == len(provenance) == summary["trainer_pairs_materialized"] >= 20_000
    assert summary["unproven_absolute_import_pairs_quarantined"] == 2057
    assert summary["label_majority_accuracy"] == 0.5
    assert summary["coarse_shortcut_majority_accuracy"] == 0.5
    encoded = json.dumps(rows, sort_keys=True)
    assert M.contains_key(rows, {"row_id", "occurrence_proof_digest"}) is False
    assert "repository_relative_path" not in encoded
    assert "source_file_digest" not in encoded
    assert not any(row["objective_family"] == "python_absolute_import_symbol_resolution" for row in rows)
    assert all(item["trainer_row_sha256"] == M.stable(row) for row, item in zip(rows, provenance))
    assert {item["status"] for item in checks} == {"passed", "blocked"}
    assert audit["stats"]["duplicate_trainer_rows"] == 0


def test_target_independent_ordering_and_private_binding() -> None:
    _summary, _audit, _checks, rows, provenance = M.build_packet()
    assert all(item["target_independent_ordering"] is True for item in provenance)
    assert all({endpoint["slot"] for endpoint in item["candidate_endpoints"]} == {"candidate_a", "candidate_b"} for item in provenance)
    assert all(row["expected_output"]["selected_candidate"] in {"candidate_a", "candidate_b"} for row in rows)


def test_build_writes_digest_bound_artifacts(tmp_path: Path) -> None:
    out, summary_path = tmp_path / "artifact", tmp_path / "summary.json"
    summary = M.build(out, summary_path)
    rows = M.read_jsonl(out / "private/trainer_pairs.jsonl")
    provenance = M.read_jsonl(out / "private/provenance_ledger.jsonl")
    contract = M.read_json(out / "contract.json")
    pointer = M.read_json(out / "digest_pointer.json")
    assert contract["trainer_rows_sha256"] == M.stable(rows)
    assert pointer["summary_sha256"] == M.stable(summary)
    assert len(rows) == len(provenance)
    assert summary_path.exists()


def test_all_authority_gates_remain_closed() -> None:
    summary, audit, _checks, _rows, _provenance = M.build_packet()
    for record in (summary, audit):
        assert all(record[field] is False for field in M.FALSE_FIELDS)
    assert summary["training_source_rows_admitted"] == 0
    assert summary["recommended_next_stage"] == "stage12686_precise_link_provenance_and_adapter_independent_review_only"
