from __future__ import annotations

import argparse
from pathlib import Path

from long_context_chunk_catalog import build_chunk_catalog
from long_context_entity_linker import build_entities
from long_context_relation_graph_builder import build_relation_graph
from long_context_example_renderer import render_examples
from long_context_program_builder import DEFAULT_TEMPLATE_FAMILIES, build_programs
from long_context_shortcut_audit import audit_examples
from long_context_common import write_json, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a long-context transition dataset from local paper/repo/dataset roots.")
    parser.add_argument("--papers-root", action="append", type=Path, default=[])
    parser.add_argument("--repos-root", action="append", type=Path, default=[])
    parser.add_argument("--datasets-root", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--paper-chunk-tokens", type=int, default=1024)
    parser.add_argument("--repo-chunk-tokens", type=int, default=512)
    parser.add_argument("--trace-chunk-tokens", type=int, default=384)
    parser.add_argument("--max-files-per-root", type=int, default=1000)
    parser.add_argument("--max-chars-per-file", type=int, default=120000)
    parser.add_argument("--min-mention-count", type=int, default=2)
    parser.add_argument("--num-programs", type=int, default=1000)
    parser.add_argument("--template-families", type=str, default=",".join(DEFAULT_TEMPLATE_FAMILIES))
    parser.add_argument("--target-context-tokens", type=int, default=100000)
    parser.add_argument("--noise-ratio", type=float, default=0.995)
    parser.add_argument("--lexical-topk", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    chunks, inventory = build_chunk_catalog(
        paper_roots=args.papers_root,
        repo_roots=args.repos_root,
        dataset_roots=args.datasets_root,
        paper_chunk_tokens=args.paper_chunk_tokens,
        repo_chunk_tokens=args.repo_chunk_tokens,
        trace_chunk_tokens=args.trace_chunk_tokens,
        max_files_per_root=args.max_files_per_root,
        max_chars_per_file=args.max_chars_per_file,
    )
    write_jsonl(out / "chunks.jsonl", chunks)
    write_json(out / "source_inventory.json", inventory)

    entities, alias_card = build_entities(chunks, min_mention_count=args.min_mention_count)
    write_jsonl(out / "entities.jsonl", entities)
    write_json(out / "entity_aliases.json", alias_card)

    links, links_summary = build_relation_graph(chunks, entities)
    write_jsonl(out / "links.jsonl", links)
    write_json(out / "links_summary.json", links_summary)

    programs = build_programs(
        chunks=chunks,
        entities=entities,
        num_programs=args.num_programs,
        template_families=tuple(item.strip() for item in args.template_families.split(",") if item.strip()),
        seed=args.seed,
    )
    write_jsonl(out / "programs.jsonl", programs)

    examples = render_examples(
        chunks=chunks,
        programs=programs,
        target_context_tokens=args.target_context_tokens,
        noise_ratio=args.noise_ratio,
        seed=args.seed,
    )
    write_jsonl(out / "examples.jsonl", examples)

    audits = audit_examples(examples=examples, chunks=chunks, lexical_topk=args.lexical_topk)
    write_jsonl(out / "quality_audits.jsonl", audits)
    write_jsonl(out / "examples_accepted.jsonl", [example for example, audit in zip(examples, audits) if audit["accepted"]])

    summary = {
        "chunk_count": len(chunks),
        "entity_count": len(entities),
        "link_count": len(links),
        "program_count": len(programs),
        "example_count": len(examples),
        "accepted_example_count": sum(1 for audit in audits if audit["accepted"]),
        "accepted_rate": (sum(1 for audit in audits if audit["accepted"]) / max(1, len(audits))),
    }
    write_json(out / "summary.json", summary)


if __name__ == "__main__":
    main()
