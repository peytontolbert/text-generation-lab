#!/usr/bin/env python3
"""Materialize targeted OpenClaw verifier observations into transition rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12005_openclaw_targeted_web_transition_rows")
ROWS = ROOT / "openclaw_targeted_web_transition_rows.jsonl"
SUMMARY = ROOT / "openclaw_targeted_web_transition_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12005_openclaw_targeted_web_transition_rows.json")
LABELS = list("ABCDEFGH")

OBSERVATIONS: list[dict[str, Any]] = [
    {
        "selected_verifier_path": "src/lib/runtimeEnv.test.ts",
        "returncode": 0,
        "stdout_tail": "Test Files  1 passed (1)\n      Tests  3 passed (3)",
        "duration": "695ms",
    },
    {
        "selected_verifier_path": "src/lib/packageLabels.test.ts",
        "returncode": 0,
        "stdout_tail": "Test Files  1 passed (1)\n      Tests  2 passed (2)",
        "duration": "2.41s",
    },
    {
        "selected_verifier_path": "src/components/SkillHeader.test.tsx",
        "returncode": 0,
        "stdout_tail": "Test Files  1 passed (1)\n      Tests  8 passed (8)",
        "duration": "6.14s",
    },
    {
        "selected_verifier_path": "packages/schema/src/schemas.test.ts",
        "returncode": 0,
        "stdout_tail": "Test Files  1 passed (1)\n      Tests  13 passed (13)",
        "duration": "2.51s",
    },
    {
        "selected_verifier_path": "src/__tests__/search-route.test.ts",
        "returncode": 0,
        "stdout_tail": "Test Files  2 passed (2)\n      Tests  19 passed (19)",
        "duration": "3.67s",
    },
    {
        "selected_verifier_path": "src/lib/diffing.test.ts",
        "returncode": 0,
        "stdout_tail": "Test Files  1 passed (1)\n      Tests  15 passed (15)",
        "duration": "1.57s",
    },
    {
        "selected_verifier_path": "packages/clawhub/src/schema/textFiles.test.ts",
        "returncode": 1,
        "stdout_tail": "No test files found, exiting with code 1\nfilter: packages/clawhub/src/schema/textFiles.test.ts\nexclude: **/node_modules/**, **/.vercel/output/**, **/.output/**, **/.nitro/**, **/dist/**, **/coverage/**, **/convex/_generated/**, packages/clawhub/**, e2e/**, **/*.e2e.test.ts",
        "duration": "579ms",
        "status": "NOT_EXERCISED",
    },
    {
        "selected_verifier_path": "packages/clawhub/src/config.test.ts",
        "returncode": 1,
        "stdout_tail": "No test files found, exiting with code 1\nfilter: packages/clawhub/src/config.test.ts\nexclude: **/node_modules/**, **/.vercel/output/**, **/.output/**, **/.nitro/**, **/dist/**, **/coverage/**, **/convex/_generated/**, packages/clawhub/**, e2e/**, **/*.e2e.test.ts",
        "duration": "937ms",
        "status": "NOT_EXERCISED",
    },
]

TRANSITION_TEXT = {
    "PASS_TO_PASS": "focused verifier executed from local source and passed",
    "PASS_CURRENT_BUILD_AND_RUN": "build and runnable verifier both passed",
    "PASS_CURRENT_BUILD": "build or collection passed but runnable verifier body did not execute",
    "FAIL_TO_PASS": "controlled broken state failed and restored or repaired source passed",
    "NOT_EXERCISED": "command did not exercise or collect the selected verifier",
    "INSUFFICIENT_EVIDENCE": "environment is underhydrated so no trustworthy transition is available",
    "FAIL_TO_FAIL": "verifier failed in the current local source state",
    "VERIFIER_REMOVED": "verifier evidence was removed and the row should abstain",
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def status(obs: dict[str, Any]) -> str:
    if obs.get("status"):
        return str(obs["status"])
    return "PASS_TO_PASS" if obs["returncode"] == 0 else "INSUFFICIENT_EVIDENCE"


def options(row_id: str) -> list[dict[str, str]]:
    keyed = [
        (hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text)
        for value, text in TRANSITION_TEXT.items()
    ]
    return [
        {
            "label": label,
            "canonical_value": value,
            "value": value,
            "text": text,
            "role": "verifier_transition_status",
            "artifact_type": "web_vitest_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def make_row(obs: dict[str, Any]) -> dict[str, Any]:
    selected = obs["selected_verifier_path"]
    semantic = status(obs)
    row_id = f"stage12005::openclaw__clawhub::{hashlib.sha1(selected.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id)
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    command = [
        "env",
        "VITE_CONVEX_URL=https://example.invalid",
        "./node_modules/.bin/vitest",
        "run",
        selected,
    ]
    prompt = "\n".join(
        [
            "Language: web_js_ts_html",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by the observed local-source Vitest command.",
            "Repository family: openclaw__clawhub",
            "Source root: /data/repositories/openclaw__clawhub",
            f"Selected verifier: {selected}",
            "Observed command: " + " ".join(command),
            f"Return code: {obs['returncode']}",
            f"Stdout tail: {obs['stdout_tail']}",
            "Options:",
            *[f"{o['label']}. {o['text']}" for o in opts],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12005::openclaw__clawhub::{selected}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": "openclaw__clawhub",
        "repo_family": "openclaw__clawhub",
        "language_family": "web_js_ts_html",
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12005_openclaw_targeted_web_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": True,
        "verifier_anchor": semantic != "INSUFFICIENT_EVIDENCE",
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "semantic_value": semantic,
        },
        "opaque_options": opts,
        "observed_verifier_transition": semantic,
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12005_openclaw_targeted_web_transition_rows",
            "selected_verifier_path": selected,
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {
                "command": command,
                "cwd": "/data/repositories/openclaw__clawhub",
                "returncode": obs["returncode"],
                "stdout_tail": obs["stdout_tail"],
                "duration": obs["duration"],
                "timed_out": False,
            },
        },
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = [make_row(obs) for obs in OBSERVATIONS]
    write_jsonl(ROWS, rows)
    status_counts = Counter(r["observed_verifier_transition"] for r in rows)
    summary = {
        "stage": "stage12005_openclaw_targeted_web_transition_rows",
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(Counter(r["language_family"] for r in rows)),
        "status_counts": dict(sorted(status_counts.items())),
        "repo_family_counts": dict(Counter(r["repo_family"] for r in rows)),
        "decision": "admit_openclaw_targeted_web_train_support",
        "claim_boundary": "OpenClaw rows are train-support only from one repo family; they improve web verifier supply but are not source-heldout frontier evidence.",
        "notes": [
            "Six targeted Vitest commands passed with positive test counts.",
            "Two package paths are admitted as NOT_EXERCISED because the root Vitest config excludes packages/clawhub/** and reports no test files found.",
        ],
        "next_stage_recommendation": {
            "stage": "stage12006_transition_support_rollup_v10",
            "action": "Merge OpenClaw targeted web rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
