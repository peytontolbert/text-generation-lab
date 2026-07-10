from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9757_full_product_harness_review_stub_files.py"
    spec = importlib.util.spec_from_file_location("stage9757", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9757_materializes_harness_stub_files():
    mod = _load()
    packets = mod.load_jsonl(mod.SOURCE_PACKETS)
    built = mod.materialize_stub_files(packets)
    metrics = built["metrics"]
    assert built["failures"] == []
    assert metrics["packets"] == 36
    assert metrics["stub_manifests"] == 36
    assert metrics["harness_run_id_stub_files"] == 36
    assert metrics["same_task_pack_stub_files"] == 36
    assert metrics["tool_trace_stub_files"] == 36
    assert metrics["verifier_result_stub_files"] == 36
    assert metrics["patch_score_stub_files"] == 36
    assert metrics["rubric_stub_files"] == 36
    assert metrics["anti_cheat_stub_files"] == 36

    first = built["manifest_rows"][0]
    root = Path(__file__).resolve().parents[1]
    harness_run = (root / first["harness_run_id"]).read_text(encoding="utf-8")
    same_pack = json.loads((root / first["same_task_pack_as_gemma12b"]).read_text(encoding="utf-8"))
    verifier = json.loads((root / first["verifier_results"]).read_text(encoding="utf-8"))
    patch_scores = json.loads((root / first["patch_minimality_or_abstain_scores"]).read_text(encoding="utf-8"))
    rubric = json.loads((root / first["expert_maintainer_rubric_scores"]).read_text(encoding="utf-8"))
    anti = json.loads((root / first["anti_cheat_cards"]).read_text(encoding="utf-8"))
    tool_trace = (root / first["tool_trace_spans"]).read_text(encoding="utf-8")

    assert "status=pending_harness_run_id" in harness_run
    assert same_pack["status"] == "pending_same_task_pack_gemma_comparison"
    assert verifier["status"] == "pending_verifier_results"
    assert patch_scores["status"] == "pending_patch_minimality_or_abstain_scores"
    assert rubric["status"] == "pending_human_review"
    assert len(rubric["subskills"]) == 16
    assert anti["status"] == "pending_cell_specific_review"
    assert tool_trace == ""
