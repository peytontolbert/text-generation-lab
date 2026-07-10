from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9955_blended_same_manifest_execution_handoff_bundle.py"
    spec = importlib.util.spec_from_file_location("stage9955", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_bundle_links_100m_gemma_and_gate():
    mod = _load()
    built = mod.build_bundle()
    assert built["passed"] is True
    assert built["metrics"]["hundred_m_future_stage"] == 9950
    assert built["metrics"]["gemma_future_stage"] == 9953
    assert built["metrics"]["row_contract_ok"] is True


def test_gemma_command_uses_local_runner_and_custom_queue():
    mod = _load()
    built = mod.build_bundle()
    cmd = built["handoff_bundle"]["gemma_execution"]["command"]
    text = " ".join(cmd)
    assert "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py" in text
    assert str(mod.GEMMA_QUEUE.relative_to(mod.ROOT)) in text
    assert str(mod.GEMMA_PACKETS.relative_to(mod.ROOT)) in text
