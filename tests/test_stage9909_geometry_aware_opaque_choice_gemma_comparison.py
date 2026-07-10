from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9909_geometry_aware_opaque_choice_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9909", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9909"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9909_prompt_hides_valid_label_line():
    mod = _load()
    row = {
        "input_state": {"candidate_choices": ["option A: x"]},
        "target": {"decoder_text": "A"},
    }
    prompt = mod.build_prompt(row)
    assert "Valid labels:" not in prompt
    assert "option label" in prompt


def test_stage9909_dry_run_shapes_results():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    stage9907_path = root / "scripts/build_stage9907_geometry_aware_opaque_choice_manifest.py"
    stage9907_spec = importlib.util.spec_from_file_location("stage9907_for_9909", stage9907_path)
    stage9907 = importlib.util.module_from_spec(stage9907_spec)
    assert stage9907_spec and stage9907_spec.loader
    stage9907_spec.loader.exec_module(stage9907)
    stage9907_rows = stage9907.build_rows()
    stage9907.write_jsonl(stage9907.MANIFEST, stage9907_rows)
    mod = _load()
    audit, rows = mod.build_audit(execute_gemma=False)
    assert audit["passed"] is True
    assert audit["gemma_executed"] is False
    assert len(audit["comparisons"]) == 8
    assert len(rows) == 32
