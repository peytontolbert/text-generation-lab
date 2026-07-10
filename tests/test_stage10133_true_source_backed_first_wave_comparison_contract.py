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


def test_stage10133_live_contract_not_ready_for_comparison() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10133_true_source_backed_first_wave_comparison_contract.py",
        "stage10133_live",
    )
    built = mod.build_contract()
    assert built["passed"] is True
    assert built["metrics"]["admitted_bundle_count"] == 0
    assert built["metrics"]["score_row_count"] == 0
    assert built["metrics"]["comparison_ready_now"] is False


def test_stage10133_temp_contract_sees_one_admitted_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for rel in [
        "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier",
        "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets",
        "runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff",
        "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier",
        "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract",
        "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support",
        "runs/local/artifacts/stage10132_true_source_backed_first_wave_adjudication_readiness_ledger",
    ]:
        shutil.copytree(ROOT / rel, repo / rel)
    _prepare_completed_bundle(repo)

    mod29 = _load(
        ROOT / "scripts/build_stage10129_true_source_backed_multilingual_adjudication_frontier.py",
        "stage10129_for_10133",
    )
    built29 = mod29.build_frontier(
        frontier_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json",
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        base_bundles_path=ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl",
        rust_bundles_path=ROOT / "runs/local/artifacts/stage10126_true_source_backed_rust_root_bundle_preview/true_source_backed_rust_root_bundle_preview.jsonl",
        root=repo,
    )
    admitted_path = repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"
    blocked_path = repo / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_blocked_manifest.json"
    admitted_path.write_text(json.dumps(built29["admitted_manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    blocked_path.write_text(json.dumps(built29["blocked_manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    mod30 = _load(
        ROOT / "scripts/build_stage10130_true_source_backed_first_wave_scoring_contract.py",
        "stage10130_for_10133",
    )
    built30 = mod30.build_contract(
        admitted_manifest_path=admitted_path,
        blocked_manifest_path=blocked_path,
        root=repo,
    )
    scoring_dir = repo / "runs/local/artifacts/stage10130_true_source_backed_first_wave_scoring_contract"
    scoring_dir.mkdir(parents=True, exist_ok=True)
    (scoring_dir / "true_source_backed_first_wave_scoring_contract.json").write_text(json.dumps(built30["contract"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (scoring_dir / "true_source_backed_first_wave_scoring_rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in built30["score_rows"]),
        encoding="utf-8",
    )

    mod32 = _load(
        ROOT / "scripts/build_stage10132_true_source_backed_first_wave_adjudication_readiness_ledger.py",
        "stage10132_for_10133",
    )
    built32 = mod32.build_ledger(
        frontier_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier.json",
        queue_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_queue.jsonl",
        workbook_path=repo / "runs/local/artifacts/stage10128_true_source_backed_multilingual_review_frontier/true_source_backed_multilingual_review_frontier_first_wave_signoff_workbook.json",
        blocked_path=blocked_path,
        admitted_path=admitted_path,
        scoring_path=scoring_dir / "true_source_backed_first_wave_scoring_contract.json",
        gold_support_path=repo / "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support/true_source_backed_first_wave_gold_adjudication_support.json",
        root=repo,
    )
    readiness_dir = repo / "runs/local/artifacts/stage10132_true_source_backed_first_wave_adjudication_readiness_ledger"
    readiness_dir.mkdir(parents=True, exist_ok=True)
    (readiness_dir / "true_source_backed_first_wave_adjudication_readiness_ledger.json").write_text(
        json.dumps(built32, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mod33 = _load(
        ROOT / "scripts/build_stage10133_true_source_backed_first_wave_comparison_contract.py",
        "stage10133_temp",
    )
    built33 = mod33.build_contract(
        admitted_path=admitted_path,
        blocked_path=blocked_path,
        scoring_path=scoring_dir / "true_source_backed_first_wave_scoring_contract.json",
        scoring_rows_path=scoring_dir / "true_source_backed_first_wave_scoring_rows.jsonl",
        gold_support_path=repo / "runs/local/artifacts/stage10131_true_source_backed_first_wave_gold_adjudication_support/true_source_backed_first_wave_gold_adjudication_support.json",
        readiness_path=readiness_dir / "true_source_backed_first_wave_adjudication_readiness_ledger.json",
    )
    assert built33["passed"] is True
    assert built33["metrics"]["admitted_bundle_count"] == 1
    assert built33["metrics"]["score_row_count"] == 8
    assert built33["metrics"]["bundles_scoreable_now"] == 1
    assert built33["metrics"]["comparison_ready_now"] is False
    assert built33["prediction_schema"]["perspective_predictions"][0]["answer_kind"].startswith("one_of_")


def test_stage10133_main_writes_contract() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10133_true_source_backed_first_wave_comparison_contract.py",
        "stage10133_written",
    )
    mod.main()
    contract = json.loads(mod.CONTRACT.read_text(encoding="utf-8"))
    assert contract["metrics"]["admitted_bundle_count"] == 0
    assert contract["metrics"]["comparison_ready_now"] is False
