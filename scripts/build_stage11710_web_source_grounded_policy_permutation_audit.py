#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11710_web_source_grounded_policy_permutation_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_source_grounded_policy_permutation_audit.json"
ROW_CARDS = OUT / "web_source_grounded_policy_permutation_rows.jsonl"

STAGE11709 = ROOT / "scripts/build_stage11709_web_source_grounded_nonverifier_policy_audit.py"
spec = importlib.util.spec_from_file_location("stage11709_base_for_11710", STAGE11709)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11709}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

BRIDGED_ROWS = ART / "stage11690_original_web_canonical_bridge_audit/original_web_canonical_bridged_rows.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def set_target(row: dict[str, Any], label: str) -> None:
    row["bounded_choice_target_label"] = label
    row["target_text"] = label
    target = dict(row.get("target") or {})
    target["decoder_text"] = label
    target["bounded_choice_target_label"] = label
    row["target"] = target


def permute_row(row: dict[str, Any], offset: int) -> dict[str, Any]:
    out = copy.deepcopy(row)
    opts = options(out)
    labels = [str(opt.get("label") or "").strip() for opt in opts]
    if not labels:
        return out
    target_old = target_label(out)
    # Rotate labels and option order differently so label identity and position both change.
    rotated_labels = labels[offset % len(labels) :] + labels[: offset % len(labels)]
    old_to_new: dict[str, str] = {}
    new_opts: list[dict[str, Any]] = []
    for opt, new_label in zip(opts, rotated_labels):
        clone = copy.deepcopy(opt)
        old_label = str(clone.get("label") or "").strip()
        old_to_new[old_label] = new_label
        clone["label"] = new_label
        new_opts.append(clone)
    new_opts = new_opts[-(offset % len(new_opts)) :] + new_opts[: -(offset % len(new_opts))] if offset % len(new_opts) else new_opts
    out["opaque_options"] = new_opts
    source = dict(out.get("standalone_projection_source") or {})
    source["opaque_options"] = copy.deepcopy(new_opts)
    source["stage11710_label_permutation"] = {"offset": offset, "old_to_new": old_to_new}
    out["standalone_projection_source"] = source
    if target_old in old_to_new:
        set_target(out, old_to_new[target_old])
    out["row_id"] = f"{out.get('row_id')}::stage11710_perm_{offset}"
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows = [base.base.NORMALIZER.normalize_row(row) for row in load_jsonl(BRIDGED_ROWS)]
    permutations = [1, 2, 3]
    cards: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for offset in permutations:
        rows = [permute_row(row, offset) for row in base_rows]
        scored, _meta = base.product_score_rows(rows)
        correct = sum(1 for row in scored if row["product_correct"])
        summaries[f"perm_{offset}"] = {
            "rows": len(scored),
            "correct": correct,
            "accuracy": correct / len(scored) if scored else None,
            "misses": [str(row.get("row_id")) for row in scored if not row["product_correct"]],
        }
        for row in scored:
            cards.append({"permutation_offset": offset, **row})
    write_jsonl(ROW_CARDS, cards)
    all_stable = all(item["correct"] == 66 and item["rows"] == 66 for item in summaries.values())
    gates = {
        "all_three_permutations_66_of_66": all_stable,
        "all_rows_scored": all(item["rows"] == 66 for item in summaries.values()),
        "no_permutation_misses": all(not item["misses"] for item in summaries.values()),
    }
    decision = "source_grounded_policy_permutation_stable" if all(gates.values()) else "source_grounded_policy_permutation_unstable"
    summary = {
        "stage": 11710,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "permutation_results": summaries,
        "gates": gates,
        "interpretation": [
            "This relabels and reorders candidate options while preserving semantic candidate objects.",
            "Passing this audit means the Stage11709 policy is not dependent on original option letters or positions.",
        ],
        "source_artifacts": {"bridged_rows": rel(BRIDGED_ROWS), "stage11709_script": rel(STAGE11709)},
        "outputs": {"summary": rel(SUMMARY), "row_cards": rel(ROW_CARDS)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "permutation_results": summaries, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
