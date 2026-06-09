#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


QUERY_RE = re.compile(r"query=([^ ]+) of ([^ ]+) target for")
DOC_RE = re.compile(r"statement=dslot_([0-9a-f]+) of dslot_([0-9a-f]+) target")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _query_key(row: dict[str, Any]) -> tuple[str, str] | None:
    match = QUERY_RE.search(str(row.get("query_text", "")))
    if not match:
        return None
    field, relation = match.groups()
    return field, relation


def _doc_slots(candidate: dict[str, Any]) -> tuple[str, str] | None:
    match = DOC_RE.search(str(candidate.get("doc_text", "")))
    if not match:
        return None
    field_slot, relation_slot = match.groups()
    return field_slot, relation_slot


def _learn_map(rows: list[dict[str, Any]], splits: set[str], *, label: str) -> dict[tuple[str, str], tuple[str, str]]:
    counts: dict[tuple[str, str], collections.Counter[tuple[str, str]]] = collections.defaultdict(collections.Counter)
    for row in rows:
        if row.get("operation") != "composition" or row.get("split") not in splits:
            continue
        key = _query_key(row)
        if key is None:
            continue
        for candidate in row.get("candidates", []) or []:
            is_positive = bool(candidate.get("is_exact")) if label == "exact" else bool(candidate.get("is_exact") or candidate.get("is_answer_match"))
            slots = _doc_slots(candidate)
            if is_positive and slots is not None:
                counts[key][slots] += 1
    return {key: counter.most_common(1)[0][0] for key, counter in counts.items() if counter}


def _score(rows: list[dict[str, Any]], split: str, mapping: dict[tuple[str, str], tuple[str, str]]) -> dict[str, Any]:
    total = known_keys = proof_present = proof_exact_present = 0
    base_answer = base_exact = proof_answer = proof_exact = 0
    recoverable_answer = recoverable_exact = 0
    by_key: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.get("operation") != "composition" or row.get("split") != split:
            continue
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        total += 1
        key = _query_key(row)
        key_name = "/".join(key) if key else "unknown"
        key_stats = by_key.setdefault(key_name, {"rows": 0, "base_answer": 0, "base_exact": 0, "proof_answer": 0, "proof_exact": 0})
        key_stats["rows"] += 1
        target = mapping.get(key) if key else None
        known_keys += int(target is not None)

        base_order = sorted(range(len(candidates)), key=lambda idx: (-float(candidates[idx].get("base_score", 0.0) or 0.0), idx))
        base_top = candidates[base_order[0]]
        base_is_answer = bool(base_top.get("is_exact") or base_top.get("is_answer_match"))
        base_is_exact = bool(base_top.get("is_exact"))
        base_answer += int(base_is_answer)
        base_exact += int(base_is_exact)
        key_stats["base_answer"] += int(base_is_answer)
        key_stats["base_exact"] += int(base_is_exact)

        def proof_match(idx: int) -> int:
            slots = _doc_slots(candidates[idx])
            return int(target is not None and slots == target)

        if target is not None and any(proof_match(idx) for idx in range(len(candidates))):
            proof_present += 1
            proof_exact_present += int(any(proof_match(idx) and bool(candidates[idx].get("is_exact")) for idx in range(len(candidates))))

        proof_order = sorted(
            range(len(candidates)),
            key=lambda idx: (-proof_match(idx), -float(candidates[idx].get("base_score", 0.0) or 0.0), idx),
        )
        proof_top = candidates[proof_order[0]]
        proof_is_answer = bool(proof_top.get("is_exact") or proof_top.get("is_answer_match"))
        proof_is_exact = bool(proof_top.get("is_exact"))
        proof_answer += int(proof_is_answer)
        proof_exact += int(proof_is_exact)
        key_stats["proof_answer"] += int(proof_is_answer)
        key_stats["proof_exact"] += int(proof_is_exact)

        recoverable_answer += int(any(bool(c.get("is_exact") or c.get("is_answer_match")) for c in candidates))
        recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))

    return {
        "rows": total,
        "known_keys": known_keys,
        "base_answer_exact": [base_answer, base_exact],
        "proof_bonus_answer_exact": [proof_answer, proof_exact],
        "recoverable_answer_exact": [recoverable_answer, recoverable_exact],
        "proof_match_present": proof_present,
        "proof_exact_present": proof_exact_present,
        "by_query_key": by_key,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", default="runs/local/artifacts/stage907_broad_bridge_curriculum_targets.jsonl")
    parser.add_argument("--output", default="runs/local/artifacts/stage912_composition_proof_edge_diagnostic_summary.json")
    args = parser.parse_args()

    rows = _iter_jsonl(Path(args.targets_jsonl))
    train_calib_exact_map = _learn_map(rows, {"train", "calibration"}, label="exact")
    eval_exact_oracle_map = _learn_map(rows, {"eval"}, label="exact")
    eval_answer_oracle_map = _learn_map(rows, {"eval"}, label="answer")
    summary = {
        "artifact_kind": "stage912_composition_proof_edge_diagnostic",
        "decision": "Diagnostic only. Composition proof-edge lexical-to-dslot maps do not transfer across split-salted dslot ids.",
        "interpretation": (
            "Composition queries expose lexical field/relation names while candidate docs expose split-local dslot ids. "
            "A train/calibration proof-edge map saturates train but gives no eval proof matches because the slot ids are salted per split. "
            "An accepted route must learn or emit proof-edge structure inside the model/curriculum rather than memorize dslot ids."
        ),
        "train_calibration_exact_map": {"/".join(key): list(value) for key, value in sorted(train_calib_exact_map.items())},
        "eval_exact_oracle_map": {"/".join(key): list(value) for key, value in sorted(eval_exact_oracle_map.items())},
        "eval_answer_oracle_map": {"/".join(key): list(value) for key, value in sorted(eval_answer_oracle_map.items())},
        "scores": {
            "train_calibration_map_on_train": _score(rows, "train", train_calib_exact_map),
            "train_calibration_map_on_calibration": _score(rows, "calibration", train_calib_exact_map),
            "train_calibration_map_on_eval": _score(rows, "eval", train_calib_exact_map),
            "eval_exact_oracle_map_on_eval": _score(rows, "eval", eval_exact_oracle_map),
            "eval_answer_oracle_map_on_eval": _score(rows, "eval", eval_answer_oracle_map),
        },
        "next_steps": [
            "Add composition rows with explicit qslot-style latent proof edges for relation and answer field, then salt them by split and train a side-invariant predictor.",
            "Distill proof-edge prediction into encoder states instead of using frozen-hidden candidate CE.",
            "Keep Stage909 as the accepted typed-access frontier until a proof-edge or encoder-owned route beats it without eval-local slot maps.",
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
