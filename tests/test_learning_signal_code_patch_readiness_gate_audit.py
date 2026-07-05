from scripts.learning_signal_code_patch_readiness_builder import build_card, build_readiness_rows
from scripts.learning_signal_code_patch_readiness_gate_audit import audit_readiness_rows
from scripts.learning_signal_contract_builder import build_learning_signal_rows
from scripts.learning_signal_implementation_plan_builder import build_plan_rows


def test_readiness_gate_passes_closed_complete_rows():
    readiness_rows = build_readiness_rows(build_plan_rows(build_learning_signal_rows()))
    audit = audit_readiness_rows(readiness_rows)
    assert audit["passed"] is True
    assert audit["rows"] == build_card(readiness_rows)["rows"]
    assert audit["readiness_gate_pass_rows"] == audit["rows"]
    assert audit["missing_plan_id_count"] == 0
    assert audit["missing_file_count"] == 0
    assert audit["authority_open_rows"] == []
    assert audit["loss_open_rows"] == []
    assert audit["opening_rows"] == []
    assert audit["bad_route_rows"] == []
    assert audit["code_patch_authorized"] is False
    assert audit["training_authorized"] is False
    assert audit["decoder_ce_authorized"] is False


def test_readiness_gate_detects_open_loss_and_bad_route():
    readiness_rows = build_readiness_rows(build_plan_rows(build_learning_signal_rows()))
    readiness_rows[0]["loss_mask"]["decoder_ce"] = True
    readiness_rows[0]["route"] = "TRAIN"
    audit = audit_readiness_rows(readiness_rows)
    assert audit["passed"] is False
    assert readiness_rows[0]["row_id"] in audit["loss_open_rows"]
    assert readiness_rows[0]["row_id"] in audit["bad_route_rows"]
