#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10555
NAME = "stage10555_masked_projection_successor_with_v27_preservation_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "masked_projection_successor_with_v27_preservation_package.json"
ALL_ROWS_PATH = OUT_DIR / "masked_projection_successor_with_v27_preservation_rows.jsonl"
TRAIN_ROWS_PATH = OUT_DIR / "train_rows.jsonl"
EVAL_ROWS_PATH = OUT_DIR / "eval_rows.jsonl"
STRICT_ROWS_PATH = OUT_DIR / "strict_eval_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

SUCCESSOR_DIR = ROOT / "runs/local/artifacts/stage10543_masked_projection_successor_package"
V27_DIR = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package"
CANARY_STRICT = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def clone(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def normalize_support_row(row: dict[str, Any]) -> dict[str, Any]:
    out = clone(row)
    out["split"] = "train"
    out["prompt_text"] = str(out.get("prompt_text") or out.get("input_text") or "")
    out["decoder_text"] = str(out.get("decoder_text") or out.get("target_text") or "")
    out["objective_family"] = "masked_projection_successor_with_v27_preservation"
    out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    out["disable_losses"] = ["denoise_ce", "runtime_reward", "structured_aux"]
    out["expected_enabled_loss"] = "decoder_ce_plus_bounded_choice_aux"
    out["preservation_support_source"] = "reviewed_v27_non_strict"
    return out


def normalize_successor_row(row: dict[str, Any]) -> dict[str, Any]:
    out = clone(row)
    out["preservation_support_source"] = "masked_projection_successor"
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    successor_train = [normalize_successor_row(row) for row in load_jsonl(SUCCESSOR_DIR / "train_rows.jsonl")]
    successor_eval = [normalize_successor_row(row) for row in load_jsonl(SUCCESSOR_DIR / "validation_rows.jsonl")]
    successor_strict = [normalize_successor_row(row) for row in load_jsonl(SUCCESSOR_DIR / "strict_eval_rows.jsonl")]
    v27_train = [normalize_support_row(row) for row in load_jsonl(V27_DIR / "agentkernel_lite_encdec_train.jsonl")]
    v27_validation = [normalize_support_row(row) for row in load_jsonl(V27_DIR / "agentkernel_lite_encdec_validation.jsonl")]

    canary_ids = {row["row_id"] for row in load_jsonl(CANARY_STRICT)}
    v27_support = v27_train + v27_validation
    v27_overlap = sorted(row["row_id"] for row in v27_support if row["row_id"] in canary_ids)

    train_rows = successor_train + v27_support
    eval_rows = successor_eval
    strict_rows = successor_strict
    all_rows = train_rows + eval_rows + strict_rows

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(v27_overlap) == 0,
        "claim_scope": [
            "Corrective successor package that keeps the stage10543 long-context strict slice unchanged while adding non-strict reviewed v2.7 support rows for bounded-choice preservation.",
            "The added reviewed support rows are train-only and do not overlap the 24-row repaired-v2.7 canary.",
            "This package is intended to test whether a mixed seq2seq-plus-bounded-choice curriculum can retain old maintainer competence without abandoning the new long-context bootstrap path.",
        ],
        "inputs": {
            "successor_package": display(SUCCESSOR_DIR / "masked_projection_successor_package.json"),
            "successor_rows": display(SUCCESSOR_DIR / "masked_projection_successor_rows.jsonl"),
            "reviewed_v27_package": display(V27_DIR / "reviewed_multilingual_v27_manifest_package.json"),
            "reviewed_v27_train": display(V27_DIR / "agentkernel_lite_encdec_train.jsonl"),
            "reviewed_v27_validation": display(V27_DIR / "agentkernel_lite_encdec_validation.jsonl"),
            "canary_overlay": display(CANARY_STRICT),
        },
        "rows": {
            "train": len(train_rows),
            "eval": len(eval_rows),
            "strict_eval": len(strict_rows),
            "all": len(all_rows),
        },
        "support_mix": {
            "successor_train_rows": len(successor_train),
            "reviewed_v27_support_rows": len(v27_support),
            "reviewed_v27_train_rows": len(v27_train),
            "reviewed_v27_validation_rows": len(v27_validation),
            "reviewed_v27_canary_overlap_rows": len(v27_overlap),
            "reviewed_v27_canary_overlap_examples": v27_overlap[:8],
        },
        "language_counts": {
            "train": count_by(train_rows, "language_family"),
            "eval": count_by(eval_rows, "language_family"),
            "strict_eval": count_by(strict_rows, "language_family"),
        },
        "target_subtypes": {
            "train": count_by(train_rows, "target_subtype"),
            "eval": count_by(eval_rows, "target_subtype"),
            "strict_eval": count_by(strict_rows, "target_subtype"),
        },
        "bounded_choice_support": {
            "train_rows_with_standalone_projection_source": sum(1 for row in train_rows if row.get("standalone_projection_source")),
            "eval_rows_with_standalone_projection_source": sum(1 for row in eval_rows if row.get("standalone_projection_source")),
            "strict_rows_with_standalone_projection_source": sum(1 for row in strict_rows if row.get("standalone_projection_source")),
        },
        "outputs": {
            "all_rows": display(ALL_ROWS_PATH),
            "train_rows": display(TRAIN_ROWS_PATH),
            "eval_rows": display(EVAL_ROWS_PATH),
            "strict_rows": display(STRICT_ROWS_PATH),
        },
        "known_limits": [
            "The 54-row strict successor slice remains generation-only and still cannot support bounded-choice scoring directly.",
            "Reviewed v2.7 support rows are small relative to the long-context train supply and are intended as preservation anchors, not a new headline benchmark.",
        ],
    }

    write_jsonl(TRAIN_ROWS_PATH, train_rows)
    write_jsonl(EVAL_ROWS_PATH, eval_rows)
    write_jsonl(STRICT_ROWS_PATH, strict_rows)
    write_jsonl(ALL_ROWS_PATH, all_rows)
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "rows": payload["rows"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
