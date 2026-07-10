from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from long_context_common import extract_compound_terms, extract_terms, write_json, write_jsonl
from long_context_compound_candidate_curator import curate_compound_candidates
from long_context_example_renderer import render_examples


def _read_chunk_rows(index_dir: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in sorted((index_dir / 'chunks').glob('*.parquet')):
        rows.extend(pq.read_table(path).to_pylist())
    return rows


def _read_candidate_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def _chunk_locator(chunk: dict[str, Any], *, role: str) -> dict[str, Any]:
    metadata = json.loads(chunk.get('metadata_json') or '{}')
    return {
        'chunk_id': str(chunk.get('chunk_id') or ''),
        'role': role,
        'source_type': str(chunk.get('source_type') or ''),
        'source_id': str(chunk.get('source_id') or ''),
        'doc_id': str(chunk.get('doc_id') or ''),
        'chunk_index': int(chunk.get('chunk_index') or 0),
        'modality': str(chunk.get('modality') or ''),
        'path': str(metadata.get('path') or ''),
        'language': metadata.get('language'),
        'token_count': int(chunk.get('token_count') or 0),
    }


def _context_rows_for_example(example: dict[str, Any], candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    retrieval_links = {
        str(row.get('chunk_id') or ''): dict(row)
        for row in (_require_task_metadata(candidate).get('retrieval_links') or [])
        if str(row.get('chunk_id') or '')
    }
    support_ids = {str(chunk_id) for chunk_id in candidate.get('supporting_chunk_ids', [])}
    rows: list[dict[str, Any]] = []
    for chunk_id in example.get('rendered_chunk_ids', []):
        chunk = chunk_by_id.get(str(chunk_id))
        if not chunk:
            raise ValueError(f'missing_chunk_for_rendered_context:{example.get("example_id")}:{chunk_id}')
        metadata = json.loads(chunk.get('metadata_json') or '{}')
        retrieval = retrieval_links.get(str(chunk_id), {})
        role = str(retrieval.get('role') or '')
        if not role:
            role = 'supporting_evidence' if str(chunk_id) in support_ids else 'distractor_context'
        retrieval_reason = 'retrieval_link' if retrieval else ('supporting_chunk' if str(chunk_id) in support_ids else 'noise_context')
        rows.append({
            'chunk_id': str(chunk.get('chunk_id') or ''),
            'source_type': str(chunk.get('source_type') or ''),
            'source_id': str(chunk.get('source_id') or ''),
            'doc_id': str(chunk.get('doc_id') or ''),
            'path': str(metadata.get('path') or ''),
            'chunk_index': int(chunk.get('chunk_index') or 0),
            'token_count': int(chunk.get('token_count') or 0),
            'text': str(chunk.get('text') or ''),
            'role': role,
            'retrieval_reason': retrieval_reason,
            'distance_from_seed': 0 if retrieval or str(chunk_id) in support_ids else 2,
            'retrieval_score': float(retrieval.get('score') or (1.0 if str(chunk_id) in support_ids else 0.0)),
        })
    if not rows:
        raise ValueError(f'missing_context_rows:{example.get("example_id")}')
    return rows


def _require_task_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    metadata = candidate.get('dataset_compiler')
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError(f"missing_dataset_compiler:{candidate.get('candidate_id')}")
    retrieval_links = metadata.get('retrieval_links') or []
    quality = metadata.get('quality') or {}
    difficulty = metadata.get('difficulty') or {}
    if not retrieval_links:
        raise ValueError(f"missing_retrieval_links:{candidate.get('candidate_id')}")
    if quality.get('bucket') in {None, ''}:
        raise ValueError(f"missing_quality_bucket:{candidate.get('candidate_id')}")
    if difficulty.get('level') is None:
        raise ValueError(f"missing_difficulty_level:{candidate.get('candidate_id')}")
    return dict(metadata)


def _normalized_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./').lower()

def _path_suffix_candidates(path: str) -> set[str]:
    parts = [part for part in _normalized_path(path).split('/') if part]
    out: set[str] = set()
    if len(parts) >= 1:
        out.add(parts[-1])
    if len(parts) >= 2:
        out.add('/'.join(parts[-2:]))
    if len(parts) >= 3:
        out.add('/'.join(parts[-3:]))
    return out

def _is_noise_anchor_path(path: str, *, source_type: str) -> bool:
    raw = str(path or '').strip()
    if not raw:
        return True
    norm = _normalized_path(raw)
    name = Path(norm).name
    suffix = Path(norm).suffix.lower()
    if norm.startswith('.') or '/.claude/' in f'/{norm}/':
        return True
    if name in {'manifest.json', 'stats.json', 'train.jsonl', 'test.jsonl', 'validation.jsonl'}:
        return True
    if suffix == '.parquet':
        return True
    if source_type in {'paper', 'dataset'} and suffix in {'.json', '.jsonl'}:
        return True
    if source_type in {'paper', 'dataset'} and name.startswith('paper_') and suffix == '.jsonl':
        return True
    return False

def _is_viable_symbol(symbol: str) -> bool:
    raw = str(symbol or '').strip()
    if len(raw) < 4:
        return False
    if raw.upper() == raw:
        return False
    lowered = raw.lower()
    if lowered.startswith('readme') or lowered.endswith('.jsonl') or lowered.endswith('.parquet'):
        return False
    if 'guideline' in lowered or 'template' in lowered:
        return False
    return True

def _support_chunk_rows(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for chunk_id in candidate.get('supporting_chunk_ids', []):
        chunk = chunk_by_id.get(str(chunk_id))
        if chunk:
            rows.append(chunk)
    return rows

def _candidate_grounding(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metadata = _require_task_metadata(candidate)
    exact_paths: list[str] = []
    path_suffixes: list[str] = []
    repo_source_ids: list[str] = []
    terms: list[str] = []
    compounds: list[str] = []
    anchor_text_parts: list[str] = []

    def add_term_values(values: list[str]) -> None:
        for value in values:
            token = str(value or '').strip().lower()
            if len(token) < 3:
                continue
            if token not in terms:
                terms.append(token)

    def add_compound_values(values: list[str]) -> None:
        for value in values:
            token = str(value or '').strip().lower()
            if len(token) < 3:
                continue
            if token not in compounds:
                compounds.append(token)

    add_term_values(_candidate_keywords(candidate))
    add_compound_values(_contrastive_keywords(candidate))

    for row in metadata.get('retrieval_links') or []:
        source_type = str(row.get('source_type') or '')
        raw_path = str(row.get('path') or '').strip()
        if raw_path and not _is_noise_anchor_path(raw_path, source_type=source_type):
            norm = _normalized_path(raw_path)
            if norm not in exact_paths:
                exact_paths.append(norm)
            for suffix in sorted(_path_suffix_candidates(norm)):
                if suffix not in path_suffixes:
                    path_suffixes.append(suffix)
            add_term_values(extract_terms(raw_path, max_terms=24, source_type=source_type or None))
            add_compound_values(extract_compound_terms(raw_path, max_terms=12, source_type=source_type or None))
        source_id = str(row.get('source_id') or '').strip()
        if source_type == 'repo' and source_id and source_id not in repo_source_ids:
            repo_source_ids.append(source_id)

    for chunk in _support_chunk_rows(candidate, chunk_by_id):
        source_type = str(chunk.get('source_type') or '')
        source_id = str(chunk.get('source_id') or '').strip()
        if source_type == 'repo' and source_id and source_id not in repo_source_ids:
            repo_source_ids.append(source_id)
        meta = json.loads(chunk.get('metadata_json') or '{}')
        raw_path = str(meta.get('path') or '')
        if raw_path and not _is_noise_anchor_path(raw_path, source_type=source_type):
            norm = _normalized_path(raw_path)
            if norm not in exact_paths:
                exact_paths.append(norm)
            for suffix in sorted(_path_suffix_candidates(norm)):
                if suffix not in path_suffixes:
                    path_suffixes.append(suffix)
        text_sample = str(chunk.get('text') or '')[:2400]
        if text_sample:
            anchor_text_parts.append(text_sample)
            add_term_values(extract_terms(text_sample, max_terms=32, source_type=source_type or None, modality=str(chunk.get('modality') or '') or None))
            add_compound_values(extract_compound_terms(text_sample, max_terms=16, source_type=source_type or None, modality=str(chunk.get('modality') or '') or None))

    return {
        'exact_paths': exact_paths[:32],
        'path_suffixes': path_suffixes[:64],
        'repo_source_ids': repo_source_ids[:16],
        'terms': terms[:96],
        'compounds': compounds[:48],
        'anchor_text': '\n'.join(anchor_text_parts)[:12000],
    }

def _candidate_to_program(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    state_variable = str(candidate.get('state_variable') or f"{candidate.get('canonical_name')}_active")
    return {
        'program_id': str(candidate.get('candidate_id')),
        'query_text': f"What is the final value of `{state_variable}` after reconciling all evidence?",
        'supporting_chunk_ids': list(candidate.get('supporting_chunk_ids', [])),
        'final_state': dict(candidate.get('final_state') or {state_variable: True}),
        'state_probe_points': [],
        'grounding': _candidate_grounding(candidate, chunk_by_id),
    }

def _phrase_variants(name: str) -> list[str]:
    tokens = [part for part in str(name or '').lower().split('_') if part]
    if not tokens:
        return []
    variants = {
        '_'.join(tokens),
        '-'.join(tokens),
        ' '.join(tokens),
        ''.join(tokens),
    }
    return sorted(variants)


def _candidate_keywords(candidate: dict[str, Any]) -> list[str]:
    metadata = candidate.get('dataset_compiler') or {}
    tags = [str(tag).lower() for tag in metadata.get('skill_tags') or []]
    canonical = str(candidate.get('canonical_name') or '')
    variants = _phrase_variants(canonical)
    raw_tokens = [part for part in canonical.lower().split('_') if len(part) >= 3]
    keywords = []
    for item in variants + raw_tokens + tags:
        value = str(item or '').strip().lower()
        if len(value) < 3:
            continue
        if value not in keywords:
            keywords.append(value)
    return keywords[:16]


def _contrastive_keywords(candidate: dict[str, Any]) -> list[str]:
    canonical = str(candidate.get('canonical_name') or '')
    keywords = []
    for item in _phrase_variants(canonical):
        value = str(item or '').strip().lower()
        compact = value.replace('_', '').replace('-', '').replace(' ', '')
        if len(value) >= 5 and value not in keywords:
            keywords.append(value)
        if len(compact) >= 5 and compact not in keywords:
            keywords.append(compact)
    return keywords[:8]


def _extract_support_span(text: str, keywords: list[str], *, window_chars: int = 220) -> dict[str, Any] | None:
    raw = str(text or '')
    if not raw.strip():
        return None
    lowered = raw.lower()
    best: tuple[int, int, str] | None = None
    for keyword in keywords:
        if not keyword:
            continue
        match = re.search(re.escape(keyword), lowered)
        if match:
            start = max(0, match.start() - window_chars // 2)
            end = min(len(raw), match.end() + window_chars // 2)
            snippet = raw[start:end].strip()
            return {
                'match_type': 'keyword',
                'keyword': keyword,
                'char_start': match.start(),
                'char_end': match.end(),
                'snippet': snippet,
            }
        compact = keyword.replace('_', '').replace('-', '').replace(' ', '')
        if compact and compact != keyword:
            compact_match = re.search(re.escape(compact), re.sub(r'[^a-z0-9]+', '', lowered))
            if compact_match and best is None:
                best = (0, min(len(raw), window_chars), keyword)
    if best is not None:
        start, end, keyword = best
        return {
            'match_type': 'approximate',
            'keyword': keyword,
            'char_start': start,
            'char_end': end,
            'snippet': raw[start:end].strip(),
        }
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    snippet = lines[0][:window_chars]
    return {
        'match_type': 'fallback',
        'keyword': None,
        'char_start': 0,
        'char_end': min(len(raw), len(snippet)),
        'snippet': snippet,
    }


def _build_support_spans(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    keywords = _candidate_keywords(candidate)
    spans: list[dict[str, Any]] = []
    for chunk_id in candidate.get('supporting_chunk_ids', []):
        chunk = chunk_by_id.get(str(chunk_id))
        if not chunk:
            continue
        locator = _chunk_locator(chunk, role='support_span')
        span = _extract_support_span(str(chunk.get('text') or ''), keywords)
        if not span:
            continue
        spans.append({**locator, **span})
    return spans


def _build_contrastive_negatives(
    *,
    example: dict[str, Any],
    candidate: dict[str, Any],
    chunk_by_id: dict[str, dict[str, Any]],
    max_negatives: int = 3,
) -> list[dict[str, Any]]:
    support_ids = {str(chunk_id) for chunk_id in candidate.get('supporting_chunk_ids', [])}
    keywords = _contrastive_keywords(candidate)
    negatives: list[dict[str, Any]] = []
    if not keywords:
        return negatives
    for chunk_id in example.get('rendered_chunk_ids', []):
        chunk_key = str(chunk_id)
        if chunk_key in support_ids:
            continue
        chunk = chunk_by_id.get(chunk_key)
        if not chunk:
            continue
        span = _extract_support_span(str(chunk.get('text') or ''), keywords)
        if not span or span.get('match_type') == 'fallback':
            continue
        locator = _chunk_locator(chunk, role='hard_negative')
        negatives.append({
            **locator,
            **span,
            'label': 'hard_negative',
        })
        if len(negatives) >= max_negatives:
            break
    return negatives


def _software_evidence_metrics(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    variants = _phrase_variants(str(candidate.get('canonical_name') or ''))
    code_suffixes = {'.py', '.rs', '.go', '.ts', '.tsx', '.js', '.jsx', '.java', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh'}
    weak_symbol_stems = {'utils', 'helper', 'helpers', 'config', 'configs', 'prompt', 'prompts', 'main', 'core', 'test', 'tests', '__init__', 'index'}
    repo_chunks = [
        chunk_by_id[chunk_id]
        for chunk_id in candidate.get('supporting_chunk_ids', [])
        if chunk_id in chunk_by_id and str(chunk_by_id[chunk_id].get('source_type') or '') == 'repo'
    ]
    repo_variant_hits = 0
    repo_path_variant_hits = 0
    repo_text_variant_hits = 0
    repo_code_anchor_count = 0
    viable_repo_symbol_count = 0
    matched_chunk_ids: list[str] = []
    for chunk in repo_chunks:
        text = str(chunk.get('text') or '').lower()
        meta = json.loads(chunk.get('metadata_json') or '{}')
        path = str(meta.get('path') or '').lower()
        suffix = Path(path).suffix.lower()
        if path and suffix in code_suffixes and not _is_noise_anchor_path(path, source_type='repo'):
            repo_code_anchor_count += 1
            stem = Path(path).stem.strip()
            if _is_viable_symbol(stem) and stem.lower() not in weak_symbol_stems:
                viable_repo_symbol_count += 1
        hit_in_text = any(variant in text for variant in variants if variant)
        hit_in_path = any(variant in path for variant in variants if variant)
        if hit_in_text or hit_in_path:
            repo_variant_hits += 1
            matched_chunk_ids.append(str(chunk.get('chunk_id')))
        if hit_in_text:
            repo_text_variant_hits += 1
        if hit_in_path:
            repo_path_variant_hits += 1
    passes_phrase_evidence = repo_variant_hits >= 1
    passes_repo_code_anchor_evidence = repo_code_anchor_count >= 1
    passes_repo_symbol_evidence = viable_repo_symbol_count >= 1
    return {
        'software_phrase_variants': variants,
        'repo_chunk_count': len(repo_chunks),
        'repo_variant_hits': repo_variant_hits,
        'repo_text_variant_hits': repo_text_variant_hits,
        'repo_path_variant_hits': repo_path_variant_hits,
        'repo_code_anchor_count': repo_code_anchor_count,
        'viable_repo_symbol_count': viable_repo_symbol_count,
        'matched_repo_chunk_ids': matched_chunk_ids,
        'passes_phrase_evidence': passes_phrase_evidence,
        'passes_repo_code_anchor_evidence': passes_repo_code_anchor_evidence,
        'passes_repo_symbol_evidence': passes_repo_symbol_evidence,
        'passes_software_evidence': passes_phrase_evidence and passes_repo_code_anchor_evidence and passes_repo_symbol_evidence,
    }


def _enrich_scored_candidates(
    *,
    scored: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    chunk_by_id: dict[str, dict[str, Any]],
    target_domain: str,
) -> list[dict[str, Any]]:
    candidate_by_id = {str(candidate.get('candidate_id')): candidate for candidate in candidates}
    enriched: list[dict[str, Any]] = []
    for row in scored:
        candidate = candidate_by_id.get(str(row.get('candidate_id')))
        merged = dict(row)
        if candidate and row.get('domain') == 'software_concept':
            merged['evidence'] = _software_evidence_metrics(candidate, chunk_by_id)
            if target_domain == 'software' and merged['quality_tier'] == 'accepted' and not merged['evidence']['passes_software_evidence']:
                merged['quality_tier'] = 'rejected'
                if not merged['evidence']['passes_repo_code_anchor_evidence']:
                    merged['rejection_reason'] = 'missing_repo_code_anchor_evidence'
                elif not merged['evidence']['passes_repo_symbol_evidence']:
                    merged['rejection_reason'] = 'missing_repo_symbol_evidence'
                else:
                    merged['rejection_reason'] = 'missing_repo_phrase_evidence'
        enriched.append(merged)
    enriched.sort(key=lambda row: (-int(row['total_score']), row['quality_tier'], row['canonical_name']))
    return enriched


def _enrich_example_targets(example: dict[str, Any], candidate: dict[str, Any], task_metadata: dict[str, Any], support_spans: list[dict[str, Any]]) -> dict[str, Any]:
    targets = dict(example.get('targets') or {})
    final_state = dict(targets.get('final_state') or {})
    code_suffixes = {'.py', '.rs', '.go', '.ts', '.tsx', '.js', '.jsx', '.java', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh'}
    weak_symbol_stems = {'utils', 'helper', 'helpers', 'config', 'configs', 'prompt', 'prompts', 'main', 'core', 'test', 'tests', '__init__', 'index'}
    repo_code_paths: list[str] = []
    repo_test_paths: list[str] = []
    paper_dataset_paths: list[str] = []
    external_evidence_terms: list[str] = []
    key_symbols: list[str] = []

    def add_repo_path(raw_path: str) -> None:
        value = str(raw_path or '').strip()
        if not value:
            return
        suffix = Path(value).suffix.lower()
        lowered = value.lower()
        if suffix not in code_suffixes:
            return
        bucket = repo_test_paths if '/test' in lowered or lowered.endswith('_test.py') or lowered.endswith('test.py') else repo_code_paths
        if value not in bucket:
            bucket.append(value)

    def add_external_path(raw_path: str, source_type: str) -> None:
        value = str(raw_path or '').strip()
        if not value or _is_noise_anchor_path(value, source_type=source_type):
            return
        if value not in paper_dataset_paths:
            paper_dataset_paths.append(value)

    def add_external_term(raw_term: str) -> None:
        value = str(raw_term or '').strip().lower()
        if len(value) < 8:
            return
        weak_terms = {'memory', 'roundtrip', 'round-trip', 'cacheenabled', 'cache_enabled', 'cache-enabled', 'rows', 'output_dir', 'event', 'segment', 'audio'}
        if value in weak_terms:
            return
        if value not in external_evidence_terms:
            external_evidence_terms.append(value)

    def add_path_symbol(raw_path: str) -> None:
        path_obj = Path(str(raw_path or '').strip())
        if path_obj.suffix.lower() not in code_suffixes:
            return
        stem = path_obj.stem.strip()
        if not _is_viable_symbol(stem):
            return
        if stem.lower() in weak_symbol_stems:
            return
        if stem not in key_symbols:
            key_symbols.append(stem)

    for span in support_spans:
        raw_path = str(span.get('path') or '').strip()
        source_type = str(span.get('source_type') or '')
        if source_type == 'repo':
            add_repo_path(raw_path)
            add_path_symbol(raw_path)
        elif source_type in {'paper', 'dataset'}:
            add_external_path(raw_path, source_type)
            keyword = str(span.get('keyword') or '').strip()
            if keyword:
                add_external_term(keyword)

    if not repo_code_paths and not repo_test_paths:
        raise ValueError(f"missing_repo_code_anchors:{candidate.get('candidate_id')}")

    verification_paths: list[str] = []
    primary_repo_paths = repo_test_paths[:1] + repo_code_paths[:1]
    if not primary_repo_paths:
        primary_repo_paths = repo_code_paths[:2]
    elif len(primary_repo_paths) < 2 and len(repo_code_paths) > 1:
        primary_repo_paths = primary_repo_paths + repo_code_paths[1:2]
    for path_value in [*primary_repo_paths[:2], *paper_dataset_paths[:2]]:
        if path_value not in verification_paths:
            verification_paths.append(path_value)

    final_state['expected_changed_files'] = primary_repo_paths[:2]
    final_state['verification_targets'] = verification_paths[:4]
    final_state['external_evidence_terms'] = external_evidence_terms[:2]
    final_state['key_symbols'] = key_symbols[:3]
    if not final_state['expected_changed_files']:
        raise ValueError(f"missing_expected_changed_files:{candidate.get('candidate_id')}")
    if not final_state['verification_targets']:
        raise ValueError(f"missing_verification_targets:{candidate.get('candidate_id')}")
    if not final_state['key_symbols']:
        raise ValueError(f"missing_key_symbols:{candidate.get('candidate_id')}")
    targets['final_state'] = final_state
    targets['final_state_json'] = json.dumps(final_state, sort_keys=True)
    return targets

def _attach_example_metadata(
    *,
    examples: list[dict[str, Any]],
    accepted_candidates: list[dict[str, Any]],
    chunk_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_id = {str(candidate.get('candidate_id')): candidate for candidate in accepted_candidates}
    enriched_examples: list[dict[str, Any]] = []
    for example in examples:
        candidate = candidate_by_id.get(str(example.get('program_id')))
        if not candidate:
            enriched_examples.append(example)
            continue
        task_metadata = _require_task_metadata(candidate)
        retrieval_links = list(task_metadata.get('retrieval_links') or [])
        support_spans = _build_support_spans(candidate, chunk_by_id)
        contrastive_negatives = _build_contrastive_negatives(
            example=example,
            candidate=candidate,
            chunk_by_id=chunk_by_id,
        )
        task_metadata['support_spans'] = support_spans
        task_metadata['contrastive_negatives'] = contrastive_negatives
        task_metadata['model_assisted_signals'] = dict(candidate.get('model_assisted_signals') or {})
        merged = dict(example)
        merged['task_metadata'] = task_metadata
        merged['model_assisted_signals'] = dict(candidate.get('model_assisted_signals') or {})
        merged['retrieval_supervision'] = {
            'required_evidence': retrieval_links,
            'supporting_chunk_ids': list(candidate.get('supporting_chunk_ids', [])),
            'support_spans': support_spans,
            'contrastive_negatives': contrastive_negatives,
        }
        merged['targets'] = _enrich_example_targets(example, candidate, task_metadata, support_spans)
        merged['context_rows'] = _context_rows_for_example(example, candidate, chunk_by_id)
        merged['quality'] = dict(task_metadata.get('quality') or {})
        if merged['quality'].get('quality_score') is None and merged['quality'].get('overall_score') is not None:
            merged['quality']['quality_score'] = merged['quality']['overall_score']
        merged['difficulty'] = dict(task_metadata.get('difficulty') or {})
        enriched_examples.append(merged)
    return enriched_examples


def build_retrieval_training_rows(examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    positive_total = 0
    negative_total = 0
    for example in examples:
        supervision = dict(example.get('retrieval_supervision') or {})
        positives = list(supervision.get('support_spans') or [])
        negatives = list(supervision.get('contrastive_negatives') or [])
        if not positives:
            continue
        positive_total += len(positives)
        negative_total += len(negatives)
        conflict = infer_conflict_supervision(
            positives,
            final_answer=(example.get('targets') or {}).get('final_answer'),
            final_state=dict((example.get('targets') or {}).get('final_state') or {}),
        )
        rows.append({
            'retrieval_example_id': f"{example['example_id']}_retrieval",
            'source_example_id': example['example_id'],
            'program_id': example['program_id'],
            'query': dict(example.get('query') or {}),
            'task_type': str((example.get('task_metadata') or {}).get('task_type') or 'state_transition_reconciliation'),
            'skill_tags': list((example.get('task_metadata') or {}).get('skill_tags') or []),
            'difficulty': dict(example.get('difficulty') or {}),
            'quality': dict(example.get('quality') or {}),
            'conflict_supervision': conflict,
            'positive_spans': positives,
            'hard_negative_spans': negatives,
            'targets': {
                'final_state': dict((example.get('targets') or {}).get('final_state') or {}),
                'final_answer': (example.get('targets') or {}).get('final_answer'),
                'positive_chunk_ids': [span.get('chunk_id') for span in positives],
                'negative_chunk_ids': [span.get('chunk_id') for span in negatives],
            },
        })
    conflict_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for row in rows:
        label = str((row.get('conflict_supervision') or {}).get('label') or 'unknown')
        relation = str((row.get('conflict_supervision') or {}).get('relation_label') or 'unknown')
        conflict_counts[label] = conflict_counts.get(label, 0) + 1
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
    summary = {
        'retrieval_row_count': len(rows),
        'positive_span_count': positive_total,
        'hard_negative_span_count': negative_total,
        'conflict_label_counts': dict(sorted(conflict_counts.items())),
        'relation_label_counts': dict(sorted(relation_counts.items())),
    }
    return rows, summary


def build_pairwise_retrieval_rows(retrieval_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for retrieval_row in retrieval_rows:
        positives = list(retrieval_row.get('positive_spans') or [])
        negatives = list(retrieval_row.get('hard_negative_spans') or [])
        for pos_index, positive in enumerate(positives, start=1):
            for neg_index, negative in enumerate(negatives, start=1):
                rows.append({
                    'pairwise_example_id': f"{retrieval_row['retrieval_example_id']}_p{pos_index}_n{neg_index}",
                    'retrieval_example_id': retrieval_row['retrieval_example_id'],
                    'program_id': retrieval_row['program_id'],
                    'query': dict(retrieval_row.get('query') or {}),
                    'preferred_span': positive,
                    'rejected_span': negative,
                    'label': 'preferred_over_negative',
                    'difficulty': dict(retrieval_row.get('difficulty') or {}),
                    'quality': dict(retrieval_row.get('quality') or {}),
                    'conflict_supervision': dict(retrieval_row.get('conflict_supervision') or {}),
                    'task_type': retrieval_row.get('task_type'),
                    'skill_tags': list(retrieval_row.get('skill_tags') or []),
                })
    return rows, {'pairwise_row_count': len(rows)}


def build_listwise_retrieval_rows(retrieval_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for retrieval_row in retrieval_rows:
        positives = list(retrieval_row.get('positive_spans') or [])
        negatives = list(retrieval_row.get('hard_negative_spans') or [])
        candidates = []
        for index, span in enumerate(positives, start=1):
            candidates.append({
                'rank_label': 1,
                'candidate_index': index,
                'span': span,
            })
        offset = len(candidates)
        for index, span in enumerate(negatives, start=1):
            candidates.append({
                'rank_label': 0,
                'candidate_index': offset + index,
                'span': span,
            })
        if not candidates:
            continue
        rows.append({
            'listwise_example_id': f"{retrieval_row['retrieval_example_id']}_list",
            'retrieval_example_id': retrieval_row['retrieval_example_id'],
            'program_id': retrieval_row['program_id'],
            'query': dict(retrieval_row.get('query') or {}),
            'candidates': candidates,
            'difficulty': dict(retrieval_row.get('difficulty') or {}),
            'quality': dict(retrieval_row.get('quality') or {}),
            'conflict_supervision': dict(retrieval_row.get('conflict_supervision') or {}),
            'task_type': retrieval_row.get('task_type'),
            'skill_tags': list(retrieval_row.get('skill_tags') or []),
        })
    return rows, {'listwise_row_count': len(rows)}


def build_conflict_training_rows(retrieval_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    precedence_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for retrieval_row in retrieval_rows:
        positives = list(retrieval_row.get('positive_spans') or [])
        paper_spans = [span for span in positives if str(span.get('source_type') or '') == 'paper']
        repo_spans = [span for span in positives if str(span.get('source_type') or '') == 'repo']
        if not paper_spans and not repo_spans:
            continue
        conflict = dict(retrieval_row.get('conflict_supervision') or {})
        precedence = str(conflict.get('precedence_label') or conflict.get('label') or 'unknown')
        relation = str(conflict.get('relation_label') or 'unknown')
        precedence_counts[precedence] = precedence_counts.get(precedence, 0) + 1
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
        rows.append({
            'conflict_example_id': f"{retrieval_row['retrieval_example_id']}_conflict",
            'retrieval_example_id': retrieval_row['retrieval_example_id'],
            'program_id': retrieval_row['program_id'],
            'query': dict(retrieval_row.get('query') or {}),
            'paper_positive_spans': paper_spans,
            'repo_positive_spans': repo_spans,
            'targets': {
                'precedence_label': precedence,
                'relation_label': relation,
                'final_state': dict((retrieval_row.get('targets') or {}).get('final_state') or {}),
                'final_answer': (retrieval_row.get('targets') or {}).get('final_answer'),
                'paper_chunk_ids': [span.get('chunk_id') for span in paper_spans],
                'repo_chunk_ids': [span.get('chunk_id') for span in repo_spans],
            },
            'difficulty': dict(retrieval_row.get('difficulty') or {}),
            'quality': dict(retrieval_row.get('quality') or {}),
            'skill_tags': list(retrieval_row.get('skill_tags') or []),
            'task_type': 'source_conflict_reconciliation',
            'conflict_supervision': conflict,
        })
    summary = {
        'conflict_row_count': len(rows),
        'precedence_label_counts': dict(sorted(precedence_counts.items())),
        'relation_label_counts': dict(sorted(relation_counts.items())),
    }
    return rows, summary


def build_maintenance_training_rows(examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    precedence_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    for example in examples:
        retrieval = dict(example.get('retrieval_supervision') or {})
        support_spans = list(retrieval.get('support_spans') or [])
        repo_spans = [span for span in support_spans if str(span.get('source_type') or '') == 'repo']
        paper_spans = [span for span in support_spans if str(span.get('source_type') or '') == 'paper']
        negatives = list(retrieval.get('contrastive_negatives') or [])
        if not repo_spans:
            continue
        conflict = infer_conflict_supervision(
            support_spans,
            final_answer=(example.get('targets') or {}).get('final_answer'),
            final_state=dict((example.get('targets') or {}).get('final_state') or {}),
        )
        precedence = str(conflict.get('precedence_label') or conflict.get('label') or 'unknown')
        relation = str(conflict.get('relation_label') or 'unknown')
        precedence_counts[precedence] = precedence_counts.get(precedence, 0) + 1
        relation_counts[relation] = relation_counts.get(relation, 0) + 1
        rows.append({
            'maintenance_example_id': f"{example['example_id']}_maintenance",
            'source_example_id': example['example_id'],
            'program_id': example['program_id'],
            'query': dict(example.get('query') or {}),
            'repo_evidence_spans': repo_spans,
            'paper_context_spans': paper_spans,
            'hard_negative_spans': negatives,
            'targets': {
                'final_state': dict((example.get('targets') or {}).get('final_state') or {}),
                'final_answer': (example.get('targets') or {}).get('final_answer'),
                'precedence_label': precedence,
                'relation_label': relation,
                'repo_chunk_ids': [span.get('chunk_id') for span in repo_spans],
                'paper_chunk_ids': [span.get('chunk_id') for span in paper_spans],
                'negative_chunk_ids': [span.get('chunk_id') for span in negatives],
            },
            'difficulty': dict(example.get('difficulty') or {}),
            'quality': dict(example.get('quality') or {}),
            'skill_tags': list((example.get('task_metadata') or {}).get('skill_tags') or []),
            'task_type': 'repo_grounded_maintenance',
            'conflict_supervision': conflict,
        })
    summary = {
        'maintenance_row_count': len(rows),
        'maintenance_precedence_label_counts': dict(sorted(precedence_counts.items())),
        'maintenance_relation_label_counts': dict(sorted(relation_counts.items())),
    }
    return rows, summary


def _maintenance_action_policy(row: dict[str, Any]) -> dict[str, Any]:
    conflict = dict(row.get('conflict_supervision') or {})
    precedence = str(conflict.get('precedence_label') or conflict.get('label') or 'unknown')
    relation = str(conflict.get('relation_label') or 'unknown')
    negatives = list(row.get('hard_negative_spans') or [])
    repo_spans = list(row.get('repo_evidence_spans') or [])
    paper_spans = list(row.get('paper_context_spans') or [])

    if relation == 'contradiction':
        action = 'verify_first'
        rationale = 'paper and repo evidence conflict directly; verify before editing'
        winning_chunk_ids = [span.get('chunk_id') for span in repo_spans[:1] + paper_spans[:1]]
    elif relation == 'tension':
        action = 'inspect_more'
        rationale = 'evidence is mixed; inspect additional implementation context before deciding'
        winning_chunk_ids = [span.get('chunk_id') for span in repo_spans[:2]]
    elif precedence == 'repo_over_paper':
        action = 'prefer_repo'
        rationale = 'implementation evidence should dominate the maintenance decision'
        winning_chunk_ids = [span.get('chunk_id') for span in repo_spans]
    elif precedence == 'paper_over_repo':
        action = 'prefer_paper'
        rationale = 'paper evidence currently dominates the decision state'
        winning_chunk_ids = [span.get('chunk_id') for span in paper_spans]
    elif negatives:
        action = 'verify_first'
        rationale = 'competing hard negatives suggest validating the winning evidence'
        winning_chunk_ids = [span.get('chunk_id') for span in repo_spans[:1]]
    else:
        action = 'prefer_repo'
        rationale = 'repo evidence is available and no stronger contradiction is present'
        winning_chunk_ids = [span.get('chunk_id') for span in repo_spans]

    return {
        'action_label': action,
        'rationale': rationale,
        'winning_chunk_ids': [chunk_id for chunk_id in winning_chunk_ids if chunk_id],
        'cited_repo_chunk_ids': [str(span.get('chunk_id')) for span in repo_spans[:2] if span.get('chunk_id')],
        'cited_paper_chunk_ids': [str(span.get('chunk_id')) for span in paper_spans[:2] if span.get('chunk_id')],
        'rejected_negative_chunk_ids': [str(span.get('chunk_id')) for span in negatives[:2] if span.get('chunk_id')],
    }


def build_maintenance_action_rows(maintenance_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    for maintenance_row in maintenance_rows:
        policy = _maintenance_action_policy(maintenance_row)
        action = str(policy.get('action_label') or 'unknown')
        action_counts[action] = action_counts.get(action, 0) + 1
        rows.append({
            'maintenance_action_example_id': f"{maintenance_row['maintenance_example_id']}_action",
            'maintenance_example_id': maintenance_row['maintenance_example_id'],
            'program_id': maintenance_row['program_id'],
            'query': dict(maintenance_row.get('query') or {}),
            'repo_evidence_spans': list(maintenance_row.get('repo_evidence_spans') or []),
            'paper_context_spans': list(maintenance_row.get('paper_context_spans') or []),
            'hard_negative_spans': list(maintenance_row.get('hard_negative_spans') or []),
            'targets': {
                **dict(maintenance_row.get('targets') or {}),
                'action_label': action,
                'winning_chunk_ids': list(policy.get('winning_chunk_ids') or []),
                'rationale_text': str(policy.get('rationale') or ''),
                'cited_repo_chunk_ids': list(policy.get('cited_repo_chunk_ids') or []),
                'cited_paper_chunk_ids': list(policy.get('cited_paper_chunk_ids') or []),
                'rejected_negative_chunk_ids': list(policy.get('rejected_negative_chunk_ids') or []),
            },
            'difficulty': dict(maintenance_row.get('difficulty') or {}),
            'quality': dict(maintenance_row.get('quality') or {}),
            'skill_tags': list(maintenance_row.get('skill_tags') or []),
            'task_type': 'maintenance_action_policy',
            'conflict_supervision': dict(maintenance_row.get('conflict_supervision') or {}),
            'policy_supervision': policy,
        })
    return rows, {'maintenance_action_row_count': len(rows), 'maintenance_action_label_counts': dict(sorted(action_counts.items()))}


def build_maintenance_rationale_rows(maintenance_action_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rationale_count = 0
    for action_row in maintenance_action_rows:
        policy = dict(action_row.get('policy_supervision') or {})
        rationale = str(policy.get('rationale') or '')
        if not rationale:
            continue
        rationale_count += 1
        rows.append({
            'maintenance_rationale_example_id': f"{action_row['maintenance_action_example_id']}_rationale",
            'maintenance_action_example_id': action_row['maintenance_action_example_id'],
            'program_id': action_row['program_id'],
            'query': dict(action_row.get('query') or {}),
            'repo_evidence_spans': list(action_row.get('repo_evidence_spans') or []),
            'paper_context_spans': list(action_row.get('paper_context_spans') or []),
            'hard_negative_spans': list(action_row.get('hard_negative_spans') or []),
            'targets': {
                'action_label': (action_row.get('targets') or {}).get('action_label'),
                'rationale_text': rationale,
                'winning_chunk_ids': list(policy.get('winning_chunk_ids') or []),
                'cited_repo_chunk_ids': list(policy.get('cited_repo_chunk_ids') or []),
                'cited_paper_chunk_ids': list(policy.get('cited_paper_chunk_ids') or []),
                'rejected_negative_chunk_ids': list(policy.get('rejected_negative_chunk_ids') or []),
            },
            'difficulty': dict(action_row.get('difficulty') or {}),
            'quality': dict(action_row.get('quality') or {}),
            'skill_tags': list(action_row.get('skill_tags') or []),
            'task_type': 'maintenance_rationale_generation',
            'conflict_supervision': dict(action_row.get('conflict_supervision') or {}),
        })
    return rows, {'maintenance_rationale_row_count': len(rows), 'maintenance_rationale_target_count': rationale_count}


def build_maintenance_trace_rows(maintenance_action_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trace_count = 0
    for action_row in maintenance_action_rows:
        policy = dict(action_row.get('policy_supervision') or {})
        action_label = str(policy.get('action_label') or '')
        repo_ids = list(policy.get('cited_repo_chunk_ids') or [])
        paper_ids = list(policy.get('cited_paper_chunk_ids') or [])
        negative_ids = list(policy.get('rejected_negative_chunk_ids') or [])
        if not action_label:
            continue
        steps = [
            {'step_index': 1, 'action': 'inspect_repo', 'chunk_ids': repo_ids[:2]},
            {'step_index': 2, 'action': 'compare_paper', 'chunk_ids': paper_ids[:2]},
        ]
        if negative_ids:
            steps.append({'step_index': len(steps) + 1, 'action': 'verify_negative', 'chunk_ids': negative_ids[:2]})
        steps.append({'step_index': len(steps) + 1, 'action': 'decide', 'chunk_ids': list(policy.get('winning_chunk_ids') or [])[:2]})
        trace_count += 1
        rows.append({
            'maintenance_trace_example_id': f"{action_row['maintenance_action_example_id']}_trace",
            'maintenance_action_example_id': action_row['maintenance_action_example_id'],
            'program_id': action_row['program_id'],
            'query': dict(action_row.get('query') or {}),
            'trace_steps': steps,
            'targets': {
                'action_label': action_label,
                'winning_chunk_ids': list(policy.get('winning_chunk_ids') or []),
                'step_actions': [step['action'] for step in steps],
            },
            'difficulty': dict(action_row.get('difficulty') or {}),
            'quality': dict(action_row.get('quality') or {}),
            'skill_tags': list(action_row.get('skill_tags') or []),
            'task_type': 'maintenance_trace_prediction',
            'conflict_supervision': dict(action_row.get('conflict_supervision') or {}),
            'policy_supervision': policy,
        })
    return rows, {'maintenance_trace_row_count': len(rows), 'maintenance_trace_target_count': trace_count}


def _rejected_maintenance_policy(row: dict[str, Any]) -> dict[str, Any]:
    chosen = dict(row.get('policy_supervision') or {})
    chosen_action = str(chosen.get('action_label') or 'prefer_repo')
    repo_ids = list(chosen.get('cited_repo_chunk_ids') or [])
    paper_ids = list(chosen.get('cited_paper_chunk_ids') or [])
    negative_ids = list(chosen.get('rejected_negative_chunk_ids') or [])

    if chosen_action == 'prefer_repo':
        action = 'prefer_paper'
        rationale = 'paper context should dominate even though repo evidence is available'
        winning_chunk_ids = paper_ids[:2]
    elif chosen_action == 'prefer_paper':
        action = 'prefer_repo'
        rationale = 'repo evidence should dominate immediately without paper review'
        winning_chunk_ids = repo_ids[:2]
    elif chosen_action == 'inspect_more':
        action = 'prefer_repo'
        rationale = 'skip additional inspection and commit to the repo evidence early'
        winning_chunk_ids = repo_ids[:2]
    else:
        action = 'prefer_repo'
        rationale = 'skip verification and rely on repo evidence immediately'
        winning_chunk_ids = repo_ids[:2]

    rejected_trace = [
        {'step_index': 1, 'action': 'inspect_repo', 'chunk_ids': repo_ids[:2]},
        {'step_index': 2, 'action': 'decide', 'chunk_ids': winning_chunk_ids[:2]},
    ]
    return {
        'action_label': action,
        'rationale': rationale,
        'winning_chunk_ids': [chunk_id for chunk_id in winning_chunk_ids if chunk_id],
        'rejected_trace_steps': rejected_trace,
        'cited_repo_chunk_ids': repo_ids[:2],
        'cited_paper_chunk_ids': paper_ids[:2],
        'rejected_negative_chunk_ids': negative_ids[:2],
    }


def build_maintenance_preference_rows(maintenance_action_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    preference_count = 0
    for action_row in maintenance_action_rows:
        chosen = dict(action_row.get('policy_supervision') or {})
        rejected = _rejected_maintenance_policy(action_row)
        if not chosen or not rejected:
            continue
        preference_count += 1
        rows.append({
            'maintenance_preference_example_id': f"{action_row['maintenance_action_example_id']}_preference",
            'maintenance_action_example_id': action_row['maintenance_action_example_id'],
            'program_id': action_row['program_id'],
            'query': dict(action_row.get('query') or {}),
            'chosen_policy': chosen,
            'rejected_policy': rejected,
            'difficulty': dict(action_row.get('difficulty') or {}),
            'quality': dict(action_row.get('quality') or {}),
            'skill_tags': list(action_row.get('skill_tags') or []),
            'task_type': 'maintenance_policy_preference',
            'conflict_supervision': dict(action_row.get('conflict_supervision') or {}),
        })
    return rows, {'maintenance_preference_row_count': len(rows), 'maintenance_preference_target_count': preference_count}


def infer_conflict_supervision(positive_spans: list[dict[str, Any]], *, final_answer: Any | None = None, final_state: dict[str, Any] | None = None) -> dict[str, Any]:
    repo_count = sum(1 for span in positive_spans if str(span.get('source_type') or '') == 'repo')
    paper_count = sum(1 for span in positive_spans if str(span.get('source_type') or '') == 'paper')
    other_count = max(0, len(positive_spans) - repo_count - paper_count)
    if repo_count > 0 and paper_count > 0:
        if repo_count > paper_count:
            precedence_label = 'repo_over_paper'
        elif paper_count > repo_count:
            precedence_label = 'paper_over_repo'
        else:
            precedence_label = 'consensus'
    elif repo_count > 0:
        precedence_label = 'repo_over_paper'
    elif paper_count > 0:
        precedence_label = 'paper_over_repo'
    else:
        precedence_label = 'mixed_other'

    positive_markers = {'active', 'enabled', 'stable', 'improves', 'improved', 'supports', 'successful', 'correct', 'implementation', 'agent', 'used'}
    negative_markers = {'inactive', 'disabled', 'unstable', 'fails', 'failed', 'broken', 'incorrect', 'regression', 'delete', 'invalid', 'error'}
    repo_affirm_markers = {'def ', 'class ', 'return', 'implementation', 'agent', 'active', 'enabled', 'support', 'uses'}
    paper_affirm_markers = {'improves', 'improved', 'supports', 'effective', 'stable', 'active', 'efficient'}

    def _span_polarity(span: dict[str, Any]) -> int:
        snippet = str(span.get('snippet') or '').lower()
        source_type = str(span.get('source_type') or '')
        pos = sum(1 for marker in positive_markers if marker in snippet)
        neg = sum(1 for marker in negative_markers if marker in snippet)
        if source_type == 'repo':
            pos += sum(1 for marker in repo_affirm_markers if marker in snippet)
        elif source_type == 'paper':
            pos += sum(1 for marker in paper_affirm_markers if marker in snippet)
        if pos > neg:
            return 1
        if neg > pos:
            return -1
        return 0

    repo_polarities = [_span_polarity(span) for span in positive_spans if str(span.get('source_type') or '') == 'repo']
    paper_polarities = [_span_polarity(span) for span in positive_spans if str(span.get('source_type') or '') == 'paper']
    repo_signal = sum(repo_polarities)
    paper_signal = sum(paper_polarities)

    target_truth = None
    if isinstance(final_answer, bool):
        target_truth = final_answer
    elif isinstance(final_state, dict) and final_state:
        values = [value for value in final_state.values() if isinstance(value, bool)]
        if values:
            target_truth = values[-1]

    if repo_signal * paper_signal < 0 and repo_signal != 0 and paper_signal != 0:
        relation_label = 'contradiction'
    elif repo_count > 0 and paper_count > 0:
        if target_truth is True and repo_signal >= 0 and paper_signal >= 0:
            relation_label = 'agreement'
        elif target_truth is False and repo_signal <= 0 and paper_signal <= 0 and (repo_signal < 0 or paper_signal < 0):
            relation_label = 'agreement'
        elif repo_signal == paper_signal and repo_signal != 0:
            relation_label = 'agreement'
        else:
            relation_label = 'tension'
    else:
        relation_label = 'agreement'

    return {
        'label': precedence_label,
        'precedence_label': precedence_label,
        'relation_label': relation_label,
        'repo_positive_count': repo_count,
        'paper_positive_count': paper_count,
        'other_positive_count': other_count,
        'repo_polarity_score': repo_signal,
        'paper_polarity_score': paper_signal,
        'target_truth': target_truth,
    }


def build_compound_concept_examples(
    *,
    index_dir: Path,
    candidates_path: Path,
    target_context_tokens: int = 100000,
    noise_ratio: float = 0.995,
    seed: int = 1337,
    target_domain: str = 'all',
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    candidates = _read_candidate_rows(candidates_path)
    scored, summary = curate_compound_candidates(candidates, target_domain=target_domain)
    chunks = _read_chunk_rows(index_dir)
    chunk_by_id = {str(chunk['chunk_id']): chunk for chunk in chunks}
    scored = _enrich_scored_candidates(
        scored=scored,
        candidates=candidates,
        chunk_by_id=chunk_by_id,
        target_domain=target_domain,
    )
    accepted_rows = [row for row in scored if row['quality_tier'] == 'accepted']
    accepted_ids = {str(row['candidate_id']) for row in accepted_rows}
    domain_by_id = {str(row['candidate_id']): str(row['domain']) for row in accepted_rows}
    accepted_candidates = [candidate for candidate in candidates if str(candidate.get('candidate_id')) in accepted_ids]
    programs = [_candidate_to_program(candidate, chunk_by_id) for candidate in accepted_candidates]
    examples = render_examples(
        chunks=chunks,
        programs=programs,
        target_context_tokens=target_context_tokens,
        noise_ratio=noise_ratio,
        seed=seed,
    )
    examples = _attach_example_metadata(
        examples=examples,
        accepted_candidates=accepted_candidates,
        chunk_by_id=chunk_by_id,
    )
    examples_by_domain = {
        'ml_concept': [example for example in examples if domain_by_id.get(str(example.get('program_id'))) == 'ml_concept'],
        'software_concept': [example for example in examples if domain_by_id.get(str(example.get('program_id'))) == 'software_concept'],
    }
    retrieval_rows, retrieval_summary = build_retrieval_training_rows(examples)
    software_rows = [row for row in scored if row.get('domain') == 'software_concept']
    accepted_software_rows = [row for row in software_rows if row.get('quality_tier') == 'accepted']
    software_rows_with_evidence = [row for row in software_rows if row.get('evidence')]
    accepted_software_rows_with_evidence = [row for row in accepted_software_rows if row.get('evidence')]
    difficulty_counts: dict[str, int] = {}
    quality_bucket_counts: dict[str, int] = {}
    for candidate in accepted_candidates:
        task_metadata = _require_task_metadata(candidate)
        difficulty = task_metadata.get('difficulty') or {}
        difficulty_key = str(difficulty.get('level') if difficulty.get('level') is not None else 'unknown')
        difficulty_counts[difficulty_key] = difficulty_counts.get(difficulty_key, 0) + 1
        quality = task_metadata.get('quality') or {}
        quality_key = str(quality.get('bucket') or 'unknown')
        quality_bucket_counts[quality_key] = quality_bucket_counts.get(quality_key, 0) + 1
    summary = dict(summary)
    summary.update({
        'accepted_count': len(accepted_rows),
        'accepted_program_count': len(programs),
        'rendered_example_count': len(examples),
        'target_context_tokens': target_context_tokens,
        'noise_ratio': noise_ratio,
        'target_domain': target_domain,
        'difficulty_level_counts': dict(sorted(difficulty_counts.items())),
        'quality_bucket_counts': dict(sorted(quality_bucket_counts.items())),
        'support_span_count': sum(len(example.get('retrieval_supervision', {}).get('support_spans', [])) for example in examples),
        'contrastive_negative_count': sum(len(example.get('retrieval_supervision', {}).get('contrastive_negatives', [])) for example in examples),
        'retrieval_row_count': retrieval_summary['retrieval_row_count'],
        'retrieval_positive_span_count': retrieval_summary['positive_span_count'],
        'retrieval_hard_negative_span_count': retrieval_summary['hard_negative_span_count'],
        'retrieval_conflict_label_counts': retrieval_summary['conflict_label_counts'],
        'retrieval_relation_label_counts': retrieval_summary['relation_label_counts'],
        'rendered_examples_by_domain': {key: len(value) for key, value in examples_by_domain.items()},
        'software_evidence_summary': {
            'software_domain_candidate_count': len(software_rows),
            'software_domain_accepted_candidate_count': len(accepted_software_rows),
            'software_domain_rejected_candidate_count': len(software_rows) - len(accepted_software_rows),
            'software_candidates_with_repo_phrase_evidence': sum(1 for row in software_rows_with_evidence if row['evidence']['passes_software_evidence']),
            'software_candidates_without_repo_phrase_evidence': sum(1 for row in software_rows_with_evidence if not row['evidence']['passes_software_evidence']),
            'accepted_software_candidates_with_repo_phrase_evidence': sum(1 for row in accepted_software_rows_with_evidence if row['evidence']['passes_software_evidence']),
            'accepted_software_candidates_without_repo_phrase_evidence': sum(1 for row in accepted_software_rows_with_evidence if not row['evidence']['passes_software_evidence']),
        },
        'top_accepted': accepted_rows[:20],
    })
    return examples, summary, scored, examples_by_domain, retrieval_rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Render long-context examples from curated compound concept candidates.')
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--scored-output', type=Path)
    parser.add_argument('--ml-output', type=Path)
    parser.add_argument('--software-output', type=Path)
    parser.add_argument('--retrieval-output', type=Path)
    parser.add_argument('--pairwise-output', type=Path)
    parser.add_argument('--listwise-output', type=Path)
    parser.add_argument('--conflict-output', type=Path)
    parser.add_argument('--maintenance-output', type=Path)
    parser.add_argument('--maintenance-action-output', type=Path)
    parser.add_argument('--maintenance-rationale-output', type=Path)
    parser.add_argument('--maintenance-trace-output', type=Path)
    parser.add_argument('--maintenance-preference-output', type=Path)
    parser.add_argument('--target-context-tokens', type=int, default=100000)
    parser.add_argument('--noise-ratio', type=float, default=0.995)
    parser.add_argument('--seed', type=int, default=1337)
    parser.add_argument('--target-domain', choices=['all', 'ml', 'software'], default='all')
    args = parser.parse_args()
    examples, summary, scored, examples_by_domain, retrieval_rows = build_compound_concept_examples(
        index_dir=args.index_dir,
        candidates_path=args.candidates,
        target_context_tokens=args.target_context_tokens,
        noise_ratio=args.noise_ratio,
        seed=args.seed,
        target_domain=args.target_domain,
    )
    pairwise_rows, pairwise_summary = build_pairwise_retrieval_rows(retrieval_rows)
    listwise_rows, listwise_summary = build_listwise_retrieval_rows(retrieval_rows)
    conflict_rows, conflict_summary = build_conflict_training_rows(retrieval_rows)
    maintenance_rows, maintenance_summary = build_maintenance_training_rows(examples)
    maintenance_action_rows, maintenance_action_summary = build_maintenance_action_rows(maintenance_rows)
    maintenance_rationale_rows, maintenance_rationale_summary = build_maintenance_rationale_rows(maintenance_action_rows)
    maintenance_trace_rows, maintenance_trace_summary = build_maintenance_trace_rows(maintenance_action_rows)
    maintenance_preference_rows, maintenance_preference_summary = build_maintenance_preference_rows(maintenance_action_rows)
    summary.update(pairwise_summary)
    summary.update(listwise_summary)
    summary.update({f'conflict_{key}': value for key, value in conflict_summary.items()})
    summary.update(maintenance_summary)
    summary.update(maintenance_action_summary)
    summary.update(maintenance_rationale_summary)
    summary.update(maintenance_trace_summary)
    summary.update(maintenance_preference_summary)
    write_jsonl(args.output, examples)
    write_json(args.summary_output or args.output.with_name('compound_concept_examples_summary.json'), summary)
    if args.scored_output:
        write_jsonl(args.scored_output, scored)
    if args.ml_output:
        write_jsonl(args.ml_output, examples_by_domain['ml_concept'])
    if args.software_output:
        write_jsonl(args.software_output, examples_by_domain['software_concept'])
    if args.retrieval_output:
        write_jsonl(args.retrieval_output, retrieval_rows)
    if args.pairwise_output:
        write_jsonl(args.pairwise_output, pairwise_rows)
    if args.listwise_output:
        write_jsonl(args.listwise_output, listwise_rows)
    if args.conflict_output:
        write_jsonl(args.conflict_output, conflict_rows)
    if args.maintenance_output:
        write_jsonl(args.maintenance_output, maintenance_rows)
    if args.maintenance_action_output:
        write_jsonl(args.maintenance_action_output, maintenance_action_rows)
    if args.maintenance_rationale_output:
        write_jsonl(args.maintenance_rationale_output, maintenance_rationale_rows)
    if args.maintenance_trace_output:
        write_jsonl(args.maintenance_trace_output, maintenance_trace_rows)
    if args.maintenance_preference_output:
        write_jsonl(args.maintenance_preference_output, maintenance_preference_rows)


if __name__ == '__main__':
    main()
