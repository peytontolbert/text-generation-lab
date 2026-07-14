#!/usr/bin/env rust3
"""Score admitted bigram Rust source-heldout smoke rows with Stage11507."""

from __future__ import annotations

import importlib.util
import json
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11734
NAME = "stage11734_tokenizers_rust_source_heldout_100m_score"
OUT = ART / NAME
SUMMARY = OUT / "tokenizers_rust_source_heldout_100m_score.json"
RENDERED_ROWS = OUT / "tokenizers_rust_rendered_score_rows.jsonl"
SCORED_ROWS = OUT / "tokenizers_rust_100m_score_rows.jsonl"

STAGE11722 = ROOT / "scripts/build_stage11722_sentencepiece_cpp_source_heldout_100m_score.py"
spec = importlib.util.spec_from_file_location("stage11722_for_11734", STAGE11722)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to import {STAGE11722}")
stage11722 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage11722)

ROWS = ART / "stage11733_tokenizers_rust_no_train_overlap_and_admission/tokenizers_rust_admitted_smoke_rows.jsonl"
ADMISSION = ART / "stage11733_tokenizers_rust_no_train_overlap_and_admission/tokenizers_rust_no_train_overlap_and_admission.json"
SCORER = "encoder_option_retrieval_evidence_judgment_head"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def snippet(text: str, *, limit: int = 520) -> str:
    compact = "\n".join(line.rstrip() for line in str(text).splitlines() if line.strip())
    return compact[:limit]


def evidence_by_id(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in row.get("evidence_ledger") or [] if isinstance(item, dict)}


def render_prompt(row: dict[str, Any]) -> str:
    evidence = evidence_by_id(row)
    used = []
    seen = set()
    for opt in row.get("opaque_options") or []:
        for evidence_id in opt.get("evidence_ids") or []:
            if evidence_id in evidence and evidence_id not in seen:
                seen.add(evidence_id)
                used.append(evidence[evidence_id])
    task_instructions = {
        "symptom_localization": "Choose the candidate edit surface most directly supported by the visible source and verifier evidence.",
        "evidence_citation": "Choose the evidence item that most directly justifies the maintainer decision.",
        "patch_impact": "Choose the smallest candidate change surface likely to affect the selected verifier.",
        "verifier_outcome": "Choose the selected verifier/test anchor that should be used for this maintainer root.",
    }
    lines = [
        "TASK",
        f"language_family: {row.get('language_family')}",
        f"repo_family: {row.get('repo_family')}",
        f"task_type: {row.get('task_type')}",
        task_instructions.get(str(row.get("task_type")), "Choose the best maintainer option from the visible evidence."),
        "",
        "OBSERVED_STATE",
        "A compact Rust maintainer root has concrete implementation, test, nearby data, integration, and config evidence.",
        "Candidate file paths are intentionally visible only inside the candidate options.",
        "",
        "SOURCE_EVIDENCE",
    ]
    for item in used:
        lines.extend(
            [
                f"{item.get('id')}: kind={item.get('kind')}; summary={item.get('summary')}",
                "snippet:",
                snippet(str(item.get("text") or "")),
                "",
            ]
        )
    lines.append("CANDIDATES")
    for opt in row.get("opaque_options") or []:
        label = str(opt.get("label") or "").strip()
        role = str(opt.get("role") or "").strip()
        value = str(opt.get("value") or "").strip()
        evidence_ids = ",".join(str(eid) for eid in opt.get("evidence_ids") or [])
        lines.append(f"{label}: role={role}; value={value}; evidence_ids={evidence_ids}")
    lines.extend(["", "QUESTION", "Return exactly one candidate label."])
    return "\n".join(lines)


def render_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        target = str(row.get("target_label") or "").strip()
        rendered = dict(row)
        rendered["prompt_text"] = render_prompt(row)
        rendered["input_text"] = rendered["prompt_text"]
        rendered["target_text"] = target
        rendered["bounded_choice_target_label"] = target
        rendered["decoder_text"] = target
        rendered["standalone_projection_source"] = dict(rendered.get("standalone_projection_source") or {})
        rendered["standalone_projection_source"]["opaque_options"] = list(row.get("opaque_options") or [])
        rendered["standalone_projection_source"]["gold_value"] = row.get("target_value")
        rendered["loss_mask"] = {"bounded_choice_aux": True, "decoder_ce": True}
        out.append(rendered)
    return out


def enrich(card: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("row_id")): row for row in rows}
    enriched = []
    for scored in card.get("row_cards") or []:
        source = by_id.get(str(scored.get("row_id")), {})
        pred = str(scored.get("constrained_choice_top1_label") or "")
        target = str(scored.get("bounded_choice_target_label") or "")
        pred_opt = next((opt for opt in source.get("opaque_options") or [] if str(opt.get("label") or "") == pred), {})
        target_opt = next((opt for opt in source.get("opaque_options") or [] if str(opt.get("label") or "") == target), {})
        merged = dict(scored)
        for key in ["language_family", "repo_family", "root_id", "task_type", "target_value", "source_heldout_attestation"]:
            merged[key] = source.get(key)
        merged["predicted_value"] = pred_opt.get("value")
        merged["predicted_role"] = pred_opt.get("role")
        merged["target_value"] = target_opt.get("value") or source.get("target_value")
        merged["target_role"] = target_opt.get("role")
        enriched.append(merged)
    return enriched


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "accuracy": correct / len(scored) if scored else None,
        "coverage": len(scored) / len(rows) if rows else None,
    }


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    return {name: metric(bucket) for name, bucket in sorted(buckets.items())}


def main() -> None:
    admission = stage11722.load_json(ADMISSION)
    if admission.get("passed") is not True:
        raise SystemExit("Stage11733 admission did not pass")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_rows = stage11722.load_jsonl(ROWS)
    rows = render_rows(raw_rows)
    write_jsonl(RENDERED_ROWS, rows)
    leak = stage11722.prompt_leak_audit(rows)

    model, tokenizer, init_card = stage11722.load_runtime()
    card = stage11722._write_bounded_choice_eval_audit(
        OUT,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="tokenizers_rust_source_heldout_smoke",
        bounded_choice_aux_source=SCORER,
        eval_batch_size=4,
    )
    scored = enrich(card, rows)
    write_jsonl(SCORED_ROWS, scored)
    metrics = metric(scored)
    gates = {
        "stage11733_admitted": admission.get("passed") is True,
        "full_coverage": metrics["scored_rows"] == metrics["rows"] == 4,
        "no_prompt_target_label_leaks": leak["prompt_target_label_leaks"] == 0,
        "no_prompt_target_value_leaks": leak["prompt_target_value_leaks"] == 0,
        "hundred_m_all_correct": metrics["correct"] == 4,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "tokenizers_rust_source_heldout_100m_score_complete",
        "passed": gates["full_coverage"],
        "model_runtime": rel(stage11722.RUNTIME_BUNDLE),
        "scorer": SCORER,
        "metrics": metrics,
        "by_task": grouped(scored, "task_type"),
        "prompt_leak_audit": leak,
        "gates": gates,
        "misses": [row for row in scored if row.get("constrained_choice_match") is False],
        "runtime_init_card": init_card,
        "claim_boundary": [
            "This scores a 4-row Rust tokenizers compact source-heldout smoke packet.",
            "Rows are exact new-root/source-snapshot attested; tokenizers prior family usage means this is not broad repo-family heldout.",
            "This is bounded-choice product scoring, not executable patch repair.",
            "Gemma same-manifest and option permutation audit are still required before comparison claims.",
        ],
        "source_artifacts": {
            "admitted_rows": rel(ROWS),
            "admission": rel(ADMISSION),
            "runtime_bundle": rel(stage11722.RUNTIME_BUNDLE),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "rendered_rows": rel(RENDERED_ROWS),
            "score_rows": rel(SCORED_ROWS),
            "bounded_choice_audit": rel(OUT / "bounded_choice_eval_audit_tokenizers_rust_source_heldout_smoke.json"),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
