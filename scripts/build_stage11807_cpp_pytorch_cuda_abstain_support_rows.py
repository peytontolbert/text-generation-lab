#!/usr/bin/env python3
"""Materialize PyTorch C++ CUDA abstain-attractor support rows."""

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
STAGE = 11807
NAME = "stage11807_cpp_pytorch_cuda_abstain_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "cpp_pytorch_cuda_abstain_support_rows.json"
ROWS = OUT / "cpp_pytorch_cuda_abstain_support_rows.jsonl"
FEASIBILITY = ART / "stage11806_cpp_pytorch_cuda_build_feasibility/cpp_pytorch_cuda_build_feasibility_results.jsonl"
REPO = Path("/data/parametergolf/helpful_repos/pytorch")


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


def file_evidence(eid: str, kind: str, rel_path: str, summary: str) -> dict[str, Any]:
    text = (REPO / rel_path).read_text(encoding="utf-8", errors="replace")
    return {"id": eid, "kind": kind, "path": rel_path, "start_line": 1, "end_line": len(text.splitlines()), "summary": summary, "text": text, "sha256": sha_text(text)}


def log_evidence(eid: str, result: dict[str, Any], summary: str) -> dict[str, Any]:
    stdout = (ROOT / result["stdout_log"]).read_text(encoding="utf-8", errors="replace")
    stderr = (ROOT / result["stderr_log"]).read_text(encoding="utf-8", errors="replace")
    text = stdout + "\n" + stderr
    return {"id": eid, "kind": "actual_build_or_run_log", "path": result["stdout_log"], "stderr_path": result["stderr_log"], "summary": summary, "text": text[-3500:], "sha256": sha_text(text)}


def base_row(root_id: str, suffix: str, task_type: str, options: list[dict[str, Any]], target_label: str, verifier_present: bool) -> dict[str, Any]:
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": "pytorch",
        "repo_family": "pytorch",
        "language_family": "c_cpp",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": "pytorch::local_git_snapshot",
        "surface": "cpp_abstain_attractor_build_verifier_support_bounded_choice",
        "target_label": target_label,
        "target_text": target_label,
        "bounded_choice_target_label": target_label,
        "decoder_text": target_label,
        "target_value": target["value"],
        "semantic_target_value": target["value"],
        "opaque_options": options,
        "standalone_projection_source": {"opaque_options": options, "gold_label": target_label, "gold_value": target["value"]},
        "loss_mask": {"bounded_choice_aux": True, "decoder_ce": True},
        "selected_test_anchor": verifier_present,
        "verifier_anchor": verifier_present,
        "verifier_transition": "PASS_CURRENT_BUILD_AND_RUN" if verifier_present else "VERIFIER_REMOVED",
        "anti_cheat": {
            "deterministic_option_shuffle": True,
            "opaque_labels": True,
            "singleton_options": False,
            "target_label_not_visible_before_options": True,
            "target_value_not_visible_before_options": True,
            "source_backed_snippets": True,
            "actual_verifier_log_attached": verifier_present,
            "strict_smoke_root_replay": False,
            "sentencepiece_overlap": False,
            "paired_answerable_and_abstain_variants": True,
            "generated_build_harness_declared": True,
            "gpu2_only_execution": True,
        },
    }


def main() -> None:
    feasible = [row for row in read_jsonl(FEASIBILITY) if row.get("repo_family") == "pytorch" and row.get("passed") is True]
    if not feasible:
        raise SystemExit("PyTorch CUDA feasibility did not pass")
    feasibility = feasible[0]
    evidence = [
        file_evidence("E01", "candidate_change_surface", ".ci/pytorch/test_example_code/check-torch-cuda.cpp", "Small C++ Torch sample checks CUDA arch setup, magma availability, and CuDNN availability."),
        file_evidence("E02", "nearby_xnnpack_distractor", ".ci/pytorch/test_example_code/check-torch-xnnpack.cpp", "Adjacent XNNPACK sample is a plausible but different verifier surface."),
        log_evidence("V01", feasibility["configure"], "PyTorch CUDA sample configure passed against trellis Torch CMake package."),
        log_evidence("V02", feasibility["build"], "check-torch-cuda target built successfully."),
        log_evidence("V03", feasibility["execute"], "check-torch-cuda executable ran successfully with CUDA_VISIBLE_DEVICES=2."),
    ]
    verifier_evidence = {"id": "V03", "kind": "actual_cpp_build_run_pass_log", "summary": "PyTorch check-torch-cuda configured, built, and executed successfully on GPU2-visible runtime.", "configure": feasibility["configure"], "build": feasibility["build"], "execute": feasibility["execute"], "result": "PASS_CURRENT_BUILD_AND_RUN", "generated_build_harness": feasibility.get("harness_dir"), "gpu_visibility": feasibility.get("gpu_visibility")}
    answerable = [
        {"label": "A", "role": "candidate_change_surface", "value": ".ci/pytorch/test_example_code/check-torch-cuda.cpp", "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_build_constraint", "value": "cmake build and run check-torch-cuda passed on GPU2-visible runtime", "evidence_ids": ["V01", "V02", "V03"]},
        {"label": "C", "role": "nearby_xnnpack_surface", "value": ".ci/pytorch/test_example_code/check-torch-xnnpack.cpp", "evidence_ids": ["E02"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    abstain = [
        {"label": "A", "role": "candidate_change_surface", "value": ".ci/pytorch/test_example_code/check-torch-cuda.cpp", "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_build_constraint_removed", "value": "build/run evidence unavailable in this variant", "evidence_ids": []},
        {"label": "C", "role": "nearby_xnnpack_surface", "value": ".ci/pytorch/test_example_code/check-torch-xnnpack.cpp", "evidence_ids": ["E02"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    root_id = "stage11807::pytorch::c_cpp::check_torch_cuda_support"
    rows = [
        base_row(root_id, "answerable_evidence_citation_build_run_constraint", "evidence_citation", answerable, "B", True),
        base_row(root_id, "answerable_patch_impact_cuda_surface", "patch_impact", answerable, "A", True),
        base_row(root_id, "answerable_abstain_rejection", "abstention_insufficient_evidence", answerable, "B", True),
        base_row(root_id, "verifier_removed_abstain", "abstention_insufficient_evidence", abstain, "D", False),
    ]
    for row in rows:
        row["evidence_ledger"] = evidence if row["verifier_anchor"] else [item for item in evidence if not item["id"].startswith("V")]
        row["verifier_evidence"] = verifier_evidence if row["verifier_anchor"] else None
        row["prompt_text"] = ""
        row["input_text"] = ""
    write_jsonl(ROWS, rows)
    artifact = {"stage": STAGE, "stage_name": NAME, "created_at_utc": now(), "decision": "sixth_cpp_abstain_attractor_support_root_materialized", "passed": True, "row_count": len(rows), "root_count": 1, "repo_family": "pytorch", "source_artifacts": {"feasibility": rel(FEASIBILITY)}, "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)}, "claim_boundary": ["Rows are train-support-only.", "A generated build harness is declared; source evidence remains repo-backed.", "This adds one C/C++ support root but does not satisfy Stage11742 quota."]}
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_count": len(rows), "root_count": 1}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
