#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10842
NAME = "stage10842_residual_family_distribution_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "residual_family_distribution_audit.json"

PACKAGE_JSON = ARTIFACTS / "stage10839_current_residual_support_package" / "current_residual_support_package.json"
TRAIN_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage10839_current_residual_support_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
STAGE10820_STRICT = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
STAGE10820_EVAL = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_eval.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def task_label_distribution(rows: list[dict[str, Any]], split_name: str) -> dict[str, dict[str, int]]:
    dist: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        task = str(row.get("task_type") or "unknown")
        target = str(row.get("target_text") or "unknown")
        dist[task][target] += 1
    return {task: dict(sorted(counter.items())) for task, counter in sorted(dist.items())}


def option_count_stats(rows: list[dict[str, Any]], task_name: str) -> dict[str, Any]:
    relevant = [row for row in rows if str(row.get("task_type")) == task_name]
    counts = []
    for row in relevant:
        options = row.get("opaque_options")
        if isinstance(options, list):
            counts.append(len(options))
    singleton = sum(1 for n in counts if n == 1)
    return {
        "rows": len(relevant),
        "singleton_option_rows": singleton,
        "non_singleton_rows": len(counts) - singleton,
        "option_count_histogram": dict(sorted(Counter(counts).items())),
    }


def collect_misses(audit: dict[str, Any], task_name: str) -> list[dict[str, Any]]:
    rows = []
    for miss in audit.get("misses", []):
        if str(miss.get("task_type")) == task_name:
            rows.append(
                {
                    "row_id": miss.get("row_id"),
                    "language_family": miss.get("language_family"),
                    "predicted_label": miss.get("predicted_label"),
                    "target_label": miss.get("target_label"),
                    "full_vocab_top1_text": miss.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": miss.get("target_rank_full_vocab"),
                }
            )
    return rows


def main() -> None:
    package = load_json(PACKAGE_JSON)
    train_rows = load_jsonl(TRAIN_ROWS)
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    strict_audit = load_json(STAGE10820_STRICT)
    eval_audit = load_json(STAGE10820_EVAL)

    residual_tasks = {"evidence_citation", "verifier_outcome"}
    residual_train = [row for row in train_rows if str(row.get("task_type")) in residual_tasks]
    residual_validation = [row for row in validation_rows if str(row.get("task_type")) in residual_tasks]
    residual_strict = [row for row in strict_rows if str(row.get("task_type")) in residual_tasks]

    evidence_train_labels = Counter(str(row.get("target_text")) for row in train_rows if str(row.get("task_type")) == "evidence_citation")
    verifier_train_labels = Counter(str(row.get("target_text")) for row in train_rows if str(row.get("task_type")) == "verifier_outcome")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_distribution_audited",
        "claim_scope": [
            "Audit whether the current residual-support package has the right task and label shape to move the two remaining strict failures.",
            "Document distribution mismatches for evidence_citation and verifier_outcome so the next move is data-shape repair rather than another broad preservation probe.",
        ],
        "package_snapshot": {
            "package_stage": package["stage"],
            "train_rows": len(train_rows),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "train_by_language": count_by(train_rows, "language_family"),
            "train_by_repo": count_by(train_rows, "repo_id"),
            "train_by_task": count_by(train_rows, "task_type"),
            "train_label_distribution": count_by(train_rows, "target_text"),
            "validation_label_distribution": count_by(validation_rows, "target_text"),
            "strict_label_distribution": count_by(strict_rows, "target_text"),
        },
        "residual_family_snapshot": {
            "train_rows": len(residual_train),
            "validation_rows": len(residual_validation),
            "strict_rows": len(residual_strict),
            "train_task_label_distribution": task_label_distribution(residual_train, "train"),
            "validation_task_label_distribution": task_label_distribution(residual_validation, "validation"),
            "strict_task_label_distribution": task_label_distribution(residual_strict, "strict"),
            "verifier_option_geometry": option_count_stats(train_rows, "verifier_outcome"),
            "evidence_option_geometry": option_count_stats(train_rows, "evidence_citation"),
        },
        "residual_family_findings": [
            {
                "task_type": "evidence_citation",
                "finding": "Train targets underrepresent or omit some eval/strict labels needed by current misses.",
                "train_labels": dict(sorted(evidence_train_labels.items())),
                "strict_misses": collect_misses(strict_audit, "evidence_citation"),
                "eval_misses": collect_misses(eval_audit, "evidence_citation"),
            },
            {
                "task_type": "verifier_outcome",
                "finding": "Train verifier rows are still shaped more like preservation/support than true verifier-transition competition.",
                "train_labels": dict(sorted(verifier_train_labels.items())),
                "strict_misses": collect_misses(strict_audit, "verifier_outcome"),
                "eval_misses": collect_misses(eval_audit, "verifier_outcome"),
            },
        ],
        "diagnosis": [
            "The package is strong enough to preserve the 22/24 canary, but still too small and too label-skewed for the residual concept families.",
            "evidence_citation is being evaluated on semantic roles that are weakly represented or absent in train labels.",
            "verifier_outcome still contains too little multi-option B/C/G-style supervision relative to the current Python residual.",
            "Another broad support probe is unlikely to change the miss set without a targeted residual-family rebuild.",
        ],
        "next_best_step": "Build a residual-family rebalance request that targets evidence_citation role coverage and verifier_outcome transition geometry, then use that request instead of another generic support sweep.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
