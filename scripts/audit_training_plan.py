from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT/'scripts') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT/'scripts'))

from stage_summary_schema import AUTHORITY_KEYS, normalize_authority


def audit(path: Path) -> dict:
    plan=json.loads(path.read_text(encoding='utf-8'))
    errors=[]
    gates={}
    manifests=[Path(p) for p in plan.get('manifests', [])]
    gates['manifests_present']=bool(manifests) and all(p.is_file() for p in manifests)
    if not gates['manifests_present']:
        errors.append('one or more manifests missing')
    losses=plan.get('losses', {})
    gates['runtime_loss_zero']=float(losses.get('runtime_reward_weight', 0.0)) == 0.0
    gates['execution_not_authorized']=plan.get('execution_authorized') is False
    open_auth=[k for k,v in normalize_authority(plan).items() if v]
    gates['authority_closed']=not open_auth
    if open_auth:
        errors.append(f'authority open: {open_auth}')
    caps=plan.get('caps', {})
    gates['tiny_caps']=caps.get('max_train_rows', 999999) <= 64 and caps.get('max_steps', 999999) <= 100
    if not gates['tiny_caps']:
        errors.append('caps are not tiny')
    if not gates['execution_not_authorized']:
        errors.append('execution_authorized is not false')
    if not gates['runtime_loss_zero']:
        errors.append('runtime reward is nonzero')
    return {
        'passed': not errors,
        'plan': str(path),
        'gates': gates,
        'errors': errors,
        'manifests': [str(p) for p in manifests],
        'authority': {k: False for k in AUTHORITY_KEYS},
        'next_best_step': 'use only after final pre-execution audit and separate execution authorization',
    }


def parse_args():
    p=argparse.ArgumentParser(description='Audit non-executing training plan contract.')
    p.add_argument('plan', type=Path)
    p.add_argument('--output', type=Path, required=True)
    return p.parse_args()


def main():
    args=parse_args()
    card=audit(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card['passed'] else 1)

if __name__ == '__main__':
    main()
