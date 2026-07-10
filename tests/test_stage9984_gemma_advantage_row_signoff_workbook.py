from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9984_gemma_advantage_row_signoff_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9984", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_workbook_materializes_row_level_signoff_queue():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9983_gemma_advantage_row_review_packets as stage9983

    stage9983.main()
    mod = _load()
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["signoff_tasks"] == 22
    assert built["metrics"]["rubric_tasks"] == 11
    assert built["metrics"]["anti_cheat_tasks"] == 11
    assert built["metrics"]["review_rows"] == 11
