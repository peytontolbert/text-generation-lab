from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9259_repo_state_metadata_inventory_runner_synthetic_fixture.py"
    spec = importlib.util.spec_from_file_location("stage9259", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_synthetic_sidecar_inventory_is_metadata_only():
    mod = _load()
    sidecar = mod.build_synthetic_sidecar()
    rows = mod.inventory_rows_from_sidecar(sidecar)
    plan = mod.build_extractor_plan(rows)
    previews = mod.build_cache_preview(rows)
    audit = mod.audit_outputs(sidecar, rows, plan, previews, {"passed": True})
    assert audit["passed"] is True
    assert audit["metrics"]["rows"] == 8
    assert audit["metrics"]["languages"] == 4
    assert audit["metrics"]["body_read_authorized_rows"] == 0
    assert audit["metrics"]["runtime_authorized_rows"] == 0
    assert audit["metrics"]["authority_rows"] == 0
    assert plan["plan_status"] == "METADATA_ONLY_NO_BODY_EXTRACTION"
    assert all(row["body_read_authorized"] is False for row in rows)
    assert all(preview["body_text_present"] is False for preview in previews)


def test_sidecar_rejects_body_fields_arxiv_and_path_escape():
    mod = _load()
    sidecar = mod.build_synthetic_sidecar()
    sidecar["files"][0]["source_text"] = "def unsafe(): pass"
    sidecar["files"][1]["relative_path"] = "../escape.py"
    sidecar["input_root"] = "/arxiv/repositories"
    failures = mod.reject_sidecar(sidecar)
    assert any(failure.startswith("forbidden_record_key") for failure in failures)
    assert any(failure.startswith("path_boundary_violation") for failure in failures)
    assert "input_root_arxiv_forbidden" in failures


def test_sidecar_rejects_authorization_openings():
    mod = _load()
    sidecar = mod.build_synthetic_sidecar()
    sidecar["controls"]["read_source_bodies_now"] = True
    sidecar["controls"]["runtime_authorized_now"] = True
    sidecar["controls"]["training_authorized_now"] = True
    failures = mod.reject_sidecar(sidecar)
    assert "control_not_false:read_source_bodies_now" in failures
    assert "control_not_false:runtime_authorized_now" in failures
    assert "control_not_false:training_authorized_now" in failures
