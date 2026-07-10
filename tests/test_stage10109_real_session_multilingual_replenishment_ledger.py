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


def test_stage10109_builds_replenishment_ledger() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10109_real_session_multilingual_replenishment_ledger.py",
        "stage10109",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["inventory_rows"] == 56
    assert built["replacement_supply"]["python"]["supported_episode_count"] >= 1
    assert built["replacement_supply"]["web_js_ts_html"]["supported_episode_count"] >= 1
    assert built["replacement_supply"]["c_cpp"]["supported_episode_count"] >= 1
    assert built["replacement_supply"]["rust"]["supported_episode_count"] == 0
    assert built["claim_boundary"]["rust_real_source_supply_still_zero"] is True


def test_stage10109_outputs_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10109_real_session_multilingual_replenishment_ledger.py",
        "stage10109_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 1
    langs = {row["language_family"] for row in rows}
    assert "python" in langs
    assert "web_js_ts_html" in langs
    assert "c_cpp" in langs
