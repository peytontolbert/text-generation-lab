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


def test_stage10125_builds_rust_discovery_manifest() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10125_true_source_backed_rust_root_discovery_manifest.py",
        "stage10125_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["rust_repo_count"] >= 3
    assert built["metrics"]["candidate_root_count"] >= 6
    assert built["metrics"]["review_ready_candidates"] >= 2


def test_stage10125_includes_real_rust_candidates() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10125_true_source_backed_rust_root_discovery_manifest.py",
        "stage10125_candidates",
    )
    built = mod.build()
    rows = built["rows"]
    repos = {row["repo_id"] for row in rows}
    assert "candle" in repos
    assert "tokenizers" in repos or "linux" in repos
    top_ready = [row for row in rows if row["review_ready_for_bundle_construction"]][:5]
    assert top_ready
    assert any("implementation_vs_test" in row["competition_geometries"] or "implementation_vs_build" in row["competition_geometries"] for row in top_ready)


def test_stage10125_main_writes_manifest() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10125_true_source_backed_rust_root_discovery_manifest.py",
        "stage10125_written",
    )
    mod.main()
    payload = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    assert payload["metrics"]["rust_repo_count"] >= 3
    assert payload["metrics"]["review_ready_candidates"] >= 2
