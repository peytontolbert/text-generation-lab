from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10100_session_inventory_audit_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10100_true_source_backed_multilingual_session_inventory_audit.py",
        "stage10100",
    )
    audit = mod.build()
    assert audit["passed"] is True
    assert audit["metrics"]["inventories_scanned"] > 0
    assert "session_like_source_inventory_real/" in audit["best_bootstrap_inventory"]["inventory_path"]
    assert audit["claim_boundary"]["true_source_backed_builder_bootstrap_ready_for_python_web_c_cpp"] is True
    assert audit["claim_boundary"]["rust_replenishment_required_before_four_language_claim"] is True
    assert audit["best_bootstrap_inventory"]["language_row_counts"]["python"] > 0
    assert audit["best_bootstrap_inventory"]["language_row_counts"]["c_cpp"] > 0
    assert audit["best_bootstrap_inventory"]["language_row_counts"]["web_js_ts_html"] > 0
    assert audit["best_bootstrap_inventory"]["language_row_counts"]["rust"] == 0
