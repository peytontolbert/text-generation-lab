from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9974_real_same_manifest_loss_recovery_packet.py"
    spec = importlib.util.spec_from_file_location("stage9974", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_packet_targets_real_post_gemma_losses():
    mod = _load()
    built = mod.build_packet()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["rows"] > 0
    assert "python" in metrics["language_counts"]
    assert "c_cpp" in metrics["language_counts"]
