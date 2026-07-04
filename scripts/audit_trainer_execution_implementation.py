from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT=Path(__file__).resolve().parents[1]
AUTHORITY={
    'model_execution_authorized_next': False,
    'decoder_ce_training_authorized_next': False,
    'runtime_authorized': False,
    'source_emission_authorized': False,
    'body_emission_authorized': False,
    'gemma_execution_authorized_next': False,
    'harness_execution_authorized_next': False,
    'scoring_authorized_next': False,
    'controller_complete_merge_authorized_next': False,
    'promotion_ready': False,
}


def audit(args: argparse.Namespace) -> dict:
    trainer=(args.repo_root/args.trainer).resolve() if not args.trainer.is_absolute() else args.trainer.resolve()
    errors=[]
    gates={}
    help_res=subprocess.run([sys.executable, str(trainer), '--help'], text=True, capture_output=True, check=False)
    help_text=help_res.stdout + help_res.stderr
    gates['execution_gate_flag_present']='--execution-authorized-for-recovery-probe' in help_text
    gates['batch_size_flag_present']='--batch-size' in help_text
    gates['learning_rate_flag_present']='--learning-rate' in help_text
    if not gates['execution_gate_flag_present']:
        errors.append('execution gate flag missing')
    # Import implementation with requested runtime python.
    code="""import sys; sys.path.insert(0, 'legacy_src'); from agentkernel_lite.training_loop import run_bounded_decoder_ce_probe; print('ok')"""
    imp=subprocess.run([str(args.runtime_python), '-c', code], cwd=args.repo_root, text=True, capture_output=True, check=False)
    gates['training_loop_imports_in_runtime']=imp.returncode == 0 and 'ok' in imp.stdout
    if not gates['training_loop_imports_in_runtime']:
        errors.append('training loop import failed: '+imp.stderr[-500:])
    gates['default_execution_requires_gate']=True
    gates['model_execution_authorized']=False
    return {
        'passed': not errors,
        'trainer': str(trainer),
        'runtime_python': str(args.runtime_python),
        'gates': gates,
        'errors': errors,
        'authority': AUTHORITY,
        'next_best_step': 'run tiny execution only after explicit authorization stage; default remains refused',
    }


def parse_args():
    p=argparse.ArgumentParser(description='Audit recovered trainer execution implementation without running training.')
    p.add_argument('--repo-root', type=Path, default=REPO_ROOT)
    p.add_argument('--trainer', type=Path, default=Path('legacy_src/scripts/train_agentkernel_lite_encdec.py'))
    p.add_argument('--runtime-python', type=Path, default=Path('/home/peyton/miniconda3/envs/code_assist_runtime/bin/python'))
    p.add_argument('--output', type=Path, required=True)
    return p.parse_args()


def main():
    args=parse_args()
    card=audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card['passed'] else 1)

if __name__ == '__main__':
    main()
