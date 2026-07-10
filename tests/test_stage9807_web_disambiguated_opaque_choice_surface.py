from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9807_web_disambiguated_opaque_choice_surface.py"
    spec = importlib.util.spec_from_file_location("stage9807", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9807_builds_surface_with_web_disambiguators():
    mod = _load()
    audit = mod.build_surface()
    assert audit["passed"] is True
    assert audit["rows"] == 60
    web = mod.load_jsonl(mod.MANIFEST)
    web_strict = [row for row in web if row["language_family"] == "web_js_ts_html" and row["split"] == "strict_eval"]
    assert len(web_strict) == 5
    assert all((row.get("input_state") or {}).get("web_surface_disambiguator") for row in web_strict)

