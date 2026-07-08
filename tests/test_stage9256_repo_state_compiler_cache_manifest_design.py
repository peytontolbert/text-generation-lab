from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9256_repo_state_compiler_cache_manifest_design.py"
    spec = importlib.util.spec_from_file_location("stage9256", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_manifest_design_has_required_layers_and_closed_controls():
    mod = _load()
    manifest = mod.build_manifest()
    audit = mod.audit_manifest(manifest, {"passed": True, "authority": {}})
    assert audit["passed"] is True
    assert audit["cache_layers"] >= 10
    layer_ids = {layer["layer_id"] for layer in manifest["cache_layers"]}
    assert "psi_ast_cst_structure" in layer_ids
    assert "psi_symbol_table" in layer_ids
    assert "psi_repo_state_compressed_stream" in layer_ids
    assert manifest["controls"]["design_only_no_extraction"] is True
    assert manifest["controls"]["read_arxiv_now"] is False
    assert manifest["controls"]["training_authorized_now"] is False
    assert all(value is False for value in manifest["authority"].values())


def test_audit_rejects_open_extraction_or_missing_cache_key():
    mod = _load()
    manifest = mod.build_manifest()
    manifest["controls"]["read_repository_bodies_now"] = True
    manifest["cache_layers"][0]["cache_key_fields"] = ["repo_id"]
    audit = mod.audit_manifest(manifest, {"passed": True, "authority": {}})
    assert audit["passed"] is False
    assert "control_mismatch:read_repository_bodies_now" in audit["failures"]
    assert any(failure.startswith("missing_commit_hash_cache_key") for failure in audit["failures"])


def test_manifest_points_at_recovered_extractor_modules():
    mod = _load()
    modules = {layer["extractor_module"] for layer in mod.build_manifest()["cache_layers"]}
    assert "scripts/program_state_ast_cst_extractor.py" in modules
    assert "scripts/program_state_symbol_table_extractor.py" in modules
    assert "scripts/program_state_import_dependency_extractor.py" in modules
    assert "scripts/program_state_call_graph_extractor.py" in modules
    assert "scripts/state_space_repo_state_compressor.py" in modules
