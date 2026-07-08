from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9290_one_next_token_suffix_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9290", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9290_builds_one_next_token_suffix_rows():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.audit_rows(rows, {"passed": True})
    assert audit["passed"] is True
    assert audit["rows"] == 6
    assert audit["split_counts"] == {"eval": 1, "strict_eval": 1, "train": 4}
    assert audit["partial_target_visible_rows"] == 0
    assert audit["first_suffix_visible_rows"] == 0
    assert audit["invalid_one_next_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    for row in rows:
        target = row["target"]["decoder_text"]
        priming = row["model_input"]["bridge_priming_span"]
        suffix = target[len(priming):].strip()
        assert target.startswith(priming)
        assert len(mod.words(suffix)) == 1
        assert row["loss_mask"] == {"decoder_ce": False, "denoise_ce": True, "runtime_reward": False}
