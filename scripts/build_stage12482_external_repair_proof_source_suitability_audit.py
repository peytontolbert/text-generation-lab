#!/usr/bin/env python3
"""Proof-source suitability audit for Stage12468 external repair returns."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12482_external_repair_proof_source_suitability_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12433": ROOT / "runs/summaries/stage12433_open_swe_pilot_100_private_proof_slot_runner_postrun.json",
    "stage12445": ROOT / "runs/summaries/stage12445_adapter_execution_return_ingest_and_level3_gate.json",
    "stage12456": ROOT / "runs/summaries/stage12456_selected_test_return_proof_depth_audit.json",
    "stage12461": ROOT / "runs/summaries/stage12461_external_patch_effect_return_validator.json",
    "stage12468": ROOT / "runs/summaries/stage12468_non_bears_patch_effect_private_return_validator.json",
    "stage12481": ROOT / "runs/summaries/stage12481_private_return_materialization_attempt.json",
}
ARTIFACTS = {
    "stage12433_counts": ROOT / "runs/local/artifacts/stage12433_open_swe_pilot_100_private_proof_slot_runner_postrun/proof_slot_aggregate_counts.json",
    "stage12445_admitted": ROOT / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/admitted_level3_candidates.jsonl",
    "stage12461_accepted": ROOT / "runs/local/artifacts/stage12461_external_patch_effect_return_validator/accepted_return_ref_index.jsonl",
    "stage12481_blockers": ROOT / "runs/local/artifacts/stage12481_private_return_materialization_attempt/private_return_materialization_blockers_ref.jsonl",
}
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"
SOURCE_AUDIT_OUT = OUT_DIR / "proof_source_suitability_records.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
EXPECTED_GAP = 15
FALSE_GUARDS = {"training_allowed": False, "admission_allowed": False, "packaging_allowed": False, "execution_performed_by_stage": False, "hydration_performed_by_stage": False, "replay_performed_by_stage": False, "network_performed_by_stage": False}
ZERO_GUARDS = {"external_comparable_repair_credit_count": 0, "emitted_training_rows": 0, "sealed_eval_rows": 0}
FORBIDDEN_PUBLIC_KEYS = {"body","cmd","command","commands","commit","commit_sha","content","diff","file_content","file_path","patch","patch_body","path","paths","raw","raw_content","raw_text","repo","repo_id","repo_name","repository","sha","source","source_text","stderr","stdout","text","uri","uris","url","urls"}
PUBLIC_SAFE_KEY_RE = re.compile(r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|locator|candidate|context|label|input|excluded|request|contract|pending|file|audit|suitability|credit|authority|level)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|stdout|stderr|traceback|terminal output|command output)\\b|\\b[0-9a-f]{40}\\b|\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b", re.I|re.M)

def stable_hash(v: Any, n:int=24)->str:
    return hashlib.sha256((STAGE+":"+json.dumps(v, sort_keys=True, separators=(",",":"), default=str)).encode()).hexdigest()[:n]
def file_hash(p: Path, n:int=24)->str:
    if not p.exists() or not p.is_file(): return "missing"
    h=hashlib.sha256();
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()[:n]
def read_json(p: Path)->dict[str,Any]:
    if not p.exists(): return {"_missing": True}
    try: v=json.loads(p.read_text())
    except Exception: return {"_invalid_json": True}
    return v if isinstance(v,dict) else {"_not_object": True}
def count_jsonl(p: Path)->int:
    if not p.exists(): return 0
    return sum(1 for l in p.open() if l.strip())
def write_json(p:Path,v:Any)->None:
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v, indent=2, sort_keys=True)+"\n")
def write_jsonl(p:Path, rows:list[dict[str,Any]])->None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w') as f:
        for r in rows: f.write(json.dumps(r, sort_keys=True)+"\n")
def public_scan(label:str, v:Any)->list[str]:
    out=[]; leaf=label.rsplit('.',1)[-1].split('[',1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label): out.append(f"{label}:forbidden_public_key")
    if isinstance(v,str) and RAW_LEAK_RE.search(v): out.append(f"{label}:raw_content_pattern:{stable_hash(v)}")
    elif isinstance(v,dict):
        for k,c in v.items(): out.extend(public_scan(f"{label}.{k}", c))
    elif isinstance(v,list):
        for i,c in enumerate(v): out.extend(public_scan(f"{label}[{i}]", c))
    return out

def main()->int:
    s={k:read_json(p) for k,p in INPUTS.items()}
    stage12433_counts=read_json(ARTIFACTS['stage12433_counts'])
    records=[
        {"source_stage":"stage12433", "record_type":"stage12482_source_suitability_record_v1", "candidate_count":100, "external_repair_return_suitable_count":0, "suitability":"not_suitable", "reason_codes":["private_structure_only_no_execution","same_verifier_before_after_missing","causal_transition_missing","checkout_before_missing","patch_application_proof_missing"]},
        {"source_stage":"stage12445", "record_type":"stage12482_source_suitability_record_v1", "candidate_count":count_jsonl(ARTIFACTS['stage12445_admitted']), "external_repair_return_suitable_count":0, "suitability":"transition_support_only", "reason_codes":["level3_verifier_transition_support_not_external_patch_effect_credit","stage12456_limits_to_transition_support_only","no_separate_external_patch_effect_audit_acceptance"]},
        {"source_stage":"stage12461", "record_type":"stage12482_source_suitability_record_v1", "candidate_count":count_jsonl(ARTIFACTS['stage12461_accepted']), "external_repair_return_suitable_count":0, "suitability":"no_accepted_returns", "reason_codes":["accepted_return_ref_index_empty"]},
        {"source_stage":"stage12481", "record_type":"stage12482_source_suitability_record_v1", "candidate_count":count_jsonl(ARTIFACTS['stage12481_blockers']), "external_repair_return_suitable_count":0, "suitability":"blocked_locator_sidecar_not_proof_bundle", "reason_codes":["materialization_blocker_count_nonzero","validator_complete_return_candidate_count_zero"]},
    ]
    summary={
        "stage":STAGE,
        "record_type":"stage12482_external_repair_proof_source_suitability_audit_summary_v1",
        "decision":"no_existing_artifact_source_can_fill_stage12468_external_repair_returns",
        "claim_boundary":"Suitability audit only. It does not execute, hydrate, replay, train, admit, package, or award repair credit.",
        "source_stage_refs":list(INPUTS),
        "audited_source_count":len(records),
        "external_repair_return_suitable_source_count":sum(1 for r in records if r['external_repair_return_suitable_count']>0),
        "stage12445_level3_transition_support_count":count_jsonl(ARTIFACTS['stage12445_admitted']),
        "stage12445_external_repair_credit_eligible_count":0,
        "stage12433_proof_complete_candidates":stage12433_counts.get('proof_complete_candidates',0),
        "stage12461_accepted_external_return_count":count_jsonl(ARTIFACTS['stage12461_accepted']),
        "stage12481_validator_complete_return_candidate_count":s['stage12481'].get('validator_complete_return_candidate_count',0),
        "stage12481_materialization_blocker_count":s['stage12481'].get('materialization_blocker_count',0),
        "next_required_stage":"private_executor_full_proof_bundle_acquisition_not_existing_artifact_reuse",
        "hard_no_train_reason":"all audited existing sources are transition-support, structure-only, empty, or locator-only; none provide Stage12468-complete external repair proof",
        **FALSE_GUARDS, **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap":EXPECTED_GAP,
        "artifact_refs":{"proof_source_suitability_records":"stage12482_proof_source_suitability_records_jsonl","guardrail_scan":"stage12482_guardrail_scan_json","summary":"stage12482_summary_json"},
        "input_artifact_hashes":{**{k:file_hash(p) for k,p in INPUTS.items()}, **{k:file_hash(p) for k,p in ARTIFACTS.items()}},
    }
    payload={"summary":summary,"records":records}
    issues=public_scan('stage12482_public_artifacts', payload)
    guard={"stage":STAGE,"record_type":"stage12482_guardrail_scan_v1","scan_passed":not issues,"raw_leak_count":len(issues),"issue_hashes":[stable_hash(x) for x in issues[:50]], **FALSE_GUARDS, **ZERO_GUARDS,"remaining_external_fail_to_pass_gap":EXPECTED_GAP}
    if issues: summary['decision']='blocked_public_guardrail_scan_failed_zero_credit'
    summary['guardrail_scan_passed']=guard['scan_passed']; summary['raw_leak_count']=guard['raw_leak_count']; summary['schema_issue_count']=0 if guard['scan_passed'] else len(issues); summary['summary_hash']=stable_hash({"decision":summary['decision'],"suitable":summary['external_repair_return_suitable_source_count'],"raw":summary['raw_leak_count']})
    write_jsonl(SOURCE_AUDIT_OUT, records); write_json(GUARDRAIL_OUT, guard); write_json(LOCAL_SUMMARY_OUT, summary); write_json(SUMMARY_OUT, summary)
    print(json.dumps({"stage":STAGE,"decision":summary['decision'],"audited_source_count":len(records),"external_repair_return_suitable_source_count":summary['external_repair_return_suitable_source_count'],"stage12445_level3_transition_support_count":summary['stage12445_level3_transition_support_count'],"stage12445_external_repair_credit_eligible_count":0,"external_comparable_repair_credit_count":0,"remaining_external_fail_to_pass_gap":EXPECTED_GAP,"guardrail_scan_passed":summary['guardrail_scan_passed'],"raw_leak_count":summary['raw_leak_count'],"training_allowed":False}, indent=2, sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
