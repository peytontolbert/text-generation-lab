from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

GENERIC_FINAL_ANSWERS = {
    '',
    'software_episode',
    'repair_or_edit',
    'repair_or_edit | patch_tool_used',
    'repair_or_edit | verification_observed',
    'repair_or_edit | verification_observed | patch_tool_used',
}
CODE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh'}
CONFIG_SUFFIXES = {'.json', '.jsonl', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.xml'}
DOC_SUFFIXES = {'.md', '.rst', '.txt'}
GENERIC_VERIFICATION_FILENAMES = {'tokenizer_specs', 'config', 'configs', 'settings', 'defaults', 'spec', 'specs'}
BAD_REPO_PATH_FRAGMENTS = (
    'readme',
    'years/',
    'newsletter',
    'awesome-',
    'papers-of-the-week',
    '/docs/changelog',
)
BAD_PAPER_PATH_FRAGMENTS = ('structured/repo_skills_miner', 'repos_chunks/', '.edges.jsonl', '.entities.jsonl', '.artifacts.jsonl')
BAD_DATASET_PATH_FRAGMENTS = ('/readme.md', '/readme.rst', '/readme.txt')
TRACE_HINT_TERMS = {'trace', 'error', 'stack', 'runtime', 'assert', 'failure', 'bug', 'exception', 'stderr', 'stdout', 'log'}
SOFTWARE_PAPER_HINT_TERMS = {
    'algorithm', 'model', 'training', 'inference', 'attention', 'retrieval', 'memory', 'agent', 'software', 'code',
    'execution', 'debug', 'verification', 'compiler', 'test', 'benchmark', 'repair', 'patch'
}
LOCAL_CONTEXT_ROLES = {'seed_change', 'repo_graph_neighbor', 'test_neighbor', 'verification_constraint'}
GENERIC_OVERLAP_TERMS = TRACE_HINT_TERMS | SOFTWARE_PAPER_HINT_TERMS | {'config', 'issue', 'goal', 'task', 'route', 'changed', 'files', 'repository'}
MIN_VERIFICATION_ALIGNMENT = 0.30


def _norm_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./').lower()


def _text_tokens(text: str) -> set[str]:
    token = []
    out: list[str] = []
    for char in str(text or '').lower():
        if char.isalnum():
            token.append(char)
        else:
            if len(token) >= 3:
                out.append(''.join(token))
            token = []
    if len(token) >= 3:
        out.append(''.join(token))
    return set(out)


def _reference_terms(example: dict[str, Any]) -> set[str]:
    query = dict(example.get('query') or {})
    refs: set[str] = set()
    for path in list(query.get('seed_paths') or []) + list(query.get('selected_tests') or []):
        refs.update(_text_tokens(Path(str(path)).stem))
        refs.update(_text_tokens(str(path)))
    for symbol in list(query.get('seed_symbols') or []):
        refs.update(_text_tokens(str(symbol)))
    refs.update(_text_tokens(str(query.get('text') or '')))
    return {term for term in refs if len(term) >= 3}


def _strong_reference_terms(example: dict[str, Any]) -> set[str]:
    return {term for term in _reference_terms(example) if term not in GENERIC_OVERLAP_TERMS}


def _row_anchor_hits(row: dict[str, Any], *, seed_path_terms: set[str], selected_test_terms: set[str], seed_symbol_terms: set[str]) -> set[str]:
    observed = _text_tokens(str(row.get('text') or '')) | _text_tokens(str(row.get('path') or ''))
    hits: set[str] = set()
    if observed & seed_path_terms:
        hits.add('seed_path')
    if observed & selected_test_terms:
        hits.add('verification_target')
    if observed & seed_symbol_terms:
        hits.add('seed_symbol')
    return hits


def _verification_filename_penalty(path: str) -> float:
    stem = Path(str(path or '')).stem.lower()
    return 1.0 if stem in GENERIC_VERIFICATION_FILENAMES else 0.0


def _verification_constraint_specificity(verification_rows: list[dict[str, Any]], *, seed_path_terms: set[str], selected_test_terms: set[str], seed_symbol_terms: set[str]) -> tuple[float, int]:
    if not verification_rows:
        return 0.0, 0
    specific = 0.0
    weak_rows = 0
    for row in verification_rows:
        hits = _row_anchor_hits(
            row,
            seed_path_terms=seed_path_terms,
            selected_test_terms=selected_test_terms,
            seed_symbol_terms=seed_symbol_terms,
        )
        reasons = {part for part in str(row.get('retrieval_reason') or '').split('|') if part}
        row_score = 0.0
        if hits:
            row_score += 0.7
        if 'focus_overlap' in reasons:
            row_score += 0.2
        if 'shared_seed_symbol' in reasons or 'path_stem_overlap' in reasons:
            row_score += 0.1
        row_score -= 0.25 * _verification_filename_penalty(str(row.get('path') or ''))
        row_score = max(0.0, min(1.0, row_score))
        specific += row_score
        if row_score < 0.5:
            weak_rows += 1
    return specific / len(verification_rows), weak_rows


def _is_high_value_row(row: dict[str, Any], *, ref_terms: set[str]) -> bool:
    source_type = str(row.get('source_type') or '')
    path = _norm_path(str(row.get('path') or ''))
    text = str(row.get('text') or '')
    text_terms = _text_tokens(text)
    observed_terms = text_terms | _text_tokens(path)
    strong_ref_terms = {term for term in ref_terms if term not in GENERIC_OVERLAP_TERMS}
    strong_overlap = len(strong_ref_terms & observed_terms)
    suffix = Path(path).suffix.lower()

    if source_type == 'local_repo':
        return True
    if source_type == 'repo':
        if any(fragment in path for fragment in BAD_REPO_PATH_FRAGMENTS):
            return False
        if suffix not in CODE_SUFFIXES | CONFIG_SUFFIXES | DOC_SUFFIXES:
            return False
        return strong_overlap >= 1
    if source_type == 'dataset':
        if any(fragment in path for fragment in BAD_DATASET_PATH_FRAGMENTS):
            return False
        hint_hit = any(term in path or term in text.lower() for term in TRACE_HINT_TERMS)
        return hint_hit and strong_overlap >= 1
    if source_type == 'paper':
        if any(fragment in path for fragment in BAD_PAPER_PATH_FRAGMENTS):
            return False
        hint_hit = any(term in path or term in text.lower() for term in SOFTWARE_PAPER_HINT_TERMS)
        return hint_hit and strong_overlap >= 1
    return False


def _context_row_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    chunk_id = str(row.get('chunk_id') or '')
    if chunk_id:
        return ('chunk', chunk_id, '')
    return (
        str(row.get('source_type') or ''),
        _norm_path(str(row.get('path') or '')),
        str(row.get('text') or '')[:256],
    )


def _row_role_priority(row: dict[str, Any]) -> int:
    role = str(row.get('role') or '')
    if role == 'verification_constraint':
        return 5
    if role == 'seed_change':
        return 4
    if role == 'test_neighbor':
        return 3
    if role == 'repo_graph_neighbor':
        return 2
    if role == 'trace_analogue':
        return 1
    return 0


def prune_context_rows(example: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context_rows = [dict(row) for row in example.get('context_rows', []) if isinstance(row, dict)]
    ref_terms = _reference_terms(example)
    query = dict(example.get('query') or {})
    seed_path_terms = _text_tokens(' '.join(list(query.get('seed_paths') or []))) - GENERIC_OVERLAP_TERMS
    selected_test_terms = _text_tokens(' '.join(list(query.get('selected_tests') or []))) - GENERIC_OVERLAP_TERMS
    seed_symbol_terms = _text_tokens(' '.join(str(symbol) for symbol in list(query.get('seed_symbols') or []))) - GENERIC_OVERLAP_TERMS

    kept: list[dict[str, Any]] = []
    kept_by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
    kept_index_by_identity: dict[tuple[str, str, str], int] = {}
    dropped_low_value = 0
    dropped_duplicate = 0
    kept_external = 0
    dropped_external = 0
    for row in context_rows:
        identity = _context_row_identity(row)
        source_type = str(row.get('source_type') or '')
        role = str(row.get('role') or '')
        if source_type == 'local_repo' or role in LOCAL_CONTEXT_ROLES:
            existing = kept_by_identity.get(identity)
            if existing is not None:
                if _row_role_priority(row) > _row_role_priority(existing):
                    kept[kept_index_by_identity[identity]] = row
                    kept_by_identity[identity] = row
                dropped_duplicate += 1
                continue
            kept_index_by_identity[identity] = len(kept)
            kept_by_identity[identity] = row
            kept.append(row)
            continue
        existing = kept_by_identity.get(identity)
        if existing is not None:
            dropped_duplicate += 1
            continue
        anchor_hits = _row_anchor_hits(
            row,
            seed_path_terms=seed_path_terms,
            selected_test_terms=selected_test_terms,
            seed_symbol_terms=seed_symbol_terms,
        )
        retrieval_reasons = {part for part in str(row.get('retrieval_reason') or '').split('|') if part}
        keep_external = _is_high_value_row(row, ref_terms=ref_terms)
        if source_type == 'dataset':
            keep_external = keep_external and bool(anchor_hits)
        elif source_type == 'paper':
            keep_external = keep_external and (bool(anchor_hits) or 'focus_overlap' in retrieval_reasons)
        elif source_type == 'repo':
            keep_external = keep_external and (bool(anchor_hits) or 'path_stem_overlap' in retrieval_reasons or 'shared_seed_symbol' in retrieval_reasons)
        if keep_external:
            kept_index_by_identity[identity] = len(kept)
            kept_by_identity[identity] = row
            kept.append(row)
            kept_external += 1
        else:
            dropped_low_value += 1
            dropped_external += 1

    return kept, {
        'input_context_rows': len(context_rows),
        'kept_context_rows': len(kept),
        'dropped_low_value_rows': dropped_low_value,
        'dropped_duplicate_rows': dropped_duplicate,
        'kept_external_rows': kept_external,
        'dropped_external_rows': dropped_external,
    }


def score_example(example: dict[str, Any]) -> dict[str, Any]:
    query = dict(example.get('query') or {})
    targets = dict(example.get('targets') or {})
    final_state = dict(targets.get('final_state') or {})
    context_rows = [dict(row) for row in example.get('context_rows', []) if isinstance(row, dict)]
    ref_terms = _reference_terms(example)
    strong_ref_terms = _strong_reference_terms(example)

    selected_tests = list(query.get('selected_tests') or [])
    seed_paths = list(query.get('seed_paths') or [])
    seed_symbols = list(query.get('seed_symbols') or [])
    final_answer = str(targets.get('final_answer') or '').strip()
    expected_changed_files = list(final_state.get('expected_changed_files') or [])
    verification_targets = list(final_state.get('verification_targets') or [])

    role_counts = Counter(str(row.get('role') or '') for row in context_rows)
    verification_rows = [row for row in context_rows if str(row.get('role') or '') == 'verification_constraint']
    external_rows = [
        row for row in context_rows
        if str(row.get('source_type') or '') != 'local_repo' and str(row.get('role') or '') not in LOCAL_CONTEXT_ROLES
    ]
    high_value_rows = [row for row in external_rows if _is_high_value_row(row, ref_terms=ref_terms)]
    seed_path_terms = _text_tokens(' '.join(seed_paths)) - GENERIC_OVERLAP_TERMS
    selected_test_terms = _text_tokens(' '.join(selected_tests)) - GENERIC_OVERLAP_TERMS
    seed_symbol_terms = _text_tokens(' '.join(str(symbol) for symbol in seed_symbols)) - GENERIC_OVERLAP_TERMS
    grounded_external_rows = [
        row for row in external_rows
        if _row_anchor_hits(
            row,
            seed_path_terms=seed_path_terms,
            selected_test_terms=selected_test_terms,
            seed_symbol_terms=seed_symbol_terms,
        )
    ]
    verification_bound_external_rows = [
        row for row in external_rows
        if _row_anchor_hits(
            row,
            seed_path_terms=set(),
            selected_test_terms=selected_test_terms,
            seed_symbol_terms=set(),
        )
    ]
    verification_constraint_specificity, weak_verification_constraint_count = _verification_constraint_specificity(
        verification_rows,
        seed_path_terms=seed_path_terms,
        selected_test_terms=selected_test_terms,
        seed_symbol_terms=seed_symbol_terms,
    )
    unique_paths = {f"{row.get('source_type')}::{row.get('path')}" for row in context_rows}
    unique_external_paths = {f"{row.get('source_type')}::{row.get('path')}" for row in external_rows}
    external_source_types = {str(row.get('source_type') or '') for row in external_rows}

    label_specificity = 0.0
    if final_answer and final_answer not in GENERIC_FINAL_ANSWERS:
        label_specificity += 0.4
    if expected_changed_files:
        label_specificity += 0.3
    if verification_targets:
        label_specificity += 0.3

    verification_grounding = 0.0
    if selected_tests:
        verification_grounding += 0.4
    if role_counts.get('verification_constraint', 0) > 0:
        verification_grounding += 0.4
    if final_state.get('execution_route') in {'PATCH_PLUS_EXEC', 'PATCH_PLUS_VERIFY', 'COMMIT_PLUS_VERIFY'}:
        verification_grounding += 0.2

    query_specificity = 0.0
    if seed_paths:
        query_specificity += 0.35
    if seed_symbols:
        query_specificity += 0.25
    if len(ref_terms) >= 12:
        query_specificity += 0.2
    if 'Changed files:' in str(query.get('text') or '') and 'Verification targets:' in str(query.get('text') or ''):
        query_specificity += 0.2

    retrieval_precision = (len(high_value_rows) / len(external_rows)) if external_rows else 0.0
    grounded_retrieval_precision = (len(grounded_external_rows) / len(external_rows)) if external_rows else 0.0
    path_diversity = (len(unique_paths) / len(context_rows)) if context_rows else 0.0
    external_path_diversity = (len(unique_external_paths) / len(external_rows)) if external_rows else 0.0
    evidence_source_diversity = min(1.0, len(external_source_types) / 3.0) if external_rows else 0.0
    strong_reference_coverage = min(1.0, len(strong_ref_terms) / 12.0) if strong_ref_terms else 0.0
    verification_alignment = (len(verification_bound_external_rows) / len(external_rows)) if external_rows else 0.0

    overall = min(
        1.0,
        0.28 * label_specificity +
        0.25 * verification_grounding +
        0.17 * query_specificity +
        0.10 * retrieval_precision +
        0.05 * grounded_retrieval_precision +
        0.05 * evidence_source_diversity +
        0.05 * strong_reference_coverage +
        0.05 * verification_alignment +
        0.05 * verification_constraint_specificity
    )

    fatal_reasons: list[str] = []
    if final_answer in GENERIC_FINAL_ANSWERS:
        fatal_reasons.append('generic_final_answer')
    if not final_state:
        fatal_reasons.append('missing_final_state')
    if not expected_changed_files:
        fatal_reasons.append('missing_expected_changed_files')
    if not verification_targets:
        fatal_reasons.append('missing_verification_targets')
    if not selected_tests:
        fatal_reasons.append('missing_selected_tests')
    if role_counts.get('verification_constraint', 0) == 0:
        fatal_reasons.append('missing_verification_context')
    if verification_rows and verification_constraint_specificity < 0.55:
        fatal_reasons.append('low_verification_constraint_specificity')
    if external_rows and retrieval_precision < 0.50:
        fatal_reasons.append('low_retrieval_precision')
    if external_rows and grounded_retrieval_precision < 0.60:
        fatal_reasons.append('low_grounded_retrieval_precision')
    if external_rows and verification_alignment < MIN_VERIFICATION_ALIGNMENT:
        fatal_reasons.append('low_verification_alignment')
    if external_rows and external_path_diversity < 0.60:
        fatal_reasons.append('low_external_path_diversity')

    return {
        'overall_score': overall,
        'label_specificity': label_specificity,
        'verification_grounding': verification_grounding,
        'query_specificity': query_specificity,
        'retrieval_precision': retrieval_precision,
        'grounded_retrieval_precision': grounded_retrieval_precision,
        'path_diversity': path_diversity,
        'external_path_diversity': external_path_diversity,
        'evidence_source_diversity': evidence_source_diversity,
        'strong_reference_coverage': strong_reference_coverage,
        'verification_alignment': verification_alignment,
        'verification_constraint_specificity': verification_constraint_specificity,
        'weak_verification_constraint_count': weak_verification_constraint_count,
        'context_row_count': len(context_rows),
        'external_row_count': len(external_rows),
        'high_value_external_row_count': len(high_value_rows),
        'grounded_external_row_count': len(grounded_external_rows),
        'verification_bound_external_row_count': len(verification_bound_external_rows),
        'role_counts': dict(sorted(role_counts.items())),
        'fatal_reasons': fatal_reasons,
    }


def require_passing_example(example: dict[str, Any], *, min_quality_score: float) -> dict[str, Any]:
    report = score_example(example)
    if report['fatal_reasons']:
        raise ValueError(f"example_quality_failure:{example.get('example_id')}:" + ','.join(report['fatal_reasons']))
    if float(report['overall_score']) < float(min_quality_score):
        raise ValueError(
            f"example_quality_below_threshold:{example.get('example_id')}:{report['overall_score']:.4f}<{float(min_quality_score):.4f}"
        )
    return report


def score_examples_file(*, examples_path: Path, min_quality_score: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [json.loads(line) for line in examples_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    reports = []
    failures = []
    for row in rows:
        report = score_example(row)
        reports.append({'example_id': row.get('example_id'), 'program_id': row.get('program_id'), **report})
        if report['fatal_reasons'] or float(report['overall_score']) < float(min_quality_score):
            failures.append({'example_id': row.get('example_id'), 'fatal_reasons': report['fatal_reasons'], 'overall_score': report['overall_score']})
    summary = {
        'example_count': len(rows),
        'failing_example_count': len(failures),
        'min_quality_score': float(min_quality_score),
        'avg_overall_score': (sum(float(r['overall_score']) for r in reports) / len(reports)) if reports else 0.0,
        'failures': failures[:200],
    }
    return reports, summary
