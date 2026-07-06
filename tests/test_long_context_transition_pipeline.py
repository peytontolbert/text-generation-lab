from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_stage8800_long_context_transition_dataset import main as build_stage_main
from long_context_chunk_catalog import build_chunk_catalog
from long_context_entity_linker import build_entities
from long_context_program_builder import build_programs
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
    assert (out / "programs.jsonl").is_file()
    assert (out / "examples.jsonl").is_file()
    assert (out / "quality_audits.jsonl").is_file()
    assert (out / "summary.json").is_file()
