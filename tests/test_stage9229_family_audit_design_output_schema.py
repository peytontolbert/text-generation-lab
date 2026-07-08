from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9229_family_audit_design_output_schema.py"
spec = importlib.util.spec_from_file_location("stage9229", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9229_examples_validate_for_all_families():
    card = mod.build_card()
    assert set(card["example_designs"]) == set(mod.SUPPORTED_FAMILIES)
    for design in card["example_designs"].values():
        assert mod.validate_design(design) == []


def test_stage9229_forbids_live_and_execution_design_fields():
    assert "live_ticket_path" in mod.FORBIDDEN_DESIGN_FIELDS
    assert "trainer_command_to_execute" in mod.FORBIDDEN_DESIGN_FIELDS
    assert "checkpoint_path" in mod.FORBIDDEN_DESIGN_FIELDS
    assert "cleanup_result_path" in mod.FORBIDDEN_DESIGN_FIELDS
    assert "arxiv_inventory_path" in mod.FORBIDDEN_DESIGN_FIELDS


def test_stage9229_validate_design_rejects_forbidden_and_open_closed_fields():
    design = mod.example_design("bounded_decoder_ce_probe")
    design["live_ticket_path"] = "runs/live.json"
    assert "forbidden_field_present:live_ticket_path" in mod.validate_design(design)

    design = mod.example_design("denoise_repair_probe")
    design["cleanup_authorized"] = True
    assert "closed_field_open:cleanup_authorized" in mod.validate_design(design)


def test_stage9229_card_keeps_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())
