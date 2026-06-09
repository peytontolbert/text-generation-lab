#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


KEY_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def key_values(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in KEY_RE.finditer(str(text or ""))}


def factor_family(operation: str) -> str:
    op = str(operation or "")
    if op == "composition":
        return "composition_exact"
    if op in {"schema", "math_identity", "code_api_semantics"}:
        return "procedure_schema"
    if op == "relation":
        return "relation_binding"
    if op == "counterfactual_false_claim":
        return "counterfactual_binding"
    if op == "atomic_fact":
        return "atomic_binding"
    if op == "exception":
        return "exception_binding"
    return "unknown"


def answer_type(value: str) -> str:
    raw = str(value or "")
    if re.fullmatch(r"-?\d+", raw):
        return "integer"
    if raw.lower() in {"true", "false", "yes", "no"}:
        return "boolean"
    if re.fullmatch(r"[A-Za-z]+_v\d+", raw):
        return "symbolic_value"
    if raw.startswith("tool_"):
        return "tool_symbol"
    if raw.startswith("api_"):
        return "api_symbol"
    return "text"


def composition_depth(operation: str, row: dict[str, Any]) -> int:
    if str(operation or "") != "composition":
        return 0
    text = " ".join(
        str(row.get(key, "") or "")
        for key in ("retrieval_query_text", "retrieval_doc_text", "encoder_text")
    )
    if "two_hop" in text or "linked" in text:
        return 2
    if "set_count" in text or "count" in text:
        return 1
    return 1


def strip_selector_crutches(text: str, *, keep_operation: bool = True) -> str:
    raw = str(text or "")
    raw = re.sub(r"\bgsel=[^\s]+", "", raw)
    raw = re.sub(r"\bcollision_key(?:_value)?=[^\s]+", "", raw)
    raw = re.sub(r"\bstage\d+_[0-9a-f]{8,}\b", "", raw)
    raw = re.sub(r"\bfactgrp\|[^\s]+", "", raw)
    if not keep_operation:
        raw = re.sub(r"<AK_OP_[A-Z0-9_]+>", "", raw)
        raw = re.sub(r"\bop=[^\s]+", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def route_support(row: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, str] = {}
    values.update(key_values(str(row.get("retrieval_doc_text", "") or "")))
    values.update(key_values(str(row.get("retrieval_query_text", "") or "")))
    operation = str(row.get("operation") or detail.get("operation") or "")
    expected = str(row.get("expected_content") or detail.get("expected_content") or "")
    return {
        "operation": operation,
        "factor_family": factor_family(operation),
        "domain": values.get("domain", ""),
        "field": values.get("field", ""),
        "entity": values.get("entity", ""),
        "relation": values.get("relation", ""),
        "gsel": values.get("gsel", ""),
        "collision_key": values.get("collision_key", str(row.get("collision_key_value", "") or "")),
        "composition_depth": composition_depth(operation, row),
        "answer_type": answer_type(expected),
    }


def compact_proof_content(answer: str, support: dict[str, Any], detail: dict[str, Any]) -> str:
    payload = {
        "answer": answer,
        "route": support,
        "support_units": [
            item.get("source_id")
            for item in list(detail.get("topk", []))[:3]
            if item.get("source_id")
        ],
        "teacher_margin": detail.get("margin_to_best_wrong"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def decoder_text(task_type: str, content: str) -> str:
    return (
        f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> {task_type} "
        f"<AK_CONTENT> {content} </AK_CONTENT> <AK_END>"
    )


def build_rows(
    source_rows: list[dict[str, Any]],
    details_by_id: dict[str, dict[str, Any]],
    *,
    include_route_rows: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    row_by_id = {str(row.get("source_id") or row.get("example_id")): row for row in source_rows}
    doc_by_id = {source_id: str(row.get("retrieval_doc_text", "") or "") for source_id, row in row_by_id.items()}
    out_rows: list[dict[str, Any]] = []
    counts = {"direct": 0, "route_proof": 0, "negatives": 0}

    for row in source_rows:
        source_id = str(row.get("source_id") or row.get("example_id"))
        detail = details_by_id.get(source_id, {})
        expected = str(row.get("expected_content") or detail.get("expected_content") or "")
        support = route_support(row, detail)
        topk = list(detail.get("topk", []))
        negative_docs = [
            doc_by_id[str(item.get("source_id"))]
            for item in topk
            if not bool(item.get("answer", False))
            and str(item.get("source_id")) in doc_by_id
            and str(item.get("source_id")) != source_id
        ][:3]
        counts["negatives"] += len(negative_docs)

        query_no_selector = strip_selector_crutches(str(row.get("retrieval_query_text", "") or ""))
        direct = dict(row)
        direct.update(
            {
                "encoder_text": (
                    "<AK_QUERY> "
                    + query_no_selector
                    + "\n<AK_TASK_HINT> direct_answer=true selector_dropout=structured"
                ),
                "decoder_text": decoder_text("active_agent_direct_answer", expected),
                "json_decoder_text": json.dumps({"action": "respond", "content": expected}, sort_keys=True),
                "negative_decoder_text": "",
                "retrieval_query_text": query_no_selector,
                "retrieval_negative_doc_texts": negative_docs,
                "retrieval_loss_weight": float(row.get("retrieval_loss_weight", 1.0) or 1.0),
                "decoder_loss_weight": 1.2,
                "task_type": "active_agent_direct_answer",
                "stage783_role": "selector_dropped_direct_answer",
                "stage783_teacher_factor_mode": "text_routed_multi_axis_compose_procedure",
                "stage783_teacher_factor_weight": 8.0,
                "stage783_teacher_support": support,
                "stage783_teacher_topk": topk,
                "stage783_teacher_margin": detail.get("margin_to_best_wrong"),
            }
        )
        out_rows.append(direct)
        counts["direct"] += 1

        if include_route_rows:
            proof_content = compact_proof_content(expected, support, detail)
            route = dict(row)
            route_query = strip_selector_crutches(str(row.get("retrieval_query_text", "") or ""), keep_operation=True)
            route.update(
                {
                    "encoder_text": (
                        "<AK_QUERY> "
                        + route_query
                        + "\n<AK_TASK_HINT> infer_route=true emit_compact_proof=true"
                    ),
                    "decoder_text": decoder_text("active_agent_route_proof", proof_content),
                    "json_decoder_text": json.dumps({"action": "respond", "content": proof_content}, sort_keys=True),
                    "negative_decoder_text": "",
                    "retrieval_query_text": route_query,
                    "retrieval_negative_doc_texts": negative_docs,
                    "retrieval_loss_weight": float(row.get("retrieval_loss_weight", 1.0) or 1.0),
                    "decoder_loss_weight": 1.0,
                    "task_type": "active_agent_route_proof",
                    "stage783_role": "routed_teacher_proof_distill",
                    "stage783_teacher_factor_mode": "text_routed_multi_axis_compose_procedure",
                    "stage783_teacher_factor_weight": 8.0,
                    "stage783_teacher_support": support,
                    "stage783_teacher_topk": topk,
                    "stage783_teacher_margin": detail.get("margin_to_best_wrong"),
                }
            )
            out_rows.append(route)
            counts["route_proof"] += 1

    return out_rows, counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--teacher-train-details-jsonl", required=True)
    parser.add_argument("--teacher-eval-details-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--artifact-json", required=True)
    args = parser.parse_args()

    source_manifest_path = (ROOT / args.source_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    train_rows = list(iter_jsonl(Path(source_manifest["train_dataset_path"])))
    eval_rows = list(iter_jsonl(Path(source_manifest["eval_dataset_path"])))
    train_details = {
        str(row.get("unit_id")): row
        for row in iter_jsonl((ROOT / args.teacher_train_details_jsonl).resolve())
    }
    eval_details = {
        str(row.get("unit_id")): row
        for row in iter_jsonl((ROOT / args.teacher_eval_details_jsonl).resolve())
    }

    train_out, train_counts = build_rows(train_rows, train_details, include_route_rows=True)
    eval_out, eval_counts = build_rows(eval_rows, eval_details, include_route_rows=False)

    output_dir = (ROOT / args.output_dir).resolve()
    train_path = output_dir / "agentkernel_lite_encdec_train.jsonl"
    eval_path = output_dir / "agentkernel_lite_encdec_eval.jsonl"
    write_jsonl(train_path, train_out)
    write_jsonl(eval_path, eval_out)

    manifest = dict(source_manifest)
    manifest.update(
        {
            "artifact_kind": "agentkernel_lite_encdec_stage783_routed_teacher_distillation",
            "manifest_path": str(output_dir / "agentkernel_lite_encdec_dataset_manifest.json"),
            "train_dataset_path": str(train_path),
            "eval_dataset_path": str(eval_path),
            "train_examples": len(train_out),
            "eval_examples": len(eval_out),
            "source_manifest_path": str(source_manifest_path),
            "stage783_teacher_train_details_jsonl": str((ROOT / args.teacher_train_details_jsonl).resolve()),
            "stage783_teacher_eval_details_jsonl": str((ROOT / args.teacher_eval_details_jsonl).resolve()),
            "stage783_train_counts": train_counts,
            "stage783_eval_counts": eval_counts,
            "stage783_goal": "Distill routed factor teacher into model-only retrieval and direct answer/proof generation.",
            "timestamp": int(time.time()),
        }
    )
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    artifact = {
        "artifact_kind": "stage783_routed_teacher_distillation_dataset",
        "dataset_manifest": str(manifest_path),
        "source_manifest": str(source_manifest_path),
        "teacher_train_details_jsonl": str((ROOT / args.teacher_train_details_jsonl).resolve()),
        "teacher_eval_details_jsonl": str((ROOT / args.teacher_eval_details_jsonl).resolve()),
        "train_examples": len(train_out),
        "eval_examples": len(eval_out),
        "train_counts": train_counts,
        "eval_counts": eval_counts,
        "timestamp": int(time.time()),
    }
    artifact_path = (ROOT / args.artifact_json).resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
