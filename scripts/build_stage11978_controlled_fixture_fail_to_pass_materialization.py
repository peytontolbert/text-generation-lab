#!/usr/bin/env python3
"""Create a minimal source-backed controlled FAIL_TO_PASS transition fixture."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11978
NAME = "stage11978_controlled_fixture_fail_to_pass_materialization"
OUT = ART / NAME
FIXTURE = OUT / "fixture_repo"
WORK = OUT / "work_repo"
SUMMARY = OUT / "controlled_fixture_fail_to_pass_materialization.json"
ROWS = OUT / "controlled_fixture_fail_to_pass_review_rows.jsonl"
LABELS = list("ABCDEFGH")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_fixture() -> None:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    (FIXTURE / "maintainer_fixture").mkdir(parents=True)
    (FIXTURE / "tests").mkdir()
    (FIXTURE / "pyproject.toml").write_text('[project]\nname = "stage11978-maintainer-fixture"\nversion = "0.0.0"\n', encoding="utf-8")
    (FIXTURE / "maintainer_fixture" / "__init__.py").write_text('from .timeout import normalize_timeout\n', encoding="utf-8")
    (FIXTURE / "maintainer_fixture" / "timeout.py").write_text(
        'def normalize_timeout(value):\n'
        '    """Preserve zero as an explicit timeout while accepting None."""\n'
        '    if value is None:\n'
        '        return None\n'
        '    return float(value)\n',
        encoding="utf-8",
    )
    (FIXTURE / "tests" / "test_timeout.py").write_text(
        'from maintainer_fixture import normalize_timeout\n\n'
        'def test_zero_timeout_is_preserved():\n'
        '    assert normalize_timeout(0) == 0.0\n\n'
        'def test_none_timeout_remains_none():\n'
        '    assert normalize_timeout(None) is None\n',
        encoding="utf-8",
    )


def run_pytest(cwd: Path, name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "NVIDIA_VISIBLE_DEVICES": "",
        "PYTHONPATH": str(cwd),
        "PYTHONPYCACHEPREFIX": str(OUT / "pycache"),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TMPDIR": str(OUT / "tmp"),
        "TEMP": str(OUT / "tmp"),
        "TMP": str(OUT / "tmp"),
    })
    (OUT / "tmp").mkdir(parents=True, exist_ok=True)
    cmd = ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", f"cache_dir={OUT / 'pytest_cache'}", "tests/test_timeout.py"]
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30, check=False)
    payload = {
        "command": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "timed_out": False,
        "duration_sec": round(time.time() - started, 3),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
    write_json(OUT / "logs" / f"{name}.json", payload)
    return {**payload, "log_path": rel(OUT / "logs" / f"{name}.json")}


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v) for i, v in enumerate(values)]
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def passed(result: dict[str, Any]) -> bool:
    return result.get("returncode") == 0 and " passed" in str(result.get("stdout_tail") or "")


def make_row(baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    row_id = "stage11978::controlled_fixture::python::timeout_zero_fail_to_pass"
    target_value = "baseline passed, controlled mutation failed focused verifier, restored source passed"
    options = shuffled(row_id, [target_value, "baseline failed before mutation", "mutation did not fail focused verifier", "restore was not verified"])
    target_label = next(o["label"] for o in options if o["value"] == target_value)
    prompt = "\n".join([
        "Language: python",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition proven by baseline/mutant/restored source-backed evidence.",
        "Repository family: stage11978_controlled_fixture",
        "Source file: maintainer_fixture/timeout.py",
        "Selected verifier: tests/test_timeout.py",
        "Mutation: change `if value is None` to `if not value`, incorrectly treating zero as absent.",
        f"Baseline rc/stdout: {baseline['returncode']} {(baseline.get('stdout_tail') or '').strip()}",
        f"Mutant rc/stdout: {mutant['returncode']} {(mutant.get('stdout_tail') or '').strip()}",
        f"Restored rc/stdout: {restored['returncode']} {(restored.get('stdout_tail') or '').strip()}",
        "Options:",
        *[f"{o['label']}. {o['value']}" for o in options],
        "Answer:",
    ])
    return {
        "row_id": row_id,
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": "stage11978_controlled_fixture",
        "repo_family": "stage11978_controlled_fixture",
        "language_family": "python",
        "task_type": "transition_verifier_transition",
        "surface": "controlled_fail_to_pass_transition_review_bounded_choice",
        "split": "train",
        "split_role": "review_queue_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "opaque_options": options,
        "target_semantic_value": target_value,
        "observed_verifier_transition": "FAIL_TO_PASS",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "controlled_fixture_train_support_only": True,
            "baseline_mutant_restore_all_observed": True,
            "review_queue_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": NAME,
            "fixture_repo": rel(FIXTURE),
            "selected_verifier_path": "tests/test_timeout.py",
            "source_file": "maintainer_fixture/timeout.py",
            "observed_verifier_transition": "FAIL_TO_PASS",
            "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored},
        },
    }


def main() -> None:
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    build_fixture()
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(FIXTURE, WORK)
    baseline = run_pytest(WORK, "baseline")
    src = WORK / "maintainer_fixture" / "timeout.py"
    original = src.read_text(encoding="utf-8")
    src.write_text(original.replace("if value is None:", "if not value:", 1), encoding="utf-8")
    mutant = run_pytest(WORK, "mutant")
    src.write_text(original, encoding="utf-8")
    restored = run_pytest(WORK, "restored")
    admitted = passed(baseline) and mutant["returncode"] != 0 and passed(restored)
    rows = [make_row(baseline, mutant, restored)] if admitted else []
    write_jsonl(ROWS, rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "controlled_fixture_fail_to_pass_complete_review_queue_only",
        "summary": {"admitted_fail_to_pass_rows": len(rows), "baseline_passed": passed(baseline), "mutant_failed": mutant["returncode"] != 0, "restored_passed": passed(restored)},
        "quality_scope": "controlled_fixture_train_support_only_not_strict_eval_not_source_heldout",
        "observations": {"baseline": baseline, "mutant": mutant, "restored": restored},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS), "fixture_repo": rel(FIXTURE), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {"stage": "stage11979_transition_review_package_with_fixture_fail_to_pass", "action": "Merge Stage11976 source-backed review rows with this controlled FAIL_TO_PASS support row, keeping fixture rows train-support-only."},
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "quality_scope": artifact["quality_scope"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
