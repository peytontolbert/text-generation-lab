from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9211_repo_local_tiny_cap_adapters.py"
    spec = importlib.util.spec_from_file_location("stage9211_adapters", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_row_loss_is_exclusive_requires_only_enabled_loss():
    mod = _load()
    assert mod.row_loss_is_exclusive(
        {"loss_mask": {"decoder_ce": True, "denoise_ce": False}},
        "decoder_ce",
    )
    assert not mod.row_loss_is_exclusive(
        {"loss_mask": {"decoder_ce": True, "denoise_ce": True}},
        "decoder_ce",
    )
    assert not mod.row_loss_is_exclusive(
        {"loss_mask": {"decoder_ce": False, "denoise_ce": False}},
        "decoder_ce",
    )


def test_cap_rows_selects_exact_split_caps_and_normalizes_strict():
    mod = _load()
    rows = []
    for split in ["train", "eval", "strict"]:
        for idx in range(3):
            rows.append(
                {
                    "row_id": f"{split}_{idx}",
                    "split": split,
                    "loss_mask": {"decoder_ce": True, "denoise_ce": False},
                }
            )
    selected, audit = mod.cap_rows(
        rows,
        {"train": 2, "eval": 1, "strict_eval": 2},
        "decoder_ce",
    )
    assert audit["caps_met"] is True
    assert audit["selected_counts"] == {"train": 2, "eval": 1, "strict_eval": 2}
    assert [row["split"] for row in selected].count("strict_eval") == 2
    assert len(selected) == 5


def test_cap_rows_rejects_wrong_loss_rows():
    mod = _load()
    rows = [
        {"row_id": "a", "split": "train", "loss_mask": {"decoder_ce": False, "denoise_ce": True}},
        {"row_id": "b", "split": "train", "loss_mask": {"decoder_ce": True, "denoise_ce": False}},
    ]
    selected, audit = mod.cap_rows(rows, {"train": 1}, "decoder_ce")
    assert [row["row_id"] for row in selected] == ["b"]
    assert audit["rejected_loss_rows"] == 1
