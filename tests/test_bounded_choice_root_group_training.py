import sys

import torch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_loop import (
    _bounded_choice_contrast_spec,
    _bounded_choice_option_entries,
    _bounded_choice_same_role_listwise_loss,
    _bounded_choice_root_group_key,
    _bounded_decoder_train_batch_rows,
)


def test_root_group_key_prefers_rollout_group_then_root():
    row = {"rollout_group_id": "rollout-a", "root_id": "root-b", "row_id": "row-c"}
    assert _bounded_choice_root_group_key(row) == "rollout-a"
    assert _bounded_choice_root_group_key({"root_id": "root-b", "row_id": "row-c"}) == "root-b"
    assert _bounded_choice_root_group_key({"row_id": "row-c"}) == "row-c"


def test_web_gap_root_balanced_sampler_cycles_roots_before_duplicate_rows():
    rows = [
        {"row_id": "r1-a", "root_id": "root-1", "task_type": "evidence_citation"},
        {"row_id": "r1-b", "root_id": "root-1", "task_type": "verifier_outcome"},
        {"row_id": "r2-a", "root_id": "root-2", "task_type": "evidence_citation"},
        {"row_id": "r3-a", "root_id": "root-3", "task_type": "minimal_fix_selection"},
    ]
    batch = _bounded_decoder_train_batch_rows(rows, step=1, batch_size=3, sampler="web_gap_root_balanced")
    assert [row["root_id"] for row in batch] == ["root-1", "root-2", "root-3"]

    next_batch = _bounded_decoder_train_batch_rows(rows, step=2, batch_size=3, sampler="web_gap_root_balanced")
    assert [row["row_id"] for row in next_batch] == ["r1-b", "r2-a", "r3-a"]


def test_web_gap_same_root_grouped_sampler_packs_root_chunks():
    rows = [
        {"row_id": "r1-a", "root_id": "root-1", "task_type": "symptom_localization"},
        {"row_id": "r1-b", "root_id": "root-1", "task_type": "evidence_citation"},
        {"row_id": "r1-c", "root_id": "root-1", "task_type": "verifier_outcome"},
        {"row_id": "r2-a", "root_id": "root-2", "task_type": "symptom_localization"},
        {"row_id": "r2-b", "root_id": "root-2", "task_type": "minimal_fix_selection"},
        {"row_id": "r3-a", "root_id": "root-3", "task_type": "abstention_insufficient_evidence"},
    ]
    batch = _bounded_decoder_train_batch_rows(rows, step=1, batch_size=4, sampler="web_gap_same_root_grouped")
    assert [row["root_id"] for row in batch] == ["root-1", "root-1", "root-2", "root-2"]
    assert [row["row_id"] for row in batch] == ["r1-a", "r1-b", "r2-b", "r2-a"]

    next_batch = _bounded_decoder_train_batch_rows(rows, step=2, batch_size=4, sampler="web_gap_same_root_grouped")
    assert [row["root_id"] for row in next_batch] == ["root-1", "root-1", "root-2", "root-2"]
    assert [row["row_id"] for row in next_batch] == ["r1-c", "r1-a", "r2-b", "r2-a"]


def test_contrast_spec_reads_canonical_candidate_role_metadata():
    row = {
        "row_id": "canonical-role-row",
        "task_type": "evidence_citation",
        "bounded_choice_target_label": "B",
        "standalone_projection_source": {
            "opaque_options": [
                {
                    "label": "A",
                    "value": "role=candidate_change_surface; artifact_type=source_path; value=src/app.ts",
                    "semantic_candidate": {"role": "candidate_change_surface"},
                },
                {
                    "label": "B",
                    "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=test/app.test.ts",
                    "canonical_candidate_object": {"role": "verifier_and_test_constraint"},
                },
                {
                    "label": "C",
                    "value": "role=symptom_or_call_path_analogue; artifact_type=trace; value=call path",
                    "role": "symptom_or_call_path_analogue",
                },
            ]
        },
    }

    spec = _bounded_choice_contrast_spec(row)

    assert spec is not None
    assert spec["target_label"] == "B"
    assert spec["contrast_label"] == "A"
    assert spec["target_value"] == "verifier_and_test_constraint"
    assert spec["contrast_value"] == "candidate_change_surface"


def test_contrast_spec_uses_verifier_transition_values_with_same_role_options():
    row = {
        "row_id": "verifier-transition-row",
        "task_type": "verifier_outcome",
        "bounded_choice_target_label": "C",
        "standalone_projection_source": {
            "opaque_options": [
                {
                    "label": "A",
                    "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=fail_targeted_test_selection",
                    "semantic_candidate": {"role": "verifier_and_test_constraint", "canonical_value": "fail_targeted_test_selection"},
                },
                {
                    "label": "B",
                    "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=not_exercised_by_selected_test",
                    "semantic_candidate": {"role": "verifier_and_test_constraint", "canonical_value": "not_exercised_by_selected_test"},
                },
                {
                    "label": "C",
                    "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=pass_targeted_test_selection",
                    "semantic_candidate": {"role": "verifier_and_test_constraint", "canonical_value": "pass_targeted_test_selection"},
                },
            ]
        },
    }

    spec = _bounded_choice_contrast_spec(row)

    assert spec is not None
    assert spec["target_label"] == "C"
    assert spec["contrast_label"] == "A"
    assert spec["target_value"] == "pass_targeted_test_selection"
    assert spec["contrast_value"] == "fail_targeted_test_selection"


def test_canonical_option_entries_expose_verifier_canonical_values():
    row = {
        "standalone_projection_source": {
            "opaque_options": [
                {
                    "label": "C",
                    "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=pass_targeted_test_selection",
                    "semantic_candidate": {"role": "verifier_and_test_constraint", "canonical_value": "pass_targeted_test_selection"},
                }
            ]
        }
    }

    entries = _bounded_choice_option_entries(row)

    assert entries == [
        {
            "label": "C",
            "value": "role=verifier_and_test_constraint; artifact_type=verifier_test; value=pass_targeted_test_selection",
            "canonical_value": "pass_targeted_test_selection",
            "semantic_role": "verifier_and_test_constraint",
            "text": "",
        }
    ]


def test_same_role_listwise_scores_candidate_change_surface_options():
    class TinyTokenizer:
        pad_id = 0
        bos_id = 1
        eos_id = 2

        def encode(self, text, max_length=None):
            return {"A": [3], "B": [4]}.get(text, [0])

    row = {
        "row_id": "same-role-candidate-row",
        "task_type": "minimal_fix_selection",
        "bounded_choice_target_label": "B",
        "standalone_projection_source": {
            "opaque_options": [
                {
                    "label": "A",
                    "value": "role=candidate_change_surface; artifact_type=edit; value=wrong_fix",
                    "semantic_candidate": {"role": "candidate_change_surface", "canonical_value": "wrong_fix"},
                },
                {
                    "label": "B",
                    "value": "role=candidate_change_surface; artifact_type=edit; value=right_fix",
                    "semantic_candidate": {"role": "candidate_change_surface", "canonical_value": "right_fix"},
                },
            ]
        },
    }
    logits = torch.zeros(1, 8)
    logits[0, 4] = 2.0

    loss, card = _bounded_choice_same_role_listwise_loss(
        first_step_logits=logits,
        pooled=None,
        rows=[row],
        tokenizer=TinyTokenizer(),
        source="decoder_first_step",
    )

    assert loss is not None
    assert card["applicable_rows"] == 1
    assert card["skipped_rows"] == 0
    assert card["target_rank1_rows"] == 1
    assert card["families"] == {"minimal_fix_selection:candidate_change_surface": 1}
