#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10827
NAME = "stage10827_evidence_role_augmented_support_package"
OUT_DIR = ARTIFACTS / NAME
PACKAGE_JSON = OUT_DIR / "evidence_role_augmented_support_package.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"

BASE_DIR = ARTIFACTS / "stage10814_reviewed_v27_plus_cpp_python_queue_support_package"
ROLE_ROWS = ARTIFACTS / "stage10826_evidence_role_support_package" / "evidence_role_candidate_rows.jsonl"


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    base_package = load_json(BASE_DIR / "reviewed_v27_plus_cpp_python_queue_support_package.json")
    base_train = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_train.jsonl")
    base_validation = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_validation.jsonl")
    base_strict = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl")
    base_stress = load_jsonl(BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl")
    role_rows = [row for row in load_jsonl(ROLE_ROWS) if row.get("split") == "train"]

    merged_train = list(base_train)
    for row in role_rows:
        updated = dict(row)
        updated["split"] = "train"
        updated["split_role"] = "train"
        updated["disable_losses"] = []
        updated["expected_enabled_loss"] = "decoder_ce"
        updated["loss_mask"] = {"decoder_ce": True}
        updated["train_support_only"] = True
        updated["strict_eval_eligible"] = False
        updated["support_package_stage"] = STAGE
        merged_train.append(updated)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_role_augmented_support_package_ready",
        "claim_scope": [
            "Augment the current queue-aligned reviewed v2.7 standalone path with train-support-only semantic evidence-role rows.",
            "Keep validation, strict, and stress splits unchanged so any future movement remains attributable to train-side evidence-role supervision.",
        ],
        "source_artifacts": {
            "base_package": rel(BASE_DIR / "reviewed_v27_plus_cpp_python_queue_support_package.json"),
            "evidence_role_package": rel(ARTIFACTS / "stage10826_evidence_role_support_package" / "evidence_role_support_package.json"),
        },
        "metrics": {
            "base_train_rows": len(base_train),
            "added_evidence_role_train_rows": len(role_rows),
            "merged_train_rows": len(merged_train),
            "validation_rows": len(base_validation),
            "strict_rows": len(base_strict),
            "stress_rows": len(base_stress),
            "added_rows_by_language": dict(sorted(Counter(str(r.get("language_family") or "unknown") for r in role_rows).items())),
            "added_rows_by_role": dict(sorted(Counter(str(r.get("semantic_role") or "unknown") for r in role_rows).items())),
        },
        "honesty_gates": [
            "validation and strict rows are byte-for-byte preserved from stage10814",
            "all evidence-role rows are train-support only",
            "same-surface evidence-role rows are not promotable headline eval artifacts",
            "future probe must report evidence_citation family deltas explicitly",
        ],
        "outputs": {
            "package_json": rel(PACKAGE_JSON),
            "train_rows": rel(TRAIN_JSONL),
            "validation_rows": rel(VALIDATION_JSONL),
            "strict_rows": rel(STRICT_JSONL),
            "stress_rows": rel(STRESS_JSONL),
        },
        "next_best_step": "Run a bounded standalone probe from this package initialized from stage10820, then audit evidence_citation and verifier_outcome family deltas separately.",
        "base_metrics_snapshot": base_package.get("metrics"),
    }

    write_json(PACKAGE_JSON, payload)
    write_jsonl(TRAIN_JSONL, merged_train)
    write_jsonl(VALIDATION_JSONL, base_validation)
    write_jsonl(STRICT_JSONL, base_strict)
    write_jsonl(STRESS_JSONL, base_stress)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
