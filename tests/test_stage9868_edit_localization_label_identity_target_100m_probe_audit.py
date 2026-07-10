from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9868_edit_localization_label_identity_target_100m_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9868", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9868_metrics_capture_last_vocab_label_collapse():
    mod = _load()
    metrics = mod.extract_metrics()
    assert metrics["mode"] == "edit_localization_probe"
    assert metrics["probe_scale"] == "target_100m"
    assert metrics["first_vocab_label"] == "K"
    assert metrics["last_vocab_label"] == "Z"
    assert metrics["collapsed_to_first_vocab_label"] is False
    assert metrics["collapsed_to_last_vocab_label"] is True
    assert metrics["eval_edit_localization_exact"] == 0.0
    assert metrics["strict_edit_localization_exact"] == 0.0


def test_stage9868_artifacts_exist_and_are_nonempty():
    mod = _load()
    artifacts = mod.artifact_status()
    missing = [name for name, status in artifacts.items() if not status["exists"] or status["bytes"] <= 0]
    assert missing == []
