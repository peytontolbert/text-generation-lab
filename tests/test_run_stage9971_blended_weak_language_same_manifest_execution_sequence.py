from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/run_stage9971_blended_weak_language_same_manifest_execution_sequence.py"
    spec = importlib.util.spec_from_file_location("stage9971_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_executable_step_ids_match_runbook():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9971_blended_weak_language_same_manifest_execution_runbook as stage9971

    stage9971.main()
    mod = _load()
    runbook = mod.load_runbook()
    assert mod.executable_step_ids(runbook) == [
        "run_stage9965_hundred_m",
        "run_stage9971_gemma",
    ]


def test_command_for_step_returns_expected_future_commands():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9971_blended_weak_language_same_manifest_execution_runbook as stage9971

    stage9971.main()
    mod = _load()
    runbook = mod.load_runbook()
    hundred_m = mod.command_for_step(runbook, "run_stage9965_hundred_m")
    gemma = mod.command_for_step(runbook, "run_stage9971_gemma")
    assert "stage9965_edit_localization_blended_weak_language_target100m_probe" in " ".join(hundred_m)
    assert "run_stage9748_standalone_gemma_queue_via_ollama.py" in " ".join(gemma)
    assert "blended_target100m::edit_localization::same_manifest_weak_language_gemma12b" in " ".join(gemma)
