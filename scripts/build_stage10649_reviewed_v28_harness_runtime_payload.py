#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
HANDOFF = ARTIFACTS / "stage10648_reviewed_v28_harness_handoff_bundle" / "reviewed_v28_harness_handoff_bundle.json"
PACKAGE_DIR = ARTIFACTS / "stage10645_reviewed_v28_candidate_manifest_package"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10422_reviewed_multilingual_v27_target100m_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def row_to_harness_row(row: dict[str, Any]) -> dict[str, Any]:
    projection = row.get("standalone_projection_source") or {}
    return {
        "row_id": row.get("row_id"),
        "split": "strict_eval",
        "prompt": row.get("prompt_text") or row.get("input_text") or "",
        "prompt_text": row.get("prompt_text") or row.get("input_text") or "",
        "expected_label": row.get("target_text"),
        "expected_answer_kind": "opaque_choice",
        "opaque_options": list(projection.get("opaque_options") or []),
        "task_type": row.get("task_type"),
        "language_family": row.get("language_family"),
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_family"),
        "source_bundle_id": row.get("source_bundle_id"),
        "claim_role": row.get("claim_role"),
        "selected_test_anchor": row.get("selected_test_anchor"),
        "verifier_anchor": row.get("verifier_anchor"),
        "abstention_heavy": row.get("abstention_heavy"),
    }


def row_to_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    copied["split"] = "strict_eval"
    copied["loss_mask"] = {"decoder_ce": True}
    copied["expected_enabled_loss"] = "decoder_ce"
    copied["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
    return copied


def main() -> None:
    handoff = load_json(HANDOFF)
    headline = load_jsonl(PACKAGE_DIR / "headline_strict_eval.jsonl")
    rust_replacement = load_jsonl(PACKAGE_DIR / "rust_replacement_experiment_eval.jsonl")

    rows_by_lang: dict[str, list[dict[str, Any]]] = {}
    for row in headline:
        rows_by_lang.setdefault(str(row.get("language_family") or ""), []).append(row)
    for row in rust_replacement:
        rows_by_lang.setdefault(str(row.get("language_family") or ""), []).append(row)

    runs = []
    for cell in handoff.get("handoff_cells") or []:
        language_family = str(cell.get("language_family") or "")
        source_rows = sorted(rows_by_lang.get(language_family, []), key=lambda item: str(item.get("row_id") or ""))
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
            "blocked_training_reason": "reviewed_v28_harness_pack_never_train_eligible",
            "rows": [row_to_harness_row(row) for row in source_rows],
            "manifest_mode": "preserved_bounded_choice_scoring",
            "manifest_rows": [row_to_manifest_row(row) for row in source_rows],
        }
        runs.append(
            {
                "cell_key": cell.get("cell_key"),
                "task_pack": task_pack,
                "hundred_m_backend": {
                    "kind": "preserved_bounded_choice_scoring",
                    "runtime_model_bundle": str(RUNTIME_BUNDLE),
                    "bounded_choice_aux_source": "encoder_option_retrieval",
                    "device": "cuda",
                },
                "gemma_backend": {
                    "kind": "ollama_generate",
                    "model": "gemma3:12b",
                    "seed": 0,
                    "temperature": 0.0,
                },
            }
        )

    payload = {
        "runtime_payload_version": "stage10649.v1",
        "created_at_utc": None,
        "notes": [
            "Reviewed v2.8 maintainer-choice harness payload compiled from headline_strict plus explicit Rust replacement rows.",
            "This payload is for the new reviewed_v28 harness handoff bundle, not the legacy stage10081 canonical edit-localization pack.",
            "100M uses preserved bounded-choice scoring from the frozen stage10422 runtime bundle.",
        ],
        "runs": runs,
    }

    out_dir = ARTIFACTS / "stage10649_reviewed_v28_harness_runtime_payload"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "reviewed_v28_harness_runtime_payload.json", payload)
    print(out_dir / "reviewed_v28_harness_runtime_payload.json")


if __name__ == "__main__":
    main()
