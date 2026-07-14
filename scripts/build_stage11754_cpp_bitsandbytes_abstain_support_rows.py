#!/usr/bin/env python3
"""Materialize C/C++ abstain-attractor support rows from bitsandbytes build evidence."""

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
STAGE = 11754
NAME = "stage11754_cpp_bitsandbytes_abstain_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "cpp_bitsandbytes_abstain_support_rows.json"
ROWS = OUT / "cpp_bitsandbytes_abstain_support_rows.jsonl"

FEASIBILITY = ART / "stage11753_cpp_bitsandbytes_build_feasibility/cpp_bitsandbytes_build_feasibility_results.jsonl"
REPO = Path("/data/parametergolf/helpful_repos/bitsandbytes")


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


def log_evidence(eid: str, kind: str, log_path: str, summary: str) -> dict[str, Any]:
    path = ROOT / log_path
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "id": eid,
        "kind": kind,
        "path": log_path,
        "summary": summary,
        "text": text[-3500:],
        "sha256": sha_text(text),
    }


def base_row(
    row_id_suffix: str,
    task_type: str,
    options: list[dict[str, Any]],
    target_label: str,
    verifier_present: bool,
) -> dict[str, Any]:
    root_id = "stage11754::bitsandbytes::c_cpp::cpu_build_support"
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{row_id_suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": "bitsandbytes",
        "repo_family": "bitsandbytes",
        "language_family": "c_cpp",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": "bitsandbytes::local_git_snapshot",
        "surface": "cpp_abstain_attractor_build_verifier_support_bounded_choice",
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
        "selected_test_anchor": verifier_present,
        "verifier_anchor": verifier_present,
        "verifier_transition": "PASS_CURRENT_BUILD" if verifier_present else "VERIFIER_REMOVED",
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
        },
    }


def main() -> None:
    feasible = [
        row
        for row in read_jsonl(FEASIBILITY)
        if row.get("repo_family") == "bitsandbytes"
        and row.get("passed") is True
        and row.get("admit_recommendation") == "candidate_for_row_materialization"
    ]
    if not feasible:
        raise SystemExit("bitsandbytes build feasibility did not pass")
    feasibility = feasible[0]
    configure = feasibility["configure"]
    build = feasibility["build"]
    evidence = [
        file_evidence(
            "E01",
            "candidate_change_surface",
            "csrc/cpu_ops.cpp",
            "CPU quantize/dequantize operations are the C++ implementation surface built by the CPU backend.",
        ),
        file_evidence(
            "E02",
            "candidate_change_surface",
            "csrc/common.cpp",
            "Shared quantization block logic supports the CPU ops surface.",
        ),
        file_evidence(
            "E03",
            "build_target_constraint",
            "CMakeLists.txt",
            "CMake defines the CPU backend and shared bitsandbytes target from C++ sources.",
            start=1,
            end=90,
        ),
        file_evidence(
            "E04",
            "nearby_backend_distractor",
            "csrc/pythonInterface.cpp",
            "Python extension interface is adjacent but not the minimal CPU kernel surface.",
        ),
        log_evidence(
            "V01",
            "configure_log",
            configure["stdout_log"],
            "CMake configured bitsandbytes with COMPUTE_BACKEND=cpu.",
        ),
        log_evidence(
            "V02",
            "build_log",
            build["stdout_log"],
            "CMake built the bitsandbytes CPU shared library successfully.",
        ),
    ]
    verifier_evidence = {
        "id": "V02",
        "kind": "actual_cpp_build_pass_log",
        "summary": "CPU-only CMake build passed and built target bitsandbytes.",
        "configure": configure,
        "build": build,
        "selected_verifier": feasibility.get("selected_verifier"),
        "result": "PASS_CURRENT_BUILD",
    }
    answerable_options = [
        {"label": "A", "role": "candidate_change_surface", "value": "csrc/cpu_ops.cpp", "evidence_ids": ["E01", "E02"]},
        {"label": "B", "role": "verifier_and_build_constraint", "value": "cmake cpu build passed for bitsandbytes target", "evidence_ids": ["E03", "V01", "V02"]},
        {"label": "C", "role": "nearby_interface_surface", "value": "csrc/pythonInterface.cpp", "evidence_ids": ["E04"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    abstain_options = [
        {"label": "A", "role": "candidate_change_surface", "value": "csrc/cpu_ops.cpp", "evidence_ids": ["E01", "E02"]},
        {"label": "B", "role": "verifier_and_build_constraint_removed", "value": "build evidence unavailable in this variant", "evidence_ids": []},
        {"label": "C", "role": "nearby_interface_surface", "value": "csrc/pythonInterface.cpp", "evidence_ids": ["E04"]},
        {"label": "D", "role": "abstain_insufficient_evidence", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE", "evidence_ids": []},
    ]
    rows = [
        base_row("answerable_evidence_citation_build_constraint", "evidence_citation", answerable_options, "B", True),
        base_row("answerable_patch_impact_cpu_surface", "patch_impact", answerable_options, "A", True),
        base_row("answerable_abstain_rejection", "abstention_insufficient_evidence", answerable_options, "B", True),
        base_row("verifier_removed_abstain", "abstention_insufficient_evidence", abstain_options, "D", False),
    ]
    for row in rows:
        visible_evidence = evidence if row["verifier_anchor"] else [item for item in evidence if not item["id"].startswith("V")]
        row["evidence_ledger"] = visible_evidence
        row["verifier_evidence"] = verifier_evidence if row["verifier_anchor"] else None
        row["prompt_text"] = ""
        row["input_text"] = ""

    write_jsonl(ROWS, rows)
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "first_cpp_abstain_attractor_support_root_materialized",
        "passed": True,
        "row_count": len(rows),
        "root_count": 1,
        "repo_family": "bitsandbytes",
        "feasibility_result": feasibility,
        "anti_leak_status": {
            "strict_smoke_root_replay": False,
            "train_support_only": True,
            "sentencepiece_overlap": False,
            "paired_answerable_and_abstain_variants": True,
        },
        "interpretation": [
            "This is the first executable C/C++ support root for the abstain-attractor lane.",
            "It includes paired answerable and verifier-removed abstention variants.",
            "Rows are train-support-only and do not satisfy the full Stage11742 C/C++ quota by themselves.",
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
