#!/usr/bin/env python3
"""Derive admitted source-heldout C++ smoke rows from Stage11718 after Stage11719."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_smoke_rows.jsonl'
AUDIT = ROOT / 'runs/local/artifacts/stage11719_sentencepiece_cpp_no_train_overlap_audit/sentencepiece_cpp_no_train_overlap_audit.json'
OUT_DIR = ROOT / 'runs/local/artifacts/stage11720_sentencepiece_cpp_admitted_smoke_packet'
SUMMARY = ROOT / 'runs/summaries/stage11720_sentencepiece_cpp_admitted_smoke_packet.json'


def main() -> None:
    audit=json.load(open(AUDIT))
    if not audit.get('passed'):
        raise SystemExit('Stage11719 did not pass; refusing admission')
    rows=[json.loads(l) for l in open(ROWS) if l.strip()]
    OUT_DIR.mkdir(parents=True, exist_ok=True); SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    admitted=[]
    for r in rows:
        rr=dict(r)
        rr['row_id']=rr['row_id'].replace('::candidate_v1','::admitted_source_heldout_v1')
        rr['split']='strict_eval'
        rr['split_role']='strict_source_heldout_smoke'
        rr['strict_eval_eligible']=True
        rr['source_heldout_admissible']=True
        rr['source_heldout_attestation']='stage11719_pass_no_exact_new_root_train_overlap'
        rr['admission_stage']=11720
        rr['admission_evidence']={
            'no_train_overlap_audit': 'runs/local/artifacts/stage11719_sentencepiece_cpp_no_train_overlap_audit/sentencepiece_cpp_no_train_overlap_audit.json',
            'source_packet': 'runs/local/artifacts/stage11718_sentencepiece_cpp_source_heldout_smoke_packet/sentencepiece_cpp_source_heldout_smoke_packet.json',
        }
        rr['anti_cheat']=dict(rr.get('anti_cheat') or {})
        rr['anti_cheat']['source_heldout_admitted_after_no_train_overlap_audit']=True
        rr['anti_cheat']['requires_no_train_overlap_audit']=False
        admitted.append(rr)
    artifact={
        'stage':11720,
        'stage_name':'sentencepiece_cpp_admitted_smoke_packet',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'decision':'sentencepiece_cpp_source_heldout_smoke_admitted',
        'passed':True,
        'language_family':'c_cpp',
        'repo_family':'sentencepiece',
        'root_id':admitted[0]['root_id'] if admitted else None,
        'row_count':len(admitted),
        'task_types':sorted({r['task_type'] for r in admitted}),
        'admission_basis':audit['decision'],
        'remaining_limitations':[
            'Verifier transition is still a static selected-test anchor, not executed fail/pass.',
            'Repo-family/source-path broad warning scan was deferred; exact new root/snapshot train overlap passed.',
            'Rows support source-heldout compact smoke, not full-product patch repair.'
        ],
        'next_stage_acceptance':[
            'run 100M selected product scorer on these 4 rows',
            'run Gemma same-manifest on these 4 rows',
            'run option permutation audit',
            'extend with executable verifier/harness rows before full-product claim'
        ],
        'outputs':{
            'artifact':'runs/local/artifacts/stage11720_sentencepiece_cpp_admitted_smoke_packet/sentencepiece_cpp_admitted_smoke_packet.json',
            'rows_jsonl':'runs/local/artifacts/stage11720_sentencepiece_cpp_admitted_smoke_packet/sentencepiece_cpp_admitted_smoke_rows.jsonl',
            'summary':'runs/summaries/stage11720_sentencepiece_cpp_admitted_smoke_packet.json'
        }
    }
    (OUT_DIR/'sentencepiece_cpp_admitted_smoke_packet.json').write_text(json.dumps(artifact,indent=2,sort_keys=True)+'\n')
    with (OUT_DIR/'sentencepiece_cpp_admitted_smoke_rows.jsonl').open('w') as fh:
        for r in admitted: fh.write(json.dumps(r,sort_keys=True)+'\n')
    shutil.copyfile(OUT_DIR/'sentencepiece_cpp_admitted_smoke_packet.json', SUMMARY)
    print(json.dumps({'artifact':str(OUT_DIR/'sentencepiece_cpp_admitted_smoke_packet.json'),'summary':str(SUMMARY),'rows':len(admitted)},indent=2))

if __name__=='__main__': main()
