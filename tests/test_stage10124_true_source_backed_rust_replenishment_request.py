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


def test_stage10124_builds_rust_replenishment_request() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10124_true_source_backed_rust_replenishment_request.py",
        "stage10124_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["claim_boundary"]["rust_present_in_current_source_backed_preview"] is False
    assert built["claim_boundary"]["fresh_rust_source_backed_roots_required"] is True
    assert built["current_evidence"]["main_inventory_rust_scan"]["rust_rows"] == 0
    assert built["target_replenishment"]["minimum_preview_ready_rust_bundles"] == 6
    assert built["target_replenishment"]["minimum_first_wave_review_ready_rust_bundles"] == 2
    assert len(built["upstream_source_routes"]["primary_external_graph_refs"]) == 2


def test_stage10124_points_to_external_graph_and_four_language_gap() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10124_true_source_backed_rust_replenishment_request.py",
        "stage10124_routes",
    )
    built = mod.build()
    refs = {row["path"] for row in built["upstream_source_routes"]["primary_external_graph_refs"]}
    assert "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl" in refs
    assert "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl" in refs
    assert built["claim_boundary"]["four_language_maintainer_claim_supported_now"] is False
    assert any("8-perspective maintainer bundle" in item for item in built["requirements"])


def test_stage10124_main_writes_request() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10124_true_source_backed_rust_replenishment_request.py",
        "stage10124_written",
    )
    mod.main()
    payload = json.loads(mod.REQUEST.read_text(encoding="utf-8"))
    assert payload["current_evidence"]["main_inventory_rust_scan"]["rust_rows"] == 0
    assert payload["target_replenishment"]["recommended_candidate_root_count"] == 12
