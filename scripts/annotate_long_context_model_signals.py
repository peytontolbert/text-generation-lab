from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from annotation_providers import ANNOTATION_PROVIDERS, AnnotationProvider
from long_context_common import read_jsonl, write_json, write_jsonl


class ModelSignalAnnotationError(RuntimeError):
    """Raised when model-signal annotation is requested without an explicit supported provider."""


def _read_chunk_rows(index_dir: Path) -> dict[str, dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: dict[str, dict[str, Any]] = {}
    for shard in sorted((index_dir / 'chunks').glob('*.parquet')):
        for row in pq.read_table(shard).to_pylist():
            rows[str(row.get('chunk_id'))] = row
    return rows


SUPPORTED_ANNOTATION_PROVIDERS = frozenset(ANNOTATION_PROVIDERS)


def list_annotation_providers() -> list[str]:
    return sorted(ANNOTATION_PROVIDERS)


def resolve_annotation_provider(provider: str | None) -> tuple[str, AnnotationProvider]:
    value = str(provider or '').strip()
    if not value:
        raise ModelSignalAnnotationError('annotation_provider_required')
    implementation = ANNOTATION_PROVIDERS.get(value)
    if implementation is None:
        raise ModelSignalAnnotationError(f'unsupported_annotation_provider:{value}')
    return value, implementation


def annotate_candidate_rows(
    *,
    index_dir: Path,
    candidates_path: Path,
    provider: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provider_name, implementation = resolve_annotation_provider(provider)
    candidates = read_jsonl(candidates_path)
    chunk_by_id = _read_chunk_rows(index_dir)
    annotated = [implementation(candidate, chunk_by_id, provider_name) for candidate in candidates]

    label_counts: dict[str, int] = {}
    failure_tag_counts: dict[str, int] = {}
    repo_evidence_count = 0
    accept_override_ready_count = 0
    for row in annotated:
        payload = row.get('model_assisted_signals') or {}
        llm_judge = payload.get('llm_judge') or {}
        reranker = payload.get('retrieval_reranker') or {}
        verification = payload.get('verification_record') or {}
        label = str(llm_judge.get('label') or 'unknown')
        label_counts[label] = label_counts.get(label, 0) + 1
        if float(reranker.get('top_repo_support_score') or 0.0) > 0.0:
            repo_evidence_count += 1
        if label == 'software_concept' and float(llm_judge.get('confidence') or 0.0) >= 0.9:
            accept_override_ready_count += 1
        for tag in verification.get('failure_tags') or []:
            key = str(tag)
            failure_tag_counts[key] = failure_tag_counts.get(key, 0) + 1

    summary = {
        'provider': provider_name,
        'candidate_count': len(annotated),
        'label_counts': dict(sorted(label_counts.items())),
        'failure_tag_counts': dict(sorted(failure_tag_counts.items())),
        'repo_evidence_candidate_count': repo_evidence_count,
        'accept_override_ready_count': accept_override_ready_count,
    }
    return annotated, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Annotate mined candidates with normalized model-assisted verifier signals.')
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--provider', type=str, required=True)
    args = parser.parse_args()

    annotated, summary = annotate_candidate_rows(
        index_dir=args.index_dir,
        candidates_path=args.candidates,
        provider=args.provider,
    )
    write_jsonl(args.output, annotated)
    write_json(args.summary_output or args.output.with_name('annotated_candidate_summary.json'), summary)


if __name__ == '__main__':
    main()
