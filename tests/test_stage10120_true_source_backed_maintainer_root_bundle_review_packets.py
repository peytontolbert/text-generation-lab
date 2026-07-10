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


def test_stage10120_builds_review_packets() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10120_true_source_backed_maintainer_root_bundle_review_packets.py",
        "stage10120_live",
    )
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["review_bundles"] == 8
    assert built["metrics"]["language_counts"] == {"c_cpp": 3, "python": 3, "web_js_ts_html": 2}
    assert built["metrics"]["perspective_rows_total"] == 64


def test_stage10120_writes_review_packet_files() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10120_true_source_backed_maintainer_root_bundle_review_packets.py",
        "stage10120_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.PACKETS.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 8
    packet = rows[0]["review_packet_paths"]
    rubric = json.loads((ROOT / packet["expert_maintainer_rubric_review"]).read_text(encoding="utf-8"))
    anti = json.loads((ROOT / packet["anti_cheat_review_card"]).read_text(encoding="utf-8"))
    rubric_draft = json.loads((ROOT / packet["rubric_recommendation_draft"]).read_text(encoding="utf-8"))
    anti_draft = json.loads((ROOT / packet["anti_cheat_recommendation_draft"]).read_text(encoding="utf-8"))
    assert rubric["status"] == "pending_human_review"
    assert anti["status"] == "pending_human_review"
    assert rubric_draft["status"] == "recommendation_draft_ready_for_human_rubric_review"
    assert anti_draft["status"] == "recommendation_draft_ready_for_human_anti_cheat_review"
