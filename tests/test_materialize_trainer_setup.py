from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.materialize_trainer_setup import (  # noqa: E402
    build_trainer_input_rows,
    materialize_joined_route_cards,
    materialize_loss_masks,
    materialize_training_setup,
)


def objective_rows() -> list[dict[str, object]]:
    return [
        {
            "row_id": "decoder_train_1",
            "semantic_key": "sem:decoder:1",
            "source_manifest": "runs/local/artifacts/stage_x/objective_rows.jsonl",
            "source_stage": 9200,
            "objective_family": "bounded_decoder_ce",
            "split": "train",
            "language_family": "python",
            "surface": "PATCH_HUNK_ARGS",
            "task_phase": "repair",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": True,
            "decode_allowed": True,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "apply the one-line patch"},
        },
        {
            "row_id": "structured_eval_1",
            "semantic_key": "sem:structured:1",
            "source_manifest": "runs/local/artifacts/stage_x/objective_rows.jsonl",
            "source_stage": 9200,
            "objective_family": "intent_to_build_strategy",
            "split": "eval",
            "language_family": "python",
            "surface": "MAINTAINER_EXPLANATION_ARGS",
            "task_phase": "analysis",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": False,
            "decode_allowed": False,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "structured label target"},
            "surface_role": "maintainer_explanation",
        },
        {
            "row_id": "denoise_strict_1",
            "semantic_key": "sem:denoise:1",
            "source_manifest": "runs/local/artifacts/stage_x/objective_rows.jsonl",
            "source_stage": 9200,
            "objective_family": "output_repair_denoise",
            "split": "strict_eval",
            "language_family": "python",
            "surface": "REPAIR_PLAN_ARGS",
            "task_phase": "repair",
            "state_schema_ref": "repo_state_graph_v1",
            "evidence_state": "direct_present",
            "decoder_budget_ok": True,
            "decode_allowed": False,
            "target_length_bucket": "bounded",
            "target": {"decoder_text": "denoise target"},
        },
    ]


def judge_rows() -> list[dict[str, object]]:
    rows = []
    for row in objective_rows():
        rows.append(
            {
                "row_id": row["row_id"],
                "semantic_key": row["semantic_key"],
                "judge_reasons": [],
                "anti_cheat": {
                    "label_leak_checked": True,
                    "shortcut_baseline_max": 0.21,
                    "split_overlap_checked": True,
                    "raw_text_forbidden_checked": True,
                    "authority_closed_checked": True,
                    "target_not_in_input_checked": True,
                },
                "authority": {},
            }
        )
    return rows


def ranker_rows() -> list[dict[str, object]]:
    return [
        {
            "row_id": "decoder_train_1",
            "semantic_key": "sem:decoder:1",
            "risk_bucket": "KEEP_BOUNDED_DECODER",
            "recommended_action": "KEEP_BOUNDED_DECODER",
            "reasons": [],
        },
        {
            "row_id": "structured_eval_1",
            "semantic_key": "sem:structured:1",
            "risk_bucket": "KEEP_STRUCTURED",
            "recommended_action": "KEEP_STRUCTURED",
            "reasons": [],
        },
        {
            "row_id": "denoise_strict_1",
            "semantic_key": "sem:denoise:1",
            "risk_bucket": "USE_FOR_DENOISE_REPAIR",
            "recommended_action": "USE_FOR_DENOISE_REPAIR",
            "reasons": [],
        },
    ]


def test_route_card_materialization_joins_real_rows() -> None:
    cards, audit = materialize_joined_route_cards(objective_rows(), judge_rows(), ranker_rows())

    assert audit["missing_judge_rows"] == 0
    assert audit["missing_ranker_rows"] == 0
    assert audit["validation_failure_count"] == 0
    assert len(cards) == 3
    assert {card["route"] for card in cards} == {
        "KEEP_BOUNDED_DECODER",
        "KEEP_STRUCTURED",
        "USE_FOR_DENOISE_REPAIR",
    }


def test_loss_masks_use_canonical_training_losses() -> None:
    route_cards, _ = materialize_joined_route_cards(objective_rows(), judge_rows(), ranker_rows())
    loss_masks, audit = materialize_loss_masks(route_cards, objective_rows())

    assert audit["missing_objective_rows"] == 0
    assert audit["forbidden_enabled_count"] == 0

    by_id = {row["row_id"]: row for row in loss_masks}
    assert by_id["decoder_train_1"]["decoder_ce_allowed"] is True
    assert by_id["decoder_train_1"]["loss_mask"]["decoder_ce"] is True
    assert by_id["structured_eval_1"]["structured_aux_allowed"] is True
    assert by_id["structured_eval_1"]["loss_mask"]["surface_role_ce"] is True
    assert by_id["denoise_strict_1"]["denoise_ce_allowed"] is True
    assert by_id["denoise_strict_1"]["loss_mask"]["denoise_ce"] is True
    assert by_id["structured_eval_1"]["runtime_reward_allowed"] is False


def test_trainer_rows_include_loss_masks_and_targets() -> None:
    route_cards, _ = materialize_joined_route_cards(objective_rows(), judge_rows(), ranker_rows())
    loss_masks, _ = materialize_loss_masks(route_cards, objective_rows())
    trainer_rows, audit = build_trainer_input_rows(objective_rows(), route_cards, loss_masks)

    assert audit["trainer_rows"] == 3
    by_id = {row["row_id"]: row for row in trainer_rows}
    assert by_id["decoder_train_1"]["loss_mask"]["decoder_ce"] is True
    assert by_id["structured_eval_1"]["loss_mask"]["surface_role_ce"] is True
    assert by_id["denoise_strict_1"]["loss_mask"]["denoise_ce"] is True
    assert by_id["decoder_train_1"]["target"]["decoder_text"] == "apply the one-line patch"


def test_materialize_training_setup_writes_end_to_end_outputs(tmp_path: Path) -> None:
    result = materialize_training_setup(
        objective_rows(),
        judge_rows(),
        ranker_rows(),
        output_dir=tmp_path,
    )

    assert result["passed"] is True
    assert (tmp_path / "route_cards.jsonl").exists()
    assert (tmp_path / "loss_mask_cards.jsonl").exists()
    assert (tmp_path / "trainer_rows.jsonl").exists()
    assert (tmp_path / "trainer_dry_run_input.json").exists()
    commands = result["trainer_input"]["recommended_commands"]
    modes = {item["mode"] for item in commands}
    assert "bounded_decoder_ce_probe" in modes
    assert "structured_policy_probe" in modes
    assert "denoise_repair_probe" in modes
