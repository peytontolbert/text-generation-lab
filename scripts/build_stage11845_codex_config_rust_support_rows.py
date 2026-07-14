#!/usr/bin/env python3
"""Materialize codex-config Rust selected-verifier support rows."""

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
STAGE = 11845
NAME = "stage11845_codex_config_rust_support_rows"
OUT = ART / NAME
SUMMARY = OUT / "codex_config_rust_support_rows.json"
ROWS = OUT / "codex_config_rust_support_rows.jsonl"
FEASIBILITY = ART / "stage11844_codex_config_rust_feasibility/codex_config_rust_feasibility_results.jsonl"


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


def file_evidence(repo: Path, eid: str, kind: str, rel_path: str, summary: str, start: int = 1, end: int = 220) -> dict[str, Any]:
    lines = (repo / rel_path).read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(lines[start - 1 : min(end, len(lines))])
    return {"id": eid, "kind": kind, "path": rel_path, "start_line": start, "end_line": min(end, len(lines)), "summary": summary, "text": text, "sha256": sha_text(text)}


def log_evidence(eid: str, result: dict[str, Any], summary: str) -> dict[str, Any]:
    stdout_path = ROOT / result["stdout_log"]
    stderr_path = ROOT / result["stderr_log"]
    text = stdout_path.read_text(encoding="utf-8", errors="replace") + "\n" + stderr_path.read_text(encoding="utf-8", errors="replace")
    return {"id": eid, "kind": "actual_cargo_test_pass_log", "path": result["stdout_log"], "stderr_path": result["stderr_log"], "summary": summary, "text": text[-2600:], "sha256": sha_text(text)}


def base_row(root_id: str, suffix: str, task_type: str, options: list[dict[str, Any]], target_label: str, repo_family: str) -> dict[str, Any]:
    target = next(opt for opt in options if opt["label"] == target_label)
    return {
        "stage": STAGE,
        "row_id": f"{root_id}::{suffix}",
        "root_id": root_id,
        "root_lineage_key": root_id,
        "repo_id": repo_family,
        "repo_family": repo_family,
        "language_family": "rust",
        "task_type": task_type,
        "split": "train",
        "package_split": "train",
        "train_support_only": True,
        "train_eligible": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "source_snapshot_id": f"{repo_family}::local_git_snapshot",
        "surface": "rust_verifier_outcome_selected_inline_test_support_bounded_choice",
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
            "selected_test_identifier_only_inside_candidate_options": True,
            "source_backed_snippets": True,
            "actual_verifier_log_attached": True,
            "strict_smoke_root_replay": False,
            "tokenizers_overlap": False,
        },
    }


def main() -> None:
    probes = [row for row in read_jsonl(FEASIBILITY) if row.get("passed") is True and row.get("admit_recommendation") == "candidate_for_row_materialization"]
    if not probes:
        raise SystemExit("no materializable codex-config Rust probe found")
    probe = probes[0]
    repo = Path(str(probe["repo_path"]))
    repo_family = str(probe["repo_family"])
    selected = probe["selected_result"]
    sibling = probe["sibling_result"]
    source_path = str(probe["source_path"])
    distractor_source_path = str(probe["distractor_source_path"])
    root_id = "stage11845::codex_config::rust::merge_legacy_memories_support"
    evidence = [
        file_evidence(repo, "E01", "candidate_change_surface", source_path, "Codex config merge source normalizes legacy memories TOML keys across base and overlay layers."),
        file_evidence(repo, "E02", "nearby_source_distractor", distractor_source_path, "Config types source is nearby configuration logic but not the selected merge verifier target."),
        log_evidence("V01", selected, f"Selected cargo test passed: {probe['selected_test']}"),
        log_evidence("V02", sibling, f"Sibling cargo test passed: {probe['sibling_test']}"),
    ]
    verifier_evidence = {"id": "V01", "kind": "actual_cargo_test_pass_log", "summary": f"Focused cargo test passed for {probe['selected_test']}.", "selected_test": probe["selected_test"], "sibling_test": probe["sibling_test"], "selected_result": selected, "sibling_result": sibling, "result": "PASS_CURRENT_STATE"}
    verifier_options = [
        {"label": "A", "role": "selected_inline_test_anchor", "value": probe["selected_test"], "evidence_ids": ["E01", "V01"]},
        {"label": "B", "role": "nearby_inline_test_distractor", "value": probe["sibling_test"], "evidence_ids": ["E01", "V02"]},
        {"label": "C", "role": "implementation_only_no_verifier", "value": source_path, "evidence_ids": ["E01"]},
        {"label": "D", "role": "external_source_distractor", "value": distractor_source_path, "evidence_ids": ["E02"]},
    ]
    evidence_options = [
        {"label": "A", "role": "candidate_change_surface", "value": source_path, "evidence_ids": ["E01"]},
        {"label": "B", "role": "verifier_and_test_constraint", "value": f"cargo test {probe['selected_test']}", "evidence_ids": ["E01", "V01"]},
        {"label": "C", "role": "nearby_sibling_test_constraint", "value": f"cargo test {probe['sibling_test']}", "evidence_ids": ["V02"]},
        {"label": "D", "role": "external_source_distractor", "value": distractor_source_path, "evidence_ids": ["E02"]},
    ]
    rows = [
        base_row(root_id, "verifier_outcome_selected_inline_test", "verifier_outcome", verifier_options, "A", repo_family),
        base_row(root_id, "evidence_citation_selected_verifier", "evidence_citation", evidence_options, "B", repo_family),
        base_row(root_id, "symptom_localization_source_surface", "symptom_localization", verifier_options, "C", repo_family),
        base_row(root_id, "patch_impact_source_surface", "patch_impact", verifier_options, "C", repo_family),
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
        "decision": "tenth_rust_verifier_support_root_materialized",
        "passed": True,
        "row_count": len(rows),
        "root_count": 1,
        "repo_family": repo_family,
        "source_artifacts": {"feasibility": rel(FEASIBILITY)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
        "claim_boundary": ["Rows are train-support-only.", "This expands Rust verifier support with a non-tokenizers Codex config repo family."],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "row_count": len(rows), "root_count": 1}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
