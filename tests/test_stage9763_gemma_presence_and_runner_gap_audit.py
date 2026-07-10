from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9763_gemma_presence_and_runner_gap_audit.py"
    spec = importlib.util.spec_from_file_location("stage9763", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9763_detects_code_only_arxiv_presence_and_runner_gap(tmp_path):
    mod = _load()

    arxiv_root = tmp_path / "arxiv"
    repos = arxiv_root / "repositories"
    gemma_repo = repos / "gemma"
    (gemma_repo / "gemma/gm/text").mkdir(parents=True)
    (repos / "axolotl/examples/gemma2").mkdir(parents=True)
    (gemma_repo / "README.md").write_text("Gemma repository mirror\n", encoding="utf-8")
    (gemma_repo / "gemma/gm/text/_tokenizer.py").write_text("class Tokenizer: pass\n", encoding="utf-8")

    stage9750 = tmp_path / "stage9750.json"
    stage9750.write_text(json.dumps({
        "passed": True,
        "runner_surfaces": {
            "target_100m_probe_trainer": {"exists": True},
            "standalone_gemma_runner_present": False,
            "full_product_harness_runner_present": False,
        },
    }), encoding="utf-8")

    source_root = tmp_path / "repo"
    (source_root / "scripts").mkdir(parents=True)
    (source_root / "legacy_src").mkdir(parents=True)
    (source_root / "scripts/example.py").write_text("print('no backend here')\n", encoding="utf-8")

    mod.ARXIV_ROOT = arxiv_root
    mod.ARXIV_REPOSITORIES = repos
    mod.STAGE9750_RUNBOOK = stage9750
    mod.SOURCE_ROOTS = [source_root / "scripts", source_root / "legacy_src"]
    mod.ROOT = source_root

    audit = mod.build_audit()

    assert audit["failures"] == []
    assert audit["arxiv_scan"]["gemma_named_directory_count"] >= 2
    assert audit["arxiv_scan"]["gemma_weight_like_file_count"] == 0
    assert audit["arxiv_scan"]["gemma_12b_present"] is False
    assert audit["runner_scan"]["inference_backend_file_count"] == 0
    assert audit["metrics"]["standalone_gemma_runner_present"] is False
    assert audit["metrics"]["full_product_harness_runner_present"] is False
    assert audit["blocker_state"] == "gemma_12b_assets_missing_and_runner_missing"
