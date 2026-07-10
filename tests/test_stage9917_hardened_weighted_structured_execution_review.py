from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9917_hardened_weighted_structured_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9917", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9917_edit_localization_uses_longer_schedule():
    mod = _load()
    assert mod.SURFACES["edit_localization"]["max_steps"] == 32
    assert mod.SURFACES["edit_localization"]["eval_interval"] == 1
    assert mod.SURFACES["edit_localization"]["restore_best"] is True
    assert mod.SURFACES["symbol_binding"]["max_steps"] == 8


def test_stage9917_surface_rows_reads_weighted_structured_state():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    stage9916_path = root / "scripts/build_stage9916_v27_hardened_edit_localization_weighted_compiler_refresh.py"
    stage9916_spec = importlib.util.spec_from_file_location("stage9916_for_9917", stage9916_path)
    stage9916 = importlib.util.module_from_spec(stage9916_spec)
    assert stage9916_spec and stage9916_spec.loader
    stage9916_spec.loader.exec_module(stage9916)
    prepared, failures = stage9916.build_prepared_rows()
    assert failures == []
    stage9916.write_jsonl(stage9916.PREPARED, prepared)
    locked_source_ids = stage9916.load_locked_source_ids_from_exclusions(stage9916.LOCKED_EXCLUSIONS)
    buckets, compile_card = stage9916.compile_rows(
        prepared,
        allow_decoder=True,
        allow_denoise=False,
        allow_runtime=False,
        require_recovered_gates=True,
        locked_source_ids=locked_source_ids,
    )
    stage9916.COMPILED_DIR.mkdir(parents=True, exist_ok=True)
    for objective, rows in buckets.items():
        stage9916.write_jsonl(stage9916.COMPILED_DIR / f"{objective}.jsonl", rows)
    stage9916.write_json(stage9916.COMPILED_DIR / "compile_card.json", compile_card)
    mod = _load()
    rows = mod.surface_rows("edit_localization")
    train_rows = [row for row in rows if str(row.get("split") or "") == "train"]
    assert len(rows) == 64
    assert len(train_rows) == 32
