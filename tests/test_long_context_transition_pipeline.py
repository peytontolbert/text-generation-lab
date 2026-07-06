from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_stage8800_long_context_transition_dataset import main as build_stage_main
from build_stage8801_long_context_corpus_index import (
    CorpusIndexSafetyError,
    build_chunk_and_mention_shards,
    build_entities_with_pyarrow,
    build_links_with_pyarrow,
    validate_corpus_index_request,
)
from long_context_chunk_catalog import build_chunk_catalog
from long_context_entity_linker import build_entities
from long_context_program_builder import build_programs
from long_context_relation_graph_builder import build_relation_graph
from long_context_example_renderer import render_examples
from long_context_shortcut_audit import audit_examples


def _make_tree(root: Path) -> tuple[Path, Path, Path]:
    papers = root / "papers"
    repos = root / "repositories"
    datasets = root / "datasets"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a").mkdir(parents=True)
    (datasets / "trace_a").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Streaming update improves the adaptive controller. Online update stays active under normal conditions.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "engine.py").write_text(
        "def online_update():\n    return 'streaming update active'\n",
        encoding="utf-8",
    )
    (datasets / "trace_a" / "failure.txt").write_text(
        "Late failure report says streaming update became invalid after regression.\n",
        encoding="utf-8",
    )
    return papers, repos, datasets


def test_long_context_pipeline_end_to_end(tmp_path: Path) -> None:
    papers, repos, datasets = _make_tree(tmp_path)
    chunks, summary = build_chunk_catalog(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[datasets],
        max_files_per_root=20,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
    )
    assert chunks
    assert summary["chunk_count"] == len(chunks)

    entities, alias_card = build_entities(chunks, min_mention_count=2)
    assert entities
    assert alias_card["entity_count"] == len(entities)

    links, links_summary = build_relation_graph(chunks, entities)
    assert links
    assert links_summary["link_count"] == len(links)

    programs = build_programs(chunks=chunks, entities=entities, num_programs=10)
    assert programs
    assert all(len(program["transitions"]) >= 2 for program in programs)

    examples = render_examples(chunks=chunks, programs=programs, target_context_tokens=256, noise_ratio=0.75)
    assert examples
    assert all(example["context_token_count"] > 0 for example in examples)

    audits = audit_examples(examples=examples, chunks=chunks, lexical_topk=4)
    assert audits
    assert all("accepted" in audit for audit in audits)


def test_stage_builder_cli_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    papers, repos, datasets = _make_tree(tmp_path / "inputs")
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_stage8800_long_context_transition_dataset.py",
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--output-dir",
            str(out),
            "--max-files-per-root",
            "20",
            "--num-programs",
            "10",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
        ],
    )
    build_stage_main()
    assert (out / "chunks.jsonl").is_file()
    assert (out / "entities.jsonl").is_file()
    assert (out / "links.jsonl").is_file()
    assert (out / "programs.jsonl").is_file()
    assert (out / "examples.jsonl").is_file()
    assert (out / "quality_audits.jsonl").is_file()
    assert (out / "summary.json").is_file()


def test_production_parquet_index_writes_outputs(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "parquet_inputs")
    out = tmp_path / "parquet_out"
    source_summary = build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[datasets],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=2,
    )
    assert source_summary["chunk_count"] >= 3
    assert list((out / "chunks").glob("*.parquet"))
    assert list((out / "chunk_mentions").glob("*.parquet"))

    entity_summary = build_entities_with_pyarrow(output_dir=out, min_mention_count=2)
    assert entity_summary["entity_count"] >= 1
    assert list((out / "entities").glob("*.parquet"))

    link_summary = build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    assert link_summary["link_count"] >= 1
    assert list((out / "links").glob("*.parquet"))


def test_production_parquet_index_requires_explicit_corpus_scan_flag(tmp_path: Path) -> None:
    try:
        validate_corpus_index_request(
            paper_roots=[],
            repo_roots=[Path('/arxiv/repositories')],
            dataset_roots=[Path('/arxiv/datasets')],
            output_dir=Path('/arxiv/long_context_transition_index'),
            allow_corpus_scan=False,
            allow_arxiv_output=False,
        )
    except CorpusIndexSafetyError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError('unguarded corpus index request was accepted')
    assert 'allow_corpus_scan_flag' in message
    assert 'arxiv_output_requires_explicit_output_flag' in message

    card = validate_corpus_index_request(
        paper_roots=[],
        repo_roots=[tmp_path / 'repo_fixture'],
        dataset_roots=[],
        output_dir=tmp_path / 'index_out',
        allow_corpus_scan=True,
        allow_arxiv_output=False,
    )
    assert card['checks']['allow_corpus_scan_flag'] is True
    assert card['output_under_arxiv'] is False
