#!/usr/bin/env python3
"""Roll up learned proof-expansion progress and remaining typed headroom."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
QSLOT_RE = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
DENT_CLAIM_RE = re.compile(r"\bstatement=claim dent_([A-Za-z0-9]+)\b")
DCLAIM_RE = re.compile(r"\bdclaim_([A-Za-z0-9]+)\b")
DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")
EXCEPTION_RE = re.compile(r"\bstatement=dent_([A-Za-z0-9]+) overrides default dslot_([A-Za-z0-9]+)\b")
ANSWER_KIND_RE = re.compile(r"\banswer=([A-Za-z0-9]+)_v")
DEFAULT_KIND_RE = re.compile(r"\bdefault ([A-Za-z0-9]+)\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _row_answer_support(row: dict[str, Any]) -> bool:
    return any(bool(candidate.get("is_exact") or candidate.get("is_answer_match")) for candidate in list(row.get("candidates", []) or []))


def _counterfactual_pool(rows: list[dict[str, Any]]) -> list[tuple[str, set[str], set[str]]]:
    out = []
    seen = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            doc = str(candidate.get("doc_text", "") or "")
            if "op=counterfactual_false_claim" not in doc or doc in seen:
                continue
            seen.add(doc)
            ents = DENT_CLAIM_RE.findall(doc)
            slots = set(DSLOT_RE.findall(doc))
            claims = set(DCLAIM_RE.findall(doc))
            if ents and slots:
                out.append((ents[0], slots, claims))
    return out


def _exception_pool(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    out = []
    seen = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            doc = str(candidate.get("doc_text", "") or "")
            if "op=exception" not in doc or doc in seen:
                continue
            seen.add(doc)
            exc = EXCEPTION_RE.search(doc)
            answer_kind = ANSWER_KIND_RE.search(doc)
            if exc and answer_kind:
                out.append((exc.group(1), exc.group(2), answer_kind.group(1)))
    return out


def _typed_remaining_headroom(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter_pool = _counterfactual_pool(rows)
    exception_pool = _exception_pool(rows)
    out: dict[str, Any] = {}
    for operation in ["counterfactual_false_claim", "exception"]:
        row_count = current = typed = recoverable = 0
        for row in rows:
            if str(row.get("operation", "")) != operation:
                continue
            row_count += 1
            supported = _row_answer_support(row)
            current += int(supported)
            query = str(row.get("query_text", ""))
            qents = QENT_RE.findall(query)
            qslots = set(QSLOT_RE.findall(query))
            if operation == "counterfactual_false_claim":
                ok = any(qents and ent == qents[0] and bool(qslots.intersection(slots)) for ent, slots, _claims in counter_pool)
                pool_docs = len(counter_pool)
            else:
                default_kinds = DEFAULT_KIND_RE.findall(query)
                ok = any(qents and default_kinds and ent == qents[0] and answer_kind == default_kinds[0] for ent, _slot, answer_kind in exception_pool)
                pool_docs = len(exception_pool)
            typed += int(ok)
            recoverable += int(ok and not supported)
        out[operation] = {
            "rows": row_count,
            "row_local_answer_support": current,
            "typed_pool_answer_support": typed,
            "typed_pool_recoverable_rows": recoverable,
            "pool_docs": pool_docs,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--stage1082-json", type=Path, default=Path("runs/local/artifacts/stage1082_learned_atomic_proof_expansion_summary.json"))
    parser.add_argument("--stage1083-json", type=Path, default=Path("runs/local/artifacts/stage1083_learned_composition_proof_expansion_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1084_proof_expansion_frontier_rollup_summary.json"))
    args = parser.parse_args()

    rows = [row for row in _iter_jsonl(args.targets_jsonl) if str(row.get("split", "")) == "eval"]
    stage1082 = json.loads(args.stage1082_json.read_text(encoding="utf-8"))
    stage1083 = json.loads(args.stage1083_json.read_text(encoding="utf-8"))
    atomic_delta = (
        int(stage1082["eval"]["atomic_learned_expanded_answer_exact"][0]) - int(stage1082["eval"]["atomic_base_answer_exact"][0]),
        int(stage1082["eval"]["atomic_learned_expanded_answer_exact"][1]) - int(stage1082["eval"]["atomic_base_answer_exact"][1]),
    )
    composition_delta = (
        int(stage1083["eval"]["composition_learned_expanded_answer_exact"][0]) - int(stage1083["eval"]["composition_current_support_answer_exact"][0]),
        int(stage1083["eval"]["composition_learned_expanded_answer_exact"][1]) - int(stage1083["eval"]["composition_current_support_answer_exact"][1]),
    )
    combined = [350 + atomic_delta[0] + composition_delta[0], 333 + atomic_delta[1] + composition_delta[1]]
    remaining = _typed_remaining_headroom(rows)
    optimistic = [
        combined[0] + remaining["counterfactual_false_claim"]["typed_pool_recoverable_rows"] + remaining["exception"]["typed_pool_recoverable_rows"],
        combined[1] + remaining["counterfactual_false_claim"]["typed_pool_recoverable_rows"] + remaining["exception"]["typed_pool_recoverable_rows"],
    ]
    summary = {
        "artifact_kind": "stage1084_proof_expansion_frontier_rollup",
        "status": "completed_proof_expansion_frontier_rollup",
        "stage1069_answer_exact": [350, 333],
        "learned_atomic_delta": list(atomic_delta),
        "learned_composition_delta": list(composition_delta),
        "projected_stage1069_plus_learned_atomic_and_composition_answer_exact": combined,
        "remaining_typed_pool_headroom": remaining,
        "optimistic_with_counterfactual_exception_typed_headroom_answer_exact": optimistic,
        "decision": (
            "Learned proof expansion over atomic and composition already projects to 393/376. "
            "Typed remaining headroom suggests counterfactual and exception expansion could add about 20 more answer rows if learned/budgeted. "
            "Next stage should implement learned counterfactual proof expansion, then learned exception default-kind expansion."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
