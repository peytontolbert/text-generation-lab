from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9976_real_loss_successor_edit_localization_request.py"
    spec = importlib.util.spec_from_file_location("stage9976", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_materializes_152_row_manifest():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9975_real_loss_successor_mix as stage9975

    stage9975.main()
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["rows"] == 152
    assert metrics["language_counts"]["python"] == 40
    assert metrics["language_counts"]["c_cpp"] == 46
