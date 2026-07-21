#!/usr/bin/env python3
"""Stage12468 revalidation gate for private proof-slot returns."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12479_patch_effect_return_revalidation_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12467 = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12478 = "stage12478_private_return_fill_packet"

RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12467 / "private_proof_slot_returns.jsonl"
STAGE12468_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12468}.json"
STAGE12478_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12478}.json"
STAGE12478_FILL = ROOT / "runs/local/artifacts" / STAGE12478 / "private_return_fill_packet_items_ref.jsonl"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"
GATE_STATUS_OUT = OUT_DIR / "revalidation_gate_status.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"

EXPECTED_GAP = 15
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}
ZERO_GUARDS = {
    "external_comparable_repair_credit_count": 0,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}
FORBIDDEN_PUBLIC_KEYS = {
    "body", "cmd", "command", "commands", "commit", "commit_sha", "content",
    "diff", "file_content", "file_path", "patch", "patch_body", "path",
    "paths", "raw", "raw_content", "raw_text", "repo", "repo_id",
    "repo_name", "repository", "sha", "source", "source_text", "stderr",
    "stdout", "text", "uri", "uris", "url", "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|"
    r"gate|credit|authority|validator|revalidation|decision)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|"
    r"stdout|stderr|traceback|terminal output|command output)\\b|"
    r"\\b[0-9a-f]{40}\\b|"
    r"\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b",
    re.IGNORECASE | re.MULTILINE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True}
    try:
        v = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"_invalid_json": True}
    return v if isinstance(v, dict) else {"_not_object": True}


def count_jsonl(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    rows = 0
    bad = 0
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            rows += 1
            try:
                if not isinstance(json.loads(line), dict):
                    bad += 1
            except json.JSONDecodeError:
                bad += 1
    return rows, bad


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def public_scan(label: str, value: Any) -> list[str]:
    issues=[]
    leaf=label.rsplit('.',1)[-1].split('[',1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value,str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value,dict):
        for k,v in value.items(): issues.extend(public_scan(f"{label}.{k}",v))
    elif isinstance(value,list):
        for i,v in enumerate(value): issues.extend(public_scan(f"{label}[{i}]",v))
    return issues


def main() -> int:
    s68=read_json(STAGE12468_SUMMARY)
    s78=read_json(STAGE12478_SUMMARY)
    fill_count, fill_bad = count_jsonl(STAGE12478_FILL)
    return_count, return_bad = count_jsonl(RETURN_FILE)
    return_exists = RETURN_FILE.exists()
    blockers=[]
    if s78.get('stage') != STAGE12478:
        blockers.append('stage12478_summary_missing_or_unexpected')
    if s78.get('guardrail_scan_passed') is not True:
        blockers.append('stage12478_guardrail_not_passed')
    if s78.get('raw_leak_count') != 0:
        blockers.append('stage12478_raw_leak_count_not_zero')
    if s78.get('fill_packet_item_count') != fill_count:
        blockers.append('stage12478_fill_packet_count_mismatch')
    if fill_bad:
        blockers.append('stage12478_fill_packet_jsonl_invalid')
    if return_bad:
        blockers.append('private_return_jsonl_invalid')
    pending_conditions=[]
    if not return_exists:
        pending_conditions.append('private_return_file_missing')
    if return_exists and return_count <= 0:
        pending_conditions.append('private_return_file_empty')

    gate_status = {
        'stage': STAGE,
        'record_type': 'stage12479_revalidation_gate_status_v1',
        'private_return_file_exists': return_exists,
        'private_return_row_count': return_count,
        'private_return_file_ref_hash': file_hash(RETURN_FILE),
        'stage12478_fill_packet_item_count': fill_count,
        'stage12468_current_decision_ref_hash': stable_hash(s68.get('decision')),
        'stage12468_current_credit_count': s68.get('external_comparable_repair_credit_count', 0),
        'stage12468_rerun_allowed_by_gate': return_exists and return_count > 0 and not blockers and not pending_conditions,
        'stage12468_rerun_required_after_returns_exist': True,
        'stage12468_rerun_reason': 'missing_private_return' if not return_exists else 'private_return_present_requires_validator_rerun',
        'credit_authority_stage': STAGE12468,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        'remaining_external_fail_to_pass_gap': EXPECTED_GAP,
    }
    summary = {
        'stage': STAGE,
        'record_type': 'stage12479_patch_effect_return_revalidation_gate_summary_v1',
        'decision': 'blocked_private_returns_missing_no_revalidation_run' if not return_exists else ('stage12468_rerun_ready_zero_credit_by_this_stage' if not blockers and not pending_conditions else 'blocked_private_return_revalidation_gate_zero_credit'),
        'claim_boundary': 'Gate only. It does not run private execution or award credit; Stage12468 remains the only credit authority.',
        'source_stage_refs': [STAGE12478, STAGE12468],
        'private_return_file_exists': return_exists,
        'private_return_row_count': return_count,
        'stage12478_fill_packet_item_count': fill_count,
        'stage12468_rerun_allowed_by_gate': gate_status['stage12468_rerun_allowed_by_gate'],
        'stage12468_rerun_required_after_returns_exist': True,
        'stage12468_rerun_reason': gate_status['stage12468_rerun_reason'],
        'stage12468_current_external_comparable_repair_credit_count': s68.get('external_comparable_repair_credit_count', 0),
        'credit_authority_stage': STAGE12468,
        'stage_blockers': sorted(set(blockers)),
        'pending_conditions': sorted(set(pending_conditions)),
        'blocked_condition_count': len(set(pending_conditions)),
        'next_required_actions': ['populate_private_return_file_from_stage12478_fill_packet', 'rerun_stage12468_validator_after_returns_exist'],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        'remaining_external_fail_to_pass_gap': EXPECTED_GAP,
        'artifact_refs': {
            'revalidation_gate_status': 'stage12479_revalidation_gate_status_json',
            'guardrail_scan': 'stage12479_guardrail_scan_json',
            'local_summary': 'stage12479_local_summary_json',
            'summary': 'stage12479_summary_json',
        },
        'input_artifact_hashes': {
            'stage12478_summary': file_hash(STAGE12478_SUMMARY),
            'stage12478_fill_packet': file_hash(STAGE12478_FILL),
            'stage12468_summary': file_hash(STAGE12468_SUMMARY),
            'private_return_file': file_hash(RETURN_FILE),
        },
    }
    payload={'summary':summary,'gate_status':gate_status}
    issues=public_scan('stage12479_public_artifacts', payload)
    guard={'stage':STAGE,'record_type':'stage12479_guardrail_scan_v1','scan_passed':not issues,'raw_leak_count':len(issues),'issue_hashes':[stable_hash(x) for x in issues[:50]], **FALSE_GUARDS, **ZERO_GUARDS, 'remaining_external_fail_to_pass_gap':EXPECTED_GAP}
    if issues:
        summary['decision']='blocked_public_guardrail_scan_failed_zero_credit'
        summary['stage_blockers']=sorted(set([*summary['stage_blockers'],'stage12479_public_guardrail_scan_failed']))
    summary['guardrail_scan_passed']=guard['scan_passed']
    summary['raw_leak_count']=guard['raw_leak_count']
    summary['schema_issue_count']=len(summary['stage_blockers'])
    summary['summary_hash']=stable_hash({'decision':summary['decision'],'private_return_file_exists':return_exists,'return_count':return_count,'blockers':summary['stage_blockers']})
    write_json(GATE_STATUS_OUT, gate_status)
    write_json(GUARDRAIL_OUT, guard)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps({'stage':STAGE,'decision':summary['decision'],'private_return_file_exists':return_exists,'private_return_row_count':return_count,'stage12468_rerun_allowed_by_gate':summary['stage12468_rerun_allowed_by_gate'],'external_comparable_repair_credit_count':0,'remaining_external_fail_to_pass_gap':EXPECTED_GAP,'guardrail_scan_passed':summary['guardrail_scan_passed'],'raw_leak_count':summary['raw_leak_count'],'schema_issue_count':summary['schema_issue_count'],'blocked_condition_count':summary['blocked_condition_count'],'training_allowed':False,'admission_allowed':False}, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
