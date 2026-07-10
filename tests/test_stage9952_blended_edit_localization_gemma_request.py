from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9952_blended_edit_localization_gemma_request.py"
    spec = importlib.util.spec_from_file_location("stage9952", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_queue_preserves_blended_row_counts_and_local_gemma_ready():
    mod = _load()
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["queue_entries"] == 1
    assert built["metrics"]["edit_localization_rows"] == 72
    assert built["metrics"]["edit_localization_web_rows"] == 27
    assert built["metrics"]["same_manifest_compare_rows"] == 48
    assert built["metrics"]["local_gemma3_12b_present"] is True
    packet = built["packets"][0]
    assert len(packet["same_surface_packet"]["row_ids"]) == 48
    assert packet["same_surface_packet"]["surface_hash"]


def test_runner_command_uses_custom_queue_and_packets():
    mod = _load()
    built = mod.build_queue()
    cmd = built["runner_command"]
    text = " ".join(cmd)
    assert "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py" in text
    assert str(mod.QUEUE.relative_to(mod.ROOT)) in text
    assert str(mod.PACKETS.relative_to(mod.ROOT)) in text
    assert mod.CELL_KEY in text
