#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12281_semantic_review_packet_normalized_exact_verifiers'
INP=ROOT/'runs/local/artifacts/stage12280_external_normalized_verifier_identity_selector/normalized_exact_verifier_candidates.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
def iterj(p):
    with p.open('r',encoding='utf-8') as f:
        for l in f:
            l=l.strip()
            if l: yield json.loads(l)
def wj(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def wjl(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
packets=[]
for r in iterj(INP):
    packets.append({'schema_version':'normalized_exact_semantic_review_packet_v1','stage':STAGE,'candidate_id':r['candidate_id'],'source_refs':r['source_refs'],'root_recovery':r['root_recovery'],'patch_ref':r['patch_ref'],'matched_verifier_identity_digest':r['matched_verifier_identity_digest'],'pre_verifier_refs':r['pre_verifier_refs'],'post_verifier_refs':r['post_verifier_refs'],'deterministic_gates':r['deterministic_gates'],'review_questions':['Is selected patch semantically responsible for normalized exact verifier transition?','Is failure code-related rather than env/tooling?','Is normalized verifier identity strict enough for external comparable repair?','Any hidden post-failure or prior-patch attachment risk?'],'allowed_review_labels':['ADMIT_EXTERNAL_COMPARABLE_REPAIR','ADMIT_TRAIN_SUPPORT_ONLY','SPLIT_REQUIRED','QUARANTINE_SEMANTIC_MISMATCH','QUARANTINE_ENV_OR_TOOLING','QUARANTINE_INSUFFICIENT_EVIDENCE'],'guardrails':r['guardrails']})
summary={'stage':STAGE,'decision':'normalized_exact_review_packet_ready_no_admission','review_packet_count':len(packets),'repo_family_counts':dict(Counter((p['root_recovery'] or {}).get('repo_family_label') for p in packets)),'training_rows_emitted':0,'admitted_rows':0,'next_stage':'stage12282_normalized_exact_semantic_review_ingest'}
wjl(OUT/'normalized_exact_semantic_review_packets.jsonl',packets); wj(OUT/'normalized_exact_semantic_review_packet_summary.json',summary); wj(SUMMARY,summary); (OUT/'NORMALIZED_EXACT_REVIEW_PACKET_STAGE12281.md').write_text('# Stage12281 Normalized Exact Review Packet\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
