from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9225_explicit_one_family_request_schema.py"
spec = importlib.util.spec_from_file_location("stage9225", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9225_template_example_is_valid_and_design_only():
    card = mod.build_card()
    assert mod.validate_request(card["template_example"]) == []
    assert card["template_example"]["request_scope"] == "design_family_specific_final_preexecution_audit_only"
    assert card["template_example"]["trainer_invocation_allowed"] is False
    assert card["template_example"]["cleanup_allowed"] is False
    assert card["template_example"]["arxiv_access_allowed"] is False


def test_stage9225_rejects_execution_cleanup_arxiv_and_multi_family_requests():
    request = dict(mod.TEMPLATE_EXAMPLE)
    request["trainer_invocation_allowed"] = True
    assert "trainer_invocation_requested" in mod.validate_request(request)

    request = dict(mod.TEMPLATE_EXAMPLE)
    request["cleanup_allowed"] = True
    assert "cleanup_requested" in mod.validate_request(request)

    request = dict(mod.TEMPLATE_EXAMPLE)
    request["arxiv_access_allowed"] = True
    assert "arxiv_access_requested" in mod.validate_request(request)

    request = dict(mod.TEMPLATE_EXAMPLE)
    request["requested_family"] = ["structured_policy_probe", "bounded_decoder_ce_probe"]
    assert "multiple_families_requested" in mod.validate_request(request)


def test_stage9225_card_keeps_all_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())


def test_stage9225_validation_rejects_open_metric_or_invalid_template():
    card = mod.build_card()
    card["metrics"]["model_forward_attempted"] = True
    assert "model_forward_attempted" in mod.validate_card(card)

    card = mod.build_card()
    card["template_example"]["runtime_allowed"] = True
    assert "template_example_invalid" in mod.validate_card(card)
