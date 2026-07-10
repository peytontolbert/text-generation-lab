from __future__ import annotations

import json
from typing import Any

from long_context_compound_candidate_curator import (
    GENERIC_COMPOUND_TOKENS,
    ML_TOKENS,
    SOFTWARE_HIGH_SIGNAL_TOKENS,
    SOFTWARE_LOW_SIGNAL_TOKENS,
)


def _tokenize(value: str) -> list[str]:
    return [part for part in str(value or '').lower().replace('-', '_').split('_') if part]


def _phrase_variants(name: str) -> list[str]:
    tokens = _tokenize(name)
    if not tokens:
        return []
    values: list[str] = []
    for item in ('_'.join(tokens), '-'.join(tokens), ' '.join(tokens), ''.join(tokens)):
        if item and item not in values:
            values.append(item)
    return values


def _chunk_text(row: dict[str, Any]) -> str:
    metadata = json.loads(row.get('metadata_json') or '{}')
    path = str(metadata.get('path') or '')
    text = str(row.get('text') or '')
    return f"{path}\n{text}".strip()


def _chunk_locator(row: dict[str, Any], *, score: float) -> dict[str, Any]:
    metadata = json.loads(row.get('metadata_json') or '{}')
    return {
        'chunk_id': str(row.get('chunk_id') or ''),
        'source_type': str(row.get('source_type') or ''),
        'source_id': str(row.get('source_id') or ''),
        'doc_id': str(row.get('doc_id') or ''),
        'path': str(metadata.get('path') or ''),
        'language': metadata.get('language'),
        'score': round(score, 4),
    }


def _bounded(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _keyword_overlap_score(text: str, keywords: list[str]) -> float:
    lowered = str(text or '').lower()
    if not keywords:
        return 0.0
    hits = 0
    for keyword in keywords:
        if keyword and keyword in lowered:
            hits += 1
    return _bounded(hits / max(1, len(keywords)))


def _lexicon_hits(tokens: list[str], lexicon: set[str]) -> int:
    return sum(1 for token in tokens if token in lexicon)


def annotate_candidate(candidate: dict[str, Any], chunk_by_id: dict[str, dict[str, Any]], provider_name: str) -> dict[str, Any]:
    name = str(candidate.get('canonical_name') or '')
    tokens = _tokenize(name)
    keywords = _phrase_variants(name) + tokens
    support_rows = [chunk_by_id[str(chunk_id)] for chunk_id in candidate.get('supporting_chunk_ids', []) if str(chunk_id) in chunk_by_id]
    repo_rows = [row for row in support_rows if str(row.get('source_type') or '') == 'repo']
    paper_rows = [row for row in support_rows if str(row.get('source_type') or '') == 'paper']

    scored_repo_rows: list[tuple[float, dict[str, Any]]] = []
    scored_paper_rows: list[tuple[float, dict[str, Any]]] = []
    for row in repo_rows:
        scored_repo_rows.append((_keyword_overlap_score(_chunk_text(row), keywords), row))
    for row in paper_rows:
        scored_paper_rows.append((_keyword_overlap_score(_chunk_text(row), keywords), row))
    scored_repo_rows.sort(key=lambda item: item[0], reverse=True)
    scored_paper_rows.sort(key=lambda item: item[0], reverse=True)

    top_repo_support_score = scored_repo_rows[0][0] if scored_repo_rows else 0.0
    top_paper_support_score = scored_paper_rows[0][0] if scored_paper_rows else 0.0
    repo_evidence = [_chunk_locator(row, score=score) for score, row in scored_repo_rows[:3] if score > 0.0]
    paper_evidence = [_chunk_locator(row, score=score) for score, row in scored_paper_rows[:3] if score > 0.0]

    ml_hits = _lexicon_hits(tokens, ML_TOKENS)
    software_hits = _lexicon_hits(tokens, SOFTWARE_HIGH_SIGNAL_TOKENS) * 2 + _lexicon_hits(tokens, SOFTWARE_LOW_SIGNAL_TOKENS)
    generic_hits = _lexicon_hits(tokens, GENERIC_COMPOUND_TOKENS)

    software_similarity = _bounded(top_repo_support_score * 0.7 + min(software_hits, 3) * 0.1 + (0.1 if repo_rows else 0.0) - generic_hits * 0.05)
    ml_similarity = _bounded(top_paper_support_score * 0.5 + min(ml_hits, 3) * 0.15)
    generic_risk = _bounded(generic_hits * 0.25 + (0.15 if top_repo_support_score == 0 else 0.0))

    if software_similarity >= max(0.45, ml_similarity + 0.1):
        domain_label = 'software_concept'
        domain_confidence = _bounded(0.45 + software_similarity * 0.5 + top_repo_support_score * 0.1)
    elif ml_similarity >= 0.45:
        domain_label = 'ml_concept'
        domain_confidence = _bounded(0.45 + ml_similarity * 0.5)
    else:
        domain_label = 'generic_compound'
        domain_confidence = _bounded(0.4 + generic_risk * 0.4)

    evidence_sufficiency = _bounded((1.0 if top_repo_support_score > 0 else 0.0) * 0.6 + (1.0 if top_paper_support_score > 0 else 0.0) * 0.4)
    causal_usefulness = _bounded(top_repo_support_score * 0.75 + top_paper_support_score * 0.15 + (0.1 if repo_rows else 0.0))
    progress = _bounded((causal_usefulness + evidence_sufficiency + domain_confidence) / 3.0)
    overall_score = _bounded(causal_usefulness * 0.45 + evidence_sufficiency * 0.25 + progress * 0.2 + (1.0 - generic_risk) * 0.1)

    failure_tags: list[str] = []
    if not repo_rows:
        failure_tags.append('missing_repo_support')
    if top_repo_support_score == 0.0:
        failure_tags.append('missing_repo_phrase_evidence')
    if generic_risk >= 0.4:
        failure_tags.append('generic_phrase_risk')
    if software_similarity < 0.4 and ml_similarity < 0.4:
        failure_tags.append('weak_domain_signal')

    verifier_label = domain_label
    if overall_score < 0.45:
        verifier_label = 'generic_compound'

    llm_confidence = _bounded(overall_score + (0.08 if verifier_label == 'software_concept' else 0.0))
    if verifier_label == 'software_concept' and top_repo_support_score >= 0.85 and evidence_sufficiency >= 0.9:
        llm_confidence = max(llm_confidence, 0.91)

    verification_record = {
        'provider': provider_name,
        'verifier_type': 'heuristic_proxy',
        'criteria': {
            'causal_usefulness': round(causal_usefulness, 4),
            'evidence_sufficiency': round(evidence_sufficiency, 4),
            'progress': round(progress, 4),
            'genericness_risk': round(generic_risk, 4),
        },
        'overall_score': round(overall_score, 4),
        'confidence': round(llm_confidence, 4),
        'label': verifier_label,
        'failure_tags': failure_tags,
        'evidence_spans': repo_evidence + paper_evidence,
    }

    enriched = dict(candidate)
    enriched['model_assisted_signals'] = {
        'provider': provider_name,
        'domain_classifier': {
            'label': domain_label,
            'confidence': round(domain_confidence, 4),
            'source': 'heuristic_proxy',
        },
        'retrieval_reranker': {
            'top_repo_support_score': round(top_repo_support_score, 4),
            'top_paper_support_score': round(top_paper_support_score, 4),
            'repo_evidence': repo_evidence,
            'paper_evidence': paper_evidence,
            'source': 'heuristic_proxy',
        },
        'embedding_neighbors': {
            'software_similarity': round(software_similarity, 4),
            'ml_similarity': round(ml_similarity, 4),
            'source': 'heuristic_proxy',
        },
        'llm_judge': {
            'label': verifier_label,
            'confidence': round(llm_confidence, 4),
            'source': 'heuristic_proxy',
        },
        'verification_record': verification_record,
    }
    return enriched
