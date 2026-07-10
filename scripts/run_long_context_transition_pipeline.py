from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from build_stage8801_long_context_corpus_index import (
    build_chunk_and_mention_shards,
    build_entities_with_pyarrow,
    build_links_with_pyarrow,
    validate_corpus_index_request,
)
from annotate_long_context_model_signals import ModelSignalAnnotationError, annotate_candidate_rows, resolve_annotation_provider
from build_long_context_training_packs import build_long_context_packs
from build_strict_long_context_episode_packs import build_strict_long_context_episode_packs
from build_stage8802_compound_concept_examples import (
    build_compound_concept_examples,
    build_conflict_training_rows,
    build_listwise_retrieval_rows,
    build_maintenance_action_rows,
    build_maintenance_preference_rows,
    build_maintenance_rationale_rows,
    build_maintenance_trace_rows,
    build_maintenance_training_rows,
    build_pairwise_retrieval_rows,
    build_retrieval_training_rows,
)
from long_context_candidate_miner import mine_candidates, validate_candidate_mining_request
from long_context_common import write_json, write_jsonl


def _read_source_manifest(path: Path, *, profile: str) -> tuple[list[Path], list[Path], list[Path], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    profiles = payload.get('profiles') or {}
    selected = profiles.get(profile) or {}

    def _enabled_paths(rows: list[dict[str, Any]] | None) -> list[Path]:
        out: list[Path] = []
        for row in rows or []:
            if row.get('enabled', True) is not True:
                continue
            value = str(row.get('path') or '').strip()
            if not value:
                raise ValueError(f'manifest_missing_path:{path}')
            out.append(Path(value))
        return out

    papers = _enabled_paths(selected.get('papers'))
    repos = _enabled_paths(selected.get('repos'))
    datasets = _enabled_paths(selected.get('datasets'))
    summary = {
        'manifest_path': str(path),
        'profile': profile,
        'paper_root_count': len(papers),
        'repo_root_count': len(repos),
        'dataset_root_count': len(datasets),
    }
    return papers, repos, datasets, summary


def _merge_source_roots(manifest_roots: list[Path], cli_roots: list[Path]) -> list[Path]:
    merged: list[Path] = []
    seen: set[str] = set()
    for root in [*manifest_roots, *cli_roots]:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        merged.append(root)
    return merged


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _artifact_stem(*, target_domain: str, compound_only: bool) -> str:
    parts = ["compound_concept_examples"]
    if target_domain != "all":
        parts.append(target_domain)
        parts.append("focus")
    if compound_only:
        parts.append("compound_only")
    return "_".join(parts)


def _candidate_stem(*, compound_only: bool) -> str:
    return "candidates_compound_only" if compound_only else "candidates"


def _paths(run_root: Path, *, target_domain: str, compound_only: bool) -> dict[str, Path]:
    index_dir = run_root / "index"
    candidates_dir = run_root / "candidates"
    examples_dir = run_root / "examples"
    manifests_dir = run_root / "manifests"
    stem = _artifact_stem(target_domain=target_domain, compound_only=compound_only)
    candidate_stem = _candidate_stem(compound_only=compound_only)
    return {
        "index_dir": index_dir,
        "candidate_output": candidates_dir / f"{candidate_stem}.jsonl",
        "candidate_summary_output": candidates_dir / f"{candidate_stem}_summary.json",
        "annotated_candidate_output": candidates_dir / f"{candidate_stem}_annotated.jsonl",
        "annotated_candidate_summary_output": candidates_dir / f"{candidate_stem}_annotated_summary.json",
        "examples_output": examples_dir / f"{stem}.jsonl",
        "summary_output": examples_dir / f"{stem}_summary.json",
        "scored_output": examples_dir / f"{stem}_scored.jsonl",
        "ml_output": examples_dir / f"{stem}_ml.jsonl",
        "software_output": examples_dir / f"{stem}_software.jsonl",
        "retrieval_output": examples_dir / f"{stem}_retrieval.jsonl",
        "pairwise_output": examples_dir / f"{stem}_retrieval_pairwise.jsonl",
        "listwise_output": examples_dir / f"{stem}_retrieval_listwise.jsonl",
        "conflict_output": examples_dir / f"{stem}_conflict.jsonl",
        "maintenance_output": examples_dir / f"{stem}_maintenance.jsonl",
        "maintenance_action_output": examples_dir / f"{stem}_maintenance_action.jsonl",
        "maintenance_rationale_output": examples_dir / f"{stem}_maintenance_rationale.jsonl",
        "maintenance_trace_output": examples_dir / f"{stem}_maintenance_trace.jsonl",
        "maintenance_preference_output": examples_dir / f"{stem}_maintenance_preference.jsonl",
        "pack_output_dir": run_root / "packs" / stem,
        "strict_pack_output_dir": run_root / "strict_packs" / stem,
        "manifest_output": manifests_dir / "pipeline_manifest.json",
    }


def _all_exist(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)


def _validate_annotation_request(*, annotate_model_signals: bool, annotation_provider: str | None) -> None:
    if not annotate_model_signals:
        return
    resolve_annotation_provider(annotation_provider)


def run_pipeline(
    *,
    run_root: Path,
    profile: str,
    paper_roots: list[Path],
    repo_roots: list[Path],
    dataset_roots: list[Path],
    source_manifest_path: Path | None = None,
    paper_chunk_tokens: int,
    repo_chunk_tokens: int,
    trace_chunk_tokens: int,
    max_files_per_root: int | None,
    max_chars_per_file: int,
    rows_per_shard: int,
    min_mention_count: int,
    max_chunk_frequency_ratio: float,
    max_pairwise_mentions_per_entity: int,
    max_candidates: int,
    min_sources: int,
    required_source_types: tuple[str, ...],
    max_entity_chunk_ratio: float,
    max_compound_entity_chunk_ratio: float,
    compound_only: bool,
    adjacent_support_window: int,
    max_expanded_support_chunks: int,
    include_all_mentions_in_support: bool,
    target_context_tokens: int,
    noise_ratio: float,
    seed: int,
    target_domain: str,
    allow_corpus_scan: bool,
    allow_candidate_mining: bool,
    allow_arxiv_output: bool,
    resume: bool,
    annotate_model_signals: bool = True,
    annotation_provider: str | None = None,
    build_long_context_packs_stage: bool = False,
    build_strict_long_context_packs_stage: bool = False,
    target_pack_tokens: int | None = None,
    min_pack_tokens: int | None = None,
    max_examples_per_pack: int | None = None,
    strict_min_example_quality: float = 75.0,
    strict_min_avg_example_quality: float = 85.0,
    strict_min_distinct_repos: int = 8,
    strict_require_source_types: tuple[str, ...] = ('repo', 'paper'),
    strict_min_verification_rows: int = 0,
    strict_min_locality_ready_fraction: float = 0.60,
    strict_min_retrieval_ready_fraction: float = 0.55,
    strict_min_long_range_join_ready_fraction: float = 0.40,
    strict_min_state_update_ready_fraction: float = 0.80,
    strict_min_target_rows_for_lost_state_probe: int = 32,
    strict_min_programs_for_lost_state_probe: int = 8,
) -> dict[str, Any]:
    paths = _paths(run_root, target_domain=target_domain, compound_only=compound_only)
    for key in ("index_dir", "candidate_output", "examples_output", "manifest_output"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)

    source_manifest_summary = None
    if source_manifest_path is not None:
        manifest_papers, manifest_repos, manifest_datasets, source_manifest_summary = _read_source_manifest(source_manifest_path, profile=profile)
        paper_roots = _merge_source_roots(manifest_papers, paper_roots)
        repo_roots = _merge_source_roots(manifest_repos, repo_roots)
        dataset_roots = _merge_source_roots(manifest_datasets, dataset_roots)

    _validate_annotation_request(
        annotate_model_signals=annotate_model_signals,
        annotation_provider=annotation_provider,
    )

    validate_corpus_index_request(
        paper_roots=paper_roots,
        repo_roots=repo_roots,
        dataset_roots=dataset_roots,
        output_dir=paths["index_dir"],
        allow_corpus_scan=allow_corpus_scan,
        allow_arxiv_output=allow_arxiv_output,
    )
    validate_candidate_mining_request(
        index_dir=paths["index_dir"],
        output=paths["candidate_output"],
        allow_candidate_mining=allow_candidate_mining,
        allow_arxiv_output=allow_arxiv_output,
    )

    stage_status: dict[str, Any] = {}

    index_summary_path = paths["index_dir"] / "index_summary.json"
    index_required = [
        paths["index_dir"] / "chunks",
        paths["index_dir"] / "chunk_mentions",
        paths["index_dir"] / "entities",
        paths["index_dir"] / "links",
        index_summary_path,
    ]
    if resume and _all_exist(index_required):
        stage_status["index"] = {"status": "reused", "output_dir": str(paths["index_dir"])}
    else:
        source_summary = build_chunk_and_mention_shards(
            paper_roots=paper_roots,
            repo_roots=repo_roots,
            dataset_roots=dataset_roots,
            output_dir=paths["index_dir"],
            paper_chunk_tokens=paper_chunk_tokens,
            repo_chunk_tokens=repo_chunk_tokens,
            trace_chunk_tokens=trace_chunk_tokens,
            max_files_per_root=max_files_per_root,
            max_chars_per_file=max_chars_per_file,
            rows_per_shard=rows_per_shard,
        )
        entity_summary = build_entities_with_pyarrow(
            output_dir=paths["index_dir"],
            min_mention_count=min_mention_count,
            max_chunk_frequency_ratio=max_chunk_frequency_ratio,
        )
        link_summary = build_links_with_pyarrow(
            output_dir=paths["index_dir"],
            max_pairwise_mentions_per_entity=max_pairwise_mentions_per_entity,
        )
        write_json(index_summary_path, {
            "profile": profile,
            "source_summary": source_summary,
            "entity_summary": entity_summary,
            "link_summary": link_summary,
        })
        stage_status["index"] = {
            "status": "built",
            "output_dir": str(paths["index_dir"]),
            "summary_output": str(index_summary_path),
        }

    if resume and _all_exist([paths["candidate_output"], paths["candidate_summary_output"]]):
        stage_status["candidates"] = {"status": "reused", "output": str(paths["candidate_output"])}
    else:
        candidates, candidate_summary = mine_candidates(
            index_dir=paths["index_dir"],
            max_candidates=max_candidates,
            min_sources=min_sources,
            required_source_types=required_source_types,
            max_entity_chunk_ratio=max_entity_chunk_ratio,
            max_compound_entity_chunk_ratio=max_compound_entity_chunk_ratio,
            compound_only=compound_only,
            adjacent_support_window=adjacent_support_window,
            max_expanded_support_chunks=max_expanded_support_chunks,
            include_all_mentions_in_support=include_all_mentions_in_support,
        )
        write_jsonl(paths["candidate_output"], candidates)
        write_json(paths["candidate_summary_output"], candidate_summary)
        stage_status["candidates"] = {
            "status": "built",
            "output": str(paths["candidate_output"]),
            "summary_output": str(paths["candidate_summary_output"]),
        }

    candidate_input_path = paths["candidate_output"]
    if annotate_model_signals:
        if resume and _all_exist([paths["annotated_candidate_output"], paths["annotated_candidate_summary_output"]]):
            candidate_input_path = paths["annotated_candidate_output"]
            stage_status["model_signals"] = {
                "status": "reused",
                "output": str(paths["annotated_candidate_output"]),
                "summary_output": str(paths["annotated_candidate_summary_output"]),
                "provider": annotation_provider,
            }
        else:
            annotated_candidates, annotation_summary = annotate_candidate_rows(
                index_dir=paths["index_dir"],
                candidates_path=candidate_input_path,
                provider=annotation_provider,
            )
            write_jsonl(paths["annotated_candidate_output"], annotated_candidates)
            write_json(paths["annotated_candidate_summary_output"], annotation_summary)
            candidate_input_path = paths["annotated_candidate_output"]
            stage_status["model_signals"] = {
                "status": "built",
                "output": str(paths["annotated_candidate_output"]),
                "summary_output": str(paths["annotated_candidate_summary_output"]),
                "provider": annotation_provider,
            }

    example_outputs = [
        paths["examples_output"],
        paths["summary_output"],
        paths["retrieval_output"],
        paths["pairwise_output"],
        paths["listwise_output"],
        paths["conflict_output"],
        paths["maintenance_output"],
        paths["maintenance_action_output"],
        paths["maintenance_rationale_output"],
        paths["maintenance_trace_output"],
        paths["maintenance_preference_output"],
    ]
    if resume and _all_exist(example_outputs):
        stage_status["examples"] = {"status": "reused", "output": str(paths["examples_output"])}
    else:
        examples, summary, scored, examples_by_domain, retrieval_rows = build_compound_concept_examples(
            index_dir=paths["index_dir"],
            candidates_path=candidate_input_path,
            target_context_tokens=target_context_tokens,
            noise_ratio=noise_ratio,
            seed=seed,
            target_domain=target_domain,
        )
        pairwise_rows, pairwise_summary = build_pairwise_retrieval_rows(retrieval_rows)
        listwise_rows, listwise_summary = build_listwise_retrieval_rows(retrieval_rows)
        conflict_rows, conflict_summary = build_conflict_training_rows(retrieval_rows)
        maintenance_rows, maintenance_summary = build_maintenance_training_rows(examples)
        maintenance_action_rows, maintenance_action_summary = build_maintenance_action_rows(maintenance_rows)
        maintenance_rationale_rows, maintenance_rationale_summary = build_maintenance_rationale_rows(maintenance_action_rows)
        maintenance_trace_rows, maintenance_trace_summary = build_maintenance_trace_rows(maintenance_action_rows)
        maintenance_preference_rows, maintenance_preference_summary = build_maintenance_preference_rows(maintenance_action_rows)
        summary = dict(summary)
        summary.update(pairwise_summary)
        summary.update(listwise_summary)
        summary.update({f"conflict_{key}": value for key, value in conflict_summary.items()})
        summary.update(maintenance_summary)
        summary.update(maintenance_action_summary)
        summary.update(maintenance_rationale_summary)
        summary.update(maintenance_trace_summary)
        summary.update(maintenance_preference_summary)

        write_jsonl(paths["examples_output"], examples)
        write_json(paths["summary_output"], summary)
        write_jsonl(paths["scored_output"], scored)
        write_jsonl(paths["ml_output"], examples_by_domain["ml_concept"])
        write_jsonl(paths["software_output"], examples_by_domain["software_concept"])
        write_jsonl(paths["retrieval_output"], retrieval_rows)
        write_jsonl(paths["pairwise_output"], pairwise_rows)
        write_jsonl(paths["listwise_output"], listwise_rows)
        write_jsonl(paths["conflict_output"], conflict_rows)
        write_jsonl(paths["maintenance_output"], maintenance_rows)
        write_jsonl(paths["maintenance_action_output"], maintenance_action_rows)
        write_jsonl(paths["maintenance_rationale_output"], maintenance_rationale_rows)
        write_jsonl(paths["maintenance_trace_output"], maintenance_trace_rows)
        write_jsonl(paths["maintenance_preference_output"], maintenance_preference_rows)
        stage_status["examples"] = {
            "status": "built",
            "output": str(paths["examples_output"]),
            "summary_output": str(paths["summary_output"]),
        }

    if build_strict_long_context_packs_stage:
        if target_pack_tokens is None:
            raise ValueError('target_pack_tokens_required_when_build_strict_long_context_packs_stage')
        strict_pack_required = [
            paths["strict_pack_output_dir"] / 'strict_long_context_packs.jsonl',
            paths["strict_pack_output_dir"] / 'strict_long_context_pack_training_rows.jsonl',
            paths["strict_pack_output_dir"] / 'strict_long_context_packs_summary.json',
            paths["strict_pack_output_dir"] / 'strict_long_context_training_signal_summary.json',
            paths["strict_pack_output_dir"] / 'parquet' / 'strict_long_context_packs-000000.parquet',
            paths["strict_pack_output_dir"] / 'parquet' / 'strict_long_context_pack_chunks-000000.parquet',
            paths["strict_pack_output_dir"] / 'parquet' / 'strict_long_context_pack_training_rows-000000.parquet',
            paths["strict_pack_output_dir"] / 'parquet' / 'strict_long_context_pack_quality_reports-000000.parquet',
        ]
        if resume and _all_exist(strict_pack_required):
            stage_status["strict_packs"] = {
                "status": "reused",
                "output_dir": str(paths["strict_pack_output_dir"]),
            }
        else:
            packs, pack_chunk_rows, training_rows, reports, strict_summary = build_strict_long_context_episode_packs(
                example_paths=[paths["examples_output"]],
                output_dir=paths["strict_pack_output_dir"],
                target_pack_tokens=int(target_pack_tokens),
                min_pack_tokens=min_pack_tokens,
                max_examples_per_pack=max_examples_per_pack,
                family_key_field='program_id',
                min_example_quality=float(strict_min_example_quality),
                min_avg_example_quality=float(strict_min_avg_example_quality),
                min_distinct_repos=int(strict_min_distinct_repos),
                require_source_types=set(strict_require_source_types),
                min_verification_rows=int(strict_min_verification_rows),
                min_locality_ready_fraction=float(strict_min_locality_ready_fraction),
                min_retrieval_ready_fraction=float(strict_min_retrieval_ready_fraction),
                min_long_range_join_ready_fraction=float(strict_min_long_range_join_ready_fraction),
                min_state_update_ready_fraction=float(strict_min_state_update_ready_fraction),
                min_target_rows_for_lost_state_probe=int(strict_min_target_rows_for_lost_state_probe),
                min_programs_for_lost_state_probe=int(strict_min_programs_for_lost_state_probe),
                max_packs=1,
            )
            stage_status["strict_packs"] = {
                "status": "built",
                "output_dir": str(paths["strict_pack_output_dir"]),
                "summary_output": str(paths["strict_pack_output_dir"] / 'strict_long_context_packs_summary.json'),
                "training_signal_summary_output": str(paths["strict_pack_output_dir"] / 'strict_long_context_training_signal_summary.json'),
                "pack_count": len(packs),
                "training_row_count": len(training_rows),
                "quality_report_count": len(reports),
                "accepted_pack_count": int((strict_summary.get('training_signal_summary') or {}).get('accepted_pack_count', 0)),
            }

    if build_long_context_packs_stage:
        if target_pack_tokens is None:
            raise ValueError('target_pack_tokens_required_when_build_long_context_packs_stage')
        pack_required = [
            paths["pack_output_dir"] / 'long_context_packs.jsonl',
            paths["pack_output_dir"] / 'long_context_packs_summary.json',
            paths["pack_output_dir"] / 'parquet' / 'long_context_packs-000000.parquet',
            paths["pack_output_dir"] / 'parquet' / 'long_context_pack_chunks-000000.parquet',
            paths["pack_output_dir"] / 'parquet' / 'long_context_pack_training_rows-000000.parquet',
            paths["pack_output_dir"] / 'long_context_pack_training_rows.jsonl',
        ]
        if resume and _all_exist(pack_required):
            stage_status["packs"] = {
                "status": "reused",
                "output_dir": str(paths["pack_output_dir"]),
            }
        else:
            packs, pack_chunk_rows, training_rows, pack_summary = build_long_context_packs(
                index_dir=paths["index_dir"],
                examples_path=paths["examples_output"],
                target_pack_tokens=int(target_pack_tokens),
                min_pack_tokens=min_pack_tokens,
                max_examples_per_pack=max_examples_per_pack,
            )
            paths["pack_output_dir"].mkdir(parents=True, exist_ok=True)
            write_jsonl(paths["pack_output_dir"] / 'long_context_packs.jsonl', packs)
            write_jsonl(paths["pack_output_dir"] / 'long_context_pack_training_rows.jsonl', training_rows)
            write_json(paths["pack_output_dir"] / 'long_context_packs_summary.json', pack_summary)
            from long_context_parquet import shard_path, write_parquet_shard
            write_parquet_shard(shard_path(paths["pack_output_dir"] / 'parquet', 'long_context_packs', 0), packs)
            write_parquet_shard(shard_path(paths["pack_output_dir"] / 'parquet', 'long_context_pack_chunks', 0), pack_chunk_rows)
            write_parquet_shard(shard_path(paths["pack_output_dir"] / 'parquet', 'long_context_pack_training_rows', 0), training_rows)
            stage_status["packs"] = {
                "status": "built",
                "output_dir": str(paths["pack_output_dir"]),
                "summary_output": str(paths["pack_output_dir"] / 'long_context_packs_summary.json'),
            }

    manifest = {
        "created_at_utc": _now_utc(),
        "run_root": str(run_root),
        "profile": profile,
        "target_domain": target_domain,
        "compound_only": compound_only,
        "resume": resume,
        "parameters": {
            "paper_roots": [str(path) for path in paper_roots],
            "repo_roots": [str(path) for path in repo_roots],
            "dataset_roots": [str(path) for path in dataset_roots],
            "paper_chunk_tokens": paper_chunk_tokens,
            "repo_chunk_tokens": repo_chunk_tokens,
            "trace_chunk_tokens": trace_chunk_tokens,
            "max_files_per_root": max_files_per_root,
            "max_chars_per_file": max_chars_per_file,
            "rows_per_shard": rows_per_shard,
            "min_mention_count": min_mention_count,
            "max_chunk_frequency_ratio": max_chunk_frequency_ratio,
            "max_pairwise_mentions_per_entity": max_pairwise_mentions_per_entity,
            "max_candidates": max_candidates,
            "min_sources": min_sources,
            "required_source_types": list(required_source_types),
            "max_entity_chunk_ratio": max_entity_chunk_ratio,
            "max_compound_entity_chunk_ratio": max_compound_entity_chunk_ratio,
            "adjacent_support_window": adjacent_support_window,
            "max_expanded_support_chunks": max_expanded_support_chunks,
            "include_all_mentions_in_support": include_all_mentions_in_support,
            "target_context_tokens": target_context_tokens,
            "noise_ratio": noise_ratio,
            "seed": seed,
            "annotate_model_signals": annotate_model_signals,
            "annotation_provider": annotation_provider,
            "build_long_context_packs_stage": build_long_context_packs_stage,
            "build_strict_long_context_packs_stage": build_strict_long_context_packs_stage,
            "target_pack_tokens": target_pack_tokens,
            "min_pack_tokens": min_pack_tokens,
            "max_examples_per_pack": max_examples_per_pack,
            "strict_min_example_quality": strict_min_example_quality,
            "strict_min_avg_example_quality": strict_min_avg_example_quality,
            "strict_min_distinct_repos": strict_min_distinct_repos,
            "strict_require_source_types": list(strict_require_source_types),
            "strict_min_verification_rows": strict_min_verification_rows,
            "strict_min_locality_ready_fraction": strict_min_locality_ready_fraction,
            "strict_min_retrieval_ready_fraction": strict_min_retrieval_ready_fraction,
            "strict_min_long_range_join_ready_fraction": strict_min_long_range_join_ready_fraction,
            "strict_min_state_update_ready_fraction": strict_min_state_update_ready_fraction,
            "strict_min_target_rows_for_lost_state_probe": strict_min_target_rows_for_lost_state_probe,
            "strict_min_programs_for_lost_state_probe": strict_min_programs_for_lost_state_probe,
        },
        "artifacts": {key: str(value) for key, value in paths.items()},
        "stage_status": stage_status,
    }
    write_json(paths["manifest_output"], manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full long-context transition pipeline and write a reproducible manifest.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--profile", choices=["mixed_all", "paper_repo_core", "dataset_traces"], default="mixed_all")
    parser.add_argument("--papers-root", action="append", type=Path, default=[])
    parser.add_argument("--repos-root", action="append", type=Path, default=[])
    parser.add_argument("--datasets-root", action="append", type=Path, default=[])
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--paper-chunk-tokens", type=int, default=1024)
    parser.add_argument("--repo-chunk-tokens", type=int, default=512)
    parser.add_argument("--trace-chunk-tokens", type=int, default=384)
    parser.add_argument("--max-files-per-root", type=int)
    parser.add_argument("--max-chars-per-file", type=int, default=120000)
    parser.add_argument("--rows-per-shard", type=int, default=5000)
    parser.add_argument("--min-mention-count", type=int, default=2)
    parser.add_argument("--max-chunk-frequency-ratio", type=float, default=0.05)
    parser.add_argument("--max-pairwise-mentions-per-entity", type=int, default=64)
    parser.add_argument("--max-candidates", type=int, default=5000)
    parser.add_argument("--min-sources", type=int, default=2)
    parser.add_argument("--required-source-types", type=str, default="paper,repo")
    parser.add_argument("--max-entity-chunk-ratio", type=float, default=0.01)
    parser.add_argument("--max-compound-entity-chunk-ratio", type=float, default=0.04)
    parser.add_argument("--compound-only", action="store_true")
    parser.add_argument("--adjacent-support-window", type=int, default=2)
    parser.add_argument("--max-expanded-support-chunks", type=int, default=64)
    parser.add_argument("--no-include-all-mentions-in-support", action="store_true")
    parser.add_argument("--target-context-tokens", type=int, default=100000)
    parser.add_argument("--noise-ratio", type=float, default=0.995)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--target-domain", choices=["all", "ml", "software"], default="all")
    parser.add_argument("--allow-corpus-scan", action="store_true")
    parser.add_argument("--allow-candidate-mining", action="store_true")
    parser.add_argument("--allow-arxiv-output", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-annotate-model-signals", action="store_true")
    parser.add_argument("--annotation-provider", type=str)
    parser.add_argument("--build-long-context-packs", action="store_true")
    parser.add_argument("--build-strict-long-context-packs", action="store_true")
    parser.add_argument("--target-pack-tokens", type=int)
    parser.add_argument("--min-pack-tokens", type=int)
    parser.add_argument("--max-examples-per-pack", type=int)
    parser.add_argument("--strict-min-example-quality", type=float, default=75.0)
    parser.add_argument("--strict-min-avg-example-quality", type=float, default=85.0)
    parser.add_argument("--strict-min-distinct-repos", type=int, default=8)
    parser.add_argument("--strict-require-source-types", type=str, default="repo,paper")
    parser.add_argument("--strict-min-verification-rows", type=int, default=0)
    parser.add_argument("--strict-min-locality-ready-fraction", type=float, default=0.60)
    parser.add_argument("--strict-min-retrieval-ready-fraction", type=float, default=0.55)
    parser.add_argument("--strict-min-long-range-join-ready-fraction", type=float, default=0.40)
    parser.add_argument("--strict-min-state-update-ready-fraction", type=float, default=0.80)
    parser.add_argument("--strict-min-target-rows-for-lost-state-probe", type=int, default=32)
    parser.add_argument("--strict-min-programs-for-lost-state-probe", type=int, default=8)
    args = parser.parse_args()

    run_pipeline(
        run_root=args.run_root,
        profile=args.profile,
        paper_roots=args.papers_root,
        repo_roots=args.repos_root,
        dataset_roots=args.datasets_root,
        source_manifest_path=args.source_manifest,
        paper_chunk_tokens=args.paper_chunk_tokens,
        repo_chunk_tokens=args.repo_chunk_tokens,
        trace_chunk_tokens=args.trace_chunk_tokens,
        max_files_per_root=args.max_files_per_root,
        max_chars_per_file=args.max_chars_per_file,
        rows_per_shard=args.rows_per_shard,
        min_mention_count=args.min_mention_count,
        max_chunk_frequency_ratio=args.max_chunk_frequency_ratio,
        max_pairwise_mentions_per_entity=args.max_pairwise_mentions_per_entity,
        max_candidates=args.max_candidates,
        min_sources=args.min_sources,
        required_source_types=tuple(item.strip() for item in args.required_source_types.split(",") if item.strip()),
        max_entity_chunk_ratio=args.max_entity_chunk_ratio,
        max_compound_entity_chunk_ratio=args.max_compound_entity_chunk_ratio,
        compound_only=args.compound_only,
        adjacent_support_window=args.adjacent_support_window,
        max_expanded_support_chunks=args.max_expanded_support_chunks,
        include_all_mentions_in_support=not args.no_include_all_mentions_in_support,
        target_context_tokens=args.target_context_tokens,
        noise_ratio=args.noise_ratio,
        seed=args.seed,
        target_domain=args.target_domain,
        allow_corpus_scan=args.allow_corpus_scan,
        allow_candidate_mining=args.allow_candidate_mining,
        allow_arxiv_output=args.allow_arxiv_output,
        resume=args.resume,
        annotate_model_signals=not args.no_annotate_model_signals,
        annotation_provider=args.annotation_provider,
        build_long_context_packs_stage=args.build_long_context_packs,
        build_strict_long_context_packs_stage=args.build_strict_long_context_packs,
        target_pack_tokens=args.target_pack_tokens,
        min_pack_tokens=args.min_pack_tokens,
        max_examples_per_pack=args.max_examples_per_pack,
        strict_min_example_quality=args.strict_min_example_quality,
        strict_min_avg_example_quality=args.strict_min_avg_example_quality,
        strict_min_distinct_repos=args.strict_min_distinct_repos,
        strict_require_source_types=tuple(item.strip() for item in args.strict_require_source_types.split(",") if item.strip()),
        strict_min_verification_rows=args.strict_min_verification_rows,
        strict_min_locality_ready_fraction=args.strict_min_locality_ready_fraction,
        strict_min_retrieval_ready_fraction=args.strict_min_retrieval_ready_fraction,
        strict_min_long_range_join_ready_fraction=args.strict_min_long_range_join_ready_fraction,
        strict_min_state_update_ready_fraction=args.strict_min_state_update_ready_fraction,
        strict_min_target_rows_for_lost_state_probe=args.strict_min_target_rows_for_lost_state_probe,
        strict_min_programs_for_lost_state_probe=args.strict_min_programs_for_lost_state_probe,
    )


if __name__ == "__main__":
    main()
