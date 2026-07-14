#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11580
NAME = "stage11580_web_verifier_attached_admission_package"
OUT = ART / NAME
SUMMARY = OUT / "web_verifier_attached_admission_package.json"
ROWS_OUT = OUT / "web_verifier_attached_rows.jsonl"
ADMISSION_OUT = OUT / "web_verifier_attached_admission.jsonl"

ROWS = ART / "stage11577_web_candidate_review_packet_materializer/web_candidate_review_row_shells.jsonl"
VERIFIER = ART / "stage11579_web_focused_verifier_execution/web_focused_verifier_results.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or [])


def label_for_role(row: dict[str, Any], role: str) -> str | None:
    for opt in options(row):
        if opt.get("semantic_role") == role:
            return str(opt.get("label"))
    return None


def value_for_label(row: dict[str, Any], label: str | None) -> str | None:
    for opt in options(row):
        if str(opt.get("label")) == str(label):
            return str(opt.get("value"))
    return None


def scrub_prompt(row: dict[str, Any], verifier_result: dict[str, Any]) -> str:
    text = str(row.get("input_text") or row.get("prompt_text") or "")
    parts = text.split("Choices:\n", 1)
    choices = parts[1] if len(parts) == 2 else "\n".join(f"option {o['label']}: {o['text']}" for o in options(row))
    # Keep maintainer-visible code/test content, but remove path headers before choices.
    before = parts[0] if parts else text
    before = before.replace("Visible source evidence:", "Visible source evidence (opaque source IDs):")
    before = before.replace("Visible verifier/test evidence:", "Visible verifier/test evidence (opaque verifier IDs):")
    lines = []
    for line in before.splitlines():
        if line.endswith(":") and ("/" in line or line.endswith(".ts:") or line.endswith(".tsx:") or line.endswith(".js:") or line.endswith(".jsx:")):
            if "Visible " not in line and "Choices" not in line:
                continue
        lines.append(line)
    log_preview = str(verifier_result.get("output_preview") or "")[:900]
    lines.extend(
        [
            "Observed verifier transition:",
            f"status={verifier_result.get('status')} transition={verifier_result.get('verifier_transition')}",
            f"focused_command={' '.join(verifier_result.get('command') or [])}",
            "Verifier log excerpt:",
            log_preview,
            "Choices:",
            choices,
        ]
    )
    return "\n".join(lines)


def target_for(row: dict[str, Any], verifier_result: dict[str, Any]) -> tuple[str | None, str]:
    task = str(row.get("task_type") or "")
    if task in {"symptom_localization", "minimal_fix_selection"}:
        return label_for_role(row, "candidate_change_surface"), "verifier_attached_candidate_change_surface"
    if task in {"evidence_citation", "alternative_hypothesis_elimination", "verifier_outcome"}:
        return label_for_role(row, "verifier_and_test_constraint"), "verifier_attached_verifier_constraint"
    if task == "abstention_insufficient_evidence":
        # With a passing focused verifier log, abstention should not be selected.
        return label_for_role(row, "verifier_and_test_constraint"), "verifier_attached_answer_with_visible_evidence"
    return row.get("bounded_choice_target_label"), "unchanged"


def attach(row: dict[str, Any], verifier_result: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    label, gold_status = target_for(out, verifier_result)
    prompt = scrub_prompt(out, verifier_result)
    out["input_text"] = prompt
    out["prompt_text"] = prompt
    out["bounded_choice_target_label"] = label
    out["target_text"] = label
    out["decoder_text"] = label or ""
    out["semantic_target_value"] = value_for_label(out, label)
    out["gold_status"] = gold_status
    out["verifier_evidence"] = {
        "status": verifier_result.get("status"),
        "transition": verifier_result.get("verifier_transition"),
        "command": verifier_result.get("command"),
        "log_path": verifier_result.get("log_path"),
    }
    anti = dict(out.get("anti_cheat") or {})
    anti.update(
        {
            "observed_verifier_transition_present": True,
            "requires_prompt_target_leak_review_before_training": False,
            "path_headers_removed_before_options": True,
            "trainable_without_verifier_transition": False,
        }
    )
    out["anti_cheat"] = anti
    out["missing_for_admission"] = []
    split = str(out.get("split_component") or "")
    out["trainable_now"] = split == "train_candidate"
    out["strict_eval_eligible_now"] = split == "heldout_candidate"
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    verifier = {row["root_id"]: row for row in load_jsonl(VERIFIER) if row.get("status") == "verifier_executed_passed"}
    rows = load_jsonl(ROWS)
    attached: list[dict[str, Any]] = []
    admission: list[dict[str, Any]] = []
    for row in rows:
        root = row.get("root_id")
        vr = verifier.get(root)
        if not vr:
            admission.append({"row_id": row.get("row_id"), "root_id": root, "admitted": False, "blockers": ["missing_passing_verifier_log"]})
            continue
        new_row = attach(row, vr)
        attached.append(new_row)
        admission.append(
            {
                "row_id": new_row.get("row_id"),
                "root_id": root,
                "admitted": True,
                "trainable_now": new_row.get("trainable_now"),
                "strict_eval_eligible_now": new_row.get("strict_eval_eligible_now"),
                "blockers": [],
            }
        )
    metrics = {
        "source_rows": len(rows),
        "passing_verifier_roots": len(verifier),
        "attached_rows": len(attached),
        "trainable_rows": sum(1 for row in attached if row.get("trainable_now")),
        "strict_eval_eligible_rows": sum(1 for row in attached if row.get("strict_eval_eligible_now")),
        "attached_unique_roots": len({row.get("root_id") for row in attached}),
        "trainable_unique_roots": len({row.get("root_id") for row in attached if row.get("trainable_now")}),
        "strict_unique_roots": len({row.get("root_id") for row in attached if row.get("strict_eval_eligible_now")}),
        "rows_by_task": dict(Counter(str(row.get("task_type")) for row in attached)),
        "rows_by_split": dict(Counter(str(row.get("split_component")) for row in attached)),
        "rows_by_lane": dict(Counter(str(row.get("lane")) for row in attached)),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_verifier_attached_rows_ready_for_training_probe_gate",
        "metrics": metrics,
        "training_authorized_next": metrics["trainable_unique_roots"] >= 20,
        "strict_eval_authorized_next": metrics["strict_unique_roots"] >= 3,
        "claim_boundary": [
            "These rows use current-state PASS_TO_PASS verifier logs; they support verifier-grounded Web transition learning, not bug-fix proof.",
            "Paths are retained in options but removed from pre-option evidence headers to reduce target leakage.",
            "A training probe still must preserve Stage11507 canary/residual gates and improve Web heldout before promotion.",
        ],
        "source_artifacts": {"stage11577_rows": rel(ROWS), "stage11579_verifier": rel(VERIFIER)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS_OUT), "admission": rel(ADMISSION_OUT)},
    }
    write_jsonl(ROWS_OUT, attached)
    write_jsonl(ADMISSION_OUT, admission)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics, "training_authorized_next": summary["training_authorized_next"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
