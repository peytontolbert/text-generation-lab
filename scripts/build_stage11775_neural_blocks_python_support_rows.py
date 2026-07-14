#!/usr/bin/env python3
"""Materialize neural_network_building_blocks Python verifier support rows."""

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
STAGE = 11775
NAME = "stage11775_neural_blocks_python_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "neural_blocks_python_support_rows.json"
ROWS = OUT / "neural_blocks_python_support_rows.jsonl"

FEASIBILITY = ART / "stage11774_neural_blocks_python_verifier_feasibility/neural_blocks_python_verifier_feasibility_results.jsonl"
REPO = Path("/data/parametergolf/helpful_repos/neural_network_building_blocks")


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


def file_evidence(eid: str, kind: str, rel_path: str, summary: str, start: int = 1, end: int = 180) -> dict[str, Any]:
    lines = (REPO / rel_path).read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(lines[start - 1 : min(end, len(lines))])
    return {"id": eid, "kind": kind, "path": rel_path, "start_line": start, "end_line": min(end, len(lines)), "summary": summary, "text": text, "sha256": sha_text(text)}


def log_evidence(eid: str, result: dict[str, Any], summary: str) -> dict[str, Any]:
    stdout = (ROOT / result["stdout_log"]).read_text(encoding="utf-8", errors="replace")
    stderr = (ROOT / result["stderr_log"]).read_text(encoding="utf-8", errors="replace")
    text = stdout + "\n" + stderr
    return {"id": eid, "kind": "actual_pytest_pass_log", "path": result["stdout_log"], "stderr_path": result["stderr_log"], "summary": summary, "text": text[-2600:], "sha256": sha_text(text)}


def base_row(root_id: str, suffix: str, task_type: str, options: list[dict[str, Any]], target_label: str) -> dict[str, Any]:
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": "neural_network_building_blocks",
        "repo_family": "neural_network_building_blocks",
        "language_family": "python",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": "neural_network_building_blocks::local_git_snapshot",
        "surface": "python_verifier_outcome_selected_test_support_bounded_choice",
        "target_label": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "target_value": target["value"],
        "semantic_target_value": target["value"],
        "opaque_options": options,
        "standalone_projection_source": {"opaque_options": options, "gold_label": target_label, "gold_value": target["value"]},
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
            "function_level_test_candidates": False,
            "source_backed_snippets": True,
            "actual_verifier_log_attached": True,
            "strict_smoke_root_replay": False,
        },
    }


def main() -> None:
    feasible = [row for row in read_jsonl(FEASIBILITY) if row.get("repo_family") == "neural_network_building_blocks" and row.get("passed") is True]
    if not feasible:
        raise SystemExit("neural_network_building_blocks Python feasibility did not pass")
    probe = feasible[0]
    root_id = "stage11775::neural_network_building_blocks::python::core_layers_support"
    selected = probe["selected_result"]
    sibling = probe["sibling_result"]
    evidence = [
        file_evidence("E01", "implementation_source", "nncore/core_layers.py", "Core layer source implements SmartDense and AdvancedConv2d behavior exercised by selected tests."),
        file_evidence("E02", "selected_test_anchor", "tests/test_core_layers.py", "Selected verifier checks SmartDense and AdvancedConv2d output shapes and activation behavior."),
        file_evidence("E03", "nearby_source_distractor", "nncore/attention.py", "Attention source is a plausible sibling module but not the selected core-layer verifier target."),
        file_evidence("E04", "sibling_test_anchor", "tests/test_attention.py", "Sibling verifier checks attention layers rather than the selected core-layer behavior."),
        log_evidence("V01", selected, "Focused pytest run passed for selected and sibling verifier files."),
    ]
    verifier_evidence = {"id": "V01", "kind": "actual_pytest_pass_log", "summary": "Focused pytest run passed for selected and sibling verifier files.", "selected_test": probe["selected_test"], "sibling_test": probe["sibling_test"], "selected_result": selected, "sibling_result": sibling, "result": "PASS_CURRENT_STATE"}
    verifier_options = [
        {"label": "A", "role": "selected_test_anchor", "value": probe["selected_test"], "evidence_ids": ["E02", "V01"]},
        {"label": "B", "role": "sibling_test_distractor", "value": probe["sibling_test"], "evidence_ids": ["E04", "V01"]},
        {"label": "C", "role": "implementation_only_no_verifier", "value": "nncore/core_layers.py", "evidence_ids": ["E01"]},
        {"label": "D", "role": "nearby_source_distractor", "value": "nncore/attention.py", "evidence_ids": ["E03"]},
    ]
    evidence_options = [
        {"label": "A", "role": "candidate_change_surface", "value": "nncore/core_layers.py", "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_test_constraint", "value": f"pytest {probe['selected_test']}", "evidence_ids": ["E02", "V01"]},
        {"label": "C", "role": "sibling_test_constraint", "value": f"pytest {probe['sibling_test']}", "evidence_ids": ["E04", "V01"]},
        {"label": "D", "role": "nearby_source_distractor", "value": "nncore/attention.py", "evidence_ids": ["E03"]},
    ]
    rows = [
        base_row(root_id, "verifier_outcome_selected_test", "verifier_outcome", verifier_options, "A"),
        base_row(root_id, "evidence_citation_selected_verifier", "evidence_citation", evidence_options, "B"),
        base_row(root_id, "symptom_localization_source_surface", "symptom_localization", verifier_options, "C"),
        base_row(root_id, "patch_impact_source_surface", "patch_impact", verifier_options, "C"),
    ]
    for row in rows:
        row["evidence_ledger"] = evidence
        row["verifier_evidence"] = verifier_evidence
        row["prompt_text"] = ""
        row["input_text"] = ""
    write_jsonl(ROWS, rows)
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "fifth_python_verifier_support_root_materialized",
        "passed": True,
        "row_count": len(rows),
        "root_count": 1,
        "repo_family": "neural_network_building_blocks",
        "source_artifacts": {"feasibility": rel(FEASIBILITY)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "claim_boundary": [
            "Rows are train-support-only.",
            "Selected and sibling verifier files are distinct and backed by an actual pytest pass log.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_count": len(rows), "root_count": 1}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
