from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage12559", ROOT / "scripts/build_stage12559_legacy_protected_identity_adapters.py")
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def spec(path: Path, role: str, parse=True):
    return {"path": path, "role": role, "parse_allowed": parse, "declared_count": 3}


def test_protected_payload_is_not_parsed_without_identity_sidecar(tmp_path: Path):
    path = tmp_path / "protected.jsonl"
    path.write_text('{"prompt_text":"secret"}\n', encoding="utf-8")
    row = M.adapt_source("sealed", spec(path, "protected_task_universe", False), reader=lambda _p: (_ for _ in ()).throw(AssertionError("must not parse")))
    assert row["raw_protected_payload_parsed"] is False
    assert "identity_only_sidecar_missing" in row["blocking_reasons"]


def test_exclusion_registry_is_complete_deny_set(tmp_path: Path):
    path = tmp_path / "excluded.jsonl"
    path.write_text('{"exclusion_key":"a"}\n{"exclusion_key":"b"}\n', encoding="utf-8")
    row = M.adapt_source("exclude", spec(path, "contamination_exclusion_set"))
    assert row["adapter_complete"] is True
    assert row["clearance_effect"] == "deny_set_enforced"
    assert row["normalized_identity_count"] == 2


def test_duplicate_or_missing_exclusion_key_blocks(tmp_path: Path):
    path = tmp_path / "excluded.jsonl"
    path.write_text('{"exclusion_key":"a"}\n{"exclusion_key":"a"}\n', encoding="utf-8")
    assert M.adapt_source("exclude", spec(path, "contamination_exclusion_set"))["adapter_complete"] is False


def test_evidence_metadata_never_clears_task_lineage(tmp_path: Path):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"records": [{"lineage_hash": "x"}]}), encoding="utf-8")
    row = M.adapt_source("ledger", spec(path, "evidence_metadata"))
    assert row["adapter_complete"] is False
    assert row["clearance_effect"] == "cannot_clear_replay"


def test_local_pack_ids_do_not_become_canonical_repo_identity(tmp_path: Path):
    path = tmp_path / "packs.jsonl"
    path.write_text('{"task_pack_id":"p","source_id":"s","artifact_hash":"a","lineage_hash":"l","path":"org/repo"}\n', encoding="utf-8")
    row = M.adapt_source("packs", spec(path, "protected_task_universe"))
    assert row["adapter_complete"] is False
    assert "canonical_repo_missing" in row["blocking_reasons"]


def test_missing_source_fails_closed(tmp_path: Path):
    row = M.adapt_source("missing", spec(tmp_path / "missing.jsonl", "contamination_exclusion_set"))
    assert row["source_present"] is False
    assert row["adapter_complete"] is False
