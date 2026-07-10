from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10131_builds_live_gold_support() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10131_true_source_backed_first_wave_gold_adjudication_support.py",
        "stage10131_live",
    )
    built = mod.build_support()
    assert built["passed"] is True
    assert built["metrics"]["first_wave_gold_tasks_enriched"] == 8
    assert built["metrics"]["gold_recommendation_drafts_written"] == 8
    assert built["metrics"]["recommended_abstain_primary_answers"] == 8


def test_stage10131_writes_temp_gold_recommendation_draft(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for rel in [
        "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier",
        "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets",
        "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff",
    ]:
        shutil.copytree(ROOT / rel, repo / rel)

    mod = _load(
        ROOT / "scripts/build_stage10131_true_source_backed_first_wave_gold_adjudication_support.py",
        "stage10131_temp",
    )
    built = mod.build_support(
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        queue_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_queue.jsonl",
        root=repo,
    )
    assert built["passed"] is True
    first = built["rows"][0]
    draft = json.loads((repo / first["gold_recommendation_draft"]).read_text(encoding="utf-8"))
    assert draft["status"] == "recommendation_draft_ready_for_human_gold_adjudication"
    assert len(draft["perspective_answer_kind_guidance"]) == 8
    assert draft["perspective_answer_kind_guidance"][-1]["recommended_primary_kind"] == "abstain"

    gold = json.loads((repo / first["gold_review"]).read_text(encoding="utf-8"))
    assert gold["draft_recommendation_path"] == first["gold_recommendation_draft"]
    assert gold["recommended_answer_kind_schema"]["abstention_insufficient_evidence"]["recommended_primary_kind"] == "abstain"


def test_stage10131_main_writes_manifest() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10131_true_source_backed_first_wave_gold_adjudication_support.py",
        "stage10131_written",
    )
    mod.main()
    manifest = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["metrics"]["first_wave_gold_tasks_enriched"] == 8
    assert manifest["metrics"]["gold_recommendation_drafts_written"] == 8
