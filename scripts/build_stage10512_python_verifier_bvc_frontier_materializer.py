from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10512_python_verifier_bvc_frontier_materializer"

SCHEMA = ROOT / "runs/local/artifacts/stage10511_multitarget_seq2seq_corpus_schema/multitarget_seq2seq_corpus_schema.json"
BUILDER = ROOT / "runs/local/artifacts/stage10507_python_verifier_bvc_frontier_builder/python_verifier_bvc_frontier_builder.json"
CONTEXT_BUNDLE = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/context_pack_python_replenishment_bundle.json"
CONTEXT_GOLD = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/review_packets/stage10236__code_assist__python/perspective_gold_adjudication.json"
HF_BUNDLE = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/hf_local_python_replenishment_bundle.json"
HF_GOLD = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/perspective_gold_adjudication.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_text(bundle: dict[str, Any], keys: list[str]) -> str:
    evidence = bundle.get("maintainer_visible_evidence", {})
    lines: list[str] = []
    for key in keys:
        entries = evidence.get(key, [])
        if not entries:
            continue
        sample = entries[0]
        path = sample.get("path", "unknown")
        text = sample.get("text", "")
        lines.append(f"{key} [{path}]: {text[:1200]}")
    return "\n".join(lines)


def map_target_family(answer_kind: str) -> tuple[str, str]:
    if answer_kind in {"candidate_path", "visible_evidence_key", "selected_test", "abstain"}:
        return "bounded_decision", answer_kind
    if answer_kind in {"freeform_explanation", "freeform_risk"}:
        subtype = "evidence_chain" if answer_kind == "freeform_explanation" else "repair_intent"
        return "short_structured_text", subtype
    return "short_structured_text", "repair_intent"


def materialize_bundle(
    *,
    bundle: dict[str, Any],
    gold: dict[str, Any],
    split: str,
    source_family_id: str,
    bundle_role: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gold_by_perspective = {row["perspective"]: row for row in gold["perspective_gold_answers"]}
    for perspective in bundle.get("perspective_rows", []):
        gold_row = gold_by_perspective.get(perspective["perspective"])
        if gold_row is None:
            continue
        contract = perspective["prompt_contract"]
        target_family, target_subtype = map_target_family(gold_row["gold_answer_kind"])
        input_text = (
            f"Language: python\n"
            f"View: compact_maintainer_bundle\n"
            f"Perspective: {perspective['perspective']}\n"
            f"Task: {contract['task']}\n"
            f"Evidence:\n{evidence_text(bundle, contract['visible_evidence_keys'])}\n"
            f"Candidate Paths: {json.dumps(contract['candidate_paths'])}\n"
            f"Selected Tests: {json.dumps(contract['selected_tests'])}\n"
            "Answer:\n"
        )
        rows.append(
            {
                "row_id": f"{bundle['bundle_id']}::{perspective['perspective']}::{target_family}",
                "episode_id": bundle["bundle_id"],
                "root_lineage_key": bundle["bundle_id"],
                "source_family_id": source_family_id,
                "repo_id": "code_assist",
                "repo_family": "code_assist",
                "language_family": "python",
                "split": split,
                "view_id": "compact_maintainer_bundle",
                "target_family": target_family,
                "target_subtype": target_subtype,
                "input_text": input_text,
                "target_text": gold_row["gold_answer_value"],
                "target_metadata": {
                    "answer_kind": gold_row["gold_answer_kind"],
                    "semantic_value": gold_row["gold_answer_value"],
                    "selected_tests": gold_row["selected_tests"],
                    "candidate_paths": gold_row["candidate_paths"],
                    "visible_evidence_keys": gold_row["visible_evidence_keys"],
                    "verifier_anchor_present": bool(gold_row["selected_tests"]),
                    "abstention_heavy": gold_row["gold_answer_kind"] == "abstain",
                    "bundle_role": bundle_role,
                },
                "anti_cheat": {
                    "prompt_target_leak": False,
                    "opaque_option_contract": target_family == "bounded_decision",
                    "candidate_permutation_id": None,
                    "source_heldout_admissible": False,
                    "same_root_train_eval_forbidden": True,
                    "visible_gold_string_present": False,
                },
                "source_refs": {
                    "bundle_json": str(bundle_role),
                    "gold_json": gold["draft_recommendation_path"],
                },
            }
        )
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    schema = load_json(SCHEMA)
    builder = load_json(BUILDER)
    context_bundle = load_json(CONTEXT_BUNDLE)
    context_gold = load_json(CONTEXT_GOLD)
    hf_bundle = load_json(HF_BUNDLE)
    hf_gold = load_json(HF_GOLD)

    rows = materialize_bundle(
        bundle=context_bundle,
        gold=context_gold,
        split="train_support",
        source_family_id="stage10236_context_pack_seed",
        bundle_role="execution_ready_seed",
    )
    rows.extend(
        materialize_bundle(
            bundle=hf_bundle,
            gold=hf_gold,
            split="train_support_geometry_rebuild",
            source_family_id="stage10300_hf_local_geometry_seed",
            bundle_role="geometry_rebuild_seed",
        )
    )

    summary = {
        "stage": 10512,
        "stage_name": "stage10512_python_verifier_bvc_frontier_materializer",
        "schema_path": str(SCHEMA.relative_to(ROOT)),
        "builder_path": str(BUILDER.relative_to(ROOT)),
        "materialized_row_count": len(rows),
        "materialized_verifier_rows": sum(1 for row in rows if row["target_subtype"] == "selected_test"),
        "split_counts": {
            "train_support": sum(1 for row in rows if row["split"] == "train_support"),
            "train_support_geometry_rebuild": sum(1 for row in rows if row["split"] == "train_support_geometry_rebuild"),
        },
        "frontier_gap": {
            "promotion_grade_heldout_rows": 0,
            "required_new_disjoint_roots": builder["expansion_targets"]["bundle_seed_quota"]["new_disjoint_roots_required_beyond_existing_seed"],
            "blocked_geometry_bundle_ids": [row["bundle_id"] for row in builder["blocked_geometry_reasons"]],
        },
        "claim_boundary": [
            "This is a bootstrap multi-target seed manifest, not a promotion-grade heldout frontier.",
            "All rows remain train-support-only until fresh root-disjoint verifier bundles are materialized.",
            "The hf_local rows are included as geometry-rebuild seeds and must not justify headline improvements alone.",
        ],
        "recommended_next_stage": "stage10514_multilingual_maintainer_frontier_v1_package",
        "target_families_present": sorted({row["target_family"] for row in rows}),
    }

    (ARTIFACT_DIR / "python_verifier_bvc_frontier_materializer.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (ARTIFACT_DIR / "python_verifier_bvc_seed_manifest.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
