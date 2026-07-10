from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl
from long_context_model_signal_fusion import fuse_model_assisted_signals

ML_TOKENS = {
    'pre', 'trained', 'training', 'shot', 'modal', 'entropy', 'forward', 'attention', 'encoder', 'decoder',
    'fine', 'tuning', 'scale', 'learning', 'arena', 'world', 'task', 'multimodal', 'zero', 'cross',
    'batch', 'vocab', 'head', 'heads', 'layer', 'layers', 'norm', 'grad', 'logits', 'embed', 'embeds',
    'embedding', 'embeddings', 'transformer', 'dataset', 'datasets', 'model', 'models', 'hidden', 'actor',
    'critic', 'reward', 'dtype', 'loss', 'train', 'eval', 'sample', 'samples', 'rollout', 'adapter',
}

SOFTWARE_HIGH_SIGNAL_TOKENS = {
    'api', 'http', 'web', 'cli', 'plugin', 'async', 'stream', 'cache', 'runtime', 'network', 'protocol',
    'backend', 'frontend', 'terminal', 'config', 'parser', 'logger', 'event', 'listener', 'docker', 'compose',
    'callback', 'endpoint', 'server', 'client', 'socket', 'port', 'auth', 'memory', 'interactive',
}

SOFTWARE_LOW_SIGNAL_TOKENS = {
    'args', 'parse', 'url', 'command', 'license', 'token', 'access', 'prompt', 'third', 'party', 'efficient',
    'round', 'trip', 'state', 'agent',
}

NARROW_SOFTWARE_RECOVERY_TOKENS = {'args', 'parse', 'url', 'command', 'token', 'agent', 'prompt', 'access', 'license'}

NARROW_SOFTWARE_OPERATIONAL_TOKENS = {'request', 'response', 'schema', 'version', 'handler', 'provider', 'options', 'headers', 'settings', 'summary', 'project'}

NARROW_SOFTWARE_INFRA_TOKENS = {'status', 'key', 'dir', 'path'}

NEGATIVE_TOKENS = {
    'non', 'empty', 'negative', 'level', 'defined', 'different', 'local', 'must', 'present', 'following',
}

GENERIC_COMPOUND_TOKENS = {
    'well', 'known', 'ground', 'truth', 'multi', 'stage', 'state', 'art', 'low', 'level', 'high', 'quality',
    'real', 'world', 'end', 'round', 'trip', 'present', 'different', 'local',
}

SOFTWARE_COMPOUND_ALLOWLIST = {
    'round_trip',
    'third_party',
    'single_stream',
    'non_interactive',
    'memory_efficient',
    'low_level',
    'web_arena',
}

IMPLEMENTATION_PATH_PARTS = ('/src/', '/lib/', '/app/', '/core/', '/cmd/', '/pkg/')
SOFTWARE_PATH_HINTS = (
    'api', 'cli', 'cmd', 'config', 'runtime', 'server', 'client', 'plugin', 'cache', 'stream', 'http', 'web',
    'docker', 'compose', 'socket', 'event', 'listener', 'logger', 'auth', 'token', 'endpoint', 'command',
)

TARGET_DOMAINS = {'all', 'ml', 'software'}


def _tokenize_compound(name: str) -> list[str]:
    return [part for part in str(name or '').split('_') if part]


def _domain_score(tokens: list[str], lexicon: set[str]) -> int:
    return sum(1 for token in tokens if token in lexicon)


def _software_token_profile(tokens: list[str]) -> tuple[int, int, list[str]]:
    high = sum(1 for token in tokens if token in SOFTWARE_HIGH_SIGNAL_TOKENS)
    low = sum(1 for token in tokens if token in SOFTWARE_LOW_SIGNAL_TOKENS)
    reasons = [f'software_high_token:{token}' for token in tokens if token in SOFTWARE_HIGH_SIGNAL_TOKENS]
    reasons.extend(f'software_low_token:{token}' for token in tokens if token in SOFTWARE_LOW_SIGNAL_TOKENS)
    return high, low, reasons


def _narrow_software_recovery(candidate: dict[str, Any], *, tokens: list[str], ml_score: int, negative_score: int, generic_score: int) -> tuple[bool, list[str]]:
    if ml_score > 0 or negative_score > 0 or generic_score > 0:
        return False, []
    matched_tokens = [token for token in tokens if token in NARROW_SOFTWARE_RECOVERY_TOKENS]
    matched_operational_tokens = [token for token in tokens if token in NARROW_SOFTWARE_OPERATIONAL_TOKENS]
    matched_infra_tokens = [token for token in tokens if token in NARROW_SOFTWARE_INFRA_TOKENS]
    if not matched_tokens and not matched_operational_tokens and not matched_infra_tokens:
        return False, []
    compiler = candidate.get('dataset_compiler') or {}
    links = compiler.get('retrieval_links') or []
    repo_paths = [str(link.get('path') or '').lower() for link in links if str(link.get('source_type') or '') == 'repo']
    software_path = any(any(hint in path for hint in SOFTWARE_PATH_HINTS) for path in repo_paths)
    if not software_path:
        return False, []
    reasons = [f'narrow_recovery_token:{token}' for token in matched_tokens]
    reasons.extend(f'narrow_recovery_operational:{token}' for token in matched_operational_tokens)
    reasons.extend(f'narrow_recovery_infra:{token}' for token in matched_infra_tokens)
    reasons.append('narrow_recovery:software_path')
    return True, reasons


def _software_metadata_hint(candidate: dict[str, Any]) -> tuple[int, list[str]]:
    compiler = candidate.get('dataset_compiler') or {}
    links = compiler.get('retrieval_links') or []
    tags = [str(tag) for tag in compiler.get('skill_tags') or []]
    repo_links = [link for link in links if str(link.get('source_type') or '') == 'repo']
    repo_paths = [str(link.get('path') or '').lower() for link in repo_links]
    repo_languages = [str(link.get('language') or '').lower() for link in repo_links if link.get('language')]

    score = 0
    reasons: list[str] = []
    if repo_languages:
        score += 1
        reasons.append('metadata_repo_code_language')
    if any(part in path for path in repo_paths for part in IMPLEMENTATION_PATH_PARTS):
        score += 2
        reasons.append('metadata_repo_impl_path')
    if any(hint in path for path in repo_paths for hint in SOFTWARE_PATH_HINTS):
        score += 1
        reasons.append('metadata_repo_software_path')
    if 'cross_repo_evidence' in tags:
        score += 1
        reasons.append('metadata_cross_repo_evidence')
    return score, reasons


def _accept_compound_candidate(
    *,
    domain: str,
    total_score: int,
    tokens: list[str],
    negative_score: int,
    generic_score: int,
    repo_support: int,
    software_hint: int,
    target_domain: str,
) -> bool:
    if len(tokens) < 2 or negative_score > 1:
        return False
    if target_domain == 'ml':
        return domain == 'ml_concept' and total_score >= 6
    if target_domain == 'software':
        return (
            domain == 'software_concept'
            and total_score >= 5
            and repo_support >= 1
            and (generic_score <= 1 or software_hint > 0)
        )
    if domain == 'ml_concept':
        return total_score >= 6
    if domain == 'software_concept':
        return (
            total_score >= 6
            and repo_support >= 1
            and (generic_score <= 1 or software_hint > 0)
        )
    return False


def classify_compound_candidate(candidate: dict[str, Any], *, target_domain: str = 'all') -> dict[str, Any]:
    if target_domain not in TARGET_DOMAINS:
        raise ValueError(f"unsupported target_domain: {target_domain}")
    name = str(candidate.get('canonical_name') or '')
    tokens = _tokenize_compound(name)
    repo_support = sum(1 for step in candidate.get('transition_chain', []) if str(step.get('source_type') or '') == 'repo')
    paper_support = sum(1 for step in candidate.get('transition_chain', []) if str(step.get('source_type') or '') == 'paper')
    ml_score = _domain_score(tokens, ML_TOKENS)
    software_high_score, software_low_score, software_token_reasons = _software_token_profile(tokens)
    software_score = software_high_score * 2 + software_low_score
    negative_score = _domain_score(tokens, NEGATIVE_TOKENS)
    generic_score = _domain_score(tokens, GENERIC_COMPOUND_TOKENS)
    reasons: list[str] = []
    if ml_score:
        reasons.extend(f'ml_token:{token}' for token in tokens if token in ML_TOKENS)
    reasons.extend(software_token_reasons)
    if negative_score:
        reasons.extend(f'negative_token:{token}' for token in tokens if token in NEGATIVE_TOKENS)
    if generic_score:
        reasons.extend(f'generic_token:{token}' for token in tokens if token in GENERIC_COMPOUND_TOKENS)

    allowlist_hint = 2 if name in SOFTWARE_COMPOUND_ALLOWLIST else 0
    if allowlist_hint:
        reasons.append('software_allowlist')
    metadata_hint, metadata_reasons = _software_metadata_hint(candidate)
    reasons.extend(metadata_reasons)
    narrow_recovery, narrow_recovery_reasons = _narrow_software_recovery(
        candidate,
        tokens=tokens,
        ml_score=ml_score,
        negative_score=negative_score,
        generic_score=generic_score,
    )
    reasons.extend(narrow_recovery_reasons)
    model_signal_fusion = fuse_model_assisted_signals(candidate)
    reasons.extend(model_signal_fusion['reasons'])
    software_hint = allowlist_hint + metadata_hint
    model_software_bonus = int(model_signal_fusion['software_bonus'])
    model_ml_bonus = int(model_signal_fusion['ml_bonus'])
    model_generic_penalty = int(model_signal_fusion['generic_penalty'])

    concept_bonus = 2 if len(tokens) >= 2 else 0
    support_bonus = min(repo_support, 2) + min(paper_support, 2)
    total_score = (
        (ml_score + model_ml_bonus) * 3
        + software_score * 2
        + software_hint
        + model_software_bonus
        + concept_bonus
        + support_bonus
        - negative_score * 2
        - generic_score
        - model_generic_penalty
    )
    lexical_software_signal = software_score + allowlist_hint
    if ml_score > 0 and ml_score >= max(software_high_score + software_low_score, 1):
        domain = 'ml_concept'
        reasons.append('domain:ml_concept')
    elif lexical_software_signal >= 2 or narrow_recovery or model_software_bonus >= 2 or model_signal_fusion['accept_override']:
        domain = 'software_concept'
        reasons.append('domain:software_concept')
    else:
        domain = 'generic_compound'
        reasons.append('domain:generic_compound')
    accepted = _accept_compound_candidate(
        domain=domain,
        total_score=total_score,
        tokens=tokens,
        negative_score=negative_score,
        generic_score=generic_score,
        repo_support=repo_support,
        software_hint=software_hint,
        target_domain=target_domain,
    )
    quality_tier = 'accepted' if accepted else 'rejected'
    if quality_tier == 'rejected':
        if len(tokens) < 2:
            reasons.append('reject:too_short')
        if negative_score > 1:
            reasons.append('reject:negative_score')
        if repo_support < 1:
            reasons.append('reject:no_repo_support')
        threshold = 5 if target_domain == 'software' else 6
        if domain == 'software_concept' and total_score < threshold:
            reasons.append('reject:software_score_threshold')
        if domain == 'ml_concept' and total_score < 6:
            reasons.append('reject:ml_score_threshold')
        if domain == 'generic_compound':
            reasons.append('reject:generic_domain')
        if target_domain == 'software' and model_signal_fusion['accept_override'] and repo_support < 1:
            reasons.append('reject:override_without_repo_support')
    else:
        reasons.append('accept')
    return {
        'candidate_id': candidate.get('candidate_id'),
        'canonical_name': name,
        'domain': domain,
        'ml_score': ml_score,
        'software_score': software_score,
        'negative_score': negative_score,
        'generic_score': generic_score,
        'software_hint': software_hint,
        'model_software_bonus': model_software_bonus,
        'model_ml_bonus': model_ml_bonus,
        'model_generic_penalty': model_generic_penalty,
        'accept_override': bool(model_signal_fusion['accept_override']),
        'repo_support': repo_support,
        'paper_support': paper_support,
        'total_score': total_score,
        'quality_tier': quality_tier,
        'target_domain': target_domain,
        'template_family': candidate.get('template_family'),
        'supporting_chunk_ids': candidate.get('supporting_chunk_ids', []),
        'reasons': reasons,
    }


def curate_compound_candidates(
    candidates: list[dict[str, Any]],
    *,
    target_domain: str = 'all',
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if target_domain not in TARGET_DOMAINS:
        raise ValueError(f"unsupported target_domain: {target_domain}")
    scored = [
        classify_compound_candidate(candidate, target_domain=target_domain)
        for candidate in candidates
        if '_' in str(candidate.get('canonical_name') or '')
    ]
    scored.sort(key=lambda row: (-int(row['total_score']), row['quality_tier'], row['canonical_name']))
    accepted = [row for row in scored if row['quality_tier'] == 'accepted']
    summary = {
        'target_domain': target_domain,
        'input_candidate_count': len(candidates),
        'compound_candidate_count': len(scored),
        'accepted_count': len(accepted),
        'domain_counts': {
            'ml_concept': sum(1 for row in scored if row['domain'] == 'ml_concept'),
            'software_concept': sum(1 for row in scored if row['domain'] == 'software_concept'),
            'generic_compound': sum(1 for row in scored if row['domain'] == 'generic_compound'),
        },
        'quality_tier_counts': {
            'accepted': len(accepted),
            'rejected': len(scored) - len(accepted),
        },
        'top_accepted': accepted[:20],
    }
    return scored, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Rank and filter compound concept candidates.')
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--target-domain', choices=sorted(TARGET_DOMAINS), default='all')
    args = parser.parse_args()
    scored, summary = curate_compound_candidates(read_jsonl(args.candidates), target_domain=args.target_domain)
    write_jsonl(args.output, scored)
    write_json(args.summary_output or args.output.with_name('compound_candidate_curator_summary.json'), summary)


if __name__ == '__main__':
    main()
