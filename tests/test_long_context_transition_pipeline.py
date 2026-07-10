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
from annotate_long_context_model_signals import ModelSignalAnnotationError, annotate_candidate_rows, list_annotation_providers, resolve_annotation_provider
import run_long_context_transition_pipeline as run_pipeline_module
from run_long_context_transition_pipeline import main as run_pipeline_main
from long_context_common import extract_compound_terms, write_json, write_jsonl
from long_context_compound_candidate_curator import classify_compound_candidate, curate_compound_candidates
from build_stage8802_compound_concept_examples import build_compound_concept_examples, build_conflict_training_rows, build_listwise_retrieval_rows, build_maintenance_action_rows, build_maintenance_preference_rows, build_maintenance_rationale_rows, build_maintenance_trace_rows, build_maintenance_training_rows, build_pairwise_retrieval_rows, build_retrieval_training_rows, infer_conflict_supervision
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


def test_compound_candidate_curator_accepts_ml_phrase_and_rejects_generic_phrase(tmp_path: Path) -> None:
    candidates = [
        {
            "candidate_id": "cand_round_trip",
            "canonical_name": "round_trip",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "paper"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["a", "b", "c"],
        },
        {
            "candidate_id": "cand_non_empty",
            "canonical_name": "non_empty",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["x", "y"],
        },
    ]
    scored, summary = curate_compound_candidates(candidates)
    by_name = {row["canonical_name"]: row for row in scored}
    assert by_name["round_trip"]["quality_tier"] == "accepted"
    assert by_name["non_empty"]["quality_tier"] == "rejected"
    assert summary["accepted_count"] == 1


def test_compound_candidate_curator_rejects_generic_compound() -> None:
    candidates = [
        {
            "candidate_id": "cand_well_known",
            "canonical_name": "well_known",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "paper"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["a", "b", "c"],
        },
    ]
    scored, summary = curate_compound_candidates(candidates)
    assert scored[0]["domain"] == "generic_compound"
    assert scored[0]["quality_tier"] == "rejected"
    assert summary["accepted_count"] == 0


def test_compound_candidate_curator_software_mode_recovers_real_software_compounds() -> None:
    candidates = [
        {
            "candidate_id": "cand_round_trip",
            "canonical_name": "round_trip",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["a", "b", "c"],
        },
        {
            "candidate_id": "cand_third_party",
            "canonical_name": "third_party",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["d", "e", "f"],
        },
        {
            "candidate_id": "cand_well_known",
            "canonical_name": "well_known",
            "template_family": "compound_concept_transition",
            "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
            "supporting_chunk_ids": ["x", "y"],
        },
    ]
    scored, summary = curate_compound_candidates(candidates, target_domain="software")
    by_name = {row["canonical_name"]: row for row in scored}
    assert by_name["round_trip"]["domain"] == "software_concept"
    assert by_name["round_trip"]["quality_tier"] == "accepted"
    assert by_name["third_party"]["domain"] == "software_concept"
    assert by_name["third_party"]["quality_tier"] == "accepted"
    assert by_name["well_known"]["quality_tier"] == "rejected"
    assert summary["target_domain"] == "software"
    assert summary["accepted_count"] == 2


def test_compound_candidate_curator_uses_metadata_to_recover_software_candidates() -> None:
    candidate = {
        "candidate_id": "cand_parse_args",
        "canonical_name": "parse_args",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
        "supporting_chunk_ids": ["a", "b", "c"],
        "dataset_compiler": {
            "skill_tags": ["compound_concept", "software_maintenance", "cross_repo_evidence"],
            "retrieval_links": [
                {"source_type": "repo", "path": "tooling/src/cli/args.py", "language": "python"},
                {"source_type": "repo", "path": "tooling/src/cli/parser.py", "language": "python"},
                {"source_type": "paper", "path": "paper_a/method.txt", "language": None},
            ],
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "accepted"
    assert scored["software_hint"] >= 1
    assert "metadata_repo_code_language" in scored["reasons"]
    assert "metadata_repo_impl_path" in scored["reasons"]
    assert "accept" in scored["reasons"]


def test_compound_candidate_curator_narrowly_recovers_generic_cli_like_candidate() -> None:
    candidate = {
        "candidate_id": "cand_build_command",
        "canonical_name": "build_command",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
        "supporting_chunk_ids": ["a", "b", "c"],
        "dataset_compiler": {
            "skill_tags": ["compound_concept", "software_maintenance", "cross_repo_evidence"],
            "retrieval_links": [
                {"source_type": "repo", "path": "cli/src/commands/config/mod.rs", "language": "rust"},
                {"source_type": "repo", "path": "compose/cmd/compose/build.go", "language": "go"},
                {"source_type": "paper", "path": "paper_a/method.txt", "language": None},
            ],
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "accepted"
    assert "narrow_recovery_token:command" in scored["reasons"]
    assert "narrow_recovery:software_path" in scored["reasons"]


def test_compound_candidate_curator_narrowly_recovers_operational_request_candidate() -> None:
    candidate = {
        "candidate_id": "cand_send_request",
        "canonical_name": "send_request",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
        "supporting_chunk_ids": ["a", "b", "c"],
        "dataset_compiler": {
            "skill_tags": ["compound_concept", "software_maintenance", "cross_repo_evidence"],
            "retrieval_links": [
                {"source_type": "repo", "path": "client/src/http/request.ts", "language": "typescript"},
                {"source_type": "repo", "path": "server/src/api/route.ts", "language": "typescript"},
                {"source_type": "paper", "path": "paper_a/method.txt", "language": None},
            ],
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "accepted"
    assert "narrow_recovery_operational:request" in scored["reasons"]
    assert "narrow_recovery:software_path" in scored["reasons"]


def test_compound_candidate_curator_narrowly_recovers_infra_status_candidate() -> None:
    candidate = {
        "candidate_id": "cand_get_status",
        "canonical_name": "get_status",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
        "supporting_chunk_ids": ["a", "b", "c"],
        "dataset_compiler": {
            "skill_tags": ["compound_concept", "software_maintenance", "cross_repo_evidence"],
            "retrieval_links": [
                {"source_type": "repo", "path": "cli/cloud/commands/app/status/main.py", "language": "python"},
                {"source_type": "repo", "path": "client/src/status.ts", "language": "typescript"},
                {"source_type": "paper", "path": "paper_a/method.txt", "language": None},
            ],
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "accepted"
    assert "narrow_recovery_infra:status" in scored["reasons"]
    assert "narrow_recovery:software_path" in scored["reasons"]


def test_compound_candidate_curator_uses_model_assisted_signals_to_recover_software_candidate() -> None:
    candidate = {
        "candidate_id": "cand_project_summary",
        "canonical_name": "project_summary",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "repo"}],
        "supporting_chunk_ids": ["a", "b", "c"],
        "dataset_compiler": {
            "skill_tags": ["compound_concept", "software_maintenance", "cross_repo_evidence"],
            "retrieval_links": [
                {"source_type": "repo", "path": "services/src/project/summary_handler.py", "language": "python"},
                {"source_type": "repo", "path": "client/src/project/summary.ts", "language": "typescript"},
            ],
        },
        "model_assisted_signals": {
            "domain_classifier": {"label": "software_concept", "confidence": 0.84},
            "llm_judge": {"label": "software_concept", "confidence": 0.93},
            "retrieval_reranker": {"top_repo_support_score": 0.88},
            "embedding_neighbors": {"software_similarity": 0.79, "ml_similarity": 0.11},
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "accepted"
    assert scored["accept_override"] is True
    assert scored["model_software_bonus"] >= 2
    assert "model_domain:software:0.84" in scored["reasons"]
    assert "model_llm:software:0.93" in scored["reasons"]
    assert "model_llm:accept_override" in scored["reasons"]
    assert "model_reranker:repo_support:0.88" in scored["reasons"]
    assert "model_embed:software:0.79" in scored["reasons"]


def test_compound_candidate_curator_does_not_override_missing_repo_support() -> None:
    candidate = {
        "candidate_id": "cand_project_summary_no_repo",
        "canonical_name": "project_summary",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "paper"}],
        "supporting_chunk_ids": ["a", "b"],
        "model_assisted_signals": {
            "llm_judge": {"label": "software_concept", "confidence": 0.96},
        },
    }
    scored = classify_compound_candidate(candidate, target_domain="software")
    assert scored["domain"] == "software_concept"
    assert scored["quality_tier"] == "rejected"
    assert scored["accept_override"] is True
    assert "reject:no_repo_support" in scored["reasons"]
    assert "reject:override_without_repo_support" in scored["reasons"]


def test_annotate_candidate_rows_emits_verification_record(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "annotator_inputs")
    out = tmp_path / "annotator_index"
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
    candidate = {
        "candidate_id": "cand_online_update",
        "canonical_name": "online_update",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}, {"source_type": "dataset"}],
        "supporting_chunk_ids": [],
    }
    import pyarrow.parquet as pq
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            text_value = str(row.get("text") or "").lower()
            if "online update" in text_value or "streaming update" in text_value:
                candidate["supporting_chunk_ids"].append(row["chunk_id"])
    candidates_path = tmp_path / "annotator_candidates.jsonl"
    candidates_path.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
    annotated, summary = annotate_candidate_rows(index_dir=out, candidates_path=candidates_path, provider="heuristic_proxy_v1")
    assert summary["candidate_count"] == 1
    payload = annotated[0]["model_assisted_signals"]
    assert payload["provider"] == "heuristic_proxy_v1"
    assert payload["retrieval_reranker"]["top_repo_support_score"] > 0.0
    assert payload["embedding_neighbors"]["software_similarity"] >= 0.0
    assert payload["verification_record"]["verifier_type"] == "heuristic_proxy"
    assert payload["verification_record"]["criteria"]["causal_usefulness"] > 0.0
    assert payload["verification_record"]["evidence_spans"]


def test_annotation_provider_registry_lists_heuristic_proxy() -> None:
    assert list_annotation_providers() == ["heuristic_proxy_v1"]
    provider_name, implementation = resolve_annotation_provider("heuristic_proxy_v1")
    assert provider_name == "heuristic_proxy_v1"
    assert callable(implementation)


def test_annotate_candidate_rows_requires_explicit_provider(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "annotator_required_inputs")
    out = tmp_path / "annotator_required_index"
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
    candidates_path = tmp_path / "annotator_required_candidates.jsonl"
    candidates_path.write_text(json.dumps({
        "candidate_id": "cand_online_update_required",
        "canonical_name": "online_update",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
        "supporting_chunk_ids": [],
    }) + "\n", encoding="utf-8")
    try:
        annotate_candidate_rows(index_dir=out, candidates_path=candidates_path)
    except ModelSignalAnnotationError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError("annotation stage accepted an implicit provider")
    assert "annotation_provider_required" in message


def test_annotate_candidate_rows_rejects_unsupported_provider(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "annotator_unsupported_inputs")
    out = tmp_path / "annotator_unsupported_index"
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
    candidates_path = tmp_path / "annotator_unsupported_candidates.jsonl"
    candidates_path.write_text(json.dumps({
        "candidate_id": "cand_online_update_unsupported",
        "canonical_name": "online_update",
        "template_family": "compound_concept_transition",
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
        "supporting_chunk_ids": [],
    }) + "\n", encoding="utf-8")
    try:
        annotate_candidate_rows(index_dir=out, candidates_path=candidates_path, provider="fake_provider_v0")
    except ModelSignalAnnotationError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError("annotation stage accepted an unsupported provider")
    assert "unsupported_annotation_provider:fake_provider_v0" in message


def test_extract_compound_terms_normalizes_identifiers() -> None:
    text = "multi-agent system uses stateSpaceModel and spectral_kernel_update during rollout"
    terms = extract_compound_terms(text, max_terms=16, source_type="repo", modality="code")
    assert "state_space" in terms
    assert "spectral_kernel_update" in terms
    assert "multi_agent" not in terms


def test_declared_paper_root_is_classified_as_paper_even_without_papers_in_path(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    exports_root = tmp_path / "exports_like_root"
    exports_root.mkdir(parents=True)
    paper_path = exports_root / "paper_a.txt"
    paper_path.write_text("Adaptive controller remains active.\n", encoding="utf-8")

    source_summary = build_chunk_and_mention_shards(
        paper_roots=[exports_root],
        repo_roots=[],
        dataset_roots=[],
        output_dir=tmp_path / "out",
        paper_chunk_tokens=64,
        repo_chunk_tokens=64,
        trace_chunk_tokens=64,
        rows_per_shard=8,
    )
    assert source_summary["source_type_counts"]["paper"] >= 1


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



def test_production_parquet_index_ingests_dataset_parquet_rows(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    import pyarrow as pa
    import pyarrow.parquet as pq

    datasets = tmp_path / "dataset_parquet_inputs" / "datasets"
    dataset_dir = datasets / "trace_a"
    dataset_dir.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "problem_statement": ["Tensor shape mismatch appears after adaptive update.", "Retriever selected the wrong file under strict verification."],
                "patch": ["Adjust hidden size projection before matmul.", "Rank implementation files above tests in retrieval."],
                "traceback": ["RuntimeError: mat1 and mat2 shapes cannot be multiplied", "AssertionError: missing cross repo grounding"],
            }
        ),
        dataset_dir / "train.parquet",
    )
    out = tmp_path / "dataset_parquet_out"
    source_summary = build_chunk_and_mention_shards(
        paper_roots=[],
        repo_roots=[],
        dataset_roots=[datasets],
        output_dir=out,
        trace_chunk_tokens=64,
        max_rows_per_parquet_file=8,
        rows_per_shard=4,
    )
    assert source_summary["chunk_count"] >= 2

    rows = []
    for shard in sorted((out / "chunks").glob("*.parquet")):
        rows.extend(pq.read_table(shard).to_pylist())
    assert rows
    dataset_rows = [row for row in rows if row["source_type"] == "dataset"]
    assert dataset_rows
    metadata = json.loads(dataset_rows[0]["metadata_json"])
    assert metadata["dataset_format"] == "parquet"
    assert metadata["dataset_row_index"] == 0
    assert set(metadata["dataset_text_fields"]) == {"problem_statement", "patch", "traceback"}
    assert "problem_statement" in dataset_rows[0]["text"]
    assert "traceback" in dataset_rows[0]["text"]


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




def test_build_stage8802_compound_concept_examples(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "stage8802_inputs")
    out = tmp_path / "stage8802_out"
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
    candidates_path = tmp_path / "compound_candidates.jsonl"
    candidates_path.write_text(
        json.dumps({
            "candidate_id": "cand_round_trip",
            "canonical_name": "round_trip",
            "template_family": "compound_concept_transition",
            "state_variable": "round_trip_active",
            "supporting_chunk_ids": [
                next(iter((out / "chunks").glob("*.parquet"))).name if False else "",
            ],
            "final_state": {"round_trip_active": True},
            "transition_chain": [{"source_type": "paper"}, {"source_type": "paper"}, {"source_type": "repo"}],
        }) + "\n",
        encoding="utf-8",
    )
    import pyarrow.parquet as pq
    chunk_ids = []
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            chunk_ids.append(row["chunk_id"])
    payload = {
        "candidate_id": "cand_round_trip",
        "canonical_name": "round_trip",
        "template_family": "compound_concept_transition",
        "state_variable": "round_trip_active",
        "supporting_chunk_ids": chunk_ids[:2],
        "final_state": {"round_trip_active": True},
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
    }
    candidates_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    examples, summary, scored, examples_by_domain, retrieval_rows = build_compound_concept_examples(
        index_dir=out,
        candidates_path=candidates_path,
        target_context_tokens=256,
        noise_ratio=0.5,
        seed=7,
    )
    assert scored
    assert summary["compound_candidate_count"] == 1
    assert summary["rendered_example_count"] == len(examples)
    assert summary["rendered_examples_by_domain"]["ml_concept"] == len(examples_by_domain["ml_concept"])
    assert summary["rendered_examples_by_domain"]["software_concept"] == len(examples_by_domain["software_concept"])
    assert summary["retrieval_row_count"] == len(retrieval_rows)
    assert summary["retrieval_conflict_label_counts"]
    assert summary["retrieval_relation_label_counts"]
    assert summary["conflict_conflict_row_count"] >= 0
    assert summary["maintenance_row_count"] >= 0
    assert summary["maintenance_action_row_count"] >= 0
    assert summary["maintenance_rationale_row_count"] >= 0
    assert summary["maintenance_trace_row_count"] >= 0
    assert summary["maintenance_preference_row_count"] >= 0



def test_build_stage8802_requires_compiled_task_metadata(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Round trip verification improves transfer.\n",
        encoding="utf-8",
    )
    (papers / "paper_b").mkdir(parents=True)
    (papers / "paper_b" / "storage.txt").write_text(
        "Cache eviction and serialization remain unrelated to round trip transfer.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def round_trip_request():\n    return 'round trip'\n",
        encoding="utf-8",
    )
    (repos / "repo_b" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src" / "cache.py").write_text(
        "def cache_eviction():\n    return 'stable storage'\n",
        encoding="utf-8",
    )
    out = tmp_path / "stage8802_missing_meta_out"
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
    candidates_path = tmp_path / "missing_meta_candidates.jsonl"
    import pyarrow.parquet as pq
    chunk_ids = []
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            chunk_ids.append(row["chunk_id"])
    payload = {
        "candidate_id": "cand_round_trip",
        "canonical_name": "round_trip",
        "template_family": "compound_concept_transition",
        "state_variable": "round_trip_active",
        "supporting_chunk_ids": chunk_ids,
        "final_state": {"round_trip_active": True},
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
    }
    candidates_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    try:
        build_compound_concept_examples(
            index_dir=out,
            candidates_path=candidates_path,
            target_context_tokens=256,
            noise_ratio=0.5,
            seed=7,
        )
    except ValueError as exc:
        assert "missing_dataset_compiler" in str(exc)
    else:
        raise AssertionError("builder accepted candidate without compiled metadata")


def test_build_stage8802_examples_include_task_metadata(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (papers / "paper_b").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Round trip verification improves transfer.\n",
        encoding="utf-8",
    )
    (papers / "paper_b" / "storage.txt").write_text(
        "Cache eviction and serialization are unrelated to transfer verification.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def round_trip_request():\n    return 'round trip'\n",
        encoding="utf-8",
    )
    (repos / "repo_b" / "src" / "cache.py").write_text(
        "def cache_eviction():\n    return 'stable storage'\n",
        encoding="utf-8",
    )
    out = tmp_path / "stage8802_meta_out"
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
    candidates_path = tmp_path / "stage8802_meta_candidates.jsonl"
    import pyarrow.parquet as pq
    chunk_rows = []
    for shard in sorted((out / "chunks").glob("*.parquet")):
        chunk_rows.extend(pq.read_table(shard).to_pylist())
    chunk_ids = [
        row["chunk_id"]
        for row in chunk_rows
        if json.loads(row["metadata_json"]).get("path") in {"paper_a/method.txt", "repo_a/src/engine.py"}
    ]
    payload = {
        "candidate_id": "cand_round_trip",
        "canonical_name": "round_trip",
        "template_family": "compound_concept_transition",
        "state_variable": "round_trip_active",
        "supporting_chunk_ids": chunk_ids,
        "final_state": {"round_trip_active": True},
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
        "dataset_compiler": {
            "task_type": "state_transition_reconciliation",
            "segmentation_units": ["paper", "repo"],
            "skill_tags": ["state_transition", "retrieval_grounded", "software_maintenance"],
            "difficulty": {"level": 2, "label": "cross_source", "signals": {"supporting_chunk_count": len(chunk_ids)}},
            "quality": {"overall_score": 0.92, "bucket": "high"},
            "retrieval_links": [
                {"chunk_id": row["chunk_id"], "role": "paper_support" if row["source_type"] == "paper" else "repo_support", "source_type": row["source_type"], "source_id": row["source_id"], "doc_id": row["doc_id"], "chunk_index": row["chunk_index"], "modality": row["modality"], "path": json.loads(row["metadata_json"]).get("path", ""), "language": json.loads(row["metadata_json"]).get("language"), "token_count": row["token_count"]}
                for row in chunk_rows
            ],
        },
        "model_assisted_signals": {
            "llm_judge": {"label": "software_concept"},
            "verification_record": {"verifier_type": "heuristic_proxy"},
        },
    }
    candidates_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    examples, summary, _, _, retrieval_rows = build_compound_concept_examples(
        index_dir=out,
        candidates_path=candidates_path,
        target_context_tokens=96,
        noise_ratio=0.25,
        seed=7,
        target_domain="software",
    )
    assert examples
    assert examples[0]["task_metadata"]["task_type"] == "state_transition_reconciliation"
    assert examples[0]["retrieval_supervision"]["required_evidence"]
    assert examples[0]["retrieval_supervision"]["support_spans"]
    assert examples[0]["task_metadata"]["support_spans"]
    assert examples[0]["retrieval_supervision"]["support_spans"][0]["snippet"]
    assert isinstance(examples[0]["retrieval_supervision"]["contrastive_negatives"], list)
    assert isinstance(examples[0]["task_metadata"]["contrastive_negatives"], list)
    assert examples[0]["task_metadata"]["model_assisted_signals"]["llm_judge"]["label"] in {"software_concept", "ml_concept", "generic_compound"}
    assert examples[0]["model_assisted_signals"]["verification_record"]["verifier_type"] == "heuristic_proxy"
    assert examples[0]["quality"]["bucket"] in {"high", "medium", "low", "unknown"}
    assert examples[0]["difficulty"]
    assert summary["quality_bucket_counts"]
    assert summary["difficulty_level_counts"]
    assert summary["support_span_count"] >= 1
    assert retrieval_rows
    assert retrieval_rows[0]["positive_spans"]
    assert summary["contrastive_negative_count"] >= 0
    final_state = json.loads(examples[0]["targets"]["final_state_json"])
    assert final_state["expected_changed_files"]
    assert all(not str(path).endswith((".parquet", ".jsonl")) for path in final_state["expected_changed_files"])
    assert final_state["verification_targets"]
    assert "manifest.json" not in final_state["verification_targets"]
    assert all(not str(path).endswith(".parquet") for path in final_state["verification_targets"])
    assert final_state["key_symbols"]


def test_build_stage8802_software_target_rejects_missing_repo_phrase_evidence(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Third party verification is discussed here.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "client.py").write_text(
        "def handle_request():\n    return 'ok'\n",
        encoding="utf-8",
    )
    out = tmp_path / "stage8802_software_reject_out"
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
    candidates_path = tmp_path / "software_reject_candidates.jsonl"
    import pyarrow.parquet as pq
    chunk_ids = []
    for shard in sorted((out / "chunks").glob("*.parquet")):
        for row in pq.read_table(shard).to_pylist():
            chunk_ids.append(row["chunk_id"])
    payload = {
        "candidate_id": "cand_third_party",
        "canonical_name": "third_party",
        "template_family": "compound_concept_transition",
        "state_variable": "third_party_active",
        "supporting_chunk_ids": chunk_ids,
        "final_state": {"third_party_active": True},
        "transition_chain": [{"source_type": "paper"}, {"source_type": "repo"}],
    }
    candidates_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    examples, summary, scored, examples_by_domain, retrieval_rows = build_compound_concept_examples(
        index_dir=out,
        candidates_path=candidates_path,
        target_context_tokens=256,
        noise_ratio=0.5,
        seed=7,
        target_domain="software",
    )
    assert scored[0]["quality_tier"] == "rejected"
    assert scored[0]["rejection_reason"] == "missing_repo_phrase_evidence"
    assert summary["accepted_count"] == 0
    assert summary["rendered_example_count"] == 0
    assert summary["software_evidence_summary"]["software_domain_candidate_count"] == 1
    assert summary["software_evidence_summary"]["software_domain_accepted_candidate_count"] == 0
    assert summary["software_evidence_summary"]["software_domain_rejected_candidate_count"] == 1
    assert summary["software_evidence_summary"]["software_candidates_without_repo_phrase_evidence"] == 1
    assert summary["software_evidence_summary"]["accepted_software_candidates_with_repo_phrase_evidence"] == 0
    assert examples == []
    assert examples_by_domain["software_concept"] == []
    assert retrieval_rows == []


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


def test_candidate_miner_emits_dataset_compiler_metadata(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Pre trained encoder improves transfer and stability.\n",
        encoding="utf-8",
    )
    (papers / "paper_a" / "results.txt").write_text(
        "Pre trained encoder improves robustness in evaluation.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def round_trip_request():\n    return 'round trip'\n",
        encoding="utf-8",
    )
    (repos / "repo_b" / "src" / "helper.py").write_text(
        "def round_trip_encoder_eval():\n    return 'round trip'\n",
        encoding="utf-8",
    )
    out = tmp_path / "compiler_meta_out"
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
    target = next(candidate for candidate in candidates if candidate["canonical_name"] == "round_trip")
    compiler = target["dataset_compiler"]
    assert compiler["task_type"] == "state_transition_reconciliation"
    assert compiler["retrieval_links"]
    assert compiler["quality"]["bucket"] in {"high", "medium", "low"}
    assert compiler["difficulty"]["level"] >= 1
    assert summary["quality_bucket_counts"]
    assert summary["difficulty_level_counts"]



def test_candidate_miner_expands_support_beyond_causal_core(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src").mkdir(parents=True)
    paper_text = " ".join(["Pre trained encoder improves stability and transfer."] * 24)
    repo_a_text = "\n".join([
        "def round_trip_encoder_step_%02d():" % idx + "\n    return 'round trip encoder'"
        for idx in range(12)
    ])
    repo_b_text = "\n".join([
        "def round_trip_adapter_step_%02d():" % idx + "\n    return 'round trip encoder'"
        for idx in range(12)
    ])
    (papers / "paper_a" / "method.txt").write_text(paper_text, encoding="utf-8")
    (papers / "paper_a" / "results.txt").write_text(paper_text, encoding="utf-8")
    (repos / "repo_a" / "src" / "engine.py").write_text(repo_a_text, encoding="utf-8")
    (repos / "repo_b" / "src" / "adapter.py").write_text(repo_b_text, encoding="utf-8")
    out = tmp_path / "expanded_support_out"
    build_chunk_and_mention_shards(
        paper_roots=[papers],
        repo_roots=[repos],
        dataset_roots=[],
        output_dir=out,
        paper_chunk_tokens=16,
        repo_chunk_tokens=16,
        trace_chunk_tokens=16,
        rows_per_shard=8,
    )
    build_entities_with_pyarrow(output_dir=out, min_mention_count=2, max_chunk_frequency_ratio=1.0)
    build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=8)
    candidates, summary = mine_candidates(
        index_dir=out,
        max_candidates=10,
        required_source_types=("paper", "repo"),
        max_entity_chunk_ratio=1.0,
        max_compound_entity_chunk_ratio=1.0,
        adjacent_support_window=2,
        max_expanded_support_chunks=32,
    )
    target = next(candidate for candidate in candidates if candidate["canonical_name"] == "round_trip")
    assert len(target["core_supporting_chunk_ids"]) == len(target["transition_chain"])
    assert set(target["core_supporting_chunk_ids"]).issubset(set(target["supporting_chunk_ids"]))
    assert len(target["supporting_chunk_ids"]) > len(target["core_supporting_chunk_ids"])
    assert target["support_expansion"]["extra_supporting_chunk_count"] > 0
    assert summary["supporting_chunk_count_stats"]["expanded_max"] >= len(target["supporting_chunk_ids"])
    roles = {row["role"] for row in target["dataset_compiler"]["retrieval_links"]}
    assert "adjacent_context" in roles or "entity_mention_support" in roles


def test_candidate_miner_compound_support_allows_one_paper_doc_with_multi_repo_docs(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (repos / "repo_b" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Large scale training improves transfer.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def large_scale_update():\n    return 'large scale'\n",
        encoding="utf-8",
    )
    (repos / "repo_b" / "src" / "helper.py").write_text(
        "def large_scale_eval():\n    return 'large scale'\n",
        encoding="utf-8",
    )
    out = tmp_path / "compound_support_out"
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
    candidates, _ = mine_candidates(index_dir=out, max_candidates=20, required_source_types=("paper", "repo"), max_entity_chunk_ratio=1.0, max_compound_entity_chunk_ratio=1.0, compound_only=True)
    assert any(candidate["canonical_name"] == "large_scale" for candidate in candidates)


def test_candidate_miner_compound_only_mode_filters_unigrams(tmp_path: Path) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers = tmp_path / "papers"
    repos = tmp_path / "repositories"
    (papers / "paper_a").mkdir(parents=True)
    (repos / "repo_a" / "src").mkdir(parents=True)
    (papers / "paper_a" / "method.txt").write_text(
        "Pre trained encoder improves transfer. Local update remains stable.\n",
        encoding="utf-8",
    )
    (papers / "paper_a" / "results.txt").write_text(
        "Pre trained setup improves robustness. Local behavior also changes.\n",
        encoding="utf-8",
    )
    (repos / "repo_a" / "src" / "engine.py").write_text(
        "def round_trip_request():\n    return 'round trip'\n\ndef local_update():\n    return 'local'\n",
        encoding="utf-8",
    )
    out = tmp_path / "compound_only_out"
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
    candidates, summary = mine_candidates(index_dir=out, max_candidates=20, required_source_types=("paper", "repo"), max_entity_chunk_ratio=1.0, max_compound_entity_chunk_ratio=1.0, compound_only=True)
    assert candidates
    assert all('_' in candidate["canonical_name"] for candidate in candidates)
    assert summary["compound_only"] is True


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
        "def round_trip_request():\n    return 'round trip'\n",
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
    assert summary["compound_only"] is False
    repo_chunk_ids = {
        chunk_id
        for candidate in candidates
        for chunk_id, transition in zip(candidate.get("core_supporting_chunk_ids", candidate["supporting_chunk_ids"]), candidate["transition_chain"])
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


def test_run_long_context_transition_pipeline_cli(tmp_path: Path, monkeypatch) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "runner_inputs")
    run_root = tmp_path / "runner_out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_long_context_transition_pipeline.py",
            "--run-root",
            str(run_root),
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--profile",
            "paper_repo_core",
            "--max-files-per-root",
            "20",
            "--max-candidates",
            "16",
            "--compound-only",
            "--target-domain",
            "software",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
            "--allow-corpus-scan",
            "--allow-candidate-mining",
            "--annotation-provider",
            "heuristic_proxy_v1",
            "--resume",
        ],
    )
    run_pipeline_main()

    manifest = json.loads((run_root / "manifests" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_domain"] == "software"
    assert manifest["compound_only"] is True
    assert manifest["parameters"]["annotate_model_signals"] is True
    assert (run_root / "index" / "index_summary.json").is_file()
    assert (run_root / "candidates" / "candidates_compound_only.jsonl").is_file()
    assert (run_root / "candidates" / "candidates_compound_only_annotated.jsonl").is_file()
    assert (run_root / "candidates" / "candidates_compound_only_annotated_summary.json").is_file()
    assert (run_root / "examples" / "compound_concept_examples_software_focus_compound_only.jsonl").is_file()
    assert (run_root / "examples" / "compound_concept_examples_software_focus_compound_only_maintenance_preference.jsonl").is_file()


def test_run_long_context_transition_pipeline_cli_with_pack_stage(tmp_path: Path, monkeypatch) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "runner_pack_inputs")
    run_root = tmp_path / "runner_pack_out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_long_context_transition_pipeline.py",
            "--run-root",
            str(run_root),
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--profile",
            "paper_repo_core",
            "--max-files-per-root",
            "20",
            "--max-candidates",
            "16",
            "--compound-only",
            "--target-domain",
            "software",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
            "--allow-corpus-scan",
            "--allow-candidate-mining",
            "--annotation-provider",
            "heuristic_proxy_v1",
            "--build-long-context-packs",
            "--target-pack-tokens",
            "512",
            "--min-pack-tokens",
            "128",
            "--resume",
        ],
    )
    run_pipeline_main()
    manifest = json.loads((run_root / "manifests" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parameters"]["build_long_context_packs_stage"] is True
    pack_dir = run_root / "packs" / "compound_concept_examples_software_focus_compound_only"
    assert (pack_dir / "long_context_packs.jsonl").is_file()
    assert (pack_dir / "long_context_pack_training_rows.jsonl").is_file()
    assert (pack_dir / "long_context_packs_summary.json").is_file()
    assert (pack_dir / "parquet" / "long_context_packs-000000.parquet").is_file()
    assert (pack_dir / "parquet" / "long_context_pack_chunks-000000.parquet").is_file()
    assert (pack_dir / "parquet" / "long_context_pack_training_rows-000000.parquet").is_file()


def test_run_long_context_transition_pipeline_cli_builds_strict_packs(tmp_path: Path, monkeypatch) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "runner_strict_inputs")
    run_root = tmp_path / "runner_strict_out"

    def _fake_strict_builder(**kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "parquet").mkdir(parents=True, exist_ok=True)
        packs = [{"pack_id": "pack-1", "pack_token_count": 512, "example_ids": ["ex-1"]}]
        pack_chunk_rows = [{"pack_id": "pack-1", "chunk_id": "c1"}]
        training_rows = [{"pack_id": "pack-1", "context_rows": [], "target_rows": []}]
        reports = [{"pack_id": "pack-1", "fatal_reasons": [], "avg_example_quality": 90.0, "min_example_quality": 90.0, "pack_token_count": 512}]
        summary = {
            "pack_count": 1,
            "training_signal_summary": {
                "accepted_pack_count": 1,
                "pack_count": 1,
                "readiness_counts": {
                    "locality_probe_ready": 1,
                    "retrieval_probe_ready": 1,
                    "long_range_join_probe_ready": 1,
                    "lost_state_probe_ready": 1,
                    "state_update_probe_ready": 1,
                },
            },
        }
        write_jsonl(output_dir / "strict_long_context_packs.jsonl", packs)
        write_jsonl(output_dir / "strict_long_context_pack_training_rows.jsonl", training_rows)
        write_jsonl(output_dir / "strict_long_context_pack_quality_reports.jsonl", reports)
        write_json(output_dir / "strict_long_context_packs_summary.json", summary)
        write_json(output_dir / "strict_long_context_training_signal_summary.json", summary["training_signal_summary"])
        write_jsonl(output_dir / "strict_long_context_training_signal_pack_audit.jsonl", [{"pack_id": "pack-1", "accepted": True}])
        write_jsonl(output_dir / "strict_long_context_training_signal_target_audit.jsonl", [{"example_id": "ex-1"}])
        write_jsonl(output_dir / "strict_long_context_pack_training_rows.audit_input.jsonl", training_rows)
        import pyarrow as pa
        import pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pylist(packs), output_dir / "parquet" / "strict_long_context_packs-000000.parquet")
        pq.write_table(pa.Table.from_pylist(pack_chunk_rows), output_dir / "parquet" / "strict_long_context_pack_chunks-000000.parquet")
        pq.write_table(pa.Table.from_pylist(training_rows), output_dir / "parquet" / "strict_long_context_pack_training_rows-000000.parquet")
        pq.write_table(pa.Table.from_pylist(reports), output_dir / "parquet" / "strict_long_context_pack_quality_reports-000000.parquet")
        return packs, pack_chunk_rows, training_rows, reports, summary

    monkeypatch.setattr(run_pipeline_module, "build_strict_long_context_episode_packs", _fake_strict_builder)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_long_context_transition_pipeline.py",
            "--run-root",
            str(run_root),
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--profile",
            "paper_repo_core",
            "--max-files-per-root",
            "20",
            "--max-candidates",
            "16",
            "--target-domain",
            "all",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
            "--allow-corpus-scan",
            "--allow-candidate-mining",
            "--annotation-provider",
            "heuristic_proxy_v1",
            "--build-strict-long-context-packs",
            "--target-pack-tokens",
            "512",
            "--min-pack-tokens",
            "128",
            "--resume",
        ],
    )
    run_pipeline_main()
    manifest = json.loads((run_root / "manifests" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parameters"]["build_strict_long_context_packs_stage"] is True
    strict_dir = run_root / "strict_packs" / "compound_concept_examples"
    assert (strict_dir / "strict_long_context_packs.jsonl").is_file()
    assert (strict_dir / "strict_long_context_pack_training_rows.jsonl").is_file()
    assert (strict_dir / "strict_long_context_packs_summary.json").is_file()
    assert (strict_dir / "strict_long_context_training_signal_summary.json").is_file()
    assert (strict_dir / "parquet" / "strict_long_context_packs-000000.parquet").is_file()
    assert (strict_dir / "parquet" / "strict_long_context_pack_chunks-000000.parquet").is_file()
    assert (strict_dir / "parquet" / "strict_long_context_pack_training_rows-000000.parquet").is_file()
    assert (strict_dir / "parquet" / "strict_long_context_pack_quality_reports-000000.parquet").is_file()


def test_run_long_context_transition_pipeline_cli_without_annotation_provider_fails(tmp_path: Path, monkeypatch) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "runner_missing_provider_inputs")
    run_root = tmp_path / "runner_missing_provider_out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_long_context_transition_pipeline.py",
            "--run-root",
            str(run_root),
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--profile",
            "paper_repo_core",
            "--max-files-per-root",
            "20",
            "--max-candidates",
            "16",
            "--compound-only",
            "--target-domain",
            "software",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
            "--allow-corpus-scan",
            "--allow-candidate-mining",
            "--resume",
        ],
    )
    try:
        run_pipeline_main()
    except ModelSignalAnnotationError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError("pipeline accepted annotation without explicit provider")
    assert "annotation_provider_required" in message


def test_run_long_context_transition_pipeline_cli_without_annotation_stage(tmp_path: Path, monkeypatch) -> None:
    if importlib.util.find_spec("pyarrow") is None:
        return
    papers, repos, datasets = _make_tree(tmp_path / "runner_no_annotation_inputs")
    run_root = tmp_path / "runner_no_annotation_out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_long_context_transition_pipeline.py",
            "--run-root",
            str(run_root),
            "--papers-root",
            str(papers),
            "--repos-root",
            str(repos),
            "--datasets-root",
            str(datasets),
            "--profile",
            "paper_repo_core",
            "--max-files-per-root",
            "20",
            "--max-candidates",
            "16",
            "--compound-only",
            "--target-domain",
            "software",
            "--target-context-tokens",
            "256",
            "--noise-ratio",
            "0.75",
            "--allow-corpus-scan",
            "--allow-candidate-mining",
            "--no-annotate-model-signals",
            "--resume",
        ],
    )
    run_pipeline_main()
    manifest = json.loads((run_root / "manifests" / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parameters"]["annotate_model_signals"] is False
    assert not (run_root / "candidates" / "candidates_compound_only_annotated.jsonl").exists()
    assert (run_root / "examples" / "compound_concept_examples_software_focus_compound_only.jsonl").is_file()


def test_render_examples_rejects_overlapping_distractors() -> None:
    chunks = [
        {
            "chunk_id": "support-paper",
            "source_type": "paper",
            "source_id": "paper_a",
            "doc_id": "paper_a/method.txt",
            "chunk_index": 0,
            "modality": "text",
            "token_count": 20,
            "text": "round trip verification improves transfer stability",
            "metadata_json": json.dumps({"path": "paper_a/method.txt"}),
        },
        {
            "chunk_id": "support-repo",
            "source_type": "repo",
            "source_id": "repo_a",
            "doc_id": "repo_a/src/engine.py",
            "chunk_index": 0,
            "modality": "code",
            "token_count": 20,
            "text": "def round_trip_request():\n    return transfer_state",
            "metadata_json": json.dumps({"path": "repo_a/src/engine.py", "language": "python"}),
        },
        {
            "chunk_id": "bad-distractor",
            "source_type": "repo",
            "source_id": "repo_a",
            "doc_id": "repo_a/src/engine_helpers.py",
            "chunk_index": 1,
            "modality": "code",
            "token_count": 40,
            "text": "round_trip_request transfer_state helper path overlaps the target heavily",
            "metadata_json": json.dumps({"path": "repo_a/src/engine_helpers.py", "language": "python"}),
        },
        {
            "chunk_id": "clean-distractor",
            "source_type": "repo",
            "source_id": "repo_b",
            "doc_id": "repo_b/src/cache.py",
            "chunk_index": 0,
            "modality": "code",
            "token_count": 80,
            "text": "cache eviction and serialization boundaries for unrelated storage workers",
            "metadata_json": json.dumps({"path": "repo_b/src/cache.py", "language": "python"}),
        },
    ]
    programs = [{
        "program_id": "prog-1",
        "query_text": "What is the final value?",
        "supporting_chunk_ids": ["support-paper", "support-repo"],
        "final_state": {"round_trip_active": True},
        "state_probe_points": [],
        "grounding": {
            "exact_paths": ["repo_a/src/engine.py", "paper_a/method.txt"],
            "path_suffixes": ["src/engine.py", "method.txt"],
            "repo_source_ids": ["repo_a"],
            "terms": ["round", "trip", "transfer", "verification"],
            "compounds": ["round_trip_request", "transfer_state"],
            "anchor_text": "round trip verification transfer_state",
        },
    }]
    examples = render_examples(chunks=chunks, programs=programs, target_context_tokens=100, noise_ratio=0.6, seed=3)
    assert examples
    rendered_ids = set(examples[0]["rendered_chunk_ids"])
    assert "bad-distractor" not in rendered_ids
    assert "clean-distractor" in rendered_ids
