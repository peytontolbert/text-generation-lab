from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9970_blended_weak_language_same_manifest_signoff_workbook.py"
    spec = importlib.util.spec_from_file_location("stage9970", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_workbook_orders_same_manifest_signoff_tasks():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9966_blended_weak_language_target100m_execution_request as stage9966
    import build_stage9967_blended_weak_language_execution_readiness_gate as stage9967
    import build_stage9968_blended_weak_language_same_manifest_handoff_bundle as stage9968
    import build_stage9969_blended_weak_language_same_manifest_review_packets as stage9969

    stage9966.main()
    stage9967.main()
    stage9968.main()
    stage9969.main()

    mod = _load()
    built = mod.build_workbook()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["signoff_tasks"] == 12
    assert metrics["attach_output_tasks"] == 4
    assert metrics["rubric_tasks"] == 4
    assert metrics["anti_cheat_tasks"] == 4
    assert metrics["unique_cells"] == 4
    assert metrics["top_queue_entry"].endswith("::attach_same_manifest_outputs")
