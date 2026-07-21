#!/usr/bin/env python3
"""Materialize semantic FAIL_TO_PASS rows from observed real-source probes."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12035_semantic_transition_expansion_rows")
PROBES = ROOT / "semantic_transition_probe_results.json"
ROWS = ROOT / "semantic_transition_expansion_rows.jsonl"
SUMMARY = ROOT / "semantic_transition_expansion_rows.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12035_semantic_transition_expansion_rows.json")
LABELS = list("ABCDEFGH")

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


def options(row_id: str, language: str) -> list[dict[str, str]]:
    keyed = [(hashlib.sha256(f"{row_id}::{value}".encode()).hexdigest(), value, text) for value, text in TRANSITION_TEXT.items()]
    return [
        {
            "label": label,
            "canonical_value": value,
            "value": value,
            "text": text,
            "role": "verifier_transition_status",
            "artifact_type": f"{language}_verifier_status",
        }
        for label, (_, value, text) in zip(LABELS, sorted(keyed))
    ]


def admissible(probe: dict[str, Any]) -> bool:
    required_build_keys = ("configure", "build_base", "build_mutant", "build_restored")
    build_ok = all(probe.get(key, {"returncode": 0})["returncode"] == 0 for key in required_build_keys)
    return probe["baseline"]["returncode"] == 0 and probe["mutant"]["returncode"] != 0 and probe["restored"]["returncode"] == 0 and build_ok


def make_row(probe: dict[str, Any]) -> dict[str, Any]:
    semantic = "FAIL_TO_PASS"
    material = f"{probe['repo_family']}::{probe['selected_verifier_path']}::{probe['mutation_kind']}::{semantic}"
    row_id = f"stage12035::{probe['repo_family']}::{hashlib.sha1(material.encode()).hexdigest()[:12]}::{semantic}"
    opts = options(row_id, probe["language_family"])
    target_label = next(o["label"] for o in opts if o["canonical_value"] == semantic)
    baseline = probe["baseline"]
    mutant = probe["mutant"]
    restored = probe["restored"]
    prompt = "\n".join(
        [
            f"Language: {probe['language_family']}",
            "Perspective: transition_verifier_transition",
            "Task: choose the verifier transition supported by real-source baseline, semantic mutation, and restore evidence.",
            f"Repository family: {probe['repo_family']}",
            f"Selected verifier: {probe['selected_verifier_path']}",
            f"Mutation kind: {probe['mutation_kind']}",
            f"Mutated source file: {probe['mutation_file']}",
            f"Baseline command: {baseline['command']}",
            f"Baseline return code: {baseline['returncode']}",
            f"Baseline output tail: {baseline['stdout_tail']}",
            f"Mutant command: {mutant['command']}",
            f"Mutant return code: {mutant['returncode']}",
            f"Mutant output tail: {mutant['stdout_tail']}",
            f"Restored command: {restored['command']}",
            f"Restored return code: {restored['returncode']}",
            f"Restored output tail: {restored['stdout_tail']}",
            "Options:",
            *[f"{o['label']}. {o['text']}" for o in opts],
            "Answer:",
        ]
    )
    return {
        "row_id": row_id,
        "root_id": row_id,
        "root_lineage_key": f"stage12035::{probe['repo_family']}::{probe['selected_verifier_path']}::{probe['mutation_kind']}",
        "source_root_id": row_id,
        "source_bundle_id": row_id,
        "repo_id": probe["repo_family"],
        "repo_family": probe["repo_family"],
        "language_family": probe["language_family"],
        "task_type": "transition_verifier_transition",
        "split": "train",
        "split_role": "stage12035_semantic_transition_expansion_train_support_only",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "input_text": prompt,
        "prompt_text": prompt,
        "target_text": target_label,
        "decoder_text": target_label,
        "bounded_choice_target_label": target_label,
        "target": {"bounded_choice_target_label": target_label, "decoder_text": target_label, "semantic_value": semantic},
        "opaque_options": opts,
        "observed_verifier_transition": semantic,
        "semantic_mutation": {
            "mutation_kind": probe["mutation_kind"],
            "mutation_file": probe["mutation_file"],
            "baseline_returncode": baseline["returncode"],
            "mutant_returncode": mutant["returncode"],
            "restored_returncode": restored["returncode"],
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "singleton_options": False,
            "train_support_only": True,
        },
        "standalone_projection_source": {
            "projection_mode": "stage12035_semantic_transition_expansion_rows",
            "selected_verifier_path": probe["selected_verifier_path"],
            "observed_verifier_transition": semantic,
            "tool_or_verifier_observation": {
                "baseline": baseline,
                "mutant": mutant,
                "restored": restored,
                "configure": probe.get("configure"),
                "build_base": probe.get("build_base"),
                "build_mutant": probe.get("build_mutant"),
                "build_restored": probe.get("build_restored"),
                "timed_out": False,
            },
        },
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(PROBES.read_text())
    probes = payload["probes"]
    rows = [make_row(probe) for probe in probes if admissible(probe)]
    rejected = [
        {
            "language_family": probe["language_family"],
            "repo_family": probe["repo_family"],
            "selected_verifier_path": probe["selected_verifier_path"],
            "baseline_returncode": probe["baseline"]["returncode"],
            "mutant_returncode": probe["mutant"]["returncode"],
            "restored_returncode": probe["restored"]["returncode"],
        }
        for probe in probes
        if not admissible(probe)
    ]
    write_jsonl(ROWS, rows)
    summary = {
        "stage": "stage12035_semantic_transition_expansion_rows",
        "probe_results_path": str(PROBES),
        "rows_path": str(ROWS),
        "admitted_rows": len(rows),
        "unique_roots": len({r["root_lineage_key"] for r in rows}),
        "language_counts": dict(sorted(Counter(r["language_family"] for r in rows).items())),
        "status_counts": dict(sorted(Counter(r["observed_verifier_transition"] for r in rows).items())),
        "repo_family_counts": dict(sorted(Counter(r["repo_family"] for r in rows).items())),
        "rejected_probe_count": len(rejected),
        "rejected_probes": rejected,
        "decision": "admit_semantic_fail_to_pass_train_support",
        "claim_boundary": "Rows are train-support only. They prove real-source semantic transition mechanics, not model promotion.",
        "next_stage_recommendation": {
            "stage": "stage12036_transition_support_rollup_v25",
            "action": "Merge semantic FAIL_TO_PASS rows and report remaining Transition-Root-250 floors.",
        },
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARY_MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
