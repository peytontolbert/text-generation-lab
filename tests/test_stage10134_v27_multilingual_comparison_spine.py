from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10134_builds_live_spine() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10134_v27_multilingual_comparison_spine.py",
        "stage10134_live",
    )
    built = mod.build_spine()
    assert built["passed"] is True
    assert built["metrics"]["standalone_first_wave_bundles"] == 8
    assert built["metrics"]["standalone_first_wave_scoreable_now"] == 0
    assert built["metrics"]["standalone_first_wave_comparison_ready_now"] is False
    assert built["metrics"]["harness_queue_entries"] == 36
    assert built["metrics"]["harness_aligned_cells"] == 13
    assert built["metrics"]["harness_canonical_handoff_cells"] == 4


def test_stage10134_main_writes_spine() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10134_v27_multilingual_comparison_spine.py",
        "stage10134_written",
    )
    mod.main()
    spine = json.loads(mod.SPINE.read_text(encoding="utf-8"))
    assert spine["metrics"]["standalone_first_wave_bundles"] == 8
    assert spine["metrics"]["harness_queue_entries"] == 36
