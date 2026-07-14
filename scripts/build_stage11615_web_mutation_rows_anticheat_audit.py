#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11615
NAME = "stage11615_web_mutation_rows_anticheat_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_mutation_rows_anticheat_audit.json"
ADMITTED_ROWS = OUT / "web_mutation_rows_admitted_train_support.jsonl"
REJECTED_ROWS = OUT / "web_mutation_rows_rejected.jsonl"
ROWS = ART / "stage11614_web_mutation_fail_to_pass_rows/web_mutation_fail_to_pass_train_support_rows.jsonl"
PACKETS = ART / "stage11614_web_mutation_fail_to_pass_rows/web_mutation_fail_to_pass_root_packets.jsonl"

REQUIRED_TASKS = {
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "patch_impact",
    "abstention_insufficient_evidence",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    src = row.get("standalone_projection_source") if isinstance(row.get("standalone_projection_source"), dict) else {}
    return list(src.get("opaque_options") or [])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(ROWS)
    packets = load_jsonl(PACKETS)
    packet_by_root = {str(packet.get("root_id")): packet for packet in packets}
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    tasks_by_root: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        blockers: list[str] = []
        rid = str(row.get("root_id") or "")
        tasks_by_root[rid].add(str(row.get("task_type") or ""))
        opts = options(row)
        labels = [str(opt.get("label") or "") for opt in opts]
        values_before_choices = str(row.get("prompt_text") or "").split("Choices:", 1)[0]
        target_label = str(row.get("bounded_choice_target_label") or "")
        target_value = str(row.get("semantic_target_value") or "")
        anti = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
        packet = packet_by_root.get(rid, {})
        if row.get("source_kind") != "controlled_bug_injection_fail_to_pass":
            blockers.append("wrong_source_kind")
        if row.get("strict_eval_eligible_now") is not False:
            blockers.append("strict_eval_not_false")
        if not row.get("trainable_now"):
            blockers.append("not_trainable")
        if not opts or len(opts) < 3:
            blockers.append("insufficient_options")
        if len(labels) != len(set(labels)):
            blockers.append("duplicate_option_labels")
        if target_label not in labels:
            blockers.append("target_label_missing_from_options")
        if target_label and f"option {target_label}" in values_before_choices:
            blockers.append("target_label_visible_before_choices")
        if not anti.get("deterministic_option_shuffle"):
            blockers.append("deterministic_option_shuffle_missing")
        if not anti.get("opaque_labels"):
            blockers.append("opaque_labels_missing")
        if not anti.get("controlled_bug_injection_declared"):
            blockers.append("controlled_bug_injection_not_declared")
        if anti.get("restore_byte_exact") is not True:
            blockers.append("restore_proof_missing")
        if not (row.get("verifier_evidence") or {}).get("transition") == "FAIL_TO_PASS":
            blockers.append("missing_fail_to_pass_transition")
        if packet.get("restore_byte_exact") is not True:
            blockers.append("packet_restore_not_exact")
        if packet.get("original_sha256") != packet.get("restored_sha256"):
            blockers.append("packet_sha_mismatch")
        if target_value and row.get("task_type") == "abstention_insufficient_evidence" and row.get("semantic_target_role") == "abstain_insufficient_evidence":
            blockers.append("abstention_target_wrong_for_answerable_mutation")
        out = dict(row)
        out["stage11615_anticheat_blockers"] = blockers
        if blockers:
            rejected.append(out)
        else:
            out["stage11615_admitted_train_support"] = True
            admitted.append(out)
    root_task_gaps = {rid: sorted(REQUIRED_TASKS - tasks) for rid, tasks in tasks_by_root.items() if REQUIRED_TASKS - tasks}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "mutation_rows_admitted_for_train_support" if admitted and not root_task_gaps else "mutation_rows_blocked_or_incomplete",
        "input_rows": len(rows),
        "admitted_rows": len(admitted),
        "rejected_rows": len(rejected),
        "root_count": len(tasks_by_root),
        "complete_six_task_roots": sum(1 for tasks in tasks_by_root.values() if REQUIRED_TASKS <= tasks),
        "root_task_gaps": root_task_gaps,
        "admitted_by_task": dict(Counter(str(row.get("task_type")) for row in admitted)),
        "admitted_by_target_role": dict(Counter(str(row.get("semantic_target_role")) for row in admitted)),
        "blocker_counts": dict(Counter(blocker for row in rejected for blocker in row.get("stage11615_anticheat_blockers", []))),
        "claim_boundary": [
            "Admitted rows are controlled bug-injection train support only, not strict eval and not organic issue replay.",
            "Gold semantic values may appear in legitimate code/test/log evidence; the audit only forbids label leakage before choices and requires opaque shuffled labels.",
            "A promotion package must still evaluate on separate heldout Web roots and same-manifest Gemma.",
        ],
        "source_artifacts": {"rows": rel(ROWS), "packets": rel(PACKETS)},
        "outputs": {"summary": rel(SUMMARY), "admitted_rows": rel(ADMITTED_ROWS), "rejected_rows": rel(REJECTED_ROWS)},
    }
    write_jsonl(ADMITTED_ROWS, admitted)
    write_jsonl(REJECTED_ROWS, rejected)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "input_rows": summary["input_rows"],
        "admitted_rows": summary["admitted_rows"],
        "rejected_rows": summary["rejected_rows"],
        "complete_six_task_roots": summary["complete_six_task_roots"],
        "admitted_by_task": summary["admitted_by_task"],
        "admitted_by_target_role": summary["admitted_by_target_role"],
        "blocker_counts": summary["blocker_counts"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
