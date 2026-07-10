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


def test_stage10132_live_readiness_ledger() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10132_true_source_backed_first_wave_adjudication_readiness_ledger.py",
        "stage10132_live",
    )
    built = mod.build_ledger()
    assert built["passed"] is True
    assert built["metrics"]["first_wave_bundle_count"] == 8
    assert built["metrics"]["bundles_scoreable_now"] == 0
    assert built["metrics"]["bundles_with_all_support_attached"] == 8
    assert built["claim_boundary"]["machine_support_complete_but_human_signoff_open"] is True


def test_stage10132_marks_one_bundle_scoreable_in_temp_copy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for rel in [
        "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier",
        "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets",
        "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff",
        "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier",
        "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract",
        "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support",
    ]:
        shutil.copytree(ROOT / rel, repo / rel)
    _prepare_completed_bundle(repo)

    mod29 = _load(
        ROOT / "scripts/build_stage10129_true_source_backed_multilingual_adjudication_frontier.py",
        "stage10129_for_10132",
    )
    built29 = mod29.build_frontier(
        frontier_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json",
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        base_bundles_path=ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl",
        rust_bundles_path=ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl",
        root=repo,
    )
    (repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier").mkdir(parents=True, exist_ok=True)
    (repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json").write_text(
        json.dumps(built29["admitted_manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json").write_text(
        json.dumps(built29["blocked_manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mod32 = _load(
        ROOT / "scripts/build_stage10132_true_source_backed_first_wave_adjudication_readiness_ledger.py",
        "stage10132_temp",
    )
    built = mod32.build_ledger(
        frontier_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json",
        queue_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_queue.jsonl",
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        blocked_path=repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json",
        admitted_path=repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json",
        scoring_path=repo / "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract/true_source_backed_first_wave_scoring_contract.json",
        gold_support_path=repo / "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support/true_source_backed_first_wave_gold_adjudication_support.json",
        root=repo,
    )
    assert built["passed"] is True
    assert built["metrics"]["bundles_admitted_now"] == 1
    assert built["metrics"]["bundles_scoreable_now"] == 1
    assert built["metrics"]["rubric_reviews_complete"] == 1
    assert built["metrics"]["anti_cheat_reviews_complete"] == 1
    assert built["metrics"]["gold_adjudications_complete"] == 1


def test_stage10132_main_writes_ledger() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10132_true_source_backed_first_wave_adjudication_readiness_ledger.py",
        "stage10132_written",
    )
    mod.main()
    ledger = json.loads(mod.LEDGER.read_text(encoding="utf-8"))
    assert ledger["metrics"]["first_wave_bundle_count"] == 8
    assert ledger["metrics"]["bundles_scoreable_now"] == 0
