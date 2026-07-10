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


def test_stage10108_builds_successor_request() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10108_real_session_shortcut_safe_successor_request.py",
        "stage10108",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["packet_rows"] == 33
    assert built["metrics"]["carryforward_rows"] == 3
    assert built["metrics"]["quarantined_rows"] == 30
    assert built["claim_boundary"]["python_real_session_slice_must_be_rebuilt"] is True
    assert built["claim_boundary"]["only_low_risk_native_rows_can_be_carried_forward_now"] is True
    assert built["replacement_request"]["rust"]["replacement_rows_required"] >= 1


def test_stage10108_outputs_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10108_real_session_shortcut_safe_successor_request.py",
        "stage10108_written",
    )
    mod.main()
    safe_rows = [json.loads(line) for line in mod.SAFE_ROWS.read_text(encoding="utf-8").splitlines() if line.strip()]
    quarantined_rows = [json.loads(line) for line in mod.QUARANTINED_ROWS.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(safe_rows) == 3
    assert len(quarantined_rows) == 30
    assert all(row["risk_severity"] == "low" for row in safe_rows)
    assert all(row["risk_severity"] in {"high", "medium"} for row in quarantined_rows)
