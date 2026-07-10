from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9753_supported_standalone_review_stub_files.py"
    spec = importlib.util.spec_from_file_location("stage9753", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9753_materializes_review_stub_files(tmp_path: Path):
    mod = _load()
    packets = mod.load_jsonl(mod.SOURCE_PACKETS)
    built = mod.materialize_stub_files(packets)
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["packets"] == 13
    assert metrics["rubric_stub_files"] == 13
    assert metrics["anti_cheat_stub_files"] == 13
    assert metrics["gemma_stub_files"] == 13
    assert metrics["checkpoint_stub_files"] == 13

    first = built["manifest_rows"][0]
    root = Path(__file__).resolve().parents[1]
    rubric = json.loads((root / first["expert_maintainer_rubric_scores"]).read_text(encoding="utf-8"))
    anti = json.loads((root / first["anti_cheat_cards"]).read_text(encoding="utf-8"))
    gemma = json.loads((root / first["same_prompt_surface_gemma12b_outputs"]).read_text(encoding="utf-8"))
    checkpoint = (root / first["frozen_export_or_checkpoint_hash"]).read_text(encoding="utf-8")

    assert rubric["status"] == "pending_human_review"
    assert rubric["passed"] is False
    assert len(rubric["subskills"]) == 16
    assert anti["status"] == "pending_cell_specific_review"
    assert anti["global_stage9717_gate_passed"] is True
    assert len(anti["challenge_families"]) == 6
    assert gemma["status"] == "pending_gemma_execution"
    assert gemma["authorized_now"] is False
    assert "status=pending_checkpoint_or_export_hash" in checkpoint
