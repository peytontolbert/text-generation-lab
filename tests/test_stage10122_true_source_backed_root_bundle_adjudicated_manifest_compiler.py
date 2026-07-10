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


def _prepare_complete_reviews(root: Path) -> None:
    workbook = json.loads(
        (root / "runs/local/artifacts/stage10121_true_source_backed_root_bundle_signoff_workbook/true_source_backed_root_bundle_signoff_workbook.json").read_text(
            encoding="utf-8"
        )
    )
    by_bundle: dict[str, dict[str, Path]] = {}
    for row in workbook["rows"]:
        bundle = by_bundle.setdefault(row["bundle_id"], {})
        bundle[row["task"]] = root / row["review_file"]

    target = by_bundle[next(iter(by_bundle))]

    rubric = json.loads(target["expert_maintainer_rubric_review"].read_text(encoding="utf-8"))
    rubric.update(
        {
            "status": "completed",
            "bundle_valid_for_eval": True,
            "reviewer_id": "expert_001",
            "decision_rationale": "Maintainer-visible evidence is sufficient for bounded adjudication.",
        }
    )
    target["expert_maintainer_rubric_review"].write_text(json.dumps(rubric, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    anti_cheat = json.loads(target["cell_specific_anti_cheat_review"].read_text(encoding="utf-8"))
    anti_cheat.update(
        {
            "status": "completed",
            "admissible_for_same_surface_comparison": True,
            "reviewer_id": "audit_001",
            "decision_rationale": "No deterministic shortcut dominates the bounded evidence surface.",
        }
    )
    target["cell_specific_anti_cheat_review"].write_text(
        json.dumps(anti_cheat, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    gold = json.loads(target["perspective_gold_adjudication"].read_text(encoding="utf-8"))
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
        answer["reviewer_rationale"] = f"Human adjudication rationale {idx + 1}"
    target["perspective_gold_adjudication"].write_text(json.dumps(gold, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_stage10122_blocks_pending_live_packets() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler.py",
        "stage10122_live",
    )
    built = mod.build_adjudicated_manifest()
    assert built["passed"] is True
    assert built["metrics"]["admitted_bundles"] == 0
    assert built["metrics"]["blocked_bundles"] == 8
    assert built["metrics"]["blocked_reason_counts"]["rubric_status_not_completed"] == 8
    assert built["metrics"]["blocked_reason_counts"]["anti_cheat_status_not_completed"] == 8
    assert built["metrics"]["blocked_reason_counts"]["gold_status_not_completed"] == 8


def test_stage10122_admits_completed_bundle_in_temp_copy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview", repo / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview")
    shutil.copytree(ROOT / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets", repo / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets")
    shutil.copytree(ROOT / "runs/local/artifacts/stage10121_true_source_backed_root_bundle_signoff_workbook", repo / "runs/local/artifacts/stage10121_true_source_backed_root_bundle_signoff_workbook")
    _prepare_complete_reviews(repo)

    mod = _load(
        ROOT / "scripts/build_stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler.py",
        "stage10122_temp",
    )
    built = mod.build_adjudicated_manifest(
        root=repo,
        review_manifest_path=repo / "runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/true_source_backed_maintainer_root_bundle_review_packet_manifest.json",
        signoff_workbook_path=repo / "runs/local/artifacts/stage10121_true_source_backed_root_bundle_signoff_workbook/true_source_backed_root_bundle_signoff_workbook.json",
        source_bundles_path=repo / "runs/local/artifacts/stage10119_true_source_backed_maintainer_root_bundle_preview/true_source_backed_maintainer_root_bundle_preview.jsonl",
    )
    assert built["passed"] is True
    assert built["metrics"]["admitted_bundles"] == 1
    assert built["metrics"]["blocked_bundles"] == 7
    admitted = built["admitted_manifest"]["rows"][0]
    assert admitted["rubric_review"].endswith("expert_maintainer_rubric_review.json")
    assert admitted["anti_cheat_review"].endswith("anti_cheat_review_card.json")
    assert admitted["perspective_gold_adjudication"].endswith("perspective_gold_adjudication.json")


def test_stage10122_main_writes_manifests() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler.py",
        "stage10122_written",
    )
    mod.main()
    admitted = json.loads(mod.ADMITTED.read_text(encoding="utf-8"))
    blocked = json.loads(mod.BLOCKED.read_text(encoding="utf-8"))
    assert admitted["row_count"] == 0
    assert blocked["row_count"] == 8
