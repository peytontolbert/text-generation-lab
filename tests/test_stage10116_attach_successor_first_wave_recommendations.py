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


def test_stage10116_builds_live_refresh() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10116_attach_successor_first_wave_recommendations.py",
        "stage10116_live",
    )
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["first_wave_rows_enriched"] == 15
    assert built["metrics"]["recommendation_drafts_written"] == 30


def test_stage10116_recommendations_written_to_live_cards() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10116_attach_successor_first_wave_recommendations.py",
        "stage10116_written",
    )
    mod.main()
    payload = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    row = payload["rows"][0]
    rubric = json.loads((ROOT / row["rubric_review"]).read_text(encoding="utf-8"))
    anti = json.loads((ROOT / row["anti_cheat_review"]).read_text(encoding="utf-8"))
    assert rubric["draft_recommendation_path"].endswith("expert_maintainer_recommendation_draft.json")
    assert anti["draft_recommendation_path"].endswith("anti_cheat_recommendation_draft.json")
    assert "recommended_rubric_lines" in rubric
    assert "recommended_challenge_lines" in anti
