from __future__ import annotations

import importlib.util
import json
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
from long_context_candidate_miner import CandidateMiningSafetyError, mine_candidates, validate_candidate_mining_request
from long_context_common import extract_compound_terms
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
    (repos / "repo_a" / "src" / "assets" / "translations").mkdir(parents=True)
    (repos / "repo_a" / "src" / "assets" / "translations" / "lesson.json").write_text(
        '{"title": "Streaming update lesson", "body": "adaptive controller adversarial training dataset"}\n',
        encoding="utf-8",
    )
    (datasets / "trace_a" / "failure.txt").write_text(
        "Late failure report says streaming update became invalid after regression.\n",
        encoding="utf-8",
    )
    return papers, repos, datasets


def test_extract_compound_terms_normalizes_identifiers() -> None:
    text = "multi-agent system uses stateSpaceModel and spectral_kernel_update during rollout"
    terms = extract_compound_terms(text, max_terms=16, source_type="repo", modality="code")
    assert "state_space" in terms
    assert "spectral_kernel_update" in terms
    assert "multi_agent" not in terms


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

    entity_summary = build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    assert entity_summary["entity_count"] >= 1
    assert list((out / "entities").glob("*.parquet"))

    link_summary = build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    assert link_summary["link_count"] >= 1
    assert list((out / "links").glob("*.parquet"))


def test_production_parquet_index_balances_capped_repo_scan_across_repositories(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    repo_root = tmp_path / "balanced_repos"
    (repo_root / "repo_a" / "src" / "assets" / "translations").mkdir(parents=True)
    (repo_root / "repo_a" / "src" / "assets" / "translations" / "lesson.json").write_text(
        '{"title": "attention lesson"}\n',
        encoding="utf-8",
    )
    (repo_root / "repo_b" / "src").mkdir(parents=True)
    (repo_root / "repo_b" / "src" / "engine.py").write_text(
        "def attention_kernel():\n    return True\n",
        encoding="utf-8",
    )
    out = tmp_path / "balanced_out"
    build_chunk_and_mention_shards(
        paper_roots=[],
        repo_roots=[repo_root],
        dataset_roots=[],
        output_dir=out,
        repo_chunk_tokens=64,
        max_files_per_root=2,
        rows_per_shard=8,
    )
    import pyarrow.parquet as pq
    paths = set()
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            paths.add(json.loads(row["metadata_json"])["path"])
    assert any(path.endswith("repo_a/src/assets/translations/lesson.json") for path in paths)
    assert any(path.endswith("repo_b/src/engine.py") for path in paths)


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




def test_candidate_miner_requires_explicit_real_index_flags(tmp_path: Path) -> None:
    try:
        validate_candidate_mining_request(
            index_dir=Path('/arxiv/long_context_transition_index/slice_0006_paper_repo'),
            output=Path('/arxiv/long_context_transition_index/slice_0006_paper_repo/candidates.jsonl'),
            allow_candidate_mining=False,
            allow_arxiv_output=False,
        )
    except CandidateMiningSafetyError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError('unguarded candidate mining request was accepted')
    assert 'allow_candidate_mining_flag' in message
    assert 'arxiv_output_requires_explicit_output_flag' in message

    card = validate_candidate_mining_request(
        index_dir=tmp_path / 'fixture_index',
        output=tmp_path / 'candidates.jsonl',
        allow_candidate_mining=True,
        allow_arxiv_output=False,
    )
    assert card['checks']['allow_candidate_mining_flag'] is True
    assert card['output_under_arxiv'] is False


def test_candidate_miner_prefers_implementation_repo_rows_over_tests(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    datasets = tmp_path / "datasets"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_a" / "tests").mkdir(parents=True)
    (datasets / "trace_a").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Adaptive controller uses spectralkernel for stable update. Spectralkernel remains active.\n",
        encoding="utf-8",
    )
    impl_text = "def spectralkernel_update():\n    return spectralkernel\n"
    test_text = "def test_spectralkernel_update():\n    assert spectralkernel_update() == spectralkernel\n"
    (repos / "repo_a" / "src" / "engine.py").write_text(impl_text, encoding="utf-8")
    (repos / "repo_a" / "tests" / "test_engine.py").write_text(test_text, encoding="utf-8")
    out = tmp_path / "impl_pref_out"
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[datasets],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=8,
    )
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, _ = mine_candidates(index_dir=out, max_candidates=20, required_source_types=("paper", "repo"))
    target = next(candidate for candidate in candidates if candidate["canonical_name"] == "spectralkernel")
    import pyarrow.parquet as pq
    chunk_rows = {}
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            chunk_rows[row["chunk_id"]] = row
    repo_paths = [
        json.loads(chunk_rows[transition["trigger_chunk_id"]]["metadata_json"])["path"]
        for transition in target["transition_chain"]
        if transition["source_type"] == "repo"
    ]
    assert repo_paths
    assert repo_paths[0].endswith("repo_a/src/engine.py")


def test_candidate_miner_prefers_compound_candidates_in_order(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Pre trained encoder improves transfer. Pre trained encoder remains stable. Local update remains stable.\n",
        encoding="utf-8",
    )
    (papers / "paper_a" / "results.txt").write_text(
        "Pre trained setup improves robustness. Local behavior also changes.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def pre_trained_encoder():\n    return 'pre trained'\n",
        encoding="utf-8",
    )
    (repos / "repo_b" / "src" / "helper.py").write_text(
        "def local_update():\n    return 'local'\n",
        encoding="utf-8",
    )
    out = tmp_path / "compound_order_out"
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=8,
    )
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, summary = mine_candidates(index_dir=out, max_candidates=10, required_source_types=("paper", "repo"), max_entity_chunk_ratio=1.0, max_compound_entity_chunk_ratio=1.0)
    assert candidates
    assert candidates[0]["template_family"] == "compound_concept_transition"
    assert "compound_concept_transition" in summary["template_family_counts"]


def test_candidate_miner_rejects_single_doc_single_repo_overlap(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Angle remains stable under the adaptive controller. Angle remains observable.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def angle_update():\n    angle = 1\n    return angle\n",
        encoding="utf-8",
    )
    out = tmp_path / "single_overlap_out"
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=8,
    )
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, _ = mine_candidates(index_dir=out, max_candidates=20, required_source_types=("paper", "repo"))
    assert all(candidate["canonical_name"] != "angle" for candidate in candidates)


def test_candidate_miner_rejects_test_only_repo_evidence_when_no_impl_support(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "tests").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Adaptive controller uses spectralkernel for stable update. Spectralkernel remains active.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "tests" / "test_engine.py").write_text(
        "def test_spectralkernel_update():\n    assert spectralkernel_update() == spectralkernel\n",
        encoding="utf-8",
    )
    out = tmp_path / "test_only_out"
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=8,
    )
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, _ = mine_candidates(index_dir=out, max_candidates=20, required_source_types=("paper", "repo"))
    assert all(candidate["canonical_name"] != "spectralkernel" for candidate in candidates)


def test_candidate_miner_from_parquet_index(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "cand_inputs")
    out = tmp_path / "cand_out"
    source_summary = build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[],
        output_dir=out,
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=2,
    )
    assert source_summary["chunk_count"] >= 2
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, summary = mine_candidates(index_dir=out, max_candidates=10, required_source_types=("paper", "repo"))
    assert candidates
    assert summary["candidate_count"] == len(candidates)
    assert summary["max_entity_chunk_ratio"] == 0.01
    assert summary["max_compound_entity_chunk_ratio"] == 0.04
    assert "template_family_counts" in summary
    repo_chunk_ids = {
        chunk_id
        for candidate in candidates
        for chunk_id, transition in zip(candidate["supporting_chunk_ids"], candidate["transition_chain"])
        if transition["source_type"] == "repo"
    }
    assert repo_chunk_ids
    import pyarrow.parquet as pq
    chunk_rows = {}
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            chunk_rows[row["chunk_id"]] = row
    repo_paths = {json.loads(chunk_rows[chunk_id]["metadata_json"])["path"] for chunk_id in repo_chunk_ids}
    assert all("/assets/translations/" not in path for path in repo_paths)
    assert any(path.endswith("engine.py") for path in repo_paths)
