#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11437
NAME = "stage11437_semantic_candidate_probe_ready_filtered_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "semantic_candidate_probe_ready_filtered_package.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ARTIFACTS / "stage11436_full_coverage_semantic_candidate_package"
INPUTS = {
    "train": SOURCE / "agentkernel_lite_encdec_train.jsonl",
    "validation": SOURCE / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": SOURCE / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": SOURCE / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": SOURCE / "semantic_candidate_residual_bank.jsonl",
    "audit": SOURCE / "semantic_candidate_row_audit.jsonl",
}
OUTPUTS = {
    "train": OUT_DIR / "agentkernel_lite_encdec_train.jsonl",
    "validation": OUT_DIR / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl",
    "residual_bank": OUT_DIR / "semantic_candidate_residual_bank.jsonl",
    "quarantine": OUT_DIR / "semantic_candidate_quarantined_rows.jsonl",
}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or "")


def root_key(row: dict[str, Any]) -> str:
    for key in ("root_id", "source_root_id", "root_lineage_key", "source_bundle_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return row_id(row)


def task_type(row: dict[str, Any]) -> str:
    return str(row.get("task_type") or row.get("perspective") or "unknown")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    sps = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return [opt for opt in (sps.get("opaque_options") or []) if isinstance(opt, dict)]


def has_semantic_options(row: dict[str, Any]) -> bool:
    opts = options(row)
    return len(opts) > 1 and all(isinstance(opt.get("semantic_candidate"), dict) for opt in opts)


def target_in_options(row: dict[str, Any]) -> bool:
    target = str(row.get("bounded_choice_target_label") or row.get("target_text") or row.get("decoder_text") or "").strip()
    if isinstance(row.get("target"), dict):
        target = target or str(row["target"].get("bounded_choice_target_label") or row["target"].get("target_text") or "").strip()
    return bool(target and target in {str(opt.get("label") or "").strip() for opt in options(row)})


def admissible(row: dict[str, Any]) -> bool:
    return has_semantic_options(row) and target_in_options(row)


def count(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "roots": len({root_key(row) for row in rows}),
        "by_language": dict(sorted(Counter(str(row.get("language_family") or row.get("language") or "unknown") for row in rows).items())),
        "by_task": dict(sorted(Counter(task_type(row) for row in rows).items())),
        "singleton_or_empty_options": sum(1 for row in rows if len(options(row)) <= 1),
        "semantic_option_rows": sum(1 for row in rows if has_semantic_options(row)),
    }


def filter_split(rows: list[dict[str, Any]], split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        if admissible(row):
            kept.append(row)
        else:
            q = dict(row)
            q["stage11437_quarantine_reason"] = {
                "split": split,
                "option_count": len(options(row)),
                "has_semantic_options": has_semantic_options(row),
                "target_in_options": target_in_options(row),
            }
            quarantined.append(q)
    return kept, quarantined


def main() -> None:
    source_summary = json.loads((SOURCE / "full_coverage_semantic_candidate_package.json").read_text(encoding="utf-8"))
    quarantined_all: list[dict[str, Any]] = []
    kept_by_split: dict[str, list[dict[str, Any]]] = {}
    source_counts: dict[str, Any] = {}
    kept_counts: dict[str, Any] = {}
    quarantine_counts: dict[str, Any] = {}
    for split in ("train", "validation", "strict_eval", "stress_eval", "residual_bank"):
        rows = load_jsonl(INPUTS[split])
        kept, quarantined = filter_split(rows, split)
        kept_by_split[split] = kept
        quarantined_all.extend(quarantined)
        write_jsonl(OUTPUTS[split], kept)
        source_counts[split] = count(rows)
        kept_counts[split] = count(kept)
        quarantine_counts[split] = count(quarantined)
    write_jsonl(OUTPUTS["quarantine"], quarantined_all)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "probe_ready_filtered_semantic_candidate_package_created_with_denominator_change_disclosed",
        "claim_scope": "diagnostic semantic-candidate scorer training/eval package only; not comparable to old 22/23 canary without removed-row disclosure",
        "source_stage": source_summary.get("stage_name"),
        "inputs": {key: rel(path) for key, path in INPUTS.items()},
        "outputs": {key: rel(path) for key, path in OUTPUTS.items()},
        "source_counts": source_counts,
        "kept_counts": kept_counts,
        "quarantine_counts": quarantine_counts,
        "gates": {
            "train_nonempty": len(kept_by_split["train"]) > 0,
            "validation_nonempty": len(kept_by_split["validation"]) > 0,
            "strict_nonempty": len(kept_by_split["strict_eval"]) > 0,
            "residual_nonempty": len(kept_by_split["residual_bank"]) > 0,
            "all_kept_rows_have_full_semantic_candidate_options": all(admissible(row) for rows in kept_by_split.values() for row in rows),
            "strict_denominator_changed": len(kept_by_split["strict_eval"]) != source_counts["strict_eval"]["rows"],
            "validation_denominator_changed": len(kept_by_split["validation"]) != source_counts["validation"]["rows"],
        },
        "quarantined_row_ids_by_split": {
            split: [row_id(row) for row in quarantined_all if row.get("stage11437_quarantine_reason", {}).get("split") == split][:100]
            for split in ("train", "validation", "strict_eval", "stress_eval", "residual_bank")
        },
        "decision_basis": [
            "Stage11436 proved the residual bank is optioned and semantic-candidate ready, but train has many non-optioned role-classification rows.",
            "A semantic candidate scorer objective requires rows with multi-option opaque choices and per-option semantic metadata.",
            "The singleton Rust verifier row is quarantined from validation/strict for this diagnostic package; old canary scores must still be reported separately.",
        ],
        "recommended_next_action": "run one diagnostic semantic-candidate-head probe on this filtered package, then evaluate old 22/23 canary separately with the base scorer to ensure no regression",
    }
    write_json(SUMMARY_JSON, summary)
    write_json(RUN_SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
