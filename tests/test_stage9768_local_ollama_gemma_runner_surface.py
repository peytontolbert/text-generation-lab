from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9768_local_ollama_gemma_runner_surface.py"
    spec = importlib.util.spec_from_file_location("stage9768", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9768_surface_detects_local_ollama_candidate():
    mod = _load()
    surface = mod.build_surface(
        "ollama version is 0.18.0\n",
        "NAME          ID              SIZE      MODIFIED    \ngemma3:12b    f4031aab637d    8.1 GB    4 weeks ago\n",
        True,
    )
    assert surface["failures"] == []
    assert surface["ollama_runtime"]["installed"] is True
    assert surface["ollama_runtime"]["local_gemma_model_id"] == "gemma3:12b"
    assert surface["runner_surface"]["exists"] is True
    assert surface["runner_surface"]["supports_split_filter"] is True
    assert surface["runner_surface"]["supports_max_rows"] is True
    assert surface["blocker_state"] == "local_ollama_gemma3_12b_present_runner_surface_ready"

