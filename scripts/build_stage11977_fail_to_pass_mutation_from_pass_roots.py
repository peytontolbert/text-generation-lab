#!/usr/bin/env python3
"""Generate controlled FAIL_TO_PASS records from Stage11976 PASS_TO_PASS roots."""

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
STAGE = 11977
NAME = "stage11977_fail_to_pass_mutation_from_pass_roots"
OUT = ART / NAME
SUMMARY = OUT / "fail_to_pass_mutation_from_pass_roots.json"
RECORDS = OUT / "fail_to_pass_transition_records_review_queue.jsonl"
STAGE11976_ROWS = ART / "stage11976_transition_root_250_review_package_gate/transition_root_250_admitted_review_package.jsonl"
TMP_ROOT = Path(os.environ.get("TMPDIR") or "/data/tmp") / NAME
LABELS = list("ABCDEFGH")
PRUNE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", "target", "node_modules"}

MUTATIONS = [
    {
        "repo_family": "aider-ai__aider",
        "source_root": "/data/repositories/Aider-AI__aider",
        "test_target": "tests/basic/test_run_cmd.py",
        "source_file": "aider/run_cmd.py",
        "find": "return process.returncode, \"\".join(output)",
        "replace": "return process.returncode, \"\".join(output) + \"BROKEN\"",
        "rationale": "Corrupt run_cmd_subprocess output after command execution; the focused echo verifier should fail while baseline/restored pass.",
    },
    {
        "repo_family": "swe-agent__mini-swe-agent",
        "source_root": "/data/repositories/SWE-agent__mini-swe-agent",
        "test_target": "tests/environments/test_init.py",
        "source_file": "src/minisweagent/environments/__init__.py",
        "find": '"local": "minisweagent.environments.local.LocalEnvironment",',
        "replace": '"local": "minisweagent.environments.local.MissingEnvironment",',
        "rationale": "Break shorthand local environment resolution; the focused environment mapping verifier should fail while baseline/restored pass.",
    },
    {
        "repo_family": "lastmile-ai__mcp-agent",
        "source_root": "/data/repositories/lastmile-ai__mcp-agent",
        "test_target": "tests/config/test_env_settings.py",
        "source_file": "src/mcp_agent/config.py",
        "find": """            elif isinstance(item, dict):\n                key, value = next(iter(item.items()))\n                yield key, value\n""",
        "replace": """            elif isinstance(item, dict):\n                key, value = next(iter(item.items()))\n                yield key, None\n""",
        "rationale": "Drop dictionary fallback values from iter_env_specs; the focused env settings verifier should fail while baseline/restored pass.",
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def ignore(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in PRUNE}


def copy_repo(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def run_pytest(cwd: Path, target: str, log_name: str) -> dict[str, Any]:
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "CUDA_VISIBLE_DEVICES": "",
        "NVIDIA_VISIBLE_DEVICES": "",
        "PYTHONPATH": os.pathsep.join([str(cwd), str(cwd / "src"), env.get("PYTHONPATH", "")]),
        "PYTHONPYCACHEPREFIX": str(TMP_ROOT / "pycache"),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TMPDIR": str(TMP_ROOT), "TEMP": str(TMP_ROOT), "TMP": str(TMP_ROOT),
    })
    cmd = ["python", "-m", "pytest", "-q", "-c", "/dev/null", "-o", f"cache_dir={TMP_ROOT / 'pytest_cache'}", target]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=25, check=False)
        rc, timed_out, stdout, stderr = proc.returncode, False, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        rc, timed_out = 124, True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    payload = {"command": cmd, "cwd": str(cwd), "returncode": rc, "timed_out": timed_out, "duration_sec": round(time.time()-started,3), "stdout_tail": stdout[-4000:], "stderr_tail": stderr[-4000:]}
    log = OUT / "logs" / f"{log_name}.json"
    write_json(log, payload)
    return {**payload, "log_path": rel(log)}


def pass_result(result: dict[str, Any]) -> bool:
    combined = f"{result.get('stdout_tail') or ''}\n{result.get('stderr_tail') or ''}"
    return result.get("returncode") == 0 and " passed" in combined and " skipped" not in combined


def shuffled(row_id: str, values: list[str]) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{i}::{v}".encode()).hexdigest(), v) for i, v in enumerate(values)]
    return [{"label": label, "value": value} for label, (_, value) in zip(LABELS, sorted(keyed))]


def make_record(m: dict[str, Any], baseline: dict[str, Any], mutant: dict[str, Any], restored: dict[str, Any]) -> dict[str, Any]:
    row_id = f"stage11977::{m['repo_family']}::{hashlib.sha1(m['rationale'].encode()).hexdigest()[:12]}"
    target_value = "baseline passed, controlled source mutation failed, restored source passed"
    options = shuffled(row_id, [target_value, "baseline failed before mutation", "mutation did not fail focused verifier", "restore was not verified after mutation"])
    target_label = next(o["label"] for o in options if o["value"] == target_value)
    prompt = "\n".join([
        f"Language: python",
        "Perspective: transition_verifier_transition",
        "Task: choose the verifier transition proven by baseline/mutant/restored command evidence.",
        f"Repository family: {m['repo_family']}",
        f"Source file: {m['source_file']}",
        f"Selected verifier: {m['test_target']}",
        f"Mutation rationale: {m['rationale']}",
        f"Baseline rc/stdout: {baseline['returncode']} {(baseline.get('stdout_tail') or '')[-600:]}",
        f"Mutant rc/stdout: {mutant['returncode']} {(mutant.get('stdout_tail') or '')[-600:]}",
        f"Restored rc/stdout: {restored['returncode']} {(restored.get('stdout_tail') or '')[-600:]}",
        "Options:", *[f"{o['label']}. {o['value']}" for o in options], "Answer:"
    ])
    return {
        "row_id": row_id,
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": m["repo_family"],
        "repo_family": m["repo_family"],
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
        "anti_cheat": {"deterministic_option_shuffle": True, "target_label_not_visible_before_options": True, "target_value_not_visible_before_options": True, "singleton_options": False, "temporary_copy_only": True, "source_repo_not_modified": True, "review_queue_only": True},
        "standalone_projection_source": {"projection_mode": NAME, "selected_verifier_path": m["test_target"], "source_file": m["source_file"], "mutation_rationale": m["rationale"], "tool_or_verifier_observation": {"baseline": baseline, "mutant": mutant, "restored": restored}},
    }


def run_mutation(m: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    work = TMP_ROOT / m["repo_family"] / "repo"
    copy_repo(Path(m["source_root"]), work)
    baseline = run_pytest(work, m["test_target"], f"{m['repo_family']}_baseline")
    source = work / m["source_file"]
    original = source.read_text(encoding="utf-8")
    mutation_applied = False
    if m["find"] in original:
        source.write_text(original.replace(m["find"], m["replace"], 1), encoding="utf-8")
        mutation_applied = True
    mutant = run_pytest(work, m["test_target"], f"{m['repo_family']}_mutant") if mutation_applied else {"returncode": None, "stdout_tail": "", "stderr_tail": "mutation_not_applied", "timed_out": False}
    source.write_text(original, encoding="utf-8")
    restored = run_pytest(work, m["test_target"], f"{m['repo_family']}_restored")
    admitted = mutation_applied and pass_result(baseline) and mutant.get("returncode") not in (0, None) and pass_result(restored)
    card = {"mutation": m, "work_copy": str(work), "mutation_applied": mutation_applied, "baseline": baseline, "mutant": mutant, "restored": restored, "admitted": admitted}
    return (make_record(m, baseline, mutant, restored) if admitted else None), card


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    pass_families = {row.get("repo_family") for row in read_jsonl(STAGE11976_ROWS) if row.get("observed_verifier_transition") == "PASS_TO_PASS"}
    candidates = [m for m in MUTATIONS if m["repo_family"] in pass_families and m["repo_family"] == "aider-ai__aider"]
    records: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for m in candidates:
        record, card = run_mutation(m)
        cards.append(card)
        if record:
            records.append(record)
    write_jsonl(RECORDS, records)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "fail_to_pass_mutation_probe_complete_review_queue_only",
        "source_artifacts": {"stage11976_rows": str(STAGE11976_ROWS.relative_to(ROOT))},
        "summary": {"eligible_pass_roots": len(pass_families), "mutation_candidates": len(candidates), "admitted_fail_to_pass_records": len(records)},
        "probe_cards": cards,
        "outputs": {"summary": rel(SUMMARY), "records": rel(RECORDS), "logs": rel(OUT / "logs")},
        "next_stage_recommendation": {"stage": "stage11978_transition_root_250_review_package_with_fail_to_pass", "action": "Merge Stage11976 review package with admitted Stage11977 FAIL_TO_PASS records, then reassess Stage11967 floors."},
    }
    write_json(SUMMARY, artifact)
    print(json.dumps({"decision": artifact["decision"], "summary": artifact["summary"], "next": artifact["next_stage_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
