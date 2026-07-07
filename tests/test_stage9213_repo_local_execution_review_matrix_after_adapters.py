from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9213_repo_local_execution_review_matrix_after_adapters.py"
    spec = importlib.util.spec_from_file_location("stage9213_matrix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_path_is_repo_local_rejects_arxiv_and_traversal():
    mod = _load()
    assert mod.path_is_repo_local("runs/local/artifacts/example.jsonl")
    assert not mod.path_is_repo_local("/arxiv/blocked.jsonl")
    assert not mod.path_is_repo_local("../outside.jsonl")


def test_denoise_review_remains_schema_blocked_even_with_adapter():
    mod = _load()
    review = mod.adapted_review(
        "denoise_repair_probe",
        {
            "passed": True,
            "output_manifest": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/denoise_tiny_cap_manifest.jsonl",
        },
        {"denoise_repair_probe": {"passed": True}},
    )
    assert review["status"] == "requires_dedicated_one_run_ticket_schema"
    assert "dedicated_one_run_ticket_schema_missing" in review["review_failures"]


def test_bounded_review_can_be_future_candidate_with_adapter_and_auth():
    mod = _load()
    review = mod.adapted_review(
        "bounded_decoder_ce_probe",
        {
            "passed": True,
            "output_manifest": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/bounded_decoder_tiny_cap_manifest.jsonl",
        },
        {"bounded_decoder_ce_probe": {"passed": True}},
    )
    assert review["status"] == "future_review_candidate"
    assert review["review_failures"] == []
