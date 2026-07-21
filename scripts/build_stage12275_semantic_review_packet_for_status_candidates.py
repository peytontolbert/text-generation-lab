#!/usr/bin/env python3
"""Build Stage12275 semantic review packet for status candidates."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12275_semantic_review_packet_for_status_candidates"
INP = ROOT / "runs/local/artifacts/stage12274_status_join_for_root_repaired_child_loops/status_joined_child_loop_candidates.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY = ROOT / f"runs/summaries/{STAGE}.json"

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line=line.strip()
            if line:
                yield json.loads(line)

def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n", encoding="utf-8")

def write_jsonl(path: Path, rows: list[dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True)+"\n")

def main() -> int:
    packets=[]
    for r in iter_jsonl(INP):
        sj=r.get("status_join") or {}
        if sj.get("status_class") != "FAIL_TO_PASS_STATUS_CANDIDATE":
            continue
        packets.append({
            "schema_version":"semantic_review_packet_v1",
            "stage":STAGE,
            "child_loop_id":r.get("child_loop_id"),
            "horizon_bucket":r.get("horizon_bucket"),
            "source_refs":r.get("source_refs"),
            "root_recovery":r.get("root_recovery"),
            "lineage":r.get("lineage"),
            "child_span_refs":r.get("child_span_refs"),
            "patch_ref":r.get("patch_ref"),
            "pre_verifier_statuses":sj.get("pre_verifier_statuses"),
            "post_verifier_statuses":sj.get("post_verifier_statuses"),
            "status_join":{
                "observed_pre_patch_failure":sj.get("observed_pre_patch_failure"),
                "observed_post_patch_pass":sj.get("observed_post_patch_pass"),
                "post_patch_failure_remains":sj.get("post_patch_failure_remains"),
                "same_verifier_pre_post_by_command_head":sj.get("same_verifier_pre_post_by_command_head"),
                "status_class":sj.get("status_class"),
            },
            "review_questions":[
                "Does the selected patch semantically target the failing verifier behavior?",
                "Are pre/post verifier commands equivalent enough to count as same verifier?",
                "Is the failure from code under repair rather than env/dependency/tooling?",
                "Does any post verifier failure remain for the same verifier family?",
                "Should this be admitted as external comparable repair, train-support only, split-required, or quarantine?",
            ],
            "allowed_review_labels":[
                "ADMIT_EXTERNAL_COMPARABLE_REPAIR",
                "ADMIT_TRAIN_SUPPORT_ONLY",
                "SPLIT_REQUIRED",
                "QUARANTINE_SEMANTIC_MISMATCH",
                "QUARANTINE_ENV_OR_TOOLING",
                "QUARANTINE_PRIOR_PATCH_ATTACHMENT",
                "QUARANTINE_INSUFFICIENT_EVIDENCE",
            ],
            "guardrails":{"raw_output_emitted":False,"raw_patch_body_emitted":False,"raw_tool_arguments_emitted":False,"raw_source_path_emitted":False},
        })
    counts=Counter((p.get("root_recovery") or {}).get("repo_family_label") for p in packets)
    summary={
        "stage":STAGE,
        "decision":"semantic_review_packet_ready_no_admission_training_blocked",
        "input_status_candidates":len(packets),
        "repo_family_counts":dict(counts),
        "training_rows_emitted":0,
        "admitted_rows":0,
        "next_stage":"stage12276_semantic_review_result_ingest",
    }
    write_jsonl(OUT_DIR/"semantic_review_packets.jsonl", packets)
    write_json(OUT_DIR/"semantic_review_packet_summary.json", summary)
    write_json(SUMMARY, summary)
    (OUT_DIR/"SEMANTIC_REVIEW_PACKET_STAGE12275.md").write_text("# Stage12275 Semantic Review Packet\n\n"+json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
