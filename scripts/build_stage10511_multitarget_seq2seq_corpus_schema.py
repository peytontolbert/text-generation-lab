from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10511_multitarget_seq2seq_corpus_schema"

REFINERY_INVENTORY = ROOT / "runs/local/artifacts/stage10510_long_context_refinery_inventory/long_context_refinery_inventory.json"
PYTHON_FRONTIER = ROOT / "runs/local/artifacts/stage10507_python_verifier_bvc_frontier_builder/python_verifier_bvc_frontier_builder.json"
RUST_FRONTIER = ROOT / "runs/local/artifacts/stage10508_rust_citation_ef_frontier_builder/rust_citation_ef_frontier_builder.json"
MAINTAINER_GOLD = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/review_packets/stage10236__code_assist__python/perspective_gold_adjudication.json"
STRICT_TRAIN_READY_ROW = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/full_context_rows.jsonl"
AUGMENTED_PACK_ROW = ROOT / "runs/local/artifacts/session_like_source_inventory_real/augmented_session_packs_v3_10m_family_reuse/long_context_pack_training_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_first_jsonl(path: Path) -> dict[str, Any]:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    return json.loads(first)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    refinery = load_json(REFINERY_INVENTORY)
    python_frontier = load_json(PYTHON_FRONTIER)
    rust_frontier = load_json(RUST_FRONTIER)
    maintainer_gold = load_json(MAINTAINER_GOLD)
    strict_row = load_first_jsonl(STRICT_TRAIN_READY_ROW)
    augmented_row = load_first_jsonl(AUGMENTED_PACK_ROW)

    schema = {
        "stage": 10511,
        "stage_name": "stage10511_multitarget_seq2seq_corpus_schema",
        "purpose": [
            "Convert one long-context or maintainer episode into multiple aligned seq2seq prediction targets.",
            "Support the full 100M seq2seq prediction stack rather than a bounded-choice-only corpus.",
            "Keep source lineage, leak audits, and root-level split discipline explicit at the row schema level.",
        ],
        "episode_unit": {
            "primary_unit": "source_root_or_session_episode",
            "required_identity_fields": [
                "episode_id",
                "source_family_id",
                "repo_id",
                "repo_family",
                "language_family",
                "root_lineage_key",
                "time_or_commit_boundary",
            ],
            "split_rule": "All targets derived from one episode must stay in the same split.",
        },
        "source_filters": {
            "allow": [
                "local_repo",
                "session_trace",
                "commit_plus_verify_trace",
                "patch_plus_exec_trace",
                "reviewed_maintainer_bundle",
                "strict_long_context_row",
            ],
            "deny_or_quarantine": [
                "generic_instruction_dataset_rows without repo/session grounding",
                "rows where source_type is dataset and no maintainer repo lineage exists",
                "rows with visible gold path/test/evidence string before options",
                "rows failing prompt_target_leak audit",
                "rows without root/repo lineage keys",
            ],
            "observed_risk_example": {
                "strict_train_ready_source_type": strict_row["context_rows"][0]["source_type"],
                "augmented_pack_source_type": augmented_row["context_rows"][0]["source_type"],
                "schema_implication": "Raw long-context packs can include non-maintainer dataset chunks, so corpus extraction must filter by grounded repo/session route rather than trust every chunk in a pack.",
            },
        },
        "canonical_input_views": [
            {
                "view_id": "compact_maintainer_bundle",
                "description": "Compressed maintainer-visible bundle with candidates, selected tests, evidence keys, and bounded task prompt.",
                "best_for": ["bounded decisions", "Gemma same-surface comparison", "anti-cheat audits"],
            },
            {
                "view_id": "context_pack_state",
                "description": "Structured prompt plus retrieved context rows, suitable for next-action, evidence-chain, and verifier-target prediction.",
                "best_for": ["multi-target seq2seq", "teacher forcing from long-context traces"],
            },
            {
                "view_id": "trajectory_prefix",
                "description": "Partial session trace or patch+exec trace up to a decision point.",
                "best_for": ["next useful action", "patch intent", "abstention", "recovery decisions"],
            },
        ],
        "target_families": [
            {
                "target_family": "bounded_decision",
                "subtypes": [
                    "candidate_path",
                    "selected_test",
                    "visible_evidence_key",
                    "abstention_label",
                ],
                "length_budget_tokens": [1, 8],
                "primary_metrics": ["strict_exact", "semantic_exact", "margin_top1_top2"],
            },
            {
                "target_family": "short_structured_text",
                "subtypes": [
                    "repair_intent",
                    "evidence_chain",
                    "next_useful_action_json",
                    "verifier_conditioned_summary",
                ],
                "length_budget_tokens": [8, 64],
                "primary_metrics": ["normalized_exact", "field_semantic_match", "schema_validity"],
            },
            {
                "target_family": "constrained_generation",
                "subtypes": [
                    "one_line_rationale",
                    "patch_sketch",
                    "diff_hunk_selection",
                    "verifier_conditioned_patch_text",
                ],
                "length_budget_tokens": [64, 256],
                "primary_metrics": ["execution_backed_validity", "selected_test_pass_rate", "edit_scope_precision"],
            },
        ],
        "row_schema": {
            "required_fields": [
                "row_id",
                "episode_id",
                "root_lineage_key",
                "split",
                "view_id",
                "target_family",
                "target_subtype",
                "input_text",
                "target_text",
                "target_metadata",
                "anti_cheat",
                "source_refs",
            ],
            "anti_cheat_fields": [
                "prompt_target_leak",
                "opaque_option_contract",
                "candidate_permutation_id",
                "source_heldout_admissible",
                "same_root_train_eval_forbidden",
                "visible_gold_string_present",
            ],
            "target_metadata_fields": [
                "answer_kind",
                "semantic_value",
                "selected_tests",
                "candidate_paths",
                "visible_evidence_keys",
                "verifier_anchor_present",
                "abstention_heavy",
            ],
        },
        "maintainer_alignment_example": {
            "bundle_id": maintainer_gold["bundle_id"],
            "perspectives_available": [row["perspective"] for row in maintainer_gold["perspective_gold_answers"]],
            "verifier_example": next(
                row for row in maintainer_gold["perspective_gold_answers"] if row["perspective"] == "verifier_outcome"
            ),
            "schema_use": "This gold format becomes the canonical source for bounded_decision and short_structured_text targets derived from reviewed maintainer bundles.",
        },
        "frontier_alignment": {
            "python_required_row_contract": python_frontier["required_row_contract"],
            "rust_required_row_contract": rust_frontier["required_row_contract"],
            "implication": "The corpus schema must preserve these heldout-eval contracts while also enabling broader seq2seq targets from the same episodes.",
        },
        "materialization_rules": [
            "One episode may emit many targets, but every target inherits the same root_lineage_key and split.",
            "Do not materialize freeform targets from episodes that fail bounded anti-cheat gates.",
            "Prefer reviewed maintainer bundles and filtered long-context traces before raw augmented session packs.",
            "Require a traced or selected-test anchor for verifier-related targets.",
            "Use long-context refinery families primarily to produce new episode candidates, then compact them into maintainer-grade rows.",
        ],
        "recommended_next_steps": [
            "stage10512_python_verifier_bvc_frontier_materializer",
            "stage10513_rust_citation_ef_frontier_materializer",
            "stage10514_multilingual_maintainer_frontier_v1_package",
            "stage10515_multitarget_seq2seq_training_manifest_v1",
        ],
        "linked_inputs": {
            "refinery_inventory": str(REFINERY_INVENTORY.relative_to(ROOT)),
            "python_frontier_builder": str(PYTHON_FRONTIER.relative_to(ROOT)),
            "rust_frontier_builder": str(RUST_FRONTIER.relative_to(ROOT)),
            "maintainer_gold_example": str(MAINTAINER_GOLD.relative_to(ROOT)),
        },
    }

    (ARTIFACT_DIR / "multitarget_seq2seq_corpus_schema.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
