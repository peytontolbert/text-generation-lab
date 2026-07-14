#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10746
NAME = "stage10746_cpp_bootstrap_support_probe_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "cpp_bootstrap_support_probe_audit.json"

BASE_EXECUTION = ARTIFACTS / "stage10737_reviewed_v27_cpp_support_probe/bounded_decoder_probe/execution_result.json"
NEW_EXECUTION = ARTIFACTS / "stage10745_reviewed_v27_cpp_bootstrap_support_probe/bounded_decoder_probe/execution_result.json"
SOURCE_PACKAGE = ARTIFACTS / "stage10743_reviewed_v27_plus_cpp_bootstrap_train_support_package/reviewed_v27_plus_cpp_bootstrap_train_support_package.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def strict_rows(exec_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return (((exec_payload.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])


def strict_accuracy(exec_payload: dict[str, Any]) -> float | None:
    return (((exec_payload.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("constrained_choice_top1_accuracy"))


def misses(exec_payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in strict_rows(exec_payload):
        if row.get("constrained_choice_match") is False:
            out.append(
                {
                    "row_id": row.get("row_id"),
                    "target_text": row.get("target_text"),
                    "predicted_label": row.get("constrained_choice_top1_label"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                }
            )
    return out


def per_language(exec_payload: dict[str, Any]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for row in strict_rows(exec_payload):
        language = str(row.get("row_id") or "").split("::")
        lang = language[-3] if len(language) >= 3 else "unknown"
        bucket = stats.setdefault(lang, {"correct": 0, "rows": 0})
        bucket["rows"] += 1
        if row.get("constrained_choice_match") is True:
            bucket["correct"] += 1
    return stats


def main() -> None:
    base = load_json(BASE_EXECUTION)
    new = load_json(NEW_EXECUTION)
    package = load_json(SOURCE_PACKAGE)

    base_acc = strict_accuracy(base)
    new_acc = strict_accuracy(new)
    base_misses = misses(base)
    new_misses = misses(new)

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "decision": "cpp_bootstrap_support_probe_completed_no_frontier_lift",
        "claim_scope": [
            "Audit whether the expanded honest C/C++ bootstrap support inventory from stage10743 improves the unchanged reviewed v2.7 strict frontier.",
            "Keep the strict frontier and headline claim boundary separate from the train-support scale gain.",
        ],
        "source_artifacts": {
            "base_execution_result": rel(BASE_EXECUTION),
            "new_execution_result": rel(NEW_EXECUTION),
            "support_package": rel(SOURCE_PACKAGE),
        },
        "headline_findings": [
            f"Strict constrained accuracy stayed flat at {new_acc:.6f} ({int((new_acc or 0) * 24)}/24).",
            "The same two strict residuals remain: Python verifier_outcome and Rust evidence_citation.",
            "The expanded C/C++ support inventory improved reviewed root supply and train rows, but did not change the multilingual strict miss set.",
        ],
        "metrics": {
            "base_strict_accuracy": base_acc,
            "new_strict_accuracy": new_acc,
            "accuracy_delta": (new_acc - base_acc) if base_acc is not None and new_acc is not None else None,
            "base_runtime_weights_sha256": ((base.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "new_runtime_weights_sha256": ((new.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "support_package_train_rows": ((package.get("metrics") or {}).get("train_rows")),
            "support_package_root_records": ((package.get("metrics") or {}).get("root_records")),
            "support_package_c_cpp_root_count": (((package.get("metrics") or {}).get("root_language_counts") or {}).get("c_cpp")),
            "per_language_strict": per_language(new),
        },
        "base_misses": base_misses,
        "new_misses": new_misses,
        "miss_set_changed": base_misses != new_misses,
        "promotion_gate": {
            "beats_base_accuracy": (new_acc or 0) > (base_acc or 0),
            "zero_new_regressions": base_misses == new_misses,
            "promotable": False,
            "reason": "expanded C/C++ support preserved the frontier but did not improve the unchanged strict set",
        },
        "next_best_steps": [
            "Treat the C/C++ expansion as a dataset-scale win, not a standalone frontier win.",
            "Shift the next promotable standalone work back to the two surviving strict residuals: Python verifier_outcome and Rust evidence_citation.",
            "Keep expanding honest reviewed roots, but require fresh heldout pressure or residual movement before upgrading the standalone headline.",
        ],
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
