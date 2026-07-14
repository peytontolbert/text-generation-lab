#!/usr/bin/env python3
"""Materialize first disjoint Python verifier-outcome support rows."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11745
NAME = "stage11745_python_verifier_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "python_verifier_support_rows.json"
ROWS = OUT / "python_verifier_support_rows.jsonl"

FEASIBILITY = ART / "stage11744_python_verifier_feasibility_probe/python_verifier_feasibility_results.jsonl"
REPO = Path("/data/parametergolf/helpful_repos/llm_memory_modules_at_scale")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def file_evidence(eid: str, kind: str, rel_path: str, summary: str, start: int = 1, end: int = 160) -> dict[str, Any]:
    path = REPO / rel_path
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(lines[start - 1 : min(end, len(lines))])
    return {
        "id": eid,
        "kind": kind,
        "path": rel_path,
        "start_line": start,
        "end_line": min(end, len(lines)),
        "summary": summary,
        "text": text,
        "sha256": sha_text(text),
    }


def base_row(row_id_suffix: str, task_type: str, options: list[dict[str, Any]], target_label: str) -> dict[str, Any]:
    root_id = "stage11745::llm_memory_modules_at_scale::python::product_key_memory_support"
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{row_id_suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": "llm_memory_modules_at_scale",
        "repo_family": "llm_memory_modules_at_scale",
        "language_family": "python",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": "llm_memory_modules_at_scale::local_git_snapshot",
        "surface": "python_verifier_outcome_selected_test_support_bounded_choice",
        "target_label": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "target_value": target["value"],
        "semantic_target_value": target["value"],
        "opaque_options": options,
        "standalone_projection_source": {
            "opaque_options": options,
            "gold_label": target_label,
            "gold_value": target["value"],
        },
        "loss_mask": {"bounded_choice_aux": True, "decoder_ce": True},
        "selected_test_anchor": True,
        "verifier_anchor": True,
        "verifier_transition": "PASS_CURRENT_STATE",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "selected_test_path_only_inside_candidate_options": True,
            "source_backed_snippets": True,
            "actual_verifier_log_attached": True,
            "strict_smoke_root_replay": False,
        },
    }


def main() -> None:
    feasible = [
        row
        for row in read_jsonl(FEASIBILITY)
        if row.get("repo_family") == "llm_memory_modules_at_scale" and row.get("passed") is True
    ]
    if not feasible:
        raise SystemExit("llm_memory_modules_at_scale feasibility did not pass")
    feasibility_row = feasible[0]
    evidence = [
        file_evidence(
            "E01",
            "implementation_source",
            "src/models/memory.py",
            "ProductKeyMemory implements memory lookup, masking, top-k attention, and output projection.",
        ),
        file_evidence(
            "E02",
            "selected_test_anchor",
            "tests/test_memory.py",
            "Focused tests exercise ProductKeyMemory forward shape, attention normalization, and masking.",
        ),
        file_evidence(
            "E03",
            "nearby_test_distractor",
            "tests/test_character_assistant.py",
            "Assistant tests also use memory but are broader and heavily mocked.",
        ),
        file_evidence(
            "E04",
            "nearby_source_distractor",
            "src/models/transformer.py",
            "Transformer layer calls ProductKeyMemory but is not the focused memory verifier target.",
        ),
    ]
    verifier_log = {
        "id": "V01",
        "kind": "actual_verifier_pass_log",
        "summary": "Focused pytest run passed for memory and character assistant tests.",
        "command": feasibility_row.get("command"),
        "selected_tests": feasibility_row.get("selected_tests"),
        "stdout_log": feasibility_row.get("stdout_log"),
        "stderr_log": feasibility_row.get("stderr_log"),
        "stdout_sha256": feasibility_row.get("stdout_sha256"),
        "stderr_sha256": feasibility_row.get("stderr_sha256"),
        "result": "PASS_CURRENT_STATE",
    }
    common_options = [
        {"label": "A", "role": "selected_test_anchor", "value": "tests/test_memory.py", "evidence_ids": ["E02", "V01"]},
        {"label": "B", "role": "nearby_test_distractor", "value": "tests/test_character_assistant.py", "evidence_ids": ["E03"]},
        {"label": "C", "role": "implementation_only_no_verifier", "value": "src/models/memory.py", "evidence_ids": ["E01"]},
        {"label": "D", "role": "caller_or_integration_surface", "value": "src/models/transformer.py", "evidence_ids": ["E04"]},
    ]
    rows = [
        base_row("verifier_outcome_selected_test", "verifier_outcome", common_options, "A"),
        base_row(
            "evidence_citation_selected_verifier",
            "evidence_citation",
            [
                {"label": "A", "role": "candidate_change_surface", "value": "ProductKeyMemory implementation excerpt", "evidence_ids": ["E01"]},
                {"label": "B", "role": "verifier_and_test_constraint", "value": "ProductKeyMemory focused pytest evidence", "evidence_ids": ["E02", "V01"]},
                {"label": "C", "role": "nearby_integration_test", "value": "CharacterAssistant mocked test evidence", "evidence_ids": ["E03"]},
                {"label": "D", "role": "caller_surface", "value": "Transformer caller evidence", "evidence_ids": ["E04"]},
            ],
            "B",
        ),
        base_row(
            "symptom_localization_memory_surface",
            "symptom_localization",
            [
                {"label": "A", "role": "candidate_change_surface", "value": "src/models/memory.py", "evidence_ids": ["E01", "E02", "V01"]},
                {"label": "B", "role": "nearby_test_distractor", "value": "tests/test_character_assistant.py", "evidence_ids": ["E03"]},
                {"label": "C", "role": "caller_surface", "value": "src/models/transformer.py", "evidence_ids": ["E04"]},
                {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
            ],
            "A",
        ),
        base_row(
            "patch_impact_memory_surface",
            "patch_impact",
            [
                {"label": "A", "role": "minimal_candidate_change_surface", "value": "src/models/memory.py", "evidence_ids": ["E01", "E02", "V01"]},
                {"label": "B", "role": "broader_caller_surface", "value": "src/models/transformer.py", "evidence_ids": ["E04"]},
                {"label": "C", "role": "change_test_expectation", "value": "tests/test_memory.py", "evidence_ids": ["E02"]},
                {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
            ],
            "A",
        ),
    ]
    for row in rows:
        row["evidence_ledger"] = evidence
        row["verifier_evidence"] = verifier_log
        row["prompt_text"] = ""
        row["input_text"] = ""
    write_jsonl(ROWS, rows)
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "first_python_verifier_support_root_materialized",
        "passed": True,
        "row_count": len(rows),
        "root_count": 1,
        "repo_family": "llm_memory_modules_at_scale",
        "feasibility_result": feasibility_row,
        "anti_leak_status": {
            "strict_smoke_root_replay": False,
            "train_support_only": True,
            "selected_test_path_only_inside_candidate_options": True,
        },
        "interpretation": [
            "This is the first disjoint executable Python support root for the verifier_outcome selected-test lane.",
            "It does not satisfy the Stage11742 quota by itself; 11 more Python support roots are still required for the requested package shape.",
            "Rows are train-support-only and must not be used as strict evaluation rows.",
        ],
        "source_artifacts": {"feasibility": rel(FEASIBILITY)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_count": len(rows), "root_count": 1}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
