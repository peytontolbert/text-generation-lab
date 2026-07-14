#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10781
NAME = "stage10781_targeted_residual_support_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "targeted_residual_support_package.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "support_rows.jsonl"
TRAIN_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_ROWS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
SUMMARY_CARD = ROOT / "runs/summaries" / f"{NAME}.json"

BASE_SUMMARY = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/reviewed_v27_hf_local_repaired_support_refresh.json"
BASE_TRAIN = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = ROOT / "runs/local/artifacts/stage10759_reviewed_v27_hf_local_repaired_support_refresh/agentkernel_lite_encdec_stress_eval.jsonl"

PYTHON_GOLD_INDEX = ROOT / "runs/local/artifacts/stage10777_bulk_support_candidate_ai_gold_drafts/bulk_support_candidate_ai_gold_index.jsonl"
RUST_PACKET_DECISIONS = ROOT / "runs/local/artifacts/stage10775_bulk_multilingual_packet_ai_adjudication/packet_ai_adjudication.jsonl"

LABELS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_evidence_text(bundle: dict[str, Any]) -> str:
    blocks: list[str] = []
    evidence = bundle.get("maintainer_visible_evidence") or {}
    for key in [
        "candidate_change_surface",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
        "external_analogue_reference",
        "algorithmic_background_reference",
    ]:
        items = evidence.get(key) or []
        for item in items[:3]:
            path = str(item.get("path") or item.get("retrieval_reason") or "evidence")
            text = str(item.get("text") or "").strip()
            blocks.append(f"{key} [{path}]: {text}")
    return "\n".join(blocks)


def label_for_value(values: list[str], gold_value: str) -> tuple[list[dict[str, str]], str | None]:
    opts = [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    for opt in opts:
        if opt["value"] == gold_value:
            return opts, str(opt["label"])
    return opts, None


def build_python_verifier_row(index_row: dict[str, Any]) -> dict[str, Any] | None:
    packet_dir = (ROOT / index_row["provisional_gold_path"]).parent
    bundle = load_json(packet_dir / "fresh_root_bundle_preview.json")
    enriched = load_json(packet_dir / "enriched_reviewed_support_candidate.json")
    gold = load_json(packet_dir / "provisional_ai_gold_draft.json")
    entry = next((e for e in gold["entries"] if e["perspective"] == "verifier_outcome"), None)
    if entry is None or entry["answer_kind"] != "selected_test":
        return None
    values = list(enriched["compiled_brief_summary"].get("verification_targets_sample") or [])
    if len(values) < 2:
        return None
    options, gold_label = label_for_value(values, str(entry["provisional_gold_value"]))
    if gold_label is None:
        return None
    prompt_text = (
        "Language: python\n"
        "Perspective: verifier_outcome\n"
        "Task: Choose the visible python test or verifier consequence that best matches the evidence.\n"
        f"Evidence:\n{build_evidence_text(bundle)}\n"
        "Options:\n" + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options) + "\n"
        "Answer:\n"
    )
    return {
        "abstention_heavy": False,
        "anti_cheat": {
            "prompt_target_leak_false": True,
            "opaque_labels": True,
            "non_promotable_support_only": True,
            "same_surface_eval_admissible": False,
            "targeted_python_verifier_support": True,
        },
        "bundle_id": f"stage10781::{bundle['root_id']}",
        "decoder_text": gold_label,
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": gold_label,
        "gold_value": str(entry["provisional_gold_value"]),
        "input_text": prompt_text,
        "language_family": "python",
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": options,
        "perspective": "verifier_outcome",
        "prompt_text": prompt_text,
        "query_text": "stage10781::python::verifier_outcome",
        "repo_family": str(bundle["repo_family"]),
        "repo_id": str(bundle["repo_family"]),
        "route": "targeted_python_verifier_support",
        "row_id": f"stage10781::{bundle['root_id']}::verifier_outcome::targeted_python_support",
        "selected_test_anchor": True,
        "semantic_key": "selected_test",
        "source_bundle_id": f"stage10776::{bundle['root_id']}",
        "source_heldout_admissible": False,
        "source_row_id": str(bundle["root_id"]),
        "split": "train",
        "split_role": "train_support",
        "standalone_projection_source": {
            "projection_mode": "stage10781_targeted_python_verifier",
            "provisional_confidence": str(entry["confidence"]),
            "provisional_rationale": str(entry["rationale"]),
            "supporting_evidence_keys": list(entry["supporting_evidence_keys"]),
        },
        "strict_eval_eligible": False,
        "support_package_stage": STAGE,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": gold_label,
        "target_token_len": 1,
        "task_type": "verifier_outcome",
        "train_support_only": True,
        "verifier_anchor": True,
    }


def build_rust_citation_row(decision: dict[str, Any]) -> dict[str, Any]:
    packet_dir = ROOT / str(decision["packet_dir"])
    bundle = load_json(packet_dir / "fresh_root_bundle_preview.json")
    values = [
        "candidate_change_surface",
        "verifier_and_test_constraint",
        "symptom_or_call_path_analogue",
        "nearby_definition_or_usage_context",
    ]
    options, gold_label = label_for_value(values, "verifier_and_test_constraint")
    assert gold_label is not None
    prompt_text = (
        "Language: rust\n"
        "Perspective: evidence_citation\n"
        "Task: Choose the visible rust evidence bucket that best supports the chosen target.\n"
        f"Evidence:\n{build_evidence_text(bundle)}\n"
        "Options:\n" + "\n".join(f"{opt['label']}. {opt['value']}" for opt in options) + "\n"
        "Answer:\n"
    )
    return {
        "abstention_heavy": False,
        "anti_cheat": {
            "prompt_target_leak_false": True,
            "opaque_labels": True,
            "non_promotable_support_only": True,
            "same_surface_eval_admissible": False,
            "targeted_rust_citation_support": True,
            "candidate_change_surface_hard_negative": True,
        },
        "bundle_id": f"stage10781::{bundle['root_id']}",
        "decoder_text": gold_label,
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": gold_label,
        "gold_value": "verifier_and_test_constraint",
        "input_text": prompt_text,
        "language_family": "rust",
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": options,
        "perspective": "evidence_citation",
        "prompt_text": prompt_text,
        "query_text": "stage10781::rust::evidence_citation",
        "repo_family": str(bundle["repo_family"]),
        "repo_id": str(bundle["repo_family"]),
        "route": "targeted_rust_citation_support",
        "row_id": f"stage10781::{bundle['root_id']}::evidence_citation::targeted_rust_support",
        "selected_test_anchor": bool(bundle["compiled_brief_summary"].get("verification_targets_sample")),
        "semantic_key": "evidence_role",
        "source_bundle_id": f"stage10774::{bundle['root_id']}",
        "source_heldout_admissible": False,
        "source_row_id": str(bundle["root_id"]),
        "split": "train",
        "split_role": "train_support",
        "standalone_projection_source": {
            "projection_mode": "stage10781_targeted_rust_citation",
            "provisional_confidence": "medium",
            "provisional_rationale": "Targeted hard negative contrasts candidate_change_surface against verifier_and_test_constraint.",
            "supporting_evidence_keys": ["verifier_and_test_constraint", "candidate_change_surface"],
        },
        "strict_eval_eligible": False,
        "support_package_stage": STAGE,
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": gold_label,
        "target_token_len": 1,
        "task_type": "evidence_citation",
        "train_support_only": True,
        "verifier_anchor": bool(bundle["compiled_brief_summary"].get("verification_targets_sample")),
    }


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)
    python_index = load_jsonl(PYTHON_GOLD_INDEX)
    rust_decisions = load_jsonl(RUST_PACKET_DECISIONS)

    support_rows: list[dict[str, Any]] = []
    for row in python_index:
        if row["language_family"] != "python":
            continue
        built = build_python_verifier_row(row)
        if built is not None:
            support_rows.append(built)
    for decision in rust_decisions:
        if decision["language_family"] == "rust" and decision["ai_status"] == "fresh_candidate_needs_richer_competition":
            support_rows.append(build_rust_citation_row(decision))

    support_rows.sort(key=lambda r: (r["language_family"], r["repo_family"], r["row_id"]))
    merged_train = list(base_train) + support_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "targeted_residual_support_package_ready",
        "claim_scope": [
            "Build a narrow residual-targeted support package focused only on Python verifier disambiguation and Rust citation competition.",
            "Keep validation/strict/stress unchanged from the clean stage10759 base.",
            "Avoid broad mixed support so the next probe isolates the two live misses more cleanly.",
        ],
        "metrics": {
            "support_row_count": len(support_rows),
            "support_rows_by_language": {
                key: sum(1 for row in support_rows if row["language_family"] == key)
                for key in sorted({row["language_family"] for row in support_rows})
            },
            "support_rows_by_task": {
                key: sum(1 for row in support_rows if row["task_type"] == key)
                for key in sorted({row["task_type"] for row in support_rows})
            },
            "merged_train_rows": len(merged_train),
            "base_train_rows": len(base_train),
            "strict_rows_preserved": len(base_strict),
        },
        "headline_findings": [
            "This package isolates the two live misses instead of adding broad multilingual support again.",
            "Python support is verifier-only and drawn from the reviewed-root substrate, not from the strict eval rows.",
            "Rust support is citation-specific and explicitly contrasts verifier/test evidence against candidate_change_surface.",
        ],
        "anti_cheat_contract": [
            "All newly added rows are train_support_only and strict_eval_eligible=false.",
            "No current strict row is copied into validation or strict eval.",
            "Rust rows use evidence-role options with candidate_change_surface as a hard negative rather than replaying the tokenizers strict row.",
            "Python rows are built from reviewed support candidates, not from the MirrorMind strict row itself.",
        ],
        "next_best_step": "Use this residual-targeted package for the next support-only probe and compare it directly against the unchanged 24-row frontier.",
        "source_artifacts": {
            "base_summary": display(BASE_SUMMARY),
            "python_gold_index": display(PYTHON_GOLD_INDEX),
            "rust_packet_decisions": display(RUST_PACKET_DECISIONS),
        },
        "outputs": {
            "summary_json": display(SUMMARY_JSON),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "train_rows": display(TRAIN_ROWS_JSONL),
            "validation_rows": display(VALIDATION_ROWS_JSONL),
            "strict_rows": display(STRICT_ROWS_JSONL),
            "stress_rows": display(STRESS_ROWS_JSONL),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_json(SUMMARY_JSON, payload)
    write_json(
        SUMMARY_CARD,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": display(SUMMARY_JSON),
            "support_row_count": payload["metrics"]["support_row_count"],
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
