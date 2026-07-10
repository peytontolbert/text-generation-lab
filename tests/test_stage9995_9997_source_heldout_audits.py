import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9995_source_overlap_eval_hacking_audit():
    module = load_module(ROOT / "scripts" / "build_stage9995_source_overlap_eval_hacking_audit.py", "stage9995")
    built = module.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["source_overlap_eval_rows"] == 39
    assert built["metrics"]["semantic_overlap_eval_rows"] == 77
    assert built["metrics"]["heldout_eval_rows_after_source_filter"] == 38


def test_stage9996_source_heldout_same_manifest_comparison_audit():
    module = load_module(ROOT / "scripts" / "build_stage9996_source_heldout_same_manifest_comparison_audit.py", "stage9996")
    built = module.build_audit()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["comparison_rows"] == 38
    assert metrics["wins_100m"] == 2
    assert metrics["wins_gemma"] == 0
    assert metrics["ties"] == 2
    assert metrics["per_language"]["python"]["exact_100m"] == 0.4
    assert metrics["per_language"]["python"]["exact_gemma"] == 0.4
    assert metrics["per_language"]["rust"]["exact_100m"] == 0.75
    assert metrics["per_language"]["rust"]["exact_gemma"] == 0.0


def test_stage9997_source_heldout_successor_request():
    module = load_module(ROOT / "scripts" / "build_stage9997_source_heldout_successor_request.py", "stage9997")
    built = module.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 78
    assert built["metrics"]["split_counts"] == {"eval": 21, "strict_eval": 17, "train": 40}
    assert built["metrics"]["removed_eval_rows"] == 39
