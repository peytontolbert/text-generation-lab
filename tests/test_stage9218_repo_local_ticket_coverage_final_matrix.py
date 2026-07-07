from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9218_repo_local_ticket_coverage_final_matrix.py"
    spec = importlib.util.spec_from_file_location("stage9218_matrix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_ticket_is_inactive_requires_closed_authority_and_no_command():
    mod = _load()
    ticket = {
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "command_materialized": False,
        "allowed_operations_now": [],
        "authority": dict(mod.AUTHORITY_CLOSED),
    }
    assert mod.ticket_is_inactive(ticket)
    ticket["command_materialized"] = True
    assert not mod.ticket_is_inactive(ticket)


def test_ticket_is_inactive_rejects_open_authority():
    mod = _load()
    authority = dict(mod.AUTHORITY_CLOSED)
    authority["model_execution_authorized_next"] = True
    ticket = {
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "command_materialized": False,
        "allowed_operations_now": [],
        "authority": authority,
    }
    assert not mod.ticket_is_inactive(ticket)


def test_family_specs_cover_three_probe_modes():
    mod = _load()
    assert set(mod.FAMILY_TICKET_AUDITS) == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }
