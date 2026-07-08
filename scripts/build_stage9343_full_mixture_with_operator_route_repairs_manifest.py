#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, time
from pathlib import Path
from typing import Any
try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]
STAGE=9343
NAME='stage9343_full_mixture_with_operator_route_repairs_manifest'
SOURCE_SUMMARY=ROOT/'runs/summaries/stage9342_operator_route_probe_audit.json'
BASE=ROOT/'runs/local/artifacts/stage9331_routed_ladder_suffix_manifest/routed_ladder_suffix_manifest.jsonl'
REPAIR=ROOT/'runs/local/artifacts/stage9340_operator_route_separation_manifest/operator_route_separation_manifest.jsonl'
OUT_DIR=ROOT/'runs/local/artifacts'/NAME
MANIFEST=OUT_DIR/'full_mixture_with_operator_route_repairs_manifest.jsonl'
AUDIT=OUT_DIR/'full_mixture_with_operator_route_repairs_manifest_audit.json'
SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'
DOC=ROOT/'docs/FULL_MIXTURE_WITH_OPERATOR_ROUTE_REPAIRS_MANIFEST_STAGE9343.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'

def load_json(p:Path)->dict[str,Any]: return json.loads(p.read_text()) if p.exists() else {}
def load_jsonl(p:Path)->list[dict[str,Any]]: return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_jsonl(p:Path, rows:list[dict[str,Any]])->None: p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ''

def remap(kind:str,row:dict[str,Any])->dict[str,Any]:
    new=json.loads(json.dumps(row))
    new['row_id']=f'stage9343_{kind}_{row["row_id"]}'
    new['source_row_id']=row['row_id']
    new['source_stage']=9331 if kind=='base' else 9340
    new['merged_curriculum_source']=kind
    new['objective_family']='full_mixture_with_operator_route_repairs_denoise'
    new['authority']=dict(AUTHORITY_CLOSED)
    new['loss_mask']={'decoder_ce':False,'structured_aux':False,'denoise_ce':True,'runtime_reward':False}
    mi=new.get('model_input') if isinstance(new.get('model_input'),dict) else {}
    mi['merged_curriculum_source']=kind
    mi['operator_route_rejoin_probe']=True
    new['model_input']=mi
    ac=new.get('anti_cheat') if isinstance(new.get('anti_cheat'),dict) else {}
    ac.update({'decoder_ce_closed':True,'runtime_closed':True,'operator_route_rejoin_probe':True})
    new['anti_cheat']=ac
    return new

def build_rows()->list[dict[str,Any]]:
    return [remap('base',r) for r in load_jsonl(BASE)] + [remap('operator_route_repair',r) for r in load_jsonl(REPAIR)]

def audit_rows(rows:list[dict[str,Any]])->dict[str,Any]:
    source=load_json(SOURCE_SUMMARY); failures=[]; split={}; src={}; tasks={}; routes={}; unsafe=[]
    for r in rows:
        split[str(r.get('split'))]=split.get(str(r.get('split')),0)+1
        src[str(r.get('merged_curriculum_source'))]=src.get(str(r.get('merged_curriculum_source')),0)+1
        tasks[str(r.get('repair_task_type'))]=tasks.get(str(r.get('repair_task_type')),0)+1
        mi=r.get('model_input') if isinstance(r.get('model_input'),dict) else {}
        routes[str(mi.get('opaque_phrase_route_id'))]=routes.get(str(mi.get('opaque_phrase_route_id')),0)+1
        loss=r.get('loss_mask') if isinstance(r.get('loss_mask'),dict) else {}
        auth=r.get('authority') if isinstance(r.get('authority'),dict) else {}
        if loss.get('decoder_ce') or loss.get('structured_aux') or loss.get('runtime_reward') or not loss.get('denoise_ce'): unsafe.append(str(r.get('row_id')))
        if any(bool(auth.get(k)) for k in AUTHORITY_CLOSED): unsafe.append(str(r.get('row_id')))
    if source.get('passed') is not True: failures.append('source_stage9342_not_passed')
    if len(rows)!=74: failures.append('unexpected_row_count')
    if split!={'train':40,'eval':19,'strict_eval':15}: failures.append('unexpected_split_counts')
    if src!={'base':56,'operator_route_repair':18}: failures.append('unexpected_source_counts')
    if not {'operator_route_separated_repair','repair_file_path_associated_with'}.issubset(tasks): failures.append('missing_operator_route_tasks')
    if routes.get('route_1',0)<24 or routes.get('route_file_path',0)!=2: failures.append('unexpected_route_counts')
    if unsafe: failures.append('unsafe_rows')
    return {'passed':not failures,'failures':failures,'rows':len(rows),'split_counts':split,'source_counts':src,'task_counts':tasks,'route_counts':routes,'unsafe_rows':unsafe[:20],'manifest_sha256':sha(MANIFEST),'authority':dict(AUTHORITY_CLOSED)}

def update_registry(summary:dict[str,Any])->None:
    reg=load_json(REGISTRY) or {'rows':[],'metrics':{}}
    rows=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
    rows.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']})
    rows=sorted(rows,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
    reg['rows']=rows; reg['passed']=summary['passed']
    reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(rows),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')

def main()->None:
    OUT_DIR.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
    rows=build_rows(); write_jsonl(MANIFEST,rows)
    audit=audit_rows(rows); audit['manifest_sha256']=sha(MANIFEST); AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    summary={'stage':STAGE,'stage_name':NAME,'name':NAME,'passed':audit['passed'],'authority':dict(AUTHORITY_CLOSED),'metrics':{**dict(AUTHORITY_CLOSED),**audit},'artifacts':{'manifest':str(MANIFEST.relative_to(ROOT)),'audit':str(AUDIT.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'decision':'Merged Stage9331 routed ladder rows with Stage9340 operator-route repair rows for controlled rejoin.','next_best_step':'Build Stage9344 preexecution and run a 74-row operator-route rejoin interference probe before reopening bounded decoder CE.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    DOC.write_text('\n'.join(['# Stage9343 Full Mixture With Operator Route Repairs Manifest','',f"Passed: `{audit['passed']}`",f"Rows: `{audit['rows']}`",f"Splits: `{audit['split_counts']}`",f"Sources: `{audit['source_counts']}`",f"Routes: `{audit['route_counts']}`",'This rejoins operator-route repairs after Stage9342 passed in isolation. Decoder CE and external authority remain closed.','']))
    update_registry(summary)
    print(json.dumps({'stage':STAGE,'passed':summary['passed'],'metrics':{'rows':audit['rows'],'split_counts':audit['split_counts'],'source_counts':audit['source_counts'],'route_counts':audit['route_counts'],'failures':audit['failures']}},indent=2,sort_keys=True))
if __name__=='__main__': main()
