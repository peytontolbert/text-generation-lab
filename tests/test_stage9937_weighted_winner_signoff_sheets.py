import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9937_weighted_winner_signoff_sheets.py"
    spec = importlib.util.spec_from_file_location("stage9937_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9937_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_sheets_writes_four_signoff_sheets():
    module = _load_module()
    built = module.build_sheets()
    assert built["passed"] is True
    assert built["metrics"]["signoff_sheets_written"] == 4


def test_main_writes_summary_and_manifest(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "weighted_winner_signoff_sheets.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9937_weighted_winner_signoff_sheets.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "WEIGHTED_WINNER_SIGNOFF_SHEETS_STAGE9937.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert manifest["metrics"]["signoff_sheets_written"] == 4
