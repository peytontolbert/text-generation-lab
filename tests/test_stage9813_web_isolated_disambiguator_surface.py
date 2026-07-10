from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9813_web_isolated_disambiguator_surface.py"
    spec = importlib.util.spec_from_file_location("stage9813", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9813_builds_surface_with_isolated_web_disambiguators():
    mod = _load()
    audit = mod.build_surface()
    assert audit["passed"] is True
    assert audit["rows"] == 60
    rows = mod.load_jsonl(mod.MANIFEST)
    web_strict = [row for row in rows if row["language_family"] == "web_js_ts_html" and row["split"] == "strict_eval"]
    assert len(web_strict) == 5
    assert all((row.get("input_state") or {}).get("web_surface_disambiguator") for row in web_strict)
    assert all((row.get("anti_cheat") or {}).get("web_disambiguator_isolated_field_only") is True for row in web_strict)
    assert all('Web disambiguator:' not in str((row.get("input_state") or {}).get("visible_locality_evidence") or '') for row in web_strict)
