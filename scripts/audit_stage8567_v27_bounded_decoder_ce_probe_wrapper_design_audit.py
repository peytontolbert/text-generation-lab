from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from safe_paths import UnsafePathError, assert_no_destructive_command_tokens
from stage_summary_schema import AUTHORITY_KEYS, normalize_authority


REQUIRED_FLAGS = (
    "--repo-root",
    "--manifest",
    "--mode",
    "--max-train-rows",
    "--max-eval-rows",
    "--max-strict-rows",
    "--max-steps",
    "--decoder-ce-weight",
    "--structured-aux-weight",
    "--denoise-weight",
    "--require-loss-mask-enforcement-audit",
    "--no-final-checkpoint-export",
    "--cleanup-checkpoints-after-probe",
    "--skip-final-model-save",
    "--output-dir",
    "--run-id",
    "--contract-only",
)

FORBIDDEN_FLAGS = (
    "--export",
    "--final-checkpoint-export",
    "--run-runtime",
    "--run-gemma",
    "--run-harness",
    "--hidden-scoring",
)


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def load_design(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("design must be an object")
    return payload


def audit_design(path: Path, *, check_trainer_help: bool = True) -> dict[str, Any]:
    design = load_design(path)
    command = [str(part) for part in design.get("command", [])]
    errors: list[str] = []
    gates: dict[str, bool] = {}

    for flag in REQUIRED_FLAGS:
        gates[f"command_has_{flag.lstrip('-').replace('-', '_')}"] = flag in command
    missing = [flag for flag in REQUIRED_FLAGS if flag not in command]
    if missing:
        errors.append(f"missing required flags: {missing}")

    forbidden_present = [flag for flag in FORBIDDEN_FLAGS if flag in command]
    gates["forbidden_flags_absent"] = not forbidden_present
    if forbidden_present:
        errors.append(f"forbidden flags present: {forbidden_present}")

    try:
        assert_no_destructive_command_tokens(command)
        gates["destructive_command_tokens_absent"] = True
    except UnsafePathError as exc:
        gates["destructive_command_tokens_absent"] = False
        errors.append(str(exc))

    repo_root = Path(design.get("repo_root", ""))
    output_dir = Path(design.get("output_dir", ""))
    trainer = Path(design.get("trainer", ""))
    manifest = Path(design.get("manifest", ""))
    gates["output_dir_under_repo_root"] = bool(repo_root) and bool(output_dir) and _is_relative_to(output_dir, repo_root)
    gates["trainer_exists"] = trainer.is_file()
    gates["manifest_path_declared"] = bool(str(manifest))
    if not gates["output_dir_under_repo_root"]:
        errors.append("output_dir is not under repo_root")
    if not gates["trainer_exists"]:
        errors.append(f"trainer does not exist: {trainer}")

    constraints = design.get("constraints") if isinstance(design.get("constraints"), dict) else {}
    expected_constraints = {
        "mode": "bounded_decoder_ce_probe",
        "decoder_ce_weight": 1.0,
        "structured_aux_weight": 0.0,
        "denoise_weight": 0.0,
        "no_final_checkpoint_export": True,
        "contract_only": True,
    }
    for key, expected in expected_constraints.items():
        actual = constraints.get(key)
        gates[f"constraint_{key}_matches"] = actual == expected
        if actual != expected:
            errors.append(f"constraint {key}={actual!r}, expected {expected!r}")

    auth = normalize_authority(design)
    open_auth = [key for key in AUTHORITY_KEYS if auth.get(key)]
    gates["authority_closed"] = not open_auth
    if open_auth:
        errors.append(f"authority open: {open_auth}")

    help_missing: list[str] = []
    if check_trainer_help and trainer.is_file():
        result = subprocess.run([sys.executable, str(trainer), "--help"], text=True, capture_output=True, check=False)
        help_text = result.stdout + result.stderr
        help_missing = [flag for flag in REQUIRED_FLAGS if flag not in help_text]
        gates["trainer_help_exposes_required_flags"] = result.returncode == 0 and not help_missing
        if result.returncode != 0:
            errors.append("trainer --help failed")
        if help_missing:
            errors.append(f"trainer help missing flags: {help_missing}")
    else:
        gates["trainer_help_exposes_required_flags"] = False if check_trainer_help else True

    return {
        "stage": 8567,
        "stage_name": "stage8567_v27_bounded_decoder_ce_probe_wrapper_design_audit",
        "passed": not errors,
        "design": str(path),
        "gates": gates,
        "errors": errors,
        "missing_required_flags": missing,
        "forbidden_flags_present": forbidden_present,
        "trainer_help_missing_flags": help_missing,
        "authority": {key: False for key in AUTHORITY_KEYS},
        "next_best_step": "rebuild loss-mask reopen and final pre-execution audits if wrapper audit passes",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a bounded decoder CE probe wrapper design without executing the probe.")
    parser.add_argument("design", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-trainer-help", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    card = audit_design(args.design, check_trainer_help=not args.skip_trainer_help)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
