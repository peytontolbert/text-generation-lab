from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9855_direct_multisurface_abstention_honesty_exec.py"
    spec = importlib.util.spec_from_file_location("stage9855", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9855_surface_audit_extracts_exact_scores(tmp_path: Path):
    mod = _load()
    for name in mod.REQUIRED:
        (tmp_path / name).write_text("x", encoding="utf-8")
    result = {
        "runtime_executed": True,
        "train_rows": 48,
        "eval_rows": 48,
        "strict_rows": 48,
        "eval": {
            "eval": {"field_exact": {"patch_operator": {"exact": 1.0}}},
            "strict_eval": {"field_exact": {"patch_operator": {"exact": 1.0}}},
        },
    }
    audit = mod._surface_audit(result, tmp_path, "patch_operator")
    assert audit["required_row_artifacts_present"] is True
    assert audit["eval_exact"] == 1.0
    assert audit["strict_exact"] == 1.0
