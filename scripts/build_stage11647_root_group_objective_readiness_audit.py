#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11647
NAME = "stage11647_root_group_objective_readiness_audit"
OUT = ART / NAME
SUMMARY = OUT / "root_group_objective_readiness_audit.json"
STAGE11646 = ART / "stage11646_web_heldout_gap_rollout_mining/web_heldout_gap_rollout_mining.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has(path: Path, text: str) -> bool:
    return text in read(path)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    training_loop = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
    train_cli = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
    test_file = ROOT / "tests/test_bounded_choice_root_group_training.py"
    checks = {
        "root_group_key_helper_present": has(training_loop, "def _bounded_choice_root_group_key"),
        "root_group_aux_loss_present": has(training_loop, "def _bounded_choice_root_group_aux_loss"),
        "root_balanced_sampler_present": has(training_loop, "web_gap_root_balanced"),
        "training_loop_weight_present": has(training_loop, "bounded_choice_root_group_aux_weight"),
        "cli_weight_flag_present": has(train_cli, "--bounded-choice-root-group-aux-weight"),
        "cli_sampler_choice_present": has(train_cli, "web_gap_root_balanced"),
        "focused_test_present": test_file.exists(),
    }
    py_compile = subprocess.run(
        [
            "python",
            "-m",
            "py_compile",
            str(training_loop),
            str(train_cli),
            str(test_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    stage11646 = load_json(STAGE11646)
    gates = {
        **checks,
        "py_compile_passed": py_compile.returncode == 0,
        "stage11646_gap_groups_available": (stage11646.get("metrics") or {}).get("gap_root_groups", 0) > 0,
        "stage11646_work_items_available": (stage11646.get("metrics") or {}).get("work_items", 0) > 0,
    }
    decision = "root_group_objective_ready_for_materialized_web_gap_probe" if all(gates.values()) else "root_group_objective_not_ready"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "gates": gates,
        "py_compile": {
            "returncode": py_compile.returncode,
            "stdout": py_compile.stdout,
            "stderr": py_compile.stderr,
        },
        "source_artifacts": {
            "stage11646": rel(STAGE11646),
            "training_loop": rel(training_loop),
            "train_cli": rel(train_cli),
            "focused_test": rel(test_file),
        },
        "stage11646_training_scale": (stage11646.get("next_training_design") or {}).get("rl_scale_translation"),
        "new_train_flags": {
            "sampler": "--bounded-decoder-train-sampler web_gap_root_balanced",
            "root_group_loss": "--bounded-choice-root-group-aux-weight <nonzero>",
            "recommended_pairing": "keep --bounded-choice-contrast-weight nonzero and preserve Stage11507 gates during selection",
        },
        "claim_boundary": [
            "This enables grouped/root-balanced training for future materialized rows; it is not itself a model improvement.",
            "No existing selected frontier changes: Stage11507 remains selected and Stage11634 routed policy remains the current product routing.",
            "Future promotion still requires Web heldout >38/66 while preserving compact canary/residual gates.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
