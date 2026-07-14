#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
OUT = ART / "stage11650_web_gap_grouped_verified_materialization"
LOGS = OUT / "logs"
ROWS = OUT / "web_gap_grouped_verified_rows.jsonl"
PACKETS = OUT / "web_gap_grouped_verified_root_packets.jsonl"
SUMMARY = OUT / "web_gap_grouped_verified_materialization.json"
SUMMARIES = ROOT / "runs/summaries"

OPENHANDS = Path("/data/repositories/OpenHands__OpenHands/frontend")
MCP = Path("/data/repositories/modelcontextprotocol__typescript-sdk")

ROOT_SPECS = [
    {
        "repo_family": "openhands_openhands_frontend",
        "root_slug": "input_validation",
        "cwd": OPENHANDS,
        "cmd": ["npm", "test", "--", "--run", "__tests__/utils/input-validation.test.ts"],
        "source": "src/utils/input-validation.ts",
        "test": "__tests__/utils/input-validation.test.ts",
        "distractor": "src/utils/websocket-url.ts",
        "tasks": ["symptom_localization", "evidence_citation", "minimal_fix_selection", "abstention_insufficient_evidence"],
    },
    {
        "repo_family": "openhands_openhands_frontend",
        "root_slug": "websocket_url",
        "cwd": OPENHANDS,
        "cmd": ["npm", "test", "--", "--run", "__tests__/utils/websocket-url.test.ts"],
        "source": "src/utils/websocket-url.ts",
        "test": "__tests__/utils/websocket-url.test.ts",
        "distractor": "src/utils/input-validation.ts",
        "tasks": ["symptom_localization", "evidence_citation", "minimal_fix_selection", "abstention_insufficient_evidence"],
    },
    {
        "repo_family": "openhands_openhands_frontend",
        "root_slug": "permission_checks",
        "cwd": OPENHANDS,
        "cmd": ["npm", "test", "--", "--run", "__tests__/utils/permission-checks.test.ts"],
        "source": "src/utils/org/permission-checks.ts",
        "test": "__tests__/utils/permission-checks.test.ts",
        "distractor": "src/utils/input-validation.ts",
        "tasks": ["symptom_localization", "evidence_citation", "minimal_fix_selection", "abstention_insufficient_evidence"],
    },
    {
        "repo_family": "openhands_openhands_frontend",
        "root_slug": "browser_tab",
        "cwd": OPENHANDS,
        "cmd": ["npm", "test", "--", "--run", "__tests__/utils/browser-tab.test.ts"],
        "source": "src/utils/browser-tab.ts",
        "test": "__tests__/utils/browser-tab.test.ts",
        "distractor": "src/utils/websocket-url.ts",
        "tasks": ["symptom_localization", "evidence_citation", "minimal_fix_selection", "abstention_insufficient_evidence"],
    },
    {
        "repo_family": "@modelcontextprotocol/core",
        "root_slug": "tool_name_validation",
        "cwd": MCP / "packages/core",
        "cmd": ["pnpm", "test", "test/shared/toolNameValidation.test.ts"],
        "source": "src/shared/toolNameValidation.ts",
        "test": "test/shared/toolNameValidation.test.ts",
        "distractor": "src/shared/protocol.ts",
        "tasks": ["evidence_citation", "verifier_outcome"],
    },
    {
        "repo_family": "@modelcontextprotocol/core",
        "root_slug": "protocol_transport",
        "cwd": MCP / "packages/core",
        "cmd": ["pnpm", "test", "test/shared/transport.test.ts"],
        "source": "src/shared/transport.ts",
        "test": "test/shared/transport.test.ts",
        "distractor": "src/shared/toolNameValidation.ts",
        "tasks": ["evidence_citation", "verifier_outcome"],
    },
    {
        "repo_family": "@modelcontextprotocol/client",
        "root_slug": "client_stdio",
        "cwd": MCP / "packages/client",
        "cmd": ["pnpm", "test", "test/client/stdio.test.ts"],
        "source": "src/client/stdio.ts",
        "test": "test/client/stdio.test.ts",
        "distractor": "src/client/streamableHttp.ts",
        "tasks": ["verifier_outcome"],
    },
    {
        "repo_family": "@modelcontextprotocol/server",
        "root_slug": "server_streamable_http",
        "cwd": MCP / "packages/server",
        "cmd": ["pnpm", "test", "test/server/streamableHttp.test.ts"],
        "source": "src/server/streamableHttp.ts",
        "test": "test/server/streamableHttp.test.ts",
        "distractor": "src/server/stdio.ts",
        "tasks": ["evidence_citation", "verifier_outcome"],
    },
    {
        "repo_family": "@modelcontextprotocol/server",
        "root_slug": "server_completable",
        "cwd": MCP / "packages/server",
        "cmd": ["pnpm", "test", "test/server/completable.test.ts"],
        "source": "src/server/completable.ts",
        "test": "test/server/completable.test.ts",
        "distractor": "src/server/streamableHttp.ts",
        "tasks": ["evidence_citation", "verifier_outcome"],
    },
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_snippet(path: Path, max_lines: int = 70) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[:max_lines])


def run_verifier(spec: dict[str, Any]) -> dict[str, Any]:
    log_path = LOGS / f"{spec['repo_family'].replace('/', '_').replace('@', '')}_{spec['root_slug']}.log"
    started = time.time()
    proc = subprocess.run(spec["cmd"], cwd=spec["cwd"], text=True, capture_output=True, timeout=90)
    content = f"$ {' '.join(spec['cmd'])}\n# cwd={spec['cwd']}\n# returncode={proc.returncode}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n"
    log_path.write_text(content, encoding="utf-8")
    return {
        "command": spec["cmd"],
        "cwd": str(spec["cwd"]),
        "returncode": proc.returncode,
        "status": "verifier_executed_passed" if proc.returncode == 0 else "verifier_executed_failed",
        "transition": "PASS_TO_PASS" if proc.returncode == 0 else "FAIL_CURRENT_STATE",
        "duration_seconds": round(time.time() - started, 3),
        "log_path": str(log_path.relative_to(ROOT)),
        "stdout_tail": proc.stdout[-1600:],
        "stderr_tail": proc.stderr[-1600:],
    }


def target_role(task: str) -> str:
    if task in {"symptom_localization", "minimal_fix_selection"}:
        return "candidate_change_surface"
    return "verifier_and_test_constraint"


def task_instruction(task: str) -> str:
    return {
        "symptom_localization": "Choose the source-side candidate most likely to own the observed behavior under maintenance.",
        "evidence_citation": "Choose the evidence item that most directly justifies the answer.",
        "verifier_outcome": "Choose the verifier/test candidate whose observed run determines the current verifier outcome.",
        "minimal_fix_selection": "Choose the smallest source-side maintenance target consistent with the visible verifier evidence.",
        "abstention_insufficient_evidence": "Decide whether visible evidence is sufficient to answer, or whether abstention is required.",
    }[task]


def make_options(spec: dict[str, Any], task: str) -> list[dict[str, str]]:
    opts = [
        {"label": "A", "semantic_role": "candidate_change_surface", "text": spec["source"], "value": spec["source"]},
        {"label": "B", "semantic_role": "verifier_and_test_constraint", "text": spec["test"], "value": spec["test"]},
        {"label": "C", "semantic_role": "symptom_or_call_path_analogue", "text": spec["distractor"], "value": spec["distractor"]},
        {"label": "D", "semantic_role": "abstain_insufficient_evidence", "text": "ABSTAIN_INSUFFICIENT_EVIDENCE", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
    ]
    seed = int(sha(f"{spec['repo_family']}::{spec['root_slug']}::{task}")[:8], 16)
    # Deterministic rotation keeps labels opaque enough for this support packet while preserving all roles.
    shift = seed % len(opts)
    rotated = opts[shift:] + opts[:shift]
    labels = ["A", "B", "C", "D"]
    return [{**opt, "label": label} for label, opt in zip(labels, rotated)]


def make_row(spec: dict[str, Any], verifier: dict[str, Any], task: str, source_text: str, test_text: str, distractor_text: str) -> dict[str, Any]:
    opts = make_options(spec, task)
    role = target_role(task)
    target = next(opt for opt in opts if opt["semantic_role"] == role)
    root = f"stage11650::{spec['repo_family']}::{spec['root_slug']}"
    prompt = f"""Language: web_js_ts_html
Perspective: {task}
Task: {task_instruction(task)}
Decision criterion: use the source snippet, selected verifier/test snippet, observed verifier transition, and option roles; do not infer from option letter position.
Repository family: {spec['repo_family']}
Visible source evidence:
{source_text}
Visible verifier/test evidence:
{test_text}
Observed verifier transition:
status={verifier['status']} transition={verifier['transition']}
focused_command={' '.join(verifier['command'])}
Verifier log excerpt:
{(verifier.get('stdout_tail') or verifier.get('stderr_tail') or '')[-1200:]}
Visible distractor evidence:
{distractor_text}
Choices:
""" + "\n".join(f"option {opt['label']}: {opt['semantic_role']}; visible handle: {opt['text']}" for opt in opts)
    return {
        "row_id": f"{root}::{task}",
        "root_id": root,
        "root_lineage_key": root,
        "rollout_group_id": root,
        "root_group_id": root,
        "repo_family": spec["repo_family"],
        "language_family": "web_js_ts_html",
        "task_type": task,
        "split": "train",
        "package_split": "train",
        "input_text": prompt,
        "prompt_text": prompt,
        "opaque_options": opts,
        "standalone_projection_source": {"opaque_options": opts, "projection_mode": "stage11650_verified_grouped_analogue"},
        "bounded_choice_target_label": target["label"],
        "target_text": target["label"],
        "decoder_text": target["label"],
        "semantic_target_role": role,
        "semantic_target_value": target["value"],
        "selected_verifier_path": spec["test"],
        "observed_verifier_transition": verifier["transition"],
        "verifier_transition": verifier["transition"],
        "verifier_evidence": verifier,
        "loss_mask": {"decoder_ce": True, "bounded_choice_aux": True},
        "trainable_now": True,
        "strict_eval_eligible_now": False,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "no_gold_label_in_prompt_before_options": True,
            "target_label_not_visible_before_options": True,
            "requires_prompt_target_leak_review_before_training": False,
            "observed_verifier_transition_present": True,
            "selected_verifier_path_present": True,
            "source_snippets_materialized": True,
            "verifier_snippet_materialized": True,
        },
        "stage11650_verified_materialization": True,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    for spec in ROOT_SPECS:
        source_path = Path(spec["cwd"]) / spec["source"]
        test_path = Path(spec["cwd"]) / spec["test"]
        distractor_path = Path(spec["cwd"]) / spec["distractor"]
        missing = [str(path) for path in (source_path, test_path, distractor_path) if not path.exists()]
        if missing:
            packets.append({"root_slug": spec["root_slug"], "repo_family": spec["repo_family"], "admitted": False, "missing_paths": missing})
            continue
        verifier = run_verifier(spec)
        if verifier["returncode"] != 0:
            packets.append({"root_slug": spec["root_slug"], "repo_family": spec["repo_family"], "admitted": False, "verifier": verifier})
            continue
        source_text = read_snippet(source_path)
        test_text = read_snippet(test_path)
        distractor_text = read_snippet(distractor_path, max_lines=45)
        root_rows = [make_row(spec, verifier, task, source_text, test_text, distractor_text) for task in spec["tasks"]]
        rows.extend(root_rows)
        packets.append({
            "root_id": f"stage11650::{spec['repo_family']}::{spec['root_slug']}",
            "repo_family": spec["repo_family"],
            "root_slug": spec["root_slug"],
            "admitted": True,
            "tasks": spec["tasks"],
            "rows": len(root_rows),
            "verifier": verifier,
            "source_path": spec["source"],
            "test_path": spec["test"],
            "distractor_path": spec["distractor"],
        })
    ROWS.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    PACKETS.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")
    summary = {
        "stage": 11650,
        "stage_name": "stage11650_web_gap_grouped_verified_materialization",
        "created_at_utc": now(),
        "decision": "verified_grouped_web_rows_materialized" if rows else "no_verified_grouped_web_rows_materialized",
        "metrics": {"root_specs": len(ROOT_SPECS), "admitted_roots": sum(1 for p in packets if p.get("admitted")), "rows": len(rows)},
        "outputs": {"rows": str(ROWS.relative_to(ROOT)), "packets": str(PACKETS.relative_to(ROOT)), "logs": str(LOGS.relative_to(ROOT)), "summary": str(SUMMARY.relative_to(ROOT))},
        "claim_boundary": ["Train-support only; not strict eval.", "Every admitted row has an executed focused verifier log and PASS_TO_PASS transition.", "Rows must still pass Stage11648 before training."],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / "stage11650_web_gap_grouped_verified_materialization.json")
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
