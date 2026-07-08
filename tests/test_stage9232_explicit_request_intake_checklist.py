from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9232_explicit_request_intake_checklist.py"
spec = importlib.util.spec_from_file_location("stage9232", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9232_continue_is_not_valid_request():
    assert mod.classify_request_text("please continue")["decision"] == "ambiguous_request"


def test_stage9232_valid_design_request_requires_closed_flags():
    text = "requested_family=structured_policy_probe request_scope=design_family_specific_final_preexecution_audit_only trainer=false model=false cleanup=false arxiv=false runtime=false"
    assert mod.classify_request_text(text)["decision"] == "valid_design_request"


def test_stage9232_rejects_unsafe_phrases():
    assert mod.classify_request_text("run it for bounded_decoder_ce_probe")["decision"] == "unsafe_request"
    assert mod.classify_request_text("clean up and start training")["decision"] == "unsafe_request"
    assert mod.classify_request_text("read arxiv for denoise_repair_probe")["decision"] == "unsafe_request"


def test_stage9232_keeps_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())


def test_stage9232_validation_rejects_open_metric_or_continue_as_valid():
    card = mod.build_card()
    card["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in mod.validate_card(card)

    card = mod.build_card()
    card["examples"]["casual_continue"]["decision"] = "valid_design_request"
    assert "casual_continue_treated_as_valid" in mod.validate_card(card)
