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


def test_stage10126_builds_rust_bundle_preview() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10126_true_source_backed_rust_root_bundle_preview.py",
        "stage10126_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["preview_root_bundles"] == 4
    assert built["metrics"]["bundle_language_counts"] == {"rust": 4}
    assert built["metrics"]["perspective_rows"] == 32


def test_stage10126_rust_bundles_preserve_bundle_contract() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10126_true_source_backed_rust_root_bundle_preview.py",
        "stage10126_contract",
    )
    built = mod.build()
    bundle = built["rows"][0]
    assert bundle["language_family"] == "rust"
    assert bundle["claim_boundary"]["preview_only"] is True
    assert len(bundle["perspective_rows"]) == 8
    assert bundle["maintainer_visible_evidence"]["candidate_change_surface"]
    assert bundle["candidate_paths"]


def test_stage10126_main_writes_preview() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10126_true_source_backed_rust_root_bundle_preview.py",
        "stage10126_written",
    )
    mod.main()
    manifest = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["metrics"]["preview_root_bundles"] == 4
    assert manifest["claim_boundary"]["source_backed_rust_present"] is True
