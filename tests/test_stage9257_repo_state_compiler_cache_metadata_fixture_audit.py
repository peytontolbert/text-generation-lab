from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9257_repo_state_compiler_cache_metadata_fixture_audit.py"
    spec = importlib.util.spec_from_file_location("stage9257", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_manifest():
    return {
        "cache_layers": [
            {
                "layer_id": "psi_ast_cst_structure",
                "modality": "cst_ast",
                "future_artifact": "repo_ast_cst_packets.jsonl",
                "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
            },
            {
                "layer_id": "psi_symbol_table",
                "modality": "symbol_table",
                "future_artifact": "repo_symbol_table_packets.jsonl",
                "cache_key_fields": ["repo_id", "commit_hash", "path", "source_sha256", "extractor_version"],
            },
        ]
    }


def test_metadata_fixture_rows_are_bodyless_and_authority_closed():
    mod = _load()
    rows = mod.build_fixture_rows(_source_manifest())
    audit = mod.audit_rows(rows, _source_manifest(), {"passed": True})
    assert audit["passed"] is True
    assert audit["metrics"]["rows"] == 2
    assert audit["metrics"]["raw_body_rows"] == 0
    assert audit["metrics"]["authority_rows"] == 0
    assert audit["metrics"]["arxiv_reads_attempted"] is False
    assert all(row["input_packet"]["body_text_present"] is False for row in rows)
    assert all(row["target_contract"]["decoder_text_present"] is False for row in rows)


def test_audit_rejects_forbidden_body_and_arxiv_paths():
    mod = _load()
    rows = mod.build_fixture_rows(_source_manifest())
    rows[0]["source_text"] = "def unsafe_body(): pass"
    rows[0]["input_packet"]["path"] = "/arxiv/repositories/example.py"
    audit = mod.audit_rows(rows, _source_manifest(), {"passed": True})
    assert audit["passed"] is False
    assert "raw_body_rows_nonzero" in audit["failures"]
    assert "label_leak_rows_nonzero" in audit["failures"]
    assert "arxiv_path_rows_nonzero" in audit["failures"]


def test_audit_rejects_non_opaque_ids_and_duplicate_cache_keys():
    mod = _load()
    rows = mod.build_fixture_rows(_source_manifest())
    rows[0]["row_id"] = "symbol_binding_label"
    rows[1]["cache_key"] = dict(rows[0]["cache_key"])
    audit = mod.audit_rows(rows, _source_manifest(), {"passed": True})
    assert audit["passed"] is False
    assert "invalid_opaque_id_rows_nonzero" in audit["failures"]
    assert "duplicate_cache_key_rows_nonzero" in audit["failures"]
