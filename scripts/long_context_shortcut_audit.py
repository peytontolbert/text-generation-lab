from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from long_context_common import lexical_overlap_score, read_jsonl, write_jsonl


def audit_examples(
    *,
    examples: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    lexical_topk: int = 8,
) -> list[dict[str, Any]]:
    chunk_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    audits: list[dict[str, Any]] = []
    for example in examples:
        supporting_ids = [str(item) for item in example.get("targets", {}).get("supporting_chunk_ids", [])]
        supporting = [chunk_by_id[chunk_id] for chunk_id in supporting_ids if chunk_id in chunk_by_id]
        query_text = str(example.get("query", {}).get("text") or "")
        final_answer = example.get("targets", {}).get("final_answer")
        last_chunk = supporting[-1] if supporting else None
        single_chunk_pass = len(supporting) <= 1
        last_chunk_pass = bool(last_chunk and any(str(final_answer).lower() in last_chunk.get("text", "").lower() for _ in [0]))
        ranked = sorted(
            chunks,
            key=lambda chunk: lexical_overlap_score(query_text, str(chunk.get("text") or "")),
            reverse=True,
        )[: max(1, lexical_topk)]
        topk_ids = {str(chunk["chunk_id"]) for chunk in ranked}
        lexical_topk_pass = all(chunk_id in topk_ids for chunk_id in supporting_ids[: min(2, len(supporting_ids))]) if supporting_ids else False
        counterfactual_flip_pass = len(supporting) >= 2
        state_order_sensitive = len(supporting) >= 2 and supporting_ids != list(reversed(supporting_ids))
        accepted = not single_chunk_pass and not last_chunk_pass and not lexical_topk_pass and counterfactual_flip_pass
        audits.append(
            {
                "example_id": example["example_id"],
                "single_chunk_pass": single_chunk_pass,
                "last_chunk_pass": last_chunk_pass,
                "lexical_topk_pass": lexical_topk_pass,
                "counterfactual_flip_pass": counterfactual_flip_pass,
                "state_order_sensitive": state_order_sensitive,
                "accepted": accepted,
            }
        )
    return audits


def main() -> None:
    parser = argparse.ArgumentParser(description="Run structural shortcut audits over long-context transition examples.")
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accepted-output", type=Path)
    parser.add_argument("--lexical-topk", type=int, default=8)
    args = parser.parse_args()
    examples = read_jsonl(args.examples)
    chunks = read_jsonl(args.chunks)
    audits = audit_examples(examples=examples, chunks=chunks, lexical_topk=args.lexical_topk)
    write_jsonl(args.output, audits)
    if args.accepted_output:
        accepted = [example for example, audit in zip(examples, audits) if audit["accepted"]]
        write_jsonl(args.accepted_output, accepted)


if __name__ == "__main__":
    main()
