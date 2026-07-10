from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9863_validity_weighted_multilingual_surface_truthfulness_audit.py"
    spec = importlib.util.spec_from_file_location("stage9863", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_infer_language_prefers_nested_graph_when_top_level_unknown():
    mod = _load()
    row = {
        "language_family": "unknown",
        "graph_input": {
            "nodes": [
                {"node_type": "repo", "features": {"language_family": "rust"}},
            ]
        },
    }
    assert mod.infer_language(row) == "rust"


def test_surface_language_card_requires_all_languages_per_split():
    mod = _load()
    rows = []
    for split in ["train", "eval", "strict_eval"]:
        for language in mod.REQUIRED_LANGUAGES:
            rows.append({"split": split, "language_family": language})
    card = mod.surface_language_card(rows)
    assert card["multilingual_ready"] is True
    assert card["missing_required_languages"] == []
    assert card["split_multilingual_ready"] == {"train": True, "eval": True, "strict_eval": True}


def test_build_next_command_retargets_stage9864_edit_localization():
    mod = _load()
    ticket = {
        "surface_commands": {
            "edit_localization": [
                "python",
                "legacy_src/scripts/train_agentkernel_lite_encdec.py",
                "--mode",
                "edit_localization_probe",
                "--output-dir",
                "runs/local/artifacts/stage9860_edit_localization_target_100m_structured_tiny_probe/edit_localization_probe",
                "--run-id",
                "stage9860_edit_localization_target_100m_structured_tiny_probe",
                "--decoder-ce-weight",
                "0.0",
            ]
        }
    }
    cmd = mod.build_next_command(ticket)
    joined = " ".join(cmd)
    assert "stage9864_edit_localization_target_100m_structured_tiny_probe" in joined
    assert "--mode edit_localization_probe" in joined
    assert "--decoder-ce-weight 0.0" in joined
