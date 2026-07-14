#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11464
NAME = "stage11464_selected_runtime_harness_payload"
OUT = ART / NAME
OUT_JSON = OUT / "selected_runtime_harness_payload.json"
SUMMARY_JSON = OUT / "selected_runtime_harness_payload_summary.json"

HANDOFF = ART / "stage10657_repaired_headline_harness_handoff_bundle/repaired_headline_harness_handoff_bundle.json"
MATCHED_ROWS = ART / "stage11447_selected_runtime_same_manifest_gemma_comparison/matched_comparison_rows.jsonl"
COMPARISON = ART / "stage11447_selected_runtime_same_manifest_gemma_comparison/stage11447_selected_runtime_same_manifest_gemma_comparison.json"
RUNTIME_BUNDLE = ART / "stage11444_targeted_residual_role_support_probe/runtime_model/runtime_model_bundle.json"

STRICT_ROW_SOURCES = (
    ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    ART / "stage11436_full_coverage_semantic_candidate_package/agentkernel_lite_encdec_strict_eval.jsonl",
    ART / "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison/reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl",
)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def row_to_harness_row(row: dict[str, Any], matched: dict[str, Any]) -> dict[str, Any]:
    projection = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    opaque_options = list(row.get("opaque_options") or projection.get("opaque_options") or matched.get("opaque_options") or [])
    prompt = str(row.get("prompt_text") or row.get("input_text") or matched.get("prompt_text") or "")
    return {
        "row_id": row.get("row_id") or matched.get("row_id"),
        "split": "strict_eval",
        "prompt": prompt,
        "prompt_text": prompt,
        "expected_label": row.get("target_text") or matched.get("target_text"),
        "expected_answer_kind": "opaque_choice",
        "opaque_options": opaque_options,
        "task_type": row.get("task_type") or matched.get("task_type"),
        "language_family": row.get("language_family") or matched.get("language_family"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family") or matched.get("repo_family"),
        "source_bundle_id": row.get("source_bundle_id"),
        "source_root_id": row.get("source_root_id"),
        "source_heldout_admissible": row.get("source_heldout_admissible"),
        "claim_role": row.get("claim_role") or "stage11447_matched_old_canary_strict",
        "selected_test_anchor": row.get("selected_test_anchor"),
        "verifier_anchor": row.get("verifier_anchor"),
        "abstention_heavy": row.get("abstention_heavy"),
        "stage11447_predictions": {
            "hundred_m_predicted_label": matched.get("hundred_m_predicted_label"),
            "hundred_m_correct": matched.get("hundred_m_correct"),
            "gemma12b_predicted_label": matched.get("gemma12b_predicted_label"),
            "gemma12b_correct": matched.get("gemma12b_correct"),
            "gemma12b_model": matched.get("gemma12b_model"),
        },
    }


def row_to_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = deep_copy(row)
    copied["split"] = "strict_eval"
    copied["loss_mask"] = {"decoder_ce": True}
    copied["expected_enabled_loss"] = "decoder_ce"
    copied["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
    return copied


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    handoff = load_json(HANDOFF)
    comparison = load_json(COMPARISON)
    runtime = load_json(RUNTIME_BUNDLE)
    matched_rows = load_jsonl(MATCHED_ROWS)
    matched_by_id = {str(row.get("row_id") or ""): row for row in matched_rows}

    source_by_id: dict[str, dict[str, Any]] = {}
    source_path_by_id: dict[str, str] = {}
    for source in STRICT_ROW_SOURCES:
        for row in load_jsonl(source):
            row_id = str(row.get("row_id") or "")
            if row_id and row_id not in source_by_id:
                source_by_id[row_id] = row
                source_path_by_id[row_id] = rel(source)

    missing_source_rows = sorted(set(matched_by_id) - set(source_by_id))
    resolved_rows = []
    for row_id, matched in matched_by_id.items():
        source = source_by_id.get(row_id)
        if not source:
            continue
        resolved_rows.append((source, matched))

    rows_by_lang: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for source, matched in resolved_rows:
        language = str(source.get("language_family") or matched.get("language_family") or "")
        rows_by_lang.setdefault(language, []).append((source, matched))

    runs = []
    for cell in handoff.get("handoff_cells") or []:
        language_family = str(cell.get("language_family") or "")
        source_rows = sorted(rows_by_lang.get(language_family, []), key=lambda pair: str(pair[0].get("row_id") or ""))
        task_pack = {
            "task_pack_id": cell.get("task_pack_id"),
            "source_id": cell.get("source_id"),
            "lineage_hash": cell.get("lineage_hash"),
            "split_role": "locked_regression",
            "train_eligible": False,
            "promotion_only": True,
            "hidden_final": False,
            "language_family": language_family,
            "skill_area": str(cell.get("skill_area") or "maintainer_choice"),
            "slice_tags": list(cell.get("slice_tags") or [language_family, "maintainer_choice"]),
            "thresholds": {
                "exact_accuracy_min": 0.0,
                "same_manifest_delta_vs_gemma_min": 0.0,
            },
            "blocked_training_reason": "stage11444_selected_runtime_harness_pack_never_train_eligible",
            "rows": [row_to_harness_row(row, matched) for row, matched in source_rows],
            "manifest_mode": "preserved_bounded_choice_scoring",
            "manifest_rows": [row_to_manifest_row(row) for row, _matched in source_rows],
        }
        runs.append(
            {
                "cell_key": cell.get("cell_key"),
                "task_pack": task_pack,
                "hundred_m_backend": {
                    "kind": "preserved_bounded_choice_scoring",
                    "runtime_model_bundle": rel(RUNTIME_BUNDLE),
                    "bounded_choice_aux_source": "encoder_option_retrieval",
                    "device": "cuda",
                    "weights_sha256": runtime.get("weights_sha256"),
                },
                "gemma_backend": {
                    "kind": "ollama_generate",
                    "model": "gemma3:12b",
                    "seed": 0,
                    "temperature": 0.0,
                },
            }
        )

    row_counts_by_language = {language: len(rows) for language, rows in sorted(rows_by_lang.items())}
    payload = {
        "runtime_payload_version": "stage11464.v1",
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "claim_scope": (
            "Stage11444 selected runtime harness payload for the matched old-canary strict bounded-choice slice. "
            "This payload enables full-product harness writeback for the current selected runtime; it is not a broader residual-bank claim."
        ),
        "selected_runtime": {
            "runtime_model_bundle": rel(RUNTIME_BUNDLE),
            "weights_sha256": runtime.get("weights_sha256"),
            "scorer": "encoder_option_retrieval",
        },
        "source_artifacts": {
            "handoff": rel(HANDOFF),
            "matched_rows": rel(MATCHED_ROWS),
            "comparison": rel(COMPARISON),
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "strict_row_sources": [rel(path) for path in STRICT_ROW_SOURCES],
        },
        "notes": [
            "Uses Stage10657 repaired-headline handoff cells so the existing local harness adapter can write to reserved packet paths.",
            "Uses Stage11444 runtime bundle and base encoder_option_retrieval scorer selected by Stage11446/11462.",
            "Includes the legacy singleton Rust verifier row because it is part of the current 23-row Stage11447 matched canary; downstream audits should keep flagging it as non-discriminative.",
        ],
        "runs": runs,
    }
    write_json(OUT_JSON, payload)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": payload["created_at_utc"],
        "passed": not missing_source_rows and len(resolved_rows) == len(matched_rows) and len(runs) == 4,
        "metrics": {
            "matched_rows": len(matched_rows),
            "resolved_full_rows": len(resolved_rows),
            "missing_source_rows": len(missing_source_rows),
            "runs": len(runs),
            "row_counts_by_language": row_counts_by_language,
            "hundred_m_accuracy": (comparison.get("metrics") or {}).get("hundred_m_accuracy"),
            "gemma_accuracy": (comparison.get("metrics") or {}).get("gemma_accuracy"),
        },
        "missing_source_rows": missing_source_rows,
        "source_path_by_row_id": {
            row_id: source_path_by_id[row_id]
            for row_id in sorted(matched_by_id)
            if row_id in source_path_by_id
        },
        "payload": rel(OUT_JSON),
        "source_artifacts": payload["source_artifacts"],
        "next_command": (
            "python scripts/run_stage10138_canonical_harness_local_runtime.py "
            f"{rel(OUT_JSON)} --handoff {rel(HANDOFF)} "
            "--runtime-root runs/local/artifacts/stage11465_selected_runtime_harness_local_runtime --dry-run"
        ),
    }
    write_json(SUMMARY_JSON, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY_JSON, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"passed": summary["passed"], "metrics": summary["metrics"], "payload": rel(OUT_JSON)}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
