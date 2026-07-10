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


def _prepare_completed_bundle(root: Path) -> None:
    frontier = json.loads(
        (root / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json").read_text(
            encoding="utf-8"
        )
    )
    bundle_id = frontier["recommended_first_wave"]["bundle_ids"][0]
    workbook = json.loads(
        (root / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json").read_text(
            encoding="utf-8"
        )
    )
    rows = [row for row in workbook["rows"] if row["bundle_id"] == bundle_id]
    paths = {row["task"]: root / row["review_file"] for row in rows}

    rubric = json.loads(paths["expert_maintainer_rubric_review"].read_text(encoding="utf-8"))
    rubric.update(
        {
            "status": "completed",
            "bundle_valid_for_eval": True,
            "reviewer_id": "expert_001",
            "decision_rationale": "First-wave multilingual bundle is valid for bounded maintainer evaluation.",
        }
    )
    paths["expert_maintainer_rubric_review"].write_text(json.dumps(rubric, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    anti = json.loads(paths["cell_specific_anti_cheat_review"].read_text(encoding="utf-8"))
    anti.update(
        {
            "status": "completed",
            "admissible_for_same_surface_comparison": True,
            "reviewer_id": "audit_001",
            "decision_rationale": "No dominating shortcut invalidates this first-wave bundle.",
        }
    )
    paths["cell_specific_anti_cheat_review"].write_text(json.dumps(anti, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gold = json.loads(paths["perspective_gold_adjudication"].read_text(encoding="utf-8"))
    gold.update(
        {
            "status": "completed",
            "bundle_gold_ready_for_eval": True,
            "reviewer_id": "expert_001",
        }
    )
    for idx, answer in enumerate(gold["perspective_gold_answers"]):
        answer["gold_answer_kind"] = "candidate_path"
        answer["gold_answer_value"] = answer["candidate_paths"][0] if answer["candidate_paths"] else "ABSTAIN_INSUFFICIENT_EVIDENCE"
        answer["reviewer_rationale"] = f"Multilingual frontier rationale {idx + 1}"
    paths["perspective_gold_adjudication"].write_text(json.dumps(gold, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_stage10129_blocks_pending_first_wave() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10129_true_source_backed_multilingual_adjudication_frontier.py",
        "stage10129_live",
    )
    built = mod.build_frontier()
    assert built["passed"] is True
    assert built["metrics"]["admitted_bundles"] == 0
    assert built["metrics"]["blocked_bundles"] == 8
    assert built["metrics"]["blocked_language_counts"] == {
        "c_cpp": 2,
        "python": 2,
        "rust": 2,
        "web_js_ts_html": 2,
    }


def test_stage10129_admits_completed_bundle_in_temp_copy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for rel in [
        "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview",
        "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview",
        "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier",
        "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets",
        "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff",
    ]:
        shutil.copytree(ROOT / rel, repo / rel)
    _prepare_completed_bundle(repo)

    mod = _load(
        ROOT / "scripts/build_stage10129_true_source_backed_multilingual_adjudication_frontier.py",
        "stage10129_temp",
    )
    result = mod.build_frontier(
        frontier_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json",
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        base_bundles_path=repo / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl",
        rust_bundles_path=repo / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl",
        root=repo,
    )
    assert result["passed"] is True
    assert result["metrics"]["admitted_bundles"] == 1
    assert result["metrics"]["blocked_bundles"] == 7


def test_stage10129_main_writes_frontier() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10129_true_source_backed_multilingual_adjudication_frontier.py",
        "stage10129_written",
    )
    mod.main()
    blocked = json.loads(mod.BLOCKED.read_text(encoding="utf-8"))
    assert blocked["row_count"] == 8
    assert blocked["metrics"]["blocked_language_counts"] == {
        "c_cpp": 2,
        "python": 2,
        "rust": 2,
        "web_js_ts_html": 2,
    }
