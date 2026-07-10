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


def test_stage10110_builds_successor_packet() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10110_real_session_shortcut_safe_successor_packet.py",
        "stage10110",
    )
    audit, packet_rows, dropped_rows = mod.build()
    assert audit["passed"] is True
    assert len(packet_rows) >= 1
    assert audit["metrics"]["selected_language_counts"]["python"] == 30
    assert audit["metrics"]["selected_language_counts"]["c_cpp"] == 9
    assert audit["metrics"]["selected_language_counts"]["web_js_ts_html"] == 2
    assert audit["metrics"]["unmet_quotas"]["web_js_ts_html"] == 3
    assert audit["claim_boundary"]["web_successor_packet_still_underfilled"] is True
    assert audit["claim_boundary"]["rust_successor_packet_missing_by_design"] is True
    assert isinstance(dropped_rows, list)


def test_stage10110_outputs_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10110_real_session_shortcut_safe_successor_packet.py",
        "stage10110_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.PACKET.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 41
    first = rows[0]
    assert first["prompt_surface"]["return_protocol"] == "return_only_the_candidate_id"
    assert len(first["prompt_surface"]["candidate_choices"]) == 2
    assert first["hidden_metadata"]["raw_change_paths_withheld_from_prompt"] is True
