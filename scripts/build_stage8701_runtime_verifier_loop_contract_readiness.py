#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from runtime_verifier_loop_contract import audit_runtime_verifier_loop_contract, default_runtime_verifier_loop_contract

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'runs/local/artifacts/stage8701_runtime_verifier_loop_contract_readiness'
SUMMARY = ROOT / 'runs/summaries/stage8701_runtime_verifier_loop_contract_readiness.json'
DOC = ROOT / 'docs/RUNTIME_VERIFIER_LOOP_CONTRACT_READINESS_STAGE8701.md'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_emission_authorized': False, 'body_emission_authorized': False, 'gemma_execution_authorized_next': False, 'harness_execution_authorized_next': False, 'scoring_authorized_next': False, 'controller_complete_merge_authorized_next': False, 'promotion_ready': False}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contract = default_runtime_verifier_loop_contract()
    audit = audit_runtime_verifier_loop_contract(contract)
    (OUT_DIR / 'runtime_verifier_loop_contract.json').write_text(json.dumps(contract, indent=2, sort_keys=True) + '\n')
    (OUT_DIR / 'runtime_verifier_loop_contract_audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n')
    metrics = {'phase_count': audit['phase_count'], 'failure_taxonomy_count': audit['failure_taxonomy_count'], 'repair_action_count': audit['repair_action_count'], 'authority_rows': 0, **AUTHORITY_CLOSED}
    card = {'stage': 8701, 'name': 'stage8701_runtime_verifier_loop_contract_readiness', 'stage_name': 'stage8701_runtime_verifier_loop_contract_readiness', 'passed': audit['passed'], 'authority': AUTHORITY_CLOSED, 'metrics': metrics, 'decision': 'Recovered runtime verifier loop as a non-executing closed contract: prepare -> verify -> normalize_failure -> repair_decision -> reverify_or_abstain. This does not authorize runtime execution.', 'next_best_step': 'Attach runtime verifier loop contract to central graph, then recover cross-modal alignment and modality dropout audits.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'runtime_verifier_loop_contract_readiness_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    DOC.write_text('\n'.join(['# Stage8701 Runtime Verifier Loop Contract Readiness', '', f"Passed: `{audit['passed']}`", '', 'Recovered the runtime verifier loop as a closed contract only:', '', '- prepare', '- verify', '- normalize_failure', '- repair_decision', '- reverify_or_abstain', '', 'This is not an executable harness and does not authorize runtime.', '', 'All authority remains closed.', '']))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if audit['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
