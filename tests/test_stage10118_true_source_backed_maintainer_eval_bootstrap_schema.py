from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10118_builds_bootstrap_schema() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10118_true_source_backed_maintainer_eval_bootstrap_schema.py",
        "stage10118_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["claim_boundary"]["python_bootstrap_ready"] is True
    assert built["claim_boundary"]["rust_bootstrap_ready"] is False
    assert built["metrics"]["primary_language_counts"] == {"python": 49, "web_js_ts_html": 5}
    assert built["metrics"]["any_language_signal_counts"] == {"c_cpp": 9, "python": 49, "web_js_ts_html": 6}
    assert "symptom_localization" in built["root_bundle_schema"]["perspective_requirements"]


def test_stage10118_writes_schema() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10118_true_source_backed_maintainer_eval_bootstrap_schema.py",
        "stage10118_written",
    )
    mod.main()
    payload = json.loads(mod.SCHEMA.read_text(encoding="utf-8"))
    assert payload["root_bundle_schema"]["root_id_fields"] == ["example_id", "repo_id", "seed_paths"]
    assert payload["claim_boundary"]["inventory_rows_are_raw_source_examples_not_final_eval_rows"] is True
    assert "seed_change" in payload["root_bundle_schema"]["evidence_materialization_fields"]["candidate_change_surface"][0]
