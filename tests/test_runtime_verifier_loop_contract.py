import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_verifier_loop_contract import audit_runtime_verifier_loop_contract, default_runtime_verifier_loop_contract


def test_default_runtime_verifier_loop_contract_is_closed_and_complete():
    contract = default_runtime_verifier_loop_contract()
    audit = audit_runtime_verifier_loop_contract(contract)
    assert audit["passed"] is True
    assert audit["phase_count"] == 5
    assert contract["authority"]["runtime_authorized"] is False
    assert "RETRIEVE_MORE" in contract["repair_actions"]
    assert "runtime_trace_packet" in contract["verifier_outputs"]


def test_runtime_verifier_loop_contract_rejects_open_runtime_authority():
    contract = default_runtime_verifier_loop_contract()
    contract["authority"]["runtime_authorized"] = True
    audit = audit_runtime_verifier_loop_contract(contract)
    assert audit["passed"] is False
    assert "forbidden_authority_open:runtime_authorized" in audit["failures"]


def test_runtime_verifier_loop_contract_requires_all_phases():
    contract = default_runtime_verifier_loop_contract()
    contract["phases"] = ["prepare", "verify"]
    audit = audit_runtime_verifier_loop_contract(contract)
    assert audit["passed"] is False
    assert "missing_phase:repair_decision" in audit["failures"]
