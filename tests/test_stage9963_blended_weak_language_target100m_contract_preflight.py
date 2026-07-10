from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9963_blended_weak_language_target100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9963", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_enabled_loss_requires_single_enabled_loss():
    mod = _load()
    assert mod.enabled_loss({"loss_mask": {"edit_localization_ce": True}}) == "edit_localization_ce"
    assert mod.enabled_loss({"loss_mask": {"edit_localization_ce": True, "symbol_binding_ce": True}}) is None


def test_materialize_manifests_reflects_successor_blended_growth():
    mod = _load()
    manifests, failures = mod.materialize_manifests()
    assert failures == []
    edit_rows = mod.read_jsonl(manifests["edit_localization"])
    assert len(edit_rows) == 120
    assert len([row for row in edit_rows if row.get("language_family") == "web_js_ts_html"]) == 45
    assert len([row for row in edit_rows if row.get("language_family") == "python"]) == 24
    assert len([row for row in edit_rows if row.get("language_family") == "c_cpp"]) == 30

