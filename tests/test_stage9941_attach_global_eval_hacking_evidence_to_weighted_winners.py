import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / "scripts" / "build_stage9941_attach_global_eval_hacking_evidence_to_weighted_winners.py"
    spec = importlib.util.spec_from_file_location("stage9941_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9941_module"] = module
    spec.loader.exec_module(module)
    return module


def test_build_attachment_updates_four_winner_cards():
    module = _load_module()
    built = module.build_attachment()
    assert built["passed"] is True
    assert built["metrics"]["winner_cells_attached"] == 4
    assert built["metrics"]["global_gate_attached_cards"] == 4
    assert built["metrics"]["metadata_graph_shortcut_recommended_pass_cards"] == 4


def test_main_writes_summary_and_manifest(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(module, "MANIFEST", tmp_path / "artifacts" / "attach_global_eval_hacking_evidence_to_weighted_winners.json")
    monkeypatch.setattr(module, "SUMMARY", tmp_path / "summaries" / "stage9941_attach_global_eval_hacking_evidence_to_weighted_winners.json")
    monkeypatch.setattr(module, "DOC", tmp_path / "docs" / "ATTACH_GLOBAL_EVAL_HACKING_EVIDENCE_TO_WEIGHTED_WINNERS_STAGE9941.md")
    monkeypatch.setattr(module, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(module, "update_registry", lambda summary: None)

    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert manifest["metrics"]["winner_cells_attached"] == 4
