#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP_OPS = {
    "set_member",
    "rule_case_member",
    "set_intersection_member",
    "rule_case_intersection_member",
}


def load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def iter_operation_rows(operation_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for operation, frontier in operation_report["operation_frontiers"].items():
        for bucket in ("best_raw_answer_bits_per_param", "best_reliable_answer_bits_per_param"):
            for row in frontier.get(bucket, []) or []:
                item = dict(row)
                item["frontier_bucket"] = bucket
                item["operation"] = operation
                rows.append(item)
    # Deduplicate repeated rows that appear in both raw and reliable answer lists.
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("label")), str(row.get("operation")), str(row.get("scale_band")))
        unique[key] = row
    return list(unique.values())


def build_report() -> dict[str, Any]:
    operation_report = load_json("runs/local/artifacts/operation_bits_per_param_report.json")
    rows = iter_operation_rows(operation_report)
    for row in rows:
        row["answer_exact_bits_gap"] = float(row.get("answer_bits_per_param") or 0.0) - float(row.get("exact_bits_per_param") or 0.0)
        row["answer_exact_top1_gap"] = float(row.get("answer_top1") or 0.0) - float(row.get("exact_top1") or 0.0)
        row["is_membership_op"] = row["operation"] in MEMBERSHIP_OPS

    gap_rows = [row for row in rows if row["answer_exact_bits_gap"] > 0]
    gap_rows.sort(key=lambda row: row["answer_exact_bits_gap"], reverse=True)
    membership_gap_rows = [row for row in gap_rows if row["is_membership_op"]]

    totals = {
        "rows_considered": len(rows),
        "rows_with_answer_exact_gap": len(gap_rows),
        "membership_rows_with_answer_exact_gap": len(membership_gap_rows),
        "max_answer_exact_bits_gap": gap_rows[0]["answer_exact_bits_gap"] if gap_rows else 0.0,
        "max_membership_answer_exact_bits_gap": membership_gap_rows[0]["answer_exact_bits_gap"] if membership_gap_rows else 0.0,
    }
    op_tax: dict[str, dict[str, Any]] = {}
    for row in gap_rows:
        item = op_tax.setdefault(
            row["operation"],
            {
                "operation": row["operation"],
                "gap_rows": 0,
                "max_answer_exact_bits_gap": 0.0,
                "max_answer_exact_top1_gap": 0.0,
                "example_label": "",
                "is_membership_op": row["is_membership_op"],
            },
        )
        item["gap_rows"] += 1
        if row["answer_exact_bits_gap"] > item["max_answer_exact_bits_gap"]:
            item["max_answer_exact_bits_gap"] = row["answer_exact_bits_gap"]
            item["max_answer_exact_top1_gap"] = row["answer_exact_top1_gap"]
            item["example_label"] = row["label"]

    ranked_ops = sorted(op_tax.values(), key=lambda row: row["max_answer_exact_bits_gap"], reverse=True)
    answer_equivalence_operation_ids = {
        "set_count": 6,
        "set_member": 7,
        "set_intersection_count": 8,
        "set_intersection_member": 9,
        "rule_case_count": 11,
        "rule_case_member": 12,
        "rule_case_intersection_count": 13,
        "rule_case_intersection_member": 14,
    }
    return {
        "artifact_kind": "answer_equivalence_kbpp_tax",
        "source": "runs/local/artifacts/operation_bits_per_param_report.json",
        "totals": totals,
        "ranked_operations_by_exact_answer_tax": ranked_ops,
        "top_gap_rows": gap_rows[:20],
        "membership_gap_rows": membership_gap_rows[:20],
        "training_implication": {
            "answer_equivalence_already_in_eval": True,
            "train_loss_available": "retrieval_answer_contrastive_loss",
            "recommended_operation_ids": [
                answer_equivalence_operation_ids["set_count"],
                answer_equivalence_operation_ids["set_member"],
                answer_equivalence_operation_ids["set_intersection_count"],
                answer_equivalence_operation_ids["set_intersection_member"],
                answer_equivalence_operation_ids["rule_case_count"],
                answer_equivalence_operation_ids["rule_case_member"],
                answer_equivalence_operation_ids["rule_case_intersection_count"],
                answer_equivalence_operation_ids["rule_case_intersection_member"],
            ],
            "recommended_flag": "--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14",
            "reason": (
                "Set/rule count and membership operations often have answer-correct but exact-card-different proof swaps. "
                "Answer-level contrastive supervision should preserve the useful count or member_true/member_false knowledge while reducing pressure to memorize arbitrary proof-card identity."
            ),
        },
    }


def write_doc(report: dict[str, Any]) -> None:
    ops = "\n".join(
        f"- `{row['operation']}`: max bits/param tax `{row['max_answer_exact_bits_gap']}`, "
        f"top1 tax `{row['max_answer_exact_top1_gap']}`, example `{row['example_label']}`"
        for row in report["ranked_operations_by_exact_answer_tax"][:10]
    )
    top = report["top_gap_rows"][0] if report["top_gap_rows"] else {}
    doc = f"""# Answer-Equivalence KBPP Tax

Artifact: `runs/local/artifacts/answer_equivalence_kbpp_tax.json`

## Finding

The evaluator already separates exact-card retrieval from answer-equivalent retrieval. The remaining maximization question is where exact proof-card identity consumes KBPP without adding answer knowledge.

Largest observed gap:

- Operation: `{top.get('operation')}`
- Run: `{top.get('label')}`
- Answer bits/param: `{top.get('answer_bits_per_param')}`
- Exact bits/param: `{top.get('exact_bits_per_param')}`
- Gap: `{top.get('answer_exact_bits_gap')}`

## Ranked Tax By Operation

{ops}

## Training Route

Use answer-level contrastive pressure on set/rule count and membership operations:

`{report['training_implication']['recommended_flag']}`

This targets operations `6,7,8,9,11,12,13,14`: set/rule count and membership families. The goal is to reward the useful answer knowledge, such as counts and `member_true/member_false`, while reducing pressure to memorize arbitrary exact proof-card identity.
"""
    (ROOT / "docs/answer_equivalence_kbpp_tax.md").write_text(doc, encoding="utf-8")


def main() -> None:
    report = build_report()
    output = ROOT / "runs/local/artifacts/answer_equivalence_kbpp_tax.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_doc(report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
