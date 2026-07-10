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


def test_stage10119_builds_preview() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10119_true_source_backed_maintainer_root_bundle_preview.py",
        "stage10119_live",
    )
    built = mod.build()
    manifest = built["manifest"]
    assert manifest["passed"] is True
    assert manifest["metrics"]["preview_root_bundles"] == 8
    assert manifest["metrics"]["bundle_language_counts"] == {"c_cpp": 3, "python": 3, "web_js_ts_html": 2}
    assert manifest["metrics"]["perspective_rows"] == 64


def test_stage10119_writes_bundle_preview() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10119_true_source_backed_maintainer_root_bundle_preview.py",
        "stage10119_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.BUNDLES.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 8
    assert len(rows[0]["perspective_rows"]) == 8
    assert rows[0]["claim_boundary"]["supports_training_or_scoring_now"] is False
    assert "candidate_change_surface" in rows[0]["maintainer_visible_evidence"]
