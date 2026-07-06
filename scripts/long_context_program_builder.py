from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from long_context_common import bool_flip, pick_query_text, read_jsonl, stable_id, write_jsonl


DEFAULT_TEMPLATE_FAMILIES = (
    "claim_revision",
    "alias_merge",
    "paper_repo_benchmark",
)


def _chunk_lookup(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(chunk["chunk_id"]): chunk for chunk in chunks}


def _group_entity_mentions(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for entity in entities:
        if len(entity.get("mentions", [])) < 2:
            continue
        out.append(entity)
    return out


def _family_for_mentions(entity: dict[str, Any]) -> str:
    types = set((entity.get("source_type_counts") or {}).keys())
    if "paper" in types and "repo" in types:
        return "paper_repo_benchmark"
    if len(entity.get("mentions", [])) >= 3:
        return "claim_revision"
    return "alias_merge"


def build_programs(
    *,
    chunks: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    num_programs: int = 1000,
    template_families: tuple[str, ...] = DEFAULT_TEMPLATE_FAMILIES,
    seed: int = 1337,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    chunk_by_id = _chunk_lookup(chunks)
    candidates = [entity for entity in _group_entity_mentions(entities) if _family_for_mentions(entity) in template_families]
    rng.shuffle(candidates)
    programs: list[dict[str, Any]] = []
    for entity in candidates[:num_programs]:
        mentions = [chunk_by_id[m] for m in entity.get("mentions", []) if m in chunk_by_id]
        mentions.sort(key=lambda row: (row["source_type"], row["chunk_id"]))
        if len(mentions) < 2:
            continue
        family = _family_for_mentions(entity)
        state_name = f"{entity['canonical_name']}_active"
        initial_state = {state_name: False}
        transitions = []
        current = False
        for idx, mention in enumerate(mentions[:4], start=1):
            if family == "claim_revision":
                current = True if idx % 2 == 1 else False
                kind = "claim" if idx % 2 == 1 else "revision"
            elif family == "paper_repo_benchmark":
                if mention["source_type"] == "paper":
                    current = True
                    kind = "claim"
                elif mention["source_type"] == "repo":
                    current = True
                    kind = "implementation_evidence"
                else:
                    current = bool_flip(current)
                    kind = "benchmark_result"
            else:
                current = True
                kind = "alias_merge"
            transitions.append(
                {
                    "transition_id": stable_id("t", entity["canonical_name"], str(idx), mention["chunk_id"]),
                    "trigger_chunk_id": mention["chunk_id"],
                    "kind": kind,
                    "effects": {state_name: current},
                }
            )
        if len(transitions) < 2:
            continue
        final_state = dict(initial_state)
        probe_points = []
        for transition in transitions:
            final_state.update(transition["effects"])
            probe_points.append({"after_chunk_id": transition["trigger_chunk_id"], "state": dict(final_state)})
        programs.append(
            {
                "program_id": stable_id("prog", entity["canonical_name"], family, str(len(programs) + 1)),
                "template_family": family,
                "entity_id": entity["entity_id"],
                "state_variables": [{"name": state_name, "type": "bool"}],
                "initial_state": initial_state,
                "transitions": transitions,
                "final_state": final_state,
                "query_text": pick_query_text({"state_variables": [{"name": state_name}]}),
                "state_probe_points": probe_points,
                "supporting_chunk_ids": [transition["trigger_chunk_id"] for transition in transitions],
            }
        )
    return programs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build latent state-transition programs over chunk/entity indices.")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--num-programs", type=int, default=1000)
    parser.add_argument("--template-families", type=str, default=",".join(DEFAULT_TEMPLATE_FAMILIES))
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    rows = build_programs(
        chunks=read_jsonl(args.chunks),
        entities=read_jsonl(args.entities),
        num_programs=args.num_programs,
        template_families=tuple(item.strip() for item in args.template_families.split(",") if item.strip()),
        seed=args.seed,
    )
    write_jsonl(args.output, rows)


if __name__ == "__main__":
    main()
