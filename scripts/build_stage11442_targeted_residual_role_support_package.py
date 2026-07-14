#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs/local/artifacts'
SUMMARIES = ROOT / 'runs/summaries'
STAGE = 11442
NAME = 'stage11442_targeted_residual_role_support_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'targeted_residual_role_support_package.json'

BASE = ARTIFACTS / 'stage11438_root_purged_semantic_candidate_package'
BASE_TRAIN = BASE / 'agentkernel_lite_encdec_train.jsonl'
BASE_VAL = BASE / 'agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT = BASE / 'agentkernel_lite_encdec_strict_eval.jsonl'
BASE_RESIDUAL = BASE / 'semantic_candidate_residual_bank.jsonl'
BASE_QUAR = BASE / 'semantic_candidate_quarantined_rows.jsonl'
SOURCES = {
    'fact_rich_verifier_train': ARTIFACTS / 'stage11296_capped_fact_rich_verifier_package/capped_fact_rich_verifier_train_rows.jsonl',
    'alias_free_evidence_train': ARTIFACTS / 'stage11326_alias_free_evidence_item_selection_scale_package/alias_free_evidence_item_selection_scale_train_rows.jsonl',
    'rust_verifier_support': ARTIFACTS / 'stage11429_selected_test_rust_support_package/added_selected_test_rust_support_rows.jsonl',
}
OUTPUTS = {
    'train': OUT_DIR / 'agentkernel_lite_encdec_train.jsonl',
    'validation': OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl',
    'strict_eval': OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl',
    'residual_bank': OUT_DIR / 'semantic_candidate_residual_bank.jsonl',
    'added_support': OUT_DIR / 'targeted_residual_role_added_support.jsonl',
    'candidate_audit': OUT_DIR / 'targeted_residual_role_candidate_audit.jsonl',
    'quarantine': OUT_DIR / 'targeted_residual_role_quarantine.jsonl',
}

EVIDENCE_ROLES = {
    'candidate_change_surface', 'verifier_and_test_constraint', 'symptom_or_call_path_analogue',
    'nearby_definition_or_usage_context', 'external_analogue_reference', 'algorithmic_background_reference', 'background_context'
}
ROLE_TARGETS = {'verifier_and_test_constraint', 'symptom_or_call_path_analogue', 'candidate_change_surface'}
TARGET_MIN = {
    ('python', 'verifier_and_test_constraint'): 24,
    ('c_cpp', 'verifier_and_test_constraint'): 24,
    ('rust', 'symptom_or_call_path_analogue'): 16,
    ('rust', 'candidate_change_surface'): 8,
}
MAX_PER_REPO_ROLE = 20
MAX_PER_ROOT = 4


def now_utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p: Path): return str(p.relative_to(ROOT))
def load_jsonl(p: Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_json(p: Path, obj: Any): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')
def write_jsonl(p: Path, rows: list[dict[str, Any]]): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))

def root_key(r: dict[str, Any]) -> str:
    for k in ('root_id','source_root_id','root_lineage_key','source_bundle_id'):
        v=r.get(k)
        if isinstance(v,str) and v.strip(): return v.strip()
    return str(r.get('row_id') or '')

def task_type(r): return str(r.get('task_type') or r.get('perspective') or 'unknown')
def lang(r): return str(r.get('language_family') or r.get('language') or 'unknown')
def repo(r): return str(r.get('repo_family') or r.get('repo_id') or 'unknown')
def opts(r): return [o for o in ((r.get('standalone_projection_source') or {}).get('opaque_options') or []) if isinstance(o,dict)]

def target_label(r):
    t=r.get('target') if isinstance(r.get('target'),dict) else {}
    for v in (r.get('bounded_choice_target_label'), t.get('bounded_choice_target_label'), r.get('target_text'), t.get('target_text'), r.get('decoder_text')):
        if isinstance(v,str) and v.strip(): return v.strip()
    return ''

def option_value_for_label(r, label):
    for o in opts(r):
        if str(o.get('label') or '').strip()==label:
            return str(o.get('value') or '').strip()
    return ''

def role_key(value: str) -> str:
    raw=str(value or '').strip()
    prefix=raw.split('|',1)[0].strip()
    if prefix in EVIDENCE_ROLES: return prefix
    low=re.sub(r'[_\-]+',' ', raw.lower())
    if 'verifier' in low or 'selected test' in low or 'test constraint' in low or '/tests/' in low or 'tests/' in low:
        return 'verifier_and_test_constraint'
    if 'symptom' in low or 'call path' in low or 'trace' in low:
        return 'symptom_or_call_path_analogue'
    if 'candidate' in low or 'changed' in low or 'source path' in low:
        return 'candidate_change_surface'
    return 'candidate_value_surface'

def target_role(r):
    existing=str(r.get('semantic_target_value') or '').strip()
    if existing in EVIDENCE_ROLES or existing in ROLE_TARGETS: return existing
    return role_key(option_value_for_label(r, target_label(r)))

def transition(value: str) -> str:
    up=str(value).upper()
    for tr in ('FAIL_TO_PASS','PASS_TO_PASS','FAIL_TO_FAIL','NOT_EXERCISED','INSUFFICIENT_EVIDENCE','NEEDS_VERIFIER'):
        if tr in up: return tr
    return 'NONE'

def add_semantic(r: dict[str, Any]) -> dict[str, Any]:
    out=dict(r)
    sps=dict(out.get('standalone_projection_source') or {})
    new=[]
    for i,o in enumerate(opts(out)):
        no=dict(o)
        value=str(no.get('value') or no.get('label') or '')
        sem=dict(no.get('semantic_candidate') or {})
        role=str(sem.get('evidence_role') or role_key(value))
        tr=str(sem.get('verifier_transition') or transition(value))
        sem.update({
            'schema_version': 'stage11442_targeted_residual_role_support_v1',
            'option_index': i,
            'candidate_label': str(no.get('label') or '').strip(),
            'candidate_value_family': 'verifier_transition' if tr!='NONE' else ('evidence_role_or_item' if role in EVIDENCE_ROLES else 'generic_candidate'),
            'task_type': task_type(out),
            'evidence_role': role,
            'verifier_transition': tr,
            'test_id': str(sem.get('test_id') or ''),
            'value_token_count_proxy': len(value.replace('|',' ').split()),
        })
        no['semantic_candidate']=sem
        new.append(no)
    sps['opaque_options']=new
    sps['option_semantic_schema_version']='stage11442_targeted_residual_role_support_v1'
    sps['option_semantic_records']=[o.get('semantic_candidate') for o in new]
    out['standalone_projection_source']=sps
    out['semantic_candidate_schema_version']='stage11442_targeted_residual_role_support_v1'
    out['stage11442_source_row_id']=r.get('row_id')
    return out

def admissible(r):
    label=target_label(r)
    os=opts(r)
    if task_type(r)!='evidence_citation': return False, 'not_evidence_citation'
    if len(os)<=1: return False, 'singleton_or_missing_options'
    if not label or label not in {str(o.get('label') or '').strip() for o in os}: return False, 'target_not_in_options'
    roles={role_key(str(o.get('value') or '')) for o in os}
    if target_role(r) not in ROLE_TARGETS: return False, 'target_role_not_needed'
    if len(roles & ROLE_TARGETS) < 2: return False, 'not_role_contrastive'
    return True, ''

def count(rows):
    return {
        'rows': len(rows),
        'roots': len({root_key(r) for r in rows}),
        'by_language': dict(sorted(Counter(lang(r) for r in rows).items())),
        'by_task': dict(sorted(Counter(task_type(r) for r in rows).items())),
        'by_target_role': dict(sorted(Counter(target_role(r) for r in rows).items())),
        'by_language_target_role': dict(sorted(Counter(f'{lang(r)}::{target_role(r)}' for r in rows).items())),
    }

def main():
    base_train=load_jsonl(BASE_TRAIN); val=load_jsonl(BASE_VAL); strict=load_jsonl(BASE_STRICT); residual=load_jsonl(BASE_RESIDUAL); base_quar=load_jsonl(BASE_QUAR)
    protected_roots={root_key(r) for r in val+strict+residual}
    existing_ids={str(r.get('row_id')) for r in base_train+val+strict+residual}
    existing_roots=Counter(root_key(r) for r in base_train)
    source_rows=[]
    source_name_by_id={}
    for name,path in SOURCES.items():
        for r in load_jsonl(path):
            source_rows.append(r); source_name_by_id[str(r.get('row_id'))]=name
    audit=[]; admitted=[]; quarantined=[]
    selected_by_repo_role=Counter(); selected_by_root=Counter(); selected_by_lang_role=Counter()
    for r in source_rows:
        ok, reason=admissible(r)
        tr=target_role(r); lr=(lang(r),tr); rr=(repo(r),tr)
        reasons=[]
        if not ok: reasons.append(reason)
        if root_key(r) in protected_roots: reasons.append('protected_root_overlap')
        if str(r.get('row_id')) in existing_ids: reasons.append('duplicate_row_id')
        if selected_by_repo_role[rr] >= MAX_PER_REPO_ROLE: reasons.append('repo_role_cap')
        if selected_by_root[root_key(r)] >= MAX_PER_ROOT: reasons.append('root_cap')
        if lr not in TARGET_MIN: reasons.append('not_targeted_language_role')
        if selected_by_lang_role[lr] >= TARGET_MIN.get(lr,0): reasons.append('language_role_target_filled')
        row_audit={'row_id':r.get('row_id'), 'source':source_name_by_id.get(str(r.get('row_id'))), 'language_family':lang(r), 'repo_family':repo(r), 'root_id':root_key(r), 'task_type':task_type(r), 'target_role':tr, 'blockers':reasons}
        audit.append(row_audit)
        if reasons:
            q=dict(r); q['stage11442_quarantine_reasons']=reasons; quarantined.append(q); continue
        nr=add_semantic(r)
        nr['row_id']=f"stage11442::{source_name_by_id.get(str(r.get('row_id')), 'source')}::{r.get('row_id')}"
        nr['stage11442_added_support']=True
        admitted.append(nr)
        existing_ids.add(str(nr.get('row_id')))
        selected_by_repo_role[rr]+=1; selected_by_root[root_key(r)]+=1; selected_by_lang_role[lr]+=1
    final_train=base_train+admitted
    # Hard audit root split after addition.
    overlaps=sorted({root_key(r) for r in final_train} & protected_roots)
    if overlaps:
        raise SystemExit(f'protected root overlap after selection: {overlaps[:10]}')
    write_jsonl(OUTPUTS['train'], final_train); write_jsonl(OUTPUTS['validation'], val); write_jsonl(OUTPUTS['strict_eval'], strict); write_jsonl(OUTPUTS['residual_bank'], residual)
    write_jsonl(OUTPUTS['added_support'], admitted); write_jsonl(OUTPUTS['candidate_audit'], audit); write_jsonl(OUTPUTS['quarantine'], base_quar+quarantined)
    summary={
        'stage': STAGE, 'stage_name': NAME, 'created_at_utc': now_utc(), 'passed': True,
        'decision': 'targeted_residual_role_support_package_ready_for_diagnostic_probe' if admitted else 'no_admitted_targeted_support_rows',
        'claim_scope': 'train-support package only; validation/strict/residual unchanged from root-purged semantic candidate package',
        'source_artifacts': {'base_train': rel(BASE_TRAIN), 'base_validation': rel(BASE_VAL), 'base_strict': rel(BASE_STRICT), 'base_residual': rel(BASE_RESIDUAL), **{k:rel(v) for k,v in SOURCES.items()}},
        'outputs': {k:rel(v) for k,v in OUTPUTS.items()},
        'counts': {'base_train': count(base_train), 'added_support': count(admitted), 'final_train': count(final_train), 'validation': count(val), 'strict_eval': count(strict), 'residual': count(residual), 'quarantined_candidates': count(quarantined)},
        'selection_targets': {f'{k[0]}::{k[1]}':v for k,v in TARGET_MIN.items()},
        'selected_by_language_target_role': dict(sorted((f'{k[0]}::{k[1]}',v) for k,v in selected_by_lang_role.items())),
        'candidate_blockers': dict(sorted(Counter(b for a in audit for b in a['blockers']).items())),
        'gates': {'added_support_nonempty': bool(admitted), 'root_split_clean': not overlaps, 'validation_unchanged_rows': len(val), 'strict_unchanged_rows': len(strict), 'residual_unchanged_rows': len(residual)},
        'recommended_next_action': 'run one diagnostic probe with semantic_candidate_head from Stage11440 init, then require residual >5/10 and filtered strict/eval no regression before promotion',
    }
    write_json(SUMMARY_JSON, summary); SUMMARIES.mkdir(parents=True, exist_ok=True); shutil.copyfile(SUMMARY_JSON, SUMMARIES/f'{NAME}.json')
    print(json.dumps({'decision':summary['decision'], 'counts':summary['counts']['added_support'], 'selected_by_language_target_role':summary['selected_by_language_target_role'], 'gates':summary['gates']}, indent=2, sort_keys=True))
if __name__=='__main__': main()
