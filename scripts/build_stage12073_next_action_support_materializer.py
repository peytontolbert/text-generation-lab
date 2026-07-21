#!/usr/bin/env python3
"""Materialize next-action support rows from verifier-backed transition rows.

The v35 transition support package has broad verifier-status coverage but zero
transition_next_action rows.  This stage projects those verifier-backed rows
into explicit next-action decisions using the Stage12072 contract.  Rows are
train-support-only and not promotable eval rows.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 12073
STAGE_NAME = "stage12073_next_action_support_materializer"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / STAGE_NAME
SUMMARY_PATH = ROOT / "runs" / "summaries" / f"{STAGE_NAME}.json"

V35 = (
    ROOT
    / "runs/local/artifacts/stage12056_transition_support_rollup_v35"
    / "transition_support_rows_v35.jsonl"
)
DESIGN = ROOT / "runs/summaries/stage12072_next_action_support_design.json"

ACTION_VALUES = [
    "LOCALIZE_FAILURE",
    "RETRIEVE_EVIDENCE",
    "BIND_SYMBOL",
    "SELECT_TEST",
    "PLAN_PATCH",
    "APPLY_PATCH_ABSTRACT",
    "VERIFY_RESULT",
    "REPAIR_AFTER_FAILURE",
    "ABSTAIN_OR_ROLLBACK",
]

TARGET_QUOTAS = {
    "ABSTAIN_OR_ROLLBACK": 35,
    "SELECT_TEST": 35,
    "LOCALIZE_FAILURE": 30,
    "RETRIEVE_EVIDENCE": 30,
    "PLAN_PATCH": 25,
    "VERIFY_RESULT": 25,
    "REPAIR_AFTER_FAILURE": 20,
}

TARGET_STATUS_POOLS = {
    "ABSTAIN_OR_ROLLBACK": ["INSUFFICIENT_EVIDENCE"],
    "RETRIEVE_EVIDENCE": ["INSUFFICIENT_EVIDENCE", "PASS_CURRENT_BUILD"],
    "SELECT_TEST": ["NOT_EXERCISED", "PASS_CURRENT_BUILD"],
    "LOCALIZE_FAILURE": ["FAIL_TO_PASS"],
    "PLAN_PATCH": ["FAIL_TO_PASS", "PASS_TO_PASS"],
    "VERIFY_RESULT": ["PASS_TO_PASS", "PASS_CURRENT_BUILD_AND_RUN"],
    "REPAIR_AFTER_FAILURE": ["FAIL_TO_PASS"],
}

TARGET_PHASE = {
    "ABSTAIN_OR_ROLLBACK": {
        "phase_code": "completion_gate_blocked",
        "state_text": "The current evidence does not justify a safe forward edit or completion claim.",
        "expected_artifact": "blocked_or_rollback_decision",
    },
    "RETRIEVE_EVIDENCE": {
        "phase_code": "evidence_gap_before_action",
        "state_text": "The current packet lacks enough source/verifier detail to choose a concrete edit or final verifier action.",
        "expected_artifact": "additional_relevant_evidence",
    },
    "SELECT_TEST": {
        "phase_code": "verifier_not_yet_exercising_target",
        "state_text": "The current command evidence is not yet the focused behavioral verifier for the target path.",
        "expected_artifact": "focused_verifier_selection",
    },
    "LOCALIZE_FAILURE": {
        "phase_code": "failure_observed_location_unknown",
        "state_text": "A failure/transition is visible, but the precise source or call path still needs localization.",
        "expected_artifact": "localized_source_or_call_path",
    },
    "PLAN_PATCH": {
        "phase_code": "localized_evidence_ready_for_patch_plan",
        "state_text": "The relevant source and verifier context are available enough to form a bounded repair plan.",
        "expected_artifact": "bounded_patch_plan",
    },
    "VERIFY_RESULT": {
        "phase_code": "verifier_result_needs_interpretation",
        "state_text": "A local verifier result is available and should be interpreted against the task contract.",
        "expected_artifact": "verifier_result_judgment",
    },
    "REPAIR_AFTER_FAILURE": {
        "phase_code": "failed_attempt_requires_repair",
        "state_text": "The observed result indicates the current attempt did not satisfy the verifier and needs targeted repair.",
        "expected_artifact": "repair_after_failed_verifier",
    },
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def stable_hash(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def observed_status(row: dict[str, Any]) -> str:
    return (
        (row.get("target") or {}).get("semantic_value")
        or row.get("standalone_projection_source", {}).get("observed_verifier_transition")
        or "UNKNOWN"
    )


def verifier_path(row: dict[str, Any]) -> str:
    src = row.get("standalone_projection_source") or {}
    return src.get("selected_verifier_path") or "unknown_verifier"


def verifier_observation(row: dict[str, Any]) -> dict[str, Any]:
    return (row.get("standalone_projection_source") or {}).get("tool_or_verifier_observation") or {}


def root_id(row: dict[str, Any]) -> str:
    base = row.get("root_id")
    if base:
        return base
    repo = (row.get("repo_id") or "unknown_repo").replace("/", "__")
    return f"stage12073::{repo}::{stable_hash(row.get('row_id', repo), 10)}"


def repo_family(row: dict[str, Any]) -> str:
    return row.get("repo_id") or root_id(row).split("::")[1]


def shuffled_options(row_id: str, target_value: str) -> tuple[list[dict[str, Any]], str]:
    values = list(ACTION_VALUES)
    seed = int(stable_hash(row_id + "::option_shuffle", 16), 16)
    rng = random.Random(seed)
    rng.shuffle(values)
    labels = list("ABCDEFGHI")
    opts = [
        {
            "label": label,
            "role": "allowed_maintenance_action",
            "artifact_type": "action",
            "value": value,
            "evidence_ids": [],
        }
        for label, value in zip(labels, values)
    ]
    target_label = next(opt["label"] for opt in opts if opt["value"] == target_value)
    return opts, target_label


def render_prompt(row: dict[str, Any], materialized: dict[str, Any], options: list[dict[str, Any]]) -> str:
    obs = verifier_observation(row)
    command = obs.get("command")
    if isinstance(command, list):
        command_text = " ".join(str(x) for x in command)
    else:
        command_text = str(command or "unknown")
    stdout_tail = (obs.get("stdout_tail") or "").strip()
    stderr_tail = (obs.get("stderr_tail") or "").strip()
    if len(stdout_tail) > 500:
        stdout_tail = stdout_tail[-500:]
    if len(stderr_tail) > 500:
        stderr_tail = stderr_tail[-500:]

    option_lines = [
        f"{opt['label']}: role={opt['role']}; artifact_type={opt['artifact_type']}; value={opt['value']}"
        for opt in options
    ]
    phase = materialized["milestone_state"]
    return "\n".join(
        [
            "TASK",
            f"language: {materialized['language_family']}",
            f"root_id: {materialized['root_id']}",
            "task_family: transition_next_action",
            "projection: next_action",
            "instruction: choose the next useful maintainer action using only the state and evidence below.",
            "",
            "MILESTONE_STATE",
            f"phase_code: {phase['phase_code']}",
            f"state_summary: {phase['state_text']}",
            f"expected_artifact_kind: {phase['expected_artifact']}",
            "",
            "OBSERVED_STATE",
            f"repo_family: {repo_family(row)}",
            f"selected_verifier_path: {verifier_path(row)}",
            f"observed_status: {materialized['observed_status']}",
            "",
            "SOURCE_EVIDENCE",
            f"source_ref: {materialized['visible_source_evidence']['source_ref']}",
            f"source_note: {materialized['visible_source_evidence']['source_note']}",
            "",
            "VERIFIER_EVIDENCE",
            f"verifier_ref: {materialized['visible_verifier_evidence']['verifier_ref']}",
            f"command: {command_text}",
            f"returncode: {obs.get('returncode', 'unknown')}",
            f"stdout_tail: {stdout_tail or '[empty]'}",
            f"stderr_tail: {stderr_tail or '[empty]'}",
            "",
            "CANDIDATES",
            *option_lines,
            "",
            "QUESTION",
            "Return only the option label.",
        ]
    )


def choose_sources(
    rows: list[dict[str, Any]],
    target_value: str,
    quota: int,
    repo_materialized_counts: Counter,
    repo_cap: int,
) -> list[dict[str, Any]]:
    statuses = set(TARGET_STATUS_POOLS[target_value])
    pool = [r for r in rows if observed_status(r) in statuses]
    if not pool:
        return []
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in sorted(pool, key=lambda x: (x.get("language_family") or "", repo_family(x), x.get("row_id") or "")):
        by_lang[r.get("language_family") or "unknown"].append(r)

    selected: list[dict[str, Any]] = []
    lang_order = ["python", "c_cpp", "rust", "web_js_ts_html"]
    idx = defaultdict(int)
    while len(selected) < quota:
        progressed = False
        for lang in lang_order:
            items = by_lang.get(lang) or []
            if not items:
                continue
            item = items[idx[lang] % len(items)]
            idx[lang] += 1
            repo = repo_family(item)
            if repo_materialized_counts[repo] >= repo_cap:
                # Still advance the language cursor so a capped dominant repo
                # cannot block later roots from the same language.
                continue
            selected.append(item)
            repo_materialized_counts[repo] += 1
            progressed = True
            if len(selected) >= quota:
                break
        if not progressed:
            break
    return selected[:quota]


def materialize_row(source: dict[str, Any], target_value: str, ordinal: int) -> dict[str, Any]:
    base_row_id = source.get("row_id") or stable_hash(json.dumps(source, sort_keys=True))
    rid = f"stage12073::{stable_hash(base_row_id + '::' + target_value + '::' + str(ordinal), 16)}::{target_value.lower()}::next_action"
    opts, target_label = shuffled_options(rid, target_value)
    rid_root = root_id(source)
    phase = dict(TARGET_PHASE[target_value])
    obs_status = observed_status(source)
    selected_path = verifier_path(source)
    source_ref = source.get("row_id") or rid_root
    materialized = {
        "row_id": rid,
        "root_id": f"{rid_root}::next_action::{target_value.lower()}::{ordinal}",
        "root_lineage_key": rid_root,
        "repo_id": source.get("repo_id"),
        "language_family": source.get("language_family"),
        "task_type": "transition_next_action",
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "stage12073_next_action_support": True,
        "stage12073_source_row_id": source.get("row_id"),
        "stage12073_source_observed_status": obs_status,
        "milestone_state": phase,
        "observed_status": obs_status,
        "selected_test_anchor": {
            "path": selected_path,
            "source": "stage12056_v35_verifier_support",
            "present": selected_path != "unknown_verifier",
        },
        "visible_source_evidence": {
            "source_ref": source_ref,
            "source_note": "verifier-backed transition support row from v35; source content is represented through repo/verifier lineage",
        },
        "visible_verifier_evidence": {
            "verifier_ref": "V01",
            "selected_verifier_path": selected_path,
            "observed_status": obs_status,
            "observation": verifier_observation(source),
        },
        "opaque_options": opts,
        "standalone_projection_source": {
            "projection": "next_action",
            "projection_mode": "stage12073_verifier_backed_next_action_projection_v1",
            "source_record_id": source.get("row_id"),
            "transition_record_schema": "verified_transition_record_v1",
            "gold_label": target_label,
            "gold_value": target_value,
            "observed_verifier_transition": obs_status,
            "selected_verifier_path": selected_path,
            "opaque_options": opts,
        },
        "target": {
            "bounded_choice_target_label": target_label,
            "decoder_text": target_label,
            "semantic_value": target_value,
        },
        "target_label": target_label,
        "bounded_choice_target_label": target_label,
        "target_text": target_label,
        "decoder_text": target_label,
        "loss_mask": {
            "bounded_choice_aux": True,
            "decoder_ce": True,
            "structured_aux": True,
            "transition_projection": True,
        },
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "target_label_not_visible_before_options": True,
            "candidate_values_not_order_shortcut": True,
            "no_postfix_source_in_preaction_state": True,
            "root_split_isolated": True,
            "not_promotable_eval_row": True,
            "projection_from_verified_transition_record": True,
        },
    }
    text = render_prompt(source, materialized, opts)
    materialized["input_text"] = text
    materialized["prompt_text"] = text
    return materialized


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    root_count = len({r["root_id"] for r in rows})
    lineage_count = len({r["root_lineage_key"] for r in rows})
    lang_roots: dict[str, set[str]] = defaultdict(set)
    repo_counts = Counter()
    target_counts = Counter()
    status_counts = Counter()
    leak_rows = []
    option_mirror_missing = []
    singleton_rows = []
    for r in rows:
        lang_roots[r["language_family"]].add(r["root_id"])
        repo_counts[r["repo_id"]] += 1
        target = r["target"]["semantic_value"]
        target_counts[target] += 1
        status_counts[r["observed_status"]] += 1
        before_options = r["input_text"].split("CANDIDATES", 1)[0]
        # Do not scan for the one-character opaque label directly; natural
        # prose contains A/B/C/etc.  The materialized prompt must not expose the
        # semantic target value before CANDIDATES.
        if target in before_options:
            leak_rows.append(r["row_id"])
        if not r.get("standalone_projection_source", {}).get("opaque_options"):
            option_mirror_missing.append(r["row_id"])
        if len(r.get("opaque_options") or []) <= 1:
            singleton_rows.append(r["row_id"])
    repo_cap = max(15, int(row_count * 0.10))
    repo_cap_violations = {k: v for k, v in repo_counts.items() if v > repo_cap}
    return {
        "rows": row_count,
        "unique_roots": root_count,
        "unique_lineage_roots": lineage_count,
        "target_counts": dict(target_counts),
        "observed_status_counts": dict(status_counts),
        "language_root_counts": {k: len(v) for k, v in lang_roots.items()},
        "language_row_counts": dict(Counter(r["language_family"] for r in rows)),
        "repo_family_cap": repo_cap,
        "repo_family_cap_violations": repo_cap_violations,
        "prompt_target_leak_rows": leak_rows[:20],
        "prompt_target_leak_count": len(leak_rows),
        "option_mirror_missing_count": len(option_mirror_missing),
        "singleton_option_count": len(singleton_rows),
        "passes_minimum_training_gate": (
            row_count >= 200
            and root_count >= 80
            and all(target_counts.get(k, 0) >= v for k, v in TARGET_QUOTAS.items())
            and all(len(lang_roots.get(k, set())) >= 15 for k in ["python", "c_cpp", "rust", "web_js_ts_html"])
            and not repo_cap_violations
            and not leak_rows
            and not option_mirror_missing
            and not singleton_rows
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    design = read_json(DESIGN)
    source_rows = list(iter_jsonl(V35))

    materialized: list[dict[str, Any]] = []
    ordinal = 0
    repo_cap = max(15, int(sum(TARGET_QUOTAS.values()) * 0.10))
    repo_materialized_counts: Counter = Counter()
    for target, quota in TARGET_QUOTAS.items():
        for source in choose_sources(source_rows, target, quota, repo_materialized_counts, repo_cap):
            ordinal += 1
            materialized.append(materialize_row(source, target, ordinal))

    rows_path = OUT_DIR / "next_action_support_rows.jsonl"
    with rows_path.open("w", encoding="utf-8") as f:
        for row in materialized:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    audit = audit_rows(materialized)
    summary = {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "materialized_next_action_support_train_rows_no_training_launched",
        "source_artifacts": {
            "design": str(DESIGN.relative_to(ROOT)),
            "v35_support": str(V35.relative_to(ROOT)),
        },
        "design_minimums": design["support_construction_contract"],
        "audit": audit,
        "next_recommendation": {
            "if_gate_passes": "build stage12074 next-action support rollup/probe request with protected replay, then train only if command preserves GPU2 mask",
            "if_gate_fails": "repair materializer/admission gaps before any training",
            "training_probe_goal": "old transition >364/640, protected compact gates preserved, residual >=7/10; Gemma win requires >386/640",
        },
        "outputs": {
            "rows": str(rows_path.relative_to(ROOT)),
            "summary": str((OUT_DIR / "next_action_support_materialization_summary.json").relative_to(ROOT)),
            "summary_mirror": str(SUMMARY_PATH.relative_to(ROOT)),
        },
    }

    summary_path = OUT_DIR / "next_action_support_materialization_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
