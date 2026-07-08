from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9258_repo_state_metadata_inventory_preflight_design.py"
    spec = importlib.util.spec_from_file_location("stage9258", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_design_keeps_inventory_metadata_only_and_authority_closed():
    mod = _load()
    design = mod.build_design()
    audit = mod.audit_design(design, {"passed": True})
    assert audit["passed"] is True
    assert design["controls"]["metadata_only"] is True
    assert design["controls"]["read_source_bodies_now"] is False
    assert design["controls"]["read_arxiv_now"] is False
    assert design["controls"]["runtime_authorized_now"] is False
    assert all(value is False for value in design["authority"].values())
    assert "content_sha256" in design["inventory_fields"]
    assert "delete_any_path" in design["denied_operations"]


def test_design_rejects_body_runtime_and_arxiv_openings():
    mod = _load()
    design = mod.build_design()
    for patch, expected in [
        ({"read_source_bodies_now": True}, "control_not_false:read_source_bodies_now"),
        ({"runtime_authorized_now": True}, "control_not_false:runtime_authorized_now"),
        ({"read_arxiv_now": True}, "control_not_false:read_arxiv_now"),
        ({"input_root": "/arxiv/repositories"}, "input_root_forbidden"),
    ]:
        candidate = mod.apply_patch_case(design, patch)
        audit = mod.audit_design(candidate, {"passed": True})
        assert audit["passed"] is False
        assert expected in audit["failures"]


def test_negative_cases_are_all_rejected():
    mod = _load()
    design = mod.build_design()
    negative = mod.audit_negative_cases(design)
    assert negative["negative_cases"] == len(mod.NEGATIVE_CASES)
    assert negative["negative_cases_rejected"] == negative["negative_cases"]
