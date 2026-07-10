from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any

from long_context_common import choose_distractors, read_jsonl, source_mix, stable_id, write_jsonl


def render_examples(
    *,
    chunks: list[dict[str, Any]],
    programs: list[dict[str, Any]],
    target_context_tokens: int = 100000,
    noise_ratio: float = 0.995,
    seed: int = 1337,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    chunk_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    rows: list[dict[str, Any]] = []
    used_distractor_ids: set[str] = set()
    for index, program in enumerate(programs, start=1):
        relevant = [chunk_by_id[chunk_id] for chunk_id in program.get("supporting_chunk_ids", []) if chunk_id in chunk_by_id]
        if len(relevant) < 2:
            continue
        relevant_token_total = sum(int(chunk.get("token_count", 0)) for chunk in relevant)
        if relevant_token_total >= target_context_tokens:
            continue
        distractor_budget = max(0, int(target_context_tokens * noise_ratio) - relevant_token_total)
        distractors = choose_distractors(
            chunks,
            exclude_ids={str(chunk["chunk_id"]) for chunk in relevant} | used_distractor_ids,
            target_tokens=distractor_budget,
            rng=rng,
        )
        used_distractor_ids.update(str(chunk.get("chunk_id") or "") for chunk in distractors if str(chunk.get("chunk_id") or ""))
        rng.shuffle(distractors)
        rendered_ids: list[str] = []
        insert_every = max(1, len(distractors) // len(relevant))
        cursor = 0
        for rel in relevant:
            for _ in range(insert_every):
                if cursor >= len(distractors):
                    break
                rendered_ids.append(str(distractors[cursor]["chunk_id"]))
                cursor += 1
            rendered_ids.append(str(rel["chunk_id"]))
        while cursor < len(distractors):
            rendered_ids.append(str(distractors[cursor]["chunk_id"]))
            cursor += 1
        rendered_chunks = [chunk_by_id.get(chunk_id) or next(chunk for chunk in distractors if chunk["chunk_id"] == chunk_id) for chunk_id in rendered_ids]
        context_token_count = sum(int(chunk.get("token_count", 0)) for chunk in rendered_chunks)
        rows.append(
            {
                "example_id": stable_id("lcx", program["program_id"], str(index)),
                "program_id": program["program_id"],
                "context_length_target": target_context_tokens,
                "context_token_count": context_token_count,
                "rendered_chunk_ids": rendered_ids,
                "query": {
                    "query_family": "final_state",
                    "text": program.get("query_text") or "What is the final state after all evidence?",
                },
                "targets": {
                    "final_answer": next(iter(program["final_state"].values())),
                    "final_state": program["final_state"],
                    "supporting_chunk_ids": program["supporting_chunk_ids"],
                },
                "aux_targets": {
                    "state_probe_points": program.get("state_probe_points", []),
                },
                "render_stats": {
                    "relevant_chunk_count": len(relevant),
                    "distractor_chunk_count": len(distractors),
                    "source_mix": source_mix(rendered_chunks),
                },
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Render long-context examples from latent transition programs and chunk catalogs.")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--programs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-context-tokens", type=int, default=100000)
    parser.add_argument("--noise-ratio", type=float, default=0.995)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    rows = render_examples(
        chunks=read_jsonl(args.chunks),
        programs=read_jsonl(args.programs),
        target_context_tokens=args.target_context_tokens,
        noise_ratio=args.noise_ratio,
        seed=args.seed,
    )
    write_jsonl(args.output, rows)


if __name__ == "__main__":
    main()
