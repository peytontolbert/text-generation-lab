from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9212_repo_local_tiny_cap_adapter_audit.py"
    spec = importlib.util.spec_from_file_location("stage9212_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_path_ok_rejects_arxiv_and_outside_paths():
    mod = _load()
    assert mod.path_ok("runs/local/artifacts/example.jsonl")
    assert not mod.path_ok("/arxiv/blocked.jsonl")
    assert not mod.path_ok("../outside.jsonl")


def test_exclusive_loss_rows_requires_enabled_loss_only():
    mod = _load()
    assert mod.exclusive_loss_rows(
        [{"loss_mask": {"decoder_ce": True, "denoise_ce": False}}],
        "decoder_ce",
    )
    assert not mod.exclusive_loss_rows(
        [{"loss_mask": {"decoder_ce": True, "denoise_ce": True}}],
        "decoder_ce",
    )
    assert not mod.exclusive_loss_rows(
        [{"loss_mask": {"decoder_ce": False, "denoise_ce": False}}],
        "decoder_ce",
    )


def test_split_counts_only_counts_supported_splits():
    mod = _load()
    counts = mod.split_counts(
        [
            {"split": "train"},
            {"split": "eval"},
            {"split": "strict_eval"},
            {"split": "ignored"},
        ]
    )
    assert counts == {"train": 1, "eval": 1, "strict_eval": 1}
