#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11597
NAME = "stage11597_web_answerable_no_abstain_geometry_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_answerable_no_abstain_geometry_audit.json"
SOURCE_ROWS = ART / "stage11594_web_verifier_attached_repaired_geometry_package/web_verifier_attached_repaired_rows.jsonl"
RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
SCORER = "encoder_option_retrieval_evidence_judgment_head"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def options(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((row.get("standalone_projection_source") or {}).get("opaque_options") or []) or row.get("opaque_options") or [])


def deterministic_labels(row_id: str, n: int) -> list[str]:
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n])
    seed = hashlib.sha256(row_id.encode("utf-8")).digest()
    return [label for _, label in sorted((hashlib.sha256(seed + label.encode()).hexdigest(), label) for label in labels)]


def rebuild_prompt(row: dict[str, Any], opts: list[dict[str, Any]]) -> str:
    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    before = prompt.split("Choices:", 1)[0].rstrip()
    lines = [before]
    lines.append("Answerability contract: this row contains visible source and focused verifier evidence. For non-abstention perspectives, choose among concrete candidates only. For abstention perspective, choose abstain only if the visible verifier evidence is insufficient.")
    lines.append("Choices:")
    for opt in opts:
        lines.append(f"option {opt['label']}: {opt.get('text') or opt.get('value')}")
    return "\n".join(lines)


def transform(row: dict[str, Any]) -> dict[str, Any]:
    task = str(row.get("task_type") or "")
    old_opts = [dict(opt) for opt in options(row)]
    target_role = str(row.get("semantic_target_role") or "")
    if task == "abstention_insufficient_evidence":
        keep_roles = {"verifier_and_test_constraint", "abstain_insufficient_evidence"}
    else:
        keep_roles = {"candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"}
    kept = [opt for opt in old_opts if str(opt.get("semantic_role") or "") in keep_roles]
    role_order = ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue", "abstain_insufficient_evidence"]
    kept.sort(key=lambda opt: role_order.index(str(opt.get("semantic_role"))) if str(opt.get("semantic_role")) in role_order else 99)
    labels = deterministic_labels(str(row.get("row_id")), len(kept))
    target_label = None
    new_opts = []
    for label, opt in zip(labels, kept):
        new = dict(opt)
        new["label"] = label
        role = str(new.get("semantic_role") or "")
        if role == "abstain_insufficient_evidence":
            new["value"] = "ABSTAIN_OPTION"
            new["text"] = "ABSTAIN_OPTION"
        if role == target_role:
            target_label = label
        new_opts.append(new)
    if target_label is None:
        raise ValueError(f"target role {target_role} not present for {row.get('row_id')}")
    out = dict(row)
    out["row_id"] = f"{row.get('row_id')}::answerable_no_abstain_v1"
    out["bounded_choice_target_label"] = target_label
    out["target_text"] = target_label
    out["decoder_text"] = target_label
    src = dict(out.get("standalone_projection_source") or {})
    src["opaque_options"] = new_opts
    src["answerable_no_abstain_geometry"] = True
    out["standalone_projection_source"] = src
    out["prompt_text"] = rebuild_prompt(out, new_opts)
    out["input_text"] = out["prompt_text"]
    anti = dict(out.get("anti_cheat") or {})
    anti.update({
        "answerable_non_abstention_rows_remove_abstain": task != "abstention_insufficient_evidence",
        "abstention_rows_binary_evidence_vs_abstain": task == "abstention_insufficient_evidence",
        "stage11597_answerable_geometry": True,
    })
    out["anti_cheat"] = anti
    return out


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    return out


def load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
    rows = card.get("row_cards") or []
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage": card.get("constrained_choice_coverage"),
        "target_counts": dict(Counter(str(row.get("bounded_choice_target_label")) for row in rows)),
        "prediction_counts": dict(Counter(str(row.get("constrained_choice_top1_label")) for row in rows)),
    }


def main() -> int:
    source = load_jsonl(SOURCE_ROWS)
    transformed = [transform(row) for row in source]
    train = [normalize_row(row) for row in transformed if row.get("trainable_now")]
    strict = [normalize_row(row) for row in transformed if row.get("strict_eval_eligible_now")]
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "web_answerable_no_abstain_rows.jsonl", transformed)
    write_jsonl(OUT / "web_answerable_no_abstain_train_rows.jsonl", train)
    write_jsonl(OUT / "web_answerable_no_abstain_successor_strict_rows.jsonl", strict)
    model, tokenizer, init_card = load_runtime()
    results = {}
    for name, rows in {"train": train, "successor_strict": strict}.items():
        card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=name,
            bounded_choice_aux_source=SCORER,
            eval_batch_size=8,
        )
        results[name] = metric(card)
    by_task = defaultdict(Counter)
    for row in transformed:
        by_task[str(row.get("task_type"))][len(options(row))] += 1
    decision = "answerable_no_abstain_geometry_train_probe_candidate" if results["train"].get("correct", 0) > 0 else "answerable_no_abstain_geometry_still_unmeasurable"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "scorer": SCORER,
        "metrics": {
            "rows": len(transformed),
            "train_rows": len(train),
            "strict_rows": len(strict),
            "option_count_by_task": {task: dict(counter) for task, counter in sorted(by_task.items())},
        },
        "results": results,
        "runtime_initialization": init_card,
        "claim_boundary": [
            "This is an inference audit for answerable-row option geometry only; no training was performed.",
            "Removing abstain from non-abstention rows is valid only for rows whose visible verifier/source evidence makes a non-abstain choice answerable.",
        ],
        "source_artifacts": {"source_rows": rel(SOURCE_ROWS), "runtime": rel(RUNTIME)},
        "outputs": {
            "rows": rel(OUT / "web_answerable_no_abstain_rows.jsonl"),
            "train_rows": rel(OUT / "web_answerable_no_abstain_train_rows.jsonl"),
            "strict_rows": rel(OUT / "web_answerable_no_abstain_successor_strict_rows.jsonl"),
            "summary": rel(SUMMARY),
        },
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
