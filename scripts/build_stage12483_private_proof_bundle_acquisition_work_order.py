#!/usr/bin/env python3
"""Private proof-bundle acquisition work order for Stage12468 returns."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12483_private_proof_bundle_acquisition_work_order"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12478 = "stage12478_private_return_fill_packet"
STAGE12481 = "stage12481_private_return_materialization_attempt"
STAGE12482 = "stage12482_external_repair_proof_source_suitability_audit"

VALIDATOR_CONTRACT_IN = ROOT / "runs/local/artifacts" / STAGE12468 / "validator_contract.json"
FILL_PACKET_IN = ROOT / "runs/local/artifacts" / STAGE12478 / "private_return_fill_packet_items_ref.jsonl"
BLOCKERS_IN = ROOT / "runs/local/artifacts" / STAGE12481 / "private_return_materialization_blockers_ref.jsonl"
STAGE12478_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12478}.json"
STAGE12481_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12481}.json"
STAGE12482_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12482}.json"

WORK_ORDER_OUT = OUT_DIR / "private_proof_bundle_work_items_ref.jsonl"
WORK_ORDER_SHARDS_DIR = OUT_DIR / "shards"
SLOT_INVENTORY_OUT = OUT_DIR / "required_proof_bundle_slot_inventory.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
FALSE_GUARDS = {"training_allowed": False, "admission_allowed": False, "packaging_allowed": False, "execution_performed_by_stage": False, "hydration_performed_by_stage": False, "replay_performed_by_stage": False, "network_performed_by_stage": False}
ZERO_GUARDS = {"external_comparable_repair_credit_count": 0, "emitted_training_rows": 0, "sealed_eval_rows": 0}
EXPLICIT_PRESENT_SLOTS = ["before_verifier_status_fail", "before_status_fail", "after_or_before_plus_patch_verifier_status_pass", "after_or_before_plus_patch_status_pass", "anti_leak_public_rendering_pass", "protected_overlap_audit_pass"]
MISSING_PROOF_CATEGORIES = ["before_fail_verifier_output", "after_or_before_plus_patch_pass_verifier_output", "patch_diff_and_apply_result", "same_source_and_same_verifier_identity", "verifier_relevance", "ordered_patch_before_pass_causality", "state_before_after_semantic_codes", "candidate_action_set", "stop_continue_label", "anti_leak_and_protected_overlap_evidence"]
FORBIDDEN_PUBLIC_KEYS = {"body","cmd","command","commands","commit","commit_sha","content","diff","file_content","file_path","patch","patch_body","path","paths","raw","raw_content","raw_text","repo","repo_id","repo_name","repository","sha","source","source_text","stderr","stdout","text","uri","uris","url","urls"}
PUBLIC_SAFE_KEY_RE = re.compile(r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|locator|candidate|context|label|input|excluded|request|contract|pending|file|work|order|bundle|inventory|category|credit|authority|shard)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|stdout|stderr|traceback|terminal output|command output)\\b|\\b[0-9a-f]{40}\\b|\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b", re.I|re.M)

def stable_hash(v: Any, n:int=24)->str:
    return hashlib.sha256((STAGE+":"+json.dumps(v, sort_keys=True, separators=(",",":"), default=str)).encode()).hexdigest()[:n]
def file_hash(p:Path,n:int=24)->str:
    if not p.exists() or not p.is_file(): return "missing"
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()[:n]
def read_json(p:Path)->tuple[dict[str,Any],Counter[str]]:
    issues=Counter()
    if not p.exists(): issues[f"{p.name}_missing"]+=1; return {},issues
    try: v=json.loads(p.read_text())
    except Exception: issues[f"{p.name}_invalid_json"]+=1; return {},issues
    if not isinstance(v,dict): issues[f"{p.name}_not_object"]+=1; return {},issues
    return v,issues
def read_jsonl(p:Path)->tuple[list[dict[str,Any]],Counter[str]]:
    rows=[]; issues=Counter()
    if not p.exists(): issues[f"{p.name}_missing"]+=1; return rows,issues
    for i,l in enumerate(p.open(),1):
        if not l.strip(): continue
        try: v=json.loads(l)
        except Exception: issues['input_jsonl_invalid_json']+=1; continue
        if not isinstance(v,dict): issues['input_jsonl_row_not_object']+=1; continue
        v['_stage12483_input_line_index']=i; rows.append(v)
    return rows,issues
def write_json(p:Path,v:Any)->None:
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v, indent=2, sort_keys=True)+"\n")
def write_jsonl(p:Path, rows:list[dict[str,Any]])->None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w') as f:
        for r in rows: f.write(json.dumps(r, sort_keys=True)+"\n")
def public_scan(label:str,v:Any)->list[str]:
    out=[]; leaf=label.rsplit('.',1)[-1].split('[',1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label): out.append(f"{label}:forbidden_public_key")
    if isinstance(v,str) and RAW_LEAK_RE.search(v): out.append(f"{label}:raw_content_pattern:{stable_hash(v)}")
    elif isinstance(v,dict):
        for k,c in v.items(): out.extend(public_scan(f"{label}.{k}",c))
    elif isinstance(v,list):
        for i,c in enumerate(v): out.extend(public_scan(f"{label}[{i}]",c))
    return out

def work_item(fill:dict[str,Any], blocker_by_fill:dict[str,dict[str,Any]], required_slots:list[str], lane_slots_by_ref:dict[str,Any])->dict[str,Any]:
    blocker=blocker_by_fill.get(fill.get('fill_packet_item_ref_hash'), {})
    lane_hash=fill.get('lane_ref_hash')
    return {"record_type":"stage12483_private_proof_bundle_work_item_ref_hash_only_v1", "proof_bundle_work_item_ref_hash":stable_hash({"fill":fill.get('fill_packet_item_ref_hash'),"proof":fill.get('proof_request_ref_hash')}), "fill_packet_item_ref_hash":fill.get('fill_packet_item_ref_hash'), "work_order_item_ref_hash":fill.get('work_order_item_ref_hash'), "proof_request_ref_hash":fill.get('proof_request_ref_hash'), "proof_request_id_hash":fill.get('proof_request_id_hash'), "lane_ref_hash":lane_hash, "language_family_label_hash":fill.get('language_family_label_hash'), "locator_bundle_ref_hash":fill.get('locator_bundle_ref_hash'), "target_validator_stage":STAGE12468, "required_common_proof_slots_ref_hash":stable_hash(required_slots), "required_explicit_present_slots_ref_hash":stable_hash(EXPLICIT_PRESENT_SLOTS), "missing_proof_categories_ref_hash":stable_hash(MISSING_PROOF_CATEGORIES), "stage12481_missing_required_proof_slot_count":blocker.get('missing_required_proof_slot_count'), "executor_must_acquire_real_private_evidence":True, "locator_only_bundle_rejected":True, "public_return_policy":"hash_status_only_no_raw_evidence", "expected_after_private_completion":"stage12468_compatible_private_return_row_candidate", **FALSE_GUARDS, **ZERO_GUARDS, "remaining_external_fail_to_pass_gap":EXPECTED_GAP}

def main()->int:
    contract,ci=read_json(VALIDATOR_CONTRACT_IN); fills,fi=read_jsonl(FILL_PACKET_IN); blockers,bi=read_jsonl(BLOCKERS_IN); s78,s78i=read_json(STAGE12478_SUMMARY); s81,s81i=read_json(STAGE12481_SUMMARY); s82,s82i=read_json(STAGE12482_SUMMARY)
    stage_blockers=[]
    for prefix,issues in [('contract',ci),('fills',fi),('blockers',bi),('s78',s78i),('s81',s81i),('s82',s82i)]: stage_blockers += [f"{prefix}_{k}" for k in issues]
    if contract.get('stage')!=STAGE12468: stage_blockers.append('stage12468_contract_unexpected_stage')
    if contract.get('required_status_family')!=EXPECTED_STATUS_FAMILY: stage_blockers.append('stage12468_status_family_mismatch')
    if s78.get('fill_packet_item_count')!=len(fills): stage_blockers.append('stage12478_fill_count_mismatch')
    if s81.get('materialization_blocker_count')!=len(blockers): stage_blockers.append('stage12481_blocker_count_mismatch')
    if s81.get('validator_complete_return_candidate_count')!=0: stage_blockers.append('stage12481_has_complete_returns_unexpected')
    if s82.get('external_repair_return_suitable_source_count')!=0: stage_blockers.append('stage12482_suitable_source_count_unexpected')
    for s in [s78,s81,s82]:
        if s.get('guardrail_scan_passed') is not True: stage_blockers.append(f"{s.get('stage','unknown')}_guardrail_not_passed")
        if s.get('raw_leak_count')!=0: stage_blockers.append(f"{s.get('stage','unknown')}_raw_leak_count_not_zero")
    required_slots=contract.get('required_proof_slots') if isinstance(contract.get('required_proof_slots'),list) else []
    lane_slots=contract.get('lane_specific_required_proof_slots') if isinstance(contract.get('lane_specific_required_proof_slots'),dict) else {}
    blocker_by_fill={r.get('fill_packet_item_ref_hash'):r for r in blockers if isinstance(r.get('fill_packet_item_ref_hash'),str)}
    items=[] if stage_blockers else [work_item(f, blocker_by_fill, required_slots, lane_slots) for f in fills]
    slot_inventory={"stage":STAGE,"record_type":"stage12483_required_proof_bundle_slot_inventory_v1","target_validator_stage":STAGE12468,"required_status_family":EXPECTED_STATUS_FAMILY,"required_common_slots":required_slots,"required_common_slot_count":len(required_slots),"lane_specific_required_proof_slots":lane_slots,"explicit_present_slots":EXPLICIT_PRESENT_SLOTS,"missing_proof_categories":MISSING_PROOF_CATEGORIES,"hard_rejects":["locator_only_bundle","metadata_only_bundle","pass_to_pass_bundle","patch_verifier_copresence_only","selected_test_only_bundle","cross_source_join","missing_same_verifier_identity","missing_before_fail","missing_after_patch_pass","raw_public_evidence_leak","placeholder_hash_or_claim_hash"], **FALSE_GUARDS, **ZERO_GUARDS,"remaining_external_fail_to_pass_gap":EXPECTED_GAP}
    summary={"stage":STAGE,"record_type":"stage12483_private_proof_bundle_acquisition_work_order_summary_v1","decision":"private_proof_bundle_acquisition_work_order_ready_zero_credit_no_execution" if items and not stage_blockers else "blocked_private_proof_bundle_acquisition_work_order_zero_credit","claim_boundary":"Private proof-bundle work order only. It does not execute, hydrate, replay, train, admit, package, or award repair credit.","source_stage_refs":[STAGE12478,STAGE12481,STAGE12482,STAGE12468],"proof_bundle_work_item_count":len(items),"fill_packet_item_count":len(fills),"materialization_blocker_count":len(blockers),"validator_complete_return_candidate_count":0,"official_stage12468_return_file_written":False,"target_validator_stage":STAGE12468,"credit_authority_stage":STAGE12468,"required_common_slot_count":len(required_slots),"missing_proof_category_count":len(MISSING_PROOF_CATEGORIES),"stage_blockers":sorted(set(stage_blockers)),"next_required_actions":["run_explicitly_authorized_private_executor_to_acquire_full_proof_bundles","produce_stage12468_compatible_private_return_candidates_only_when_all_slots_real","rerun_stage12468_validator_after_private_returns_exist"], **FALSE_GUARDS, **ZERO_GUARDS,"external_comparable_repair_credit_count":0,"remaining_external_fail_to_pass_gap":EXPECTED_GAP,"artifact_refs":{"private_proof_bundle_work_items_ref":"stage12483_private_proof_bundle_work_items_ref_jsonl","slot_inventory":"stage12483_required_proof_bundle_slot_inventory_json","guardrail_scan":"stage12483_guardrail_scan_json","summary":"stage12483_summary_json"},"input_artifact_hashes":{"validator_contract":file_hash(VALIDATOR_CONTRACT_IN),"fill_packet":file_hash(FILL_PACKET_IN),"blockers":file_hash(BLOCKERS_IN),"stage12478_summary":file_hash(STAGE12478_SUMMARY),"stage12481_summary":file_hash(STAGE12481_SUMMARY),"stage12482_summary":file_hash(STAGE12482_SUMMARY)}}
    payload={"summary":summary,"items":items,"slot_inventory":slot_inventory}; issues=public_scan('stage12483_public_artifacts',payload)
    guard={"stage":STAGE,"record_type":"stage12483_guardrail_scan_v1","scan_passed":not issues,"raw_leak_count":len(issues),"issue_hashes":[stable_hash(x) for x in issues[:50]], **FALSE_GUARDS, **ZERO_GUARDS,"remaining_external_fail_to_pass_gap":EXPECTED_GAP}
    if issues: summary['decision']='blocked_public_guardrail_scan_failed_zero_credit'; summary['stage_blockers']=sorted(set([*summary['stage_blockers'],'stage12483_public_guardrail_scan_failed'])); items=[]
    summary['guardrail_scan_passed']=guard['scan_passed']; summary['raw_leak_count']=guard['raw_leak_count']; summary['schema_issue_count']=len(summary['stage_blockers']); summary['summary_hash']=stable_hash({"decision":summary['decision'],"items":len(items),"raw":summary['raw_leak_count']})
    write_jsonl(WORK_ORDER_OUT,items)
    # shard public refs, no raw content
    WORK_ORDER_SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    for idx in range(0,len(items),3): write_json(WORK_ORDER_SHARDS_DIR/f"private_proof_bundle_work_items_shard_{idx//3+1:02d}.json", {"stage":STAGE,"record_type":"stage12483_private_proof_bundle_work_item_shard_v1","shard_index":idx//3+1,"item_count":len(items[idx:idx+3]),"items":items[idx:idx+3], **FALSE_GUARDS, **ZERO_GUARDS,"remaining_external_fail_to_pass_gap":EXPECTED_GAP})
    write_json(SLOT_INVENTORY_OUT,slot_inventory); write_json(GUARDRAIL_OUT,guard); write_json(LOCAL_SUMMARY_OUT,summary); write_json(SUMMARY_OUT,summary)
    print(json.dumps({"stage":STAGE,"decision":summary['decision'],"proof_bundle_work_item_count":len(items),"validator_complete_return_candidate_count":0,"official_stage12468_return_file_written":False,"external_comparable_repair_credit_count":0,"remaining_external_fail_to_pass_gap":EXPECTED_GAP,"guardrail_scan_passed":summary['guardrail_scan_passed'],"raw_leak_count":summary['raw_leak_count'],"schema_issue_count":summary['schema_issue_count'],"training_allowed":False,"admission_allowed":False}, indent=2, sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
