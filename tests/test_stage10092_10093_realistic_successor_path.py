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


def test_stage10092_shortcut_audit_builds() -> None:
    mod = _load(ROOT / "scripts/build_stage10092_canonical_source_heldout_realistic_shell_shortcut_audit.py", "stage10092")
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["heldout_rows"] == 55
    assert built["metrics"]["heldout_shell_signature_majority_lookup_exact"] == 1.0
    assert built["claim_boundary"]["expert_maintainer_realism_supported"] is False
    assert built["metrics"]["per_language_shell_metrics"]["python"]["heldout_rows"] == 11


def test_stage10093_successor_request_builds() -> None:
    stage10092 = _load(ROOT / "scripts/build_stage10092_canonical_source_heldout_realistic_shell_shortcut_audit.py", "stage10092_req")
    packet = stage10092.build()
    stage10092.write_json(stage10092.PACKET, packet)
    stage10093 = _load(ROOT / "scripts/build_stage10093_canonical_source_heldout_realistic_source_backed_successor_request.py", "stage10093")
    request, rows = stage10093.build()
    assert request["passed"] is True
    assert request["metrics"]["heldout_rows_requested"] == 55
    assert request["metrics"]["compare_subset_split_counts"] == {"eval": 38, "strict_eval": 17}
    assert len(rows) == 55
    assert all(row["source_materialization_requirements"]["failure_text_from_visible_failure_or_assertion"] is True for row in rows)
    assert request["claim_boundary"]["ready_for_expert_maintainer_comparison"] is False


def test_stage10093_rows_cover_languages() -> None:
    stage10093 = _load(ROOT / "scripts/build_stage10093_canonical_source_heldout_realistic_source_backed_successor_request.py", "stage10093_rows")
    request, rows = stage10093.build()
    langs = {row["language_family"] for row in rows}
    assert langs == {"python", "rust", "c_cpp", "web_js_ts_html"}
    counts = request["metrics"]["languages"]
    assert counts["python"] == 11
    assert counts["c_cpp"] == 20
    assert counts["rust"] == 4
    assert counts["web_js_ts_html"] == 20
