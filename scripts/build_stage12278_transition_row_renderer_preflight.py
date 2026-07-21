#!/usr/bin/env python3
"""Build Stage12278 transition row renderer preflight."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12278_transition_row_renderer_preflight'
INP=ROOT/'runs/local/artifacts/stage12276_semantic_review_result_ingest/train_support_only_repair_candidates.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'

def iter_jsonl(path: Path):
    with path.open('r',encoding='utf-8',errors='ignore') as f:
        for line in f:
            line=line.strip()
            if line: yield json.loads(line)

def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def write_jsonl(path: Path, rows: list[dict[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')

def main() -> int:
    rows=list(iter_jsonl(INP))
    groups=defaultdict(list)
    for r in rows:
        lin=r.get('lineage') or {}
        review=r.get('review') or {}
        key=(lin.get('root_lineage_key'), lin.get('split_group_id'), review.get('concise_reason_code'))
        groups[key].append(r)
    ready=[]; blocked=[]
    for key, items in groups.items():
        if len(items)>1:
            # Keep external rows if distinct by root metadata; block duplicate self/dev rows pending exact field proof.
            for r in items:
                repo=((r.get('root_recovery') or {}).get('repo_family_label'))
                if repo == 'agentkernel-seq2seq-text-lab':
                    r['preflight']={'render_allowed':False,'blocked_reason':'duplicate_self_research_group_requires_distinct_action_observation_delta_proof','dedupe_group_size':len(items)}
                    blocked.append(r)
                else:
                    r['preflight']={'render_allowed':True,'render_scope':'train_support_only_not_comparable','dedupe_group_size':len(items)}
                    ready.append(r)
        else:
            r=items[0]
            repo=((r.get('root_recovery') or {}).get('repo_family_label'))
            scope='dev_only_train_support' if repo == 'agentkernel-seq2seq-text-lab' else 'train_support_only_not_comparable'
            r['preflight']={'render_allowed':True,'render_scope':scope,'dedupe_group_size':1}
            ready.append(r)
    counts=Counter((r.get('root_recovery') or {}).get('repo_family_label') for r in ready)
    summary={
        'stage':STAGE,
        'decision':'renderer_preflight_complete_render_allowed_subset_only',
        'input_train_support_rows':len(rows),
        'render_allowed_rows':len(ready),
        'blocked_rows':len(blocked),
        'render_allowed_repo_counts':dict(counts),
        'blocked_reasons':dict(Counter((r.get('preflight') or {}).get('blocked_reason') for r in blocked)),
        'external_comparable_patch_trace_rows':0,
        'external_fail_to_pass_rows':0,
        'training_rows_emitted':0,
        'next_stage':'stage12279_transition_row_renderer_train_support_only',
        'render_requirements_inherited_from_stage12277':True,
    }
    write_jsonl(OUT/'render_allowed_train_support_candidates.jsonl', ready)
    write_jsonl(OUT/'preflight_blocked_candidates.jsonl', blocked)
    write_json(OUT/'transition_row_renderer_preflight_summary.json', summary)
    write_json(SUMMARY, summary)
    (OUT/'TRANSITION_ROW_RENDERER_PREFLIGHT_STAGE12278.md').write_text('# Stage12278 Transition Row Renderer Preflight\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return 0
if __name__=='__main__': raise SystemExit(main())
