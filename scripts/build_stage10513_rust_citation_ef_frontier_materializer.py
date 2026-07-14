from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "runs/local/artifacts/stage10513_rust_citation_ef_frontier_materializer"

SCHEMA = ROOT / "runs/local/artifacts/stage10511_multitarget_seq2seq_corpus_schema/multitarget_seq2seq_corpus_schema.json"
BUILDER = ROOT / "runs/local/artifacts/stage10508_rust_citation_ef_frontier_builder/rust_citation_ef_frontier_builder.json"
FLASH_PREVIEW = ROOT / "runs/local/artifacts/stage10413_fresh_rust_flash_attn_preview/fresh_rust_flash_attn_preview_bundle.json"
FLASH_GOLD = ROOT / "runs/local/artifacts/stage10415_rust_flash_attn_review_packets/review_packets/stage10413__candle__candle-flash-attn__rust/perspective_gold_adjudication.json"
FLASH_SUMMARY = ROOT / "runs/local/artifacts/stage10416_ai_adjudicate_rust_flash_attn_bundle/rust_flash_attn_ai_adjudication_summary.json"
RUST_CITATION_ROWS = ROOT / "runs/local/artifacts/stage10452_rust_evidence_citation_candidate_atlas/rust_evidence_citation_candidate_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


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


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    schema = load_json(SCHEMA)
    builder = load_json(BUILDER)
    flash_preview = load_json(FLASH_PREVIEW)
    flash_gold = load_json(FLASH_GOLD)
    flash_summary = load_json(FLASH_SUMMARY)
    rust_citation_rows = load_jsonl(RUST_CITATION_ROWS)

    rows: list[dict[str, Any]] = []
    for gold_row in flash_gold["perspective_gold_answers"]:
        contract = next(
            row["prompt_contract"]
            for row in flash_preview["perspective_rows"]
            if row["perspective"] == gold_row["perspective"]
        )
        target_family, target_subtype = map_target_family(gold_row["gold_answer_kind"])
        input_text = (
            f"Language: rust\n"
            f"View: compact_maintainer_bundle\n"
            f"Perspective: {gold_row['perspective']}\n"
            f"Task: {contract['task']}\n"
            f"Evidence:\n{evidence_text(flash_preview, contract['visible_evidence_keys'])}\n"
            f"Candidate Paths: {json.dumps(contract['candidate_paths'])}\n"
            f"Selected Tests: {json.dumps(contract['selected_tests'])}\n"
            "Answer:\n"
        )
        rows.append(
            {
                "row_id": f"{flash_preview['bundle_id']}::{gold_row['perspective']}::{target_family}",
                "episode_id": flash_preview["bundle_id"],
                "root_lineage_key": flash_preview["bundle_id"],
                "source_family_id": "stage10413_flash_attn_reviewed_seed",
                "repo_id": flash_preview["repo_id"],
                "repo_family": "candle",
                "language_family": "rust",
                "split": "validation_seed_abstention_heavy",
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
                    "bundle_role": "reviewed_flash_attn_seed",
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
                    "bundle_json": str(FLASH_PREVIEW.relative_to(ROOT)),
                    "gold_json": str(FLASH_GOLD.relative_to(ROOT)),
                },
            }
        )

    diagnostic_seed_rows = [
        {
            "row_id": row["row_id"],
            "source_bundle_id": row["source_bundle_id"],
            "source_manifest_name": row["source_manifest_name"],
            "split": row["split"],
        }
        for row in rust_citation_rows
    ]

    summary = {
        "stage": 10513,
        "stage_name": "stage10513_rust_citation_ef_frontier_materializer",
        "schema_path": str(SCHEMA.relative_to(ROOT)),
        "builder_path": str(BUILDER.relative_to(ROOT)),
        "flash_attn_summary": {
            "bundle_id": flash_summary["bundle_id"],
            "selected_tests": flash_summary["selected_tests"],
            "abstention_gold_count": flash_summary["abstention_gold_count"],
            "non_abstention_gold_count": flash_summary["non_abstention_gold_count"],
        },
        "materialized_row_count": len(rows),
        "materialized_evidence_rows": sum(1 for row in rows if row["target_subtype"] == "visible_evidence_key"),
        "diagnostic_candle_core_seed_row_count": len(diagnostic_seed_rows),
        "claim_boundary": [
            "Flash-attn provides the first reviewed non-tokenizers Rust seed, but it is abstention-heavy and not yet a promotion-grade E-vs-F heldout frontier.",
            "Candle-core compact-bounded rows remain diagnostic train support only.",
            "Further non-tokenizers roots still need materialization before any broad Rust-vs-Gemma claim.",
        ],
        "remaining_fresh_root_queue": builder["fresh_root_priority_queue"],
        "recommended_next_stage": "stage10514_multilingual_maintainer_frontier_v1_package",
    }

    (ARTIFACT_DIR / "rust_citation_ef_frontier_materializer.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (ARTIFACT_DIR / "rust_citation_ef_seed_manifest.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with (ARTIFACT_DIR / "rust_citation_ef_diagnostic_seed_rows.jsonl").open("w", encoding="utf-8") as handle:
        for row in diagnostic_seed_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
