#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10769
NAME = "stage10769_enriched_support_candidate_training_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "enriched_support_candidate_training_package.json"
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
GOLD_INDEX = ROOT / "runs/local/artifacts/stage10768_support_candidate_ai_gold_drafts/support_candidate_ai_gold_index.jsonl"

LABELS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M"]
SUPPORTED_PERSPECTIVES = {
    "candidate_path": {"symptom_localization", "patch_impact"},
    "evidence_role": {"evidence_citation", "alternative_hypothesis_elimination"},
    "selected_test": {"verifier_outcome"},
    "abstain": {"abstention_insufficient_evidence"},
}


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


def perspective_task(language_family: str, perspective: str) -> str:
    lang = {"python": "python", "c_cpp": "C/C++"}[language_family]
    tasks = {
        "symptom_localization": f"Choose the most likely {lang} edit target from the visible evidence.",
        "evidence_citation": f"Choose the visible {lang} evidence bucket that best supports the chosen target.",
        "alternative_hypothesis_elimination": f"Choose the visible {lang} evidence bucket that best argues against a tempting alternative target.",
        "patch_impact": f"Compare candidate {lang} edits by likely behavior change and risk.",
        "verifier_outcome": f"Choose the visible {lang} test or verifier consequence that best matches the evidence.",
        "abstention_insufficient_evidence": f"Decide whether the visible {lang} evidence is enough for a singleton answer or whether abstention is more honest.",
    }
    return tasks[perspective]


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


def opaque_options_for_entry(entry: dict[str, Any], enriched: dict[str, Any]) -> list[dict[str, str]] | None:
    answer_kind = str(entry["answer_kind"])
    gold_value = str(entry["provisional_gold_value"])
    if answer_kind == "candidate_path":
        values = [opt["value"] for opt in enriched["competition_contract"]["singleton_candidate_options"]]
        if gold_value not in values:
            return None
        return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    if answer_kind == "evidence_role":
        values = ["candidate_change_surface", "nearby_definition_or_usage_context", "symptom_or_call_path_analogue", "verifier_and_test_constraint"]
        return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    if answer_kind == "selected_test":
        values = list(enriched["compiled_brief_summary"].get("verification_targets_sample") or [])
        if len(values) < 2 or gold_value not in values:
            return None
        return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    if answer_kind == "abstain":
        values = [opt["value"] for opt in enriched["competition_contract"]["abstain_candidate_options"]]
        if "ABSTAIN_INSUFFICIENT_EVIDENCE" not in values:
            return None
        return [{"label": LABELS[idx], "value": value} for idx, value in enumerate(values)]
    return None


def label_for_value(options: list[dict[str, str]], gold_value: str) -> str | None:
    for opt in options:
        if opt["value"] == gold_value:
            return str(opt["label"])
    return None


def build_row(index_row: dict[str, Any], bundle: dict[str, Any], enriched: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(entry["perspective"])
    answer_kind = str(entry["answer_kind"])
    if perspective not in SUPPORTED_PERSPECTIVES.get(answer_kind, set()):
        return None
    options = opaque_options_for_entry(entry, enriched)
    if not options:
        return None
    gold_value = str(entry["provisional_gold_value"])
    gold_label = label_for_value(options, gold_value)
    if gold_label is None:
        return None

    evidence_text = build_evidence_text(bundle)
    option_lines = "\n".join(f"{opt['label']}. {opt['value']}" for opt in options)
    language_family = str(bundle["language_family"])
    prompt_text = (
        f"Language: {language_family}\n"
        f"Perspective: {perspective}\n"
        f"Task: {perspective_task(language_family, perspective)}\n"
        f"Evidence:\n{evidence_text}\n"
        f"Options:\n{option_lines}\n"
        f"Answer:\n"
    )
    anti_cheat = {
        "preview_support_candidate": True,
        "provisional_ai_gold": True,
        "prompt_target_leak_false": True,
        "opaque_labels": True,
        "non_promotable_support_only": True,
        "same_surface_eval_admissible": False,
        "requires_snippet_confirmation_before_scoreable": True,
    }
    source_bundle_id = f"stage10767::{bundle['root_id']}"
    return {
        "abstention_heavy": perspective == "abstention_insufficient_evidence",
        "anti_cheat": anti_cheat,
        "authority": {},
        "bundle_id": source_bundle_id,
        "decoder_text": gold_label,
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": gold_label,
        "gold_value": gold_value,
        "input_text": prompt_text,
        "language_family": language_family,
        "loss_mask": {"decoder_ce": True},
        "objective_family": "bounded_decoder_ce",
        "opaque_options": options,
        "perspective": perspective,
        "prompt_text": prompt_text,
        "query_text": f"stage10769::{language_family}::{perspective}",
        "repo_family": str(bundle["repo_family"]),
        "repo_id": str(bundle["repo_id"]),
        "route": "support_candidate_enrichment",
        "row_id": f"stage10769::{bundle['root_id']}::{perspective}::support_candidate",
        "selected_test_anchor": bool(bundle["compiled_brief_summary"].get("verification_targets_sample")),
        "semantic_key": str(entry["answer_kind"]),
        "source_bundle_id": source_bundle_id,
        "source_heldout_admissible": False,
        "source_row_id": str(bundle["root_id"]),
        "split": "train",
        "split_role": "train_support",
        "standalone_projection_source": {
            "gold_value": gold_value,
            "opaque_options": options,
            "original_answer_kind": answer_kind,
            "projection_mode": "stage10769_support_candidate_competition",
            "provisional_confidence": str(entry["confidence"]),
            "provisional_rationale": str(entry["rationale"]),
            "supporting_evidence_keys": list(entry["supporting_evidence_keys"]),
            "needs_confirmation": bool(entry["needs_confirmation"]),
        },
        "strict_eval_eligible": False,
        "support_package_stage": STAGE,
        "support_provenance": {
            "enrichment_status": str(index_row["enrichment_status"]),
            "provisional_gold_path": str(index_row["provisional_gold_path"]),
            "snippet_plan_path": str(index_row["snippet_plan_path"]),
        },
        "surface": "maintainer_bundle_compact_bounded_choice",
        "target_text": gold_label,
        "target_token_len": 1,
        "task_type": perspective,
        "train_support_only": True,
        "verifier_anchor": bool(bundle["compiled_brief_summary"].get("verification_targets_sample")),
    }


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)
    index_rows = load_jsonl(GOLD_INDEX)

    support_rows: list[dict[str, Any]] = []
    for index_row in index_rows:
        packet_dir = (ROOT / index_row["provisional_gold_path"]).parent
        bundle = load_json(packet_dir / "fresh_root_bundle_preview.json")
        enriched = load_json(packet_dir / "enriched_reviewed_support_candidate.json")
        gold = load_json(packet_dir / "provisional_ai_gold_draft.json")
        for entry in gold["entries"]:
            row = build_row(index_row, bundle, enriched, entry)
            if row is not None:
                support_rows.append(row)

    support_rows.sort(key=lambda r: (r["language_family"], r["repo_family"], r["perspective"]))
    merged_train = list(base_train) + support_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "enriched_support_candidate_training_package_ready",
        "claim_scope": [
            "Project the four enriched C/C++ and Python support candidates into a real support-only training package.",
            "Keep validation/strict/stress unchanged from the clean stage10759 base.",
            "Use provisional AI gold only for train-support rows, not for any promotable eval claim.",
        ],
        "metrics": {
            "support_row_count": len(support_rows),
            "support_rows_by_language": {
                key: sum(1 for row in support_rows if row["language_family"] == key)
                for key in sorted({row["language_family"] for row in support_rows})
            },
            "support_rows_by_perspective": {
                key: sum(1 for row in support_rows if row["perspective"] == key)
                for key in sorted({row["perspective"] for row in support_rows})
            },
            "merged_train_rows": len(merged_train),
            "base_train_rows": len(base_train),
            "strict_rows_preserved": len(base_strict),
        },
        "headline_findings": [
            "The strongest current C/C++ and Python support candidates are now represented as concrete train-support rows.",
            "Eval and strict slices remain untouched, so this package is still honesty-preserving.",
            "This is the first direct path from the first-wave root materialization effort into an executable training package.",
        ],
        "anti_cheat_contract": [
            "All newly added rows are train_support_only and strict_eval_eligible=false.",
            "All labels remain opaque and projection-scoped.",
            "All provisional gold rows remain non-promotable until snippet confirmation and reviewed adjudication complete.",
            "No current strict root is copied into strict eval or validation.",
        ],
        "next_best_step": "Use this package as the next reviewed-support-only multilingual training base, then repeat the same workflow for the fresh Rust packets before widening again.",
        "source_artifacts": {
            "base_summary": display(BASE_SUMMARY),
            "support_candidate_gold_index": display(GOLD_INDEX),
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
