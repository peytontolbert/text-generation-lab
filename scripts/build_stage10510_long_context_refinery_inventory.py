from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10510_long_context_refinery_inventory"

SCALE_PROGRAM = ROOT / "runs/local/artifacts/stage10509_maintainer_scale_program/maintainer_scale_program.json"
STRICT_TRAIN_READY = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/strict_long_context_training_dataset_card.json"
RETRIEVAL_MIXTURE = ROOT / "runs/local/artifacts/strict_long_context_retrieval_mixture_v1/strict_long_context_retrieval_training_dataset_card.json"
SESSION_PACKS_5M = ROOT / "runs/local/artifacts/session_like_source_inventory_real/session_packs_5m/long_context_packs_summary.json"
AUGMENTED_PACKS_V3_5M = ROOT / "runs/local/artifacts/session_like_source_inventory_real/augmented_session_packs_v3_5m/long_context_packs_summary.json"
AUGMENTED_PACKS_V3_10M = ROOT / "runs/local/artifacts/session_like_source_inventory_real/augmented_session_packs_v3_10m_family_reuse/long_context_packs_summary.json"
MERGED_STRICT_PACKS_5M = ROOT / "runs/local/artifacts/merged_packable_examples/strict_commit_plus_strict_session_strict_packs_5m/strict_long_context_packs_summary.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def family_record(
    *,
    family_id: str,
    role: str,
    source_path: Path,
    metrics: dict[str, Any],
    recommended_uses: list[str],
    anti_cheat_notes: list[str],
) -> dict[str, Any]:
    return {
        "family_id": family_id,
        "role": role,
        "source_path": str(source_path.relative_to(ROOT)),
        "metrics": metrics,
        "recommended_uses": recommended_uses,
        "anti_cheat_notes": anti_cheat_notes,
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    scale_program = load_json(SCALE_PROGRAM)
    strict_train_ready = load_json(STRICT_TRAIN_READY)
    retrieval_mixture = load_json(RETRIEVAL_MIXTURE)
    session_packs_5m = load_json(SESSION_PACKS_5M)
    augmented_packs_v3_5m = load_json(AUGMENTED_PACKS_V3_5M)
    augmented_packs_v3_10m = load_json(AUGMENTED_PACKS_V3_10M)
    merged_strict_packs_5m = load_json(MERGED_STRICT_PACKS_5M)

    families = [
        family_record(
            family_id="strict_long_context_train_ready_plus_audit_v1",
            role="audited_small_train_ready_reference",
            source_path=STRICT_TRAIN_READY,
            metrics={
                "trainer_rows": strict_train_ready["compile_summary"]["trainer_rows"],
                "full_context_rows": strict_train_ready["compile_summary"]["full_context_rows"],
                "memory_rows": strict_train_ready["compile_summary"]["memory_rows"],
                "retrieval_rows": strict_train_ready["compile_summary"]["retrieval_rows"],
                "strict_eval_retrieval_rows": strict_train_ready["split_pipeline"]["audit"]["summary"]["split_counts"]["strict_eval"]["retrieval_rows"],
                "loaded_pack_count": strict_train_ready["compile_summary"]["source_summary"]["loaded_pack_count"],
            },
            recommended_uses=[
                "regression-grade long-context row schema reference",
                "small audited teacher examples for seq2seq formatting",
                "anti-cheat benchmark seed for retrieval/memory surfaces",
            ],
            anti_cheat_notes=[
                "already group-aware audited",
                "too small to serve as the main scaling corpus",
                "best treated as a schema and pressure-test reference",
            ],
        ),
        family_record(
            family_id="strict_long_context_retrieval_mixture_v1",
            role="midscale_retrieval_teacher_corpus",
            source_path=RETRIEVAL_MIXTURE,
            metrics={
                "pure_grounded_rows": retrieval_mixture["profiles"][0]["row_count"],
                "mixed_grounded_long_join_rows": retrieval_mixture["profiles"][1]["row_count"],
                "trainer_default_profiles": retrieval_mixture["trainer_default_profiles"],
            },
            recommended_uses=[
                "retrieval-target teacher supervision",
                "hard-negative mining for evidence and locality distractors",
                "option-representation invariance curriculum",
            ],
            anti_cheat_notes=[
                "profile-specific heldout handling still needs explicit maintainer-root mapping",
                "use for retrieval/evidence targets, not as direct maintainer-bundle eval claims",
            ],
        ),
        family_record(
            family_id="session_packs_5m",
            role="raw_long_context_trace_source",
            source_path=SESSION_PACKS_5M,
            metrics={
                "pack_count": session_packs_5m["pack_count"],
                "training_row_count": session_packs_5m["training_row_count"],
                "total_examples_consumed": session_packs_5m["total_examples_consumed"],
                "total_unique_chunks_across_packs": session_packs_5m["total_unique_chunks_across_packs"],
                "target_pack_tokens": session_packs_5m["target_pack_tokens"],
                "avg_pack_tokens": session_packs_5m["pack_token_count_stats"]["avg"],
            },
            recommended_uses=[
                "seed long-context trace refinery",
                "compress into maintainer next-action and evidence-chain targets",
                "mine nearby plausible wrong files/tests/evidence negatives",
            ],
            anti_cheat_notes=[
                "pack_count is currently tiny",
                "best used as raw source material, not direct train-ready corpus",
            ],
        ),
        family_record(
            family_id="augmented_session_packs_v3_5m",
            role="augmented_long_context_trace_source",
            source_path=AUGMENTED_PACKS_V3_5M,
            metrics={
                "pack_count": augmented_packs_v3_5m["pack_count"],
                "training_row_count": augmented_packs_v3_5m["training_row_count"],
                "total_examples_consumed": augmented_packs_v3_5m["total_examples_consumed"],
                "total_unique_chunks_across_packs": augmented_packs_v3_5m["total_unique_chunks_across_packs"],
                "target_pack_tokens": augmented_packs_v3_5m["target_pack_tokens"],
                "avg_pack_tokens": augmented_packs_v3_5m["pack_token_count_stats"]["avg"],
            },
            recommended_uses=[
                "broader long-context target extraction than base session_packs_5m",
                "extract multiple aligned targets from the same raw maintenance episode",
                "mine family reuse and context-compression patterns",
            ],
            anti_cheat_notes=[
                "allow_example_reuse is implicit/unknown here, so dedup and root lineage checks should run before promotion use",
            ],
        ),
        family_record(
            family_id="augmented_session_packs_v3_10m_family_reuse",
            role="large_raw_long_context_refinery_source",
            source_path=AUGMENTED_PACKS_V3_10M,
            metrics={
                "pack_count": augmented_packs_v3_10m["pack_count"],
                "training_row_count": augmented_packs_v3_10m["training_row_count"],
                "total_examples_consumed": augmented_packs_v3_10m["total_examples_consumed"],
                "total_unique_chunks_across_packs": augmented_packs_v3_10m["total_unique_chunks_across_packs"],
                "target_pack_tokens": augmented_packs_v3_10m["target_pack_tokens"],
                "avg_pack_tokens": augmented_packs_v3_10m["pack_token_count_stats"]["avg"],
                "allow_example_reuse": augmented_packs_v3_10m.get("allow_example_reuse"),
                "family_key_field": augmented_packs_v3_10m.get("family_key_field"),
            },
            recommended_uses=[
                "primary refinery source for multi-target seq2seq extraction",
                "derive compact maintainer bundles, evidence chains, verifier targets, and patch-intent targets",
                "mine hard negatives from dense family reuse neighborhoods",
            ],
            anti_cheat_notes=[
                "family reuse is enabled, so promotion-grade rows need root/repo/time dedup and lineage caps",
                "do not treat these raw packs as clean heldout eval without rebuilding explicit splits",
            ],
        ),
        family_record(
            family_id="merged_packable_examples_strict_commit_plus_strict_session_strict_packs_5m",
            role="high_quality_merged_refinery_source",
            source_path=MERGED_STRICT_PACKS_5M,
            metrics={
                "pack_count": merged_strict_packs_5m["pack_count"],
                "training_row_count": merged_strict_packs_5m["training_row_count"],
                "filtered_example_count": merged_strict_packs_5m["filtered_example_count"],
                "avg_pack_example_quality": merged_strict_packs_5m["avg_pack_example_quality"],
                "min_distinct_repos": merged_strict_packs_5m["min_distinct_repos"],
                "min_verification_rows": merged_strict_packs_5m["min_verification_rows"],
                "target_pack_tokens": merged_strict_packs_5m["target_pack_tokens"],
                "avg_pack_tokens": merged_strict_packs_5m["pack_token_count_stats"]["avg"],
            },
            recommended_uses=[
                "high-quality source for first maintainer-corpus extraction passes",
                "teacher traces for verifier-conditioned target generation",
                "repo-diverse seed pool for multilingual maintainer frontier materialization",
            ],
            anti_cheat_notes=[
                "currently one merged pack, so still a refinery source rather than a final benchmark",
                "quality is high enough to prioritize for corpus-schema prototyping",
            ],
        ),
    ]

    inventory = {
        "stage": 10510,
        "stage_name": "stage10510_long_context_refinery_inventory",
        "linked_program": str(SCALE_PROGRAM.relative_to(ROOT)),
        "program_alignment": {
            "thesis": scale_program["thesis"],
            "next_program_stages": scale_program["next_program_stages"],
        },
        "summary": {
            "source_family_count": len(families),
            "largest_raw_pack_family": "augmented_session_packs_v3_10m_family_reuse",
            "highest_quality_merged_family": "merged_packable_examples_strict_commit_plus_strict_session_strict_packs_5m",
            "smallest_audited_reference": "strict_long_context_train_ready_plus_audit_v1",
            "midscale_retrieval_teacher": "strict_long_context_retrieval_mixture_v1",
        },
        "recommended_pipeline": [
            "Use strict_long_context_train_ready_plus_audit_v1 as schema and audit reference only.",
            "Use strict_long_context_retrieval_mixture_v1 to teach retrieval/evidence targets and hard-negative handling.",
            "Use augmented_session_packs_v3_10m_family_reuse and merged strict 5m packs as the primary raw refinery for multi-target seq2seq extraction.",
            "Build promotion-grade maintainer rows only after root/repo/time dedup, leak audit, and same-manifest Gemma comparison packaging.",
        ],
        "families": families,
        "next_materialization_targets": [
            {
                "stage": "stage10511_multitarget_seq2seq_corpus_schema",
                "goal": "Define one episode -> many aligned seq2seq targets (action, evidence, verifier, patch intent, abstention).",
            },
            {
                "stage": "stage10512_python_verifier_bvc_frontier_materializer",
                "goal": "Materialize the first 100-200 row Python verifier frontier from real disjoint roots.",
            },
            {
                "stage": "stage10513_rust_citation_ef_frontier_materializer",
                "goal": "Materialize the first 50-100 row Rust evidence-citation frontier from non-tokenizers roots.",
            },
        ],
    }

    (ARTIFACT_DIR / "long_context_refinery_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
