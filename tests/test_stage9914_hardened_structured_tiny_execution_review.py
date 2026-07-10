from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9914_hardened_structured_tiny_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9914", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9914_surface_rows_can_read_hardened_structured_state():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    stage9913_path = root / "scripts/build_stage9913_v27_hardened_multisurface_compiler_refresh.py"
    stage9913_spec = importlib.util.spec_from_file_location("stage9913_for_9914", stage9913_path)
    stage9913 = importlib.util.module_from_spec(stage9913_spec)
    assert stage9913_spec and stage9913_spec.loader
    stage9913_spec.loader.exec_module(stage9913)
    prepared, failures = stage9913.build_prepared_rows()
    assert failures == []
    stage9913.write_jsonl(stage9913.PREPARED, prepared)
    locked_source_ids = stage9913.load_locked_source_ids_from_exclusions(stage9913.LOCKED_EXCLUSIONS)
    buckets, compile_card = stage9913.compile_rows(
        prepared,
        allow_decoder=True,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    stage9913.COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, rows in buckets.items():
        stage9913.write_jsonl(stage9913.COMPILED_DIR / f"{objective}.jsonl", rows)
    stage9913.write_json(stage9913.COMPILED_DIR / "compile_card.json", compile_card)
    mod = _load()
    rows = mod.surface_rows("edit_localization")
    assert len(rows) > 0
    assert all(str(row.get("source_skill_area") or "") == "edit_localization" for row in rows)
