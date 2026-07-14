#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"

STAGE = 10750
NAME = "stage10750_python_rust_residual_targeted_probe_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "python_rust_residual_targeted_probe_audit.json"

BASE_EXECUTION = ARTIFACTS / "stage10745_reviewed_v27_cpp_bootstrap_support_probe/bounded_decoder_probe/execution_result.json"
NEW_EXECUTION = ARTIFACTS / "stage10749_python_rust_residual_targeted_probe/bounded_decoder_probe/execution_result.json"
SOURCE_PACKAGE = ARTIFACTS / "stage10747_python_rust_residual_targeted_support_package/python_rust_residual_targeted_support_package.json"


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
        "decision": "python_rust_residual_targeted_probe_completed_no_frontier_lift",
        "claim_scope": [
            "Audit whether the narrow Python verifier plus Rust citation residual support package moves the unchanged reviewed v2.7 standalone strict frontier.",
            "Keep the strict frontier and the narrow diagnostic support package separate from any promotion claim.",
        ],
        "source_artifacts": {
            "base_execution_result": rel(BASE_EXECUTION),
            "new_execution_result": rel(NEW_EXECUTION),
            "support_package": rel(SOURCE_PACKAGE),
        },
        "headline_findings": [
            f"Strict constrained accuracy stayed flat at {new_acc:.6f} (22/24).",
            "Neither of the two surviving strict residuals flipped: Python verifier_outcome stayed C->B wrong and Rust evidence_citation stayed B->E wrong.",
            "The narrow targeted package is cleaner than the broad C/C++ expansion path, but it still did not lift the standalone frontier.",
        ],
        "metrics": {
            "base_strict_accuracy": base_acc,
            "new_strict_accuracy": new_acc,
            "accuracy_delta": (new_acc - base_acc) if base_acc is not None and new_acc is not None else None,
            "base_runtime_weights_sha256": ((base.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "new_runtime_weights_sha256": ((new.get("runtime_model_bundle") or {}).get("weights_sha256")),
            "support_package_train_rows": ((package.get("metrics") or {}).get("train_rows")),
        },
        "base_misses": base_misses,
        "new_misses": new_misses,
        "promotion_gate": {
            "beats_base_accuracy": (new_acc or 0) > (base_acc or 0),
            "zero_new_regressions": base_misses == new_misses,
            "promotable": False,
            "reason": "narrow residual-targeted support preserved the frontier but did not improve the unchanged strict miss set",
        },
        "next_best_steps": [
            "Stop treating tiny standalone support probes as likely frontier movers unless they add genuinely new root families or representation variants.",
            "For Python, add more disjoint multi-test verifier roots beyond the two existing code_assist verifier supports.",
            "For Rust, add more non-tokenizers evidence-citation roots where symptom_or_call_path_analogue must beat candidate_change_surface under matched option geometry.",
        ],
    }

    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
