from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9791_edit_localization_opaque_choice_target100m_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9791", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9791_command_is_contract_only_and_uses_stage9790_manifest():
    mod = _load()
    cmd = mod.command()
    joined = " ".join(cmd)
    assert "--contract-only" in joined
    assert str(mod.MANIFEST.relative_to(mod.ROOT)) in joined
    assert "--mode edit_localization_probe" in joined
    assert "--max-decoder-tokens 4" in joined


def test_stage9791_stage9790_source_artifacts_exist_and_shape_match():
    mod = _load()
    source = mod.load_json(mod.SOURCE_SUMMARY)
    rows = mod.read_jsonl(mod.MANIFEST)
    assert source["passed"] is True
    assert len(rows) == 60
    assert all((row.get("target") or {}).get("decoder_text") in {"A", "B", "C", "D", "E"} for row in rows)
