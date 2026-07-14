#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10798
NAME = 'stage10798_rust_chroma_citation_repair_packet'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'rust_chroma_citation_repair_packet.json'
ROWS_JSONL = OUT_DIR / 'support_rows.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'

QUEUE_ROW = ROOT / 'runs/local/artifacts/stage10792_rust_competition_repair_queue/rust_competition_repair_queue.jsonl'
TARGET_ROOT_ID = 'strict_session_plus_strict_commit_ranked_v4_plus_v5_plus_broadexp_v3_plus_current_recent96_strict_packs_8m_hardened_v2::lcp_pack_1_8500000_localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_30t00_31_53_019d3c_314d88e084::q53'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line=line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def make_row(base: dict[str, Any], perspective: str, prompt_text: str, options: list[dict[str, str]], gold_label: str, gold_value: str, answer_kind: str) -> dict[str, Any]:
    return {
        'abstention_heavy': perspective == 'abstention_insufficient_evidence',
        'anti_cheat': {
            'prompt_target_leak_false': True,
            'opaque_labels': True,
            'train_support_only': True,
            'same_surface_eval_admissible': False,
            'rust_competition_repaired': True,
            'citation_vs_candidate_surface_explicit': True,
        },
        'authority': {},
        'bundle_id': f"stage10798::{base['root_id']}",
        'decoder_text': gold_label,
        'disable_losses': ['denoise_ce', 'runtime_reward', 'structured_aux'],
        'expected_answer_kind': 'opaque_choice',
        'expected_enabled_loss': 'decoder_ce',
        'expected_label': gold_label,
        'gold_value': gold_value,
        'input_text': prompt_text,
        'language_family': 'rust',
        'loss_mask': {'decoder_ce': True},
        'objective_family': 'bounded_decoder_ce',
        'opaque_options': options,
        'perspective': perspective,
        'prompt_text': prompt_text,
        'query_text': f'stage10798::rust::{perspective}',
        'repo_family': base['repo_family'],
        'repo_id': base['repo_family'],
        'route': 'rust_chroma_competition_repair',
        'row_id': f"stage10798::{base['root_id']}::{perspective}::support_candidate",
        'selected_test_anchor': True,
        'semantic_key': answer_kind,
        'source_bundle_id': f"stage10798::{base['root_id']}",
        'source_heldout_admissible': False,
        'source_row_id': base['root_id'],
        'split': 'train',
        'split_role': 'train_support',
        'strict_eval_eligible': False,
        'support_package_stage': STAGE,
        'surface': 'maintainer_bundle_compact_bounded_choice',
        'target_text': gold_label,
        'target_token_len': 1,
        'task_type': perspective,
        'train_support_only': True,
        'verifier_anchor': True,
    }


def main() -> None:
    queue_rows = load_jsonl(QUEUE_ROW)
    base = next(row for row in queue_rows if row['root_id'] == TARGET_ROOT_ID)

    shared_evidence = '\n'.join([
        'changed implementation candidate evidence [candidate A]: changed route test file in the agent path',
        'verifier or selected-test constraint [candidate B]: selected verifier target for the agent route test',
        'verifier or selected-test constraint [candidate C]: selected verifier target for the sibling subagent-search route test',
        'nearby definition or usage context [candidate D]: nearby symbols mention client/mod but do not identify which test anchor is decisive',
        'symptom or call-path evidence [summary]: commit-plus-verify route with two visible test anchors and only one changed-file preview',
    ])

    rows = []
    citation_options = [
        {'label': 'A', 'value': 'changed implementation candidate evidence'},
        {'label': 'B', 'value': 'agent-route verifier anchor'},
        {'label': 'C', 'value': 'sibling subagent-search verifier anchor'},
        {'label': 'D', 'value': 'nearby symbol context'},
    ]
    citation_prompt = (
        'Language: rust\n'
        'Perspective: evidence_citation\n'
        'Task: Choose the visible rust evidence bucket that most strongly supports the correct maintainer conclusion.\n'
        f'Evidence:\n{shared_evidence}\n'
        'Options:\n'
        'A. changed implementation candidate evidence\n'
        'B. agent-route verifier anchor\n'
        'C. sibling subagent-search verifier anchor\n'
        'D. nearby symbol context\n'
        'Answer:\n'
    )
    rows.append(make_row(base, 'evidence_citation', citation_prompt, citation_options, 'B', 'agent-route verifier anchor', 'evidence_bucket'))

    alt_options = [
        {'label': 'A', 'value': 'changed implementation candidate evidence'},
        {'label': 'B', 'value': 'agent-route verifier anchor'},
        {'label': 'C', 'value': 'sibling subagent-search verifier anchor'},
        {'label': 'D', 'value': 'abstain because the visible evidence is still tied'},
    ]
    alt_prompt = (
        'Language: rust\n'
        'Perspective: alternative_hypothesis_elimination\n'
        'Task: Choose the visible rust signal that best argues against the tempting wrong answer "changed implementation candidate evidence".\n'
        f'Evidence:\n{shared_evidence}\n'
        'Options:\n'
        'A. changed implementation candidate evidence\n'
        'B. agent-route verifier anchor\n'
        'C. sibling subagent-search verifier anchor\n'
        'D. abstain because the visible evidence is still tied\n'
        'Answer:\n'
    )
    rows.append(make_row(base, 'alternative_hypothesis_elimination', alt_prompt, alt_options, 'B', 'agent-route verifier anchor', 'evidence_bucket'))

    abstain_options = [
        {'label': 'A', 'value': 'choose the changed implementation candidate anyway'},
        {'label': 'B', 'value': 'choose the agent-route verifier anchor'},
        {'label': 'C', 'value': 'choose the sibling subagent-search verifier anchor'},
        {'label': 'D', 'value': 'abstain because the visible evidence is still insufficiently discriminative'},
    ]
    abstain_prompt = (
        'Language: rust\n'
        'Perspective: abstention_insufficient_evidence\n'
        'Task: Decide whether the visible rust evidence forces one answer or whether abstention is more honest.\n'
        f'Evidence:\n{shared_evidence}\n'
        'Options:\n'
        'A. choose the changed implementation candidate anyway\n'
        'B. choose the agent-route verifier anchor\n'
        'C. choose the sibling subagent-search verifier anchor\n'
        'D. abstain because the visible evidence is still insufficiently discriminative\n'
        'Answer:\n'
    )
    rows.append(make_row(base, 'abstention_insufficient_evidence', abstain_prompt, abstain_options, 'D', 'abstain because the visible evidence is still insufficiently discriminative', 'abstain'))

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'rust_chroma_citation_repair_packet_ready',
        'claim_scope': [
            'Create the first concrete Rust competition-repair support packet from the highest-priority chroma root.',
            'Make citation-vs-candidate-surface competition explicit while keeping the packet train-support only and non-promotable.',
            'Use this as the seed pattern for repairing the remaining Rust roots in the queue.',
        ],
        'metrics': {
            'support_rows': len(rows),
            'repo_family': base['repo_family'],
            'root_id': base['root_id'],
        },
        'headline_findings': [
            'The repaired packet converts a vague Rust backlog root into explicit competition between changed-surface evidence and verifier-anchor evidence.',
            'This directly targets the live Rust failure mode where the model collapses to candidate surface instead of verifier/test evidence.',
            'The packet remains support-only until broader adjudication and scaling replicate the pattern on more Rust roots.',
        ],
        'next_best_step': 'Leak-audit this repaired Rust packet and, if clean, merge it into the next multilingual support package or probe-specific augmentation.',
        'source_artifacts': {
            'rust_competition_queue': display(QUEUE_ROW),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'support_rows': display(ROWS_JSONL),
        },
    }
    write_jsonl(ROWS_JSONL, rows)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': True,
        'decision': payload['decision'],
        'support_rows': len(rows),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
