#!/usr/bin/env python3
"""Build Stage12276 semantic review result ingest.

Ingests the bounded Stage12275 semantic review decisions supplied by the review
agent. Emits train-support candidates only; no strict/source-heldout/external
comparable repair rows are admitted.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12276_semantic_review_result_ingest"
PACKETS = ROOT / "runs/local/artifacts/stage12275_semantic_review_packet_for_status_candidates/semantic_review_packets.jsonl"
OUT_DIR = ROOT / f"runs/local/artifacts/{STAGE}"
SUMMARY = ROOT / f"runs/summaries/{STAGE}.json"

REVIEW_DECISIONS = [
  {"child_loop_id":"child_loop_bdcc51688a1296c9d3b0","decision":"ADMIT_TRAIN_SUPPORT_ONLY","concise_reason_code":"external_semantic_smoke_repair_not_same_exact_verifier","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":False,"patch_effective_enough":True,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_d6616d4a2b01b1600d8d","decision":"SPLIT_REQUIRED","concise_reason_code":"passing_smokes_with_unresolved_same_family_verifier","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_9bf534dc288650c86683","decision":"QUARANTINE_ENV_OR_TOOLING","concise_reason_code":"pre_failure_permission_tooling_post_unknown","semantic_verifier_relevance_proven":False,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_d0e9e0677d8dd5959c37","decision":"QUARANTINE_ENV_OR_TOOLING","concise_reason_code":"pre_failure_timeout_post_unknown","semantic_verifier_relevance_proven":False,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_cac49393097760be77a9","decision":"QUARANTINE_ENV_OR_TOOLING","concise_reason_code":"pre_failure_permission_tooling_post_unknown","semantic_verifier_relevance_proven":False,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_2cd476e93679693887f7","decision":"ADMIT_TRAIN_SUPPORT_ONLY","concise_reason_code":"external_doc_semantic_smoke_repair_not_same_exact_verifier","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":False,"patch_effective_enough":True,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_41f258b8b1591d9ce37f","decision":"QUARANTINE_INSUFFICIENT_EVIDENCE","concise_reason_code":"post_check_not_same_pytest_verifier","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_eac0d828195261b9a991","decision":"ADMIT_TRAIN_SUPPORT_ONLY","concise_reason_code":"self_research_exact_pytest_repair","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":True,"patch_effective_enough":True,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_2ffcc7c7f6721610c1c5","decision":"ADMIT_TRAIN_SUPPORT_ONLY","concise_reason_code":"self_research_exact_pytest_repair","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":True,"patch_effective_enough":True,"external_comparable_countable":False},
  {"child_loop_id":"child_loop_a857b4d781dfd316233e","decision":"QUARANTINE_INSUFFICIENT_EVIDENCE","concise_reason_code":"self_research_no_exact_same_verifier_pass","semantic_verifier_relevance_proven":True,"same_verifier_strict_enough":False,"patch_effective_enough":False,"external_comparable_countable":False},
]


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
    packets={r["child_loop_id"]:r for r in iter_jsonl(PACKETS)}
    decisions={r["child_loop_id"]:r for r in REVIEW_DECISIONS}
    rows=[]; admitted=[]; quarantine=[]; split=[]
    for cid, dec in decisions.items():
        packet=packets.get(cid)
        row={"child_loop_id":cid,"review":dec,"packet_present":bool(packet),"source_refs":(packet or {}).get("source_refs"),"root_recovery":(packet or {}).get("root_recovery"),"lineage":(packet or {}).get("lineage"),"guardrails":{"raw_output_emitted":False,"raw_patch_body_emitted":False,"raw_tool_arguments_emitted":False,"raw_source_path_emitted":False}}
        decision=dec["decision"]
        row["admission"]={
            "train_support_allowed": decision == "ADMIT_TRAIN_SUPPORT_ONLY",
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "external_comparable_patch_trace_countable": bool(dec.get("external_comparable_countable")),
            "external_fail_to_pass_countable": False,
            "render_transition_row_allowed": False,
            "blocked_until_fields": ["state_before", "candidate_action_set", "chosen_action", "observation_status_refs", "state_after_or_delta", "stop_continue_gold", "visibility_masks"],
        }
        rows.append(row)
        if decision == "ADMIT_TRAIN_SUPPORT_ONLY": admitted.append(row)
        elif decision == "SPLIT_REQUIRED": split.append(row)
        else: quarantine.append(row)
    counts=Counter(r["review"]["decision"] for r in rows)
    repo_counts=Counter((r.get("root_recovery") or {}).get("repo_family_label") for r in admitted)
    summary={
        "stage":STAGE,
        "decision":"semantic_review_ingested_train_support_only_training_render_blocked",
        "reviewed_rows":len(rows),
        "decision_counts":dict(counts),
        "train_support_only_rows":len(admitted),
        "split_required_rows":len(split),
        "quarantine_rows":len(quarantine),
        "external_comparable_patch_trace_rows":sum(1 for r in rows if r["admission"]["external_comparable_patch_trace_countable"]),
        "external_fail_to_pass_rows":0,
        "repo_family_counts_train_support":dict(repo_counts),
        "training_rows_emitted":0,
        "admitted_for_strict_eval":0,
        "next_stage":"stage12277_transition_row_renderer_for_train_support_repairs",
        "stage12277_preconditions":["all blocked_until_fields populated", "no raw output/patch body emitted", "self-research rows marked dev-only", "external rows remain train-support-only unless exact verifier proof added"],
    }
    write_jsonl(OUT_DIR/"semantic_review_ingested_rows.jsonl", rows)
    write_jsonl(OUT_DIR/"train_support_only_repair_candidates.jsonl", admitted)
    write_jsonl(OUT_DIR/"quarantine_or_split_rows.jsonl", quarantine+split)
    write_json(OUT_DIR/"semantic_review_result_ingest_summary.json", summary)
    write_json(SUMMARY, summary)
    (OUT_DIR/"SEMANTIC_REVIEW_RESULT_INGEST_STAGE12276.md").write_text("# Stage12276 Semantic Review Result Ingest\n\n"+json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
