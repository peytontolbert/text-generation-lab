from __future__ import annotations

from typing import Any


def _bounded_score(value: Any, *, scale: float = 1.0, cap: int = 4) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(cap, int(round(numeric * scale))))


def fuse_model_assisted_signals(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = candidate.get('model_assisted_signals') or {}
    if not isinstance(payload, dict):
        return {
            'software_bonus': 0,
            'ml_bonus': 0,
            'generic_penalty': 0,
            'accept_override': False,
            'reasons': [],
        }

    reasons: list[str] = []
    software_bonus = 0
    ml_bonus = 0
    generic_penalty = 0
    accept_override = False

    domain_classifier = payload.get('domain_classifier') or {}
    if isinstance(domain_classifier, dict):
        label = str(domain_classifier.get('label') or '').strip().lower()
        confidence = float(domain_classifier.get('confidence') or 0.0)
        if label == 'software_concept':
            bonus = _bounded_score(confidence, scale=4.0, cap=4)
            software_bonus += bonus
            if bonus:
                reasons.append(f'model_domain:software:{confidence:.2f}')
        elif label == 'ml_concept':
            bonus = _bounded_score(confidence, scale=4.0, cap=4)
            ml_bonus += bonus
            if bonus:
                reasons.append(f'model_domain:ml:{confidence:.2f}')
        elif label == 'generic_compound':
            penalty = _bounded_score(confidence, scale=2.0, cap=3)
            generic_penalty += penalty
            if penalty:
                reasons.append(f'model_domain:generic:{confidence:.2f}')

    llm_judge = payload.get('llm_judge') or {}
    if isinstance(llm_judge, dict):
        label = str(llm_judge.get('label') or '').strip().lower()
        confidence = float(llm_judge.get('confidence') or 0.0)
        if label in {'software_concept', 'software', 'accept_software'}:
            bonus = _bounded_score(confidence, scale=3.0, cap=3)
            software_bonus += bonus
            if bonus:
                reasons.append(f'model_llm:software:{confidence:.2f}')
            if confidence >= 0.9:
                accept_override = True
                reasons.append('model_llm:accept_override')
        elif label in {'ml_concept', 'ml'}:
            bonus = _bounded_score(confidence, scale=3.0, cap=3)
            ml_bonus += bonus
            if bonus:
                reasons.append(f'model_llm:ml:{confidence:.2f}')
        elif label in {'generic_compound', 'generic', 'reject'}:
            penalty = _bounded_score(confidence, scale=2.0, cap=3)
            generic_penalty += penalty
            if penalty:
                reasons.append(f'model_llm:generic:{confidence:.2f}')

    reranker = payload.get('retrieval_reranker') or {}
    if isinstance(reranker, dict):
        score = float(reranker.get('top_repo_support_score') or 0.0)
        bonus = _bounded_score(score, scale=2.5, cap=3)
        software_bonus += bonus
        if bonus:
            reasons.append(f'model_reranker:repo_support:{score:.2f}')

    embeddings = payload.get('embedding_neighbors') or {}
    if isinstance(embeddings, dict):
        software_similarity = float(embeddings.get('software_similarity') or 0.0)
        ml_similarity = float(embeddings.get('ml_similarity') or 0.0)
        if software_similarity > ml_similarity:
            bonus = _bounded_score(software_similarity, scale=2.0, cap=2)
            software_bonus += bonus
            if bonus:
                reasons.append(f'model_embed:software:{software_similarity:.2f}')
        elif ml_similarity > software_similarity:
            bonus = _bounded_score(ml_similarity, scale=2.0, cap=2)
            ml_bonus += bonus
            if bonus:
                reasons.append(f'model_embed:ml:{ml_similarity:.2f}')

    return {
        'software_bonus': software_bonus,
        'ml_bonus': ml_bonus,
        'generic_penalty': generic_penalty,
        'accept_override': accept_override,
        'reasons': reasons,
    }
