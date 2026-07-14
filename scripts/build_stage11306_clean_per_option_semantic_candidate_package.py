#!/usr/bin/env python3
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'runs/local/artifacts'
STAGE=11306
NAME='stage11306_clean_per_option_semantic_candidate_package'
OUT_DIR=ARTIFACTS/NAME
SRC=ARTIFACTS/'stage11305_per_option_semantic_candidate_schema_package'
SUMMARY=OUT_DIR/'clean_per_option_semantic_candidate_package.json'

IN={
 'train': SRC/'semantic_candidate_schema_train_rows.jsonl',
 'validation': SRC/'semantic_candidate_schema_validation_rows.jsonl',
 'strict': SRC/'semantic_candidate_schema_strict_rows.jsonl',
 'judgment_validation': SRC/'semantic_candidate_schema_judgment_validation_rows.jsonl',
 'judgment_strict': SRC/'semantic_candidate_schema_judgment_strict_rows.jsonl',
 'residual': SRC/'semantic_candidate_schema_residual_rows.jsonl',
}
OUT={k:OUT_DIR/f'clean_per_option_semantic_candidate_{k}_rows.jsonl' for k in IN}

def rel(p:Path)->str: return str(p.relative_to(ROOT))
def now()->str: return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def load(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_jsonl(p:Path, rows:list[dict[str,Any]]):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
def write_json(p:Path,o:Any): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(o, indent=2, sort_keys=True)+'\n')
def root(row): return str(row.get('root_id') or row.get('source_root_id') or row.get('root_lineage_key') or row.get('row_id') or '')
def target_label(row):
    t=row.get('target') if isinstance(row.get('target'),dict) else {}
    for v in [t.get('bounded_choice_target_label'), row.get('bounded_choice_target_label'), t.get('target_text'), row.get('target_text'), row.get('decoder_text')]:
        if isinstance(v,str) and v.strip(): return v.strip()
    return ''
def options(row): return ((row.get('standalone_projection_source') or {}).get('opaque_options') or [])
def admitted(row):
    opts=options(row); label=target_label(row)
    return len(opts)>1 and bool(label) and any(str(o.get('label') or '').strip()==label for o in opts if isinstance(o,dict)) and all(isinstance((o.get('semantic_candidate') if isinstance(o,dict) else None),dict) for o in opts)
def counts(rows):
    return {'rows':len(rows),'roots':len({root(r) for r in rows}),'by_language':dict(sorted(Counter(str(r.get('language_family') or 'unknown') for r in rows).items())),'by_task':dict(sorted(Counter(str(r.get('task_type') or 'unknown') for r in rows).items()))}

def main():
    rows={k:load(p) for k,p in IN.items()}
    protected_roots={root(r) for k in ['validation','strict','judgment_validation','judgment_strict','residual'] for r in rows[k]}
    blocked_train=[]; overlap_train=[]; clean_train=[]
    for r in rows['train']:
        if not admitted(r):
            blocked_train.append(r); continue
        if root(r) in protected_roots:
            overlap_train.append(r); continue
        clean_train.append(r)
    cleaned={
        'train': clean_train,
        'validation': rows['validation'],
        'strict': rows['strict'],
        'judgment_validation': rows['judgment_validation'],
        'judgment_strict': rows['judgment_strict'],
        'residual': rows['residual'],
    }
    for k,v in cleaned.items(): write_jsonl(OUT[k], v)
    train_roots={root(r) for r in clean_train}
    protected_overlap=sorted(train_roots & protected_roots)
    summary={
      'stage':STAGE,'stage_name':NAME,'created_at_utc':now(),'passed':not protected_overlap and all(admitted(r) for r in clean_train),
      'decision':'clean_per_option_semantic_candidate_package_built',
      'source_stage':'stage11305_per_option_semantic_candidate_schema_package',
      'counts':{k:counts(v) for k,v in cleaned.items()},
      'audit':{
        'input_train_rows':len(rows['train']),'clean_train_rows':len(clean_train),'blocked_non_admitted_train_rows':len(blocked_train),'excluded_overlap_train_rows':len(overlap_train),
        'protected_root_overlap_count':len(protected_overlap),'protected_root_overlaps':protected_overlap[:50],
        'blocked_train_examples':[r.get('row_id') for r in blocked_train[:20]],
        'overlap_train_examples':[r.get('row_id') for r in overlap_train[:20]],
        'all_train_rows_have_per_option_metadata':all(admitted(r) for r in clean_train),
      },
      'source_artifacts':{k:rel(v) for k,v in IN.items()},'outputs':{k:rel(v) for k,v in OUT.items()},
      'next_action':{'recommended_stage':'stage11307_clean_per_option_semantic_candidate_probe_request','promotion_gates':['clean strict remains 22/22','clean validation >=20/23','residual >5/10','verifier_and_test_constraint residual >0/3']}
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
if __name__=='__main__': main()
