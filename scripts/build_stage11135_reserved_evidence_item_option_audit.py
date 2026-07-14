#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11135
NAME = "stage11135_reserved_evidence_item_option_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reserved_evidence_item_option_audit.json"
REWRITTEN_ROWS_JSONL = OUT_DIR / "reserved_evidence_item_option_rows.jsonl"
RESERVED_AUDIT_JSON = OUT_DIR / "reserved_evidence_item_option_bounded_choice_eval.json"
RESERVED_ROWS_SCORED_JSONL = OUT_DIR / "reserved_evidence_item_option_rows_scored.jsonl"

RUNTIME_BUNDLE = ARTIFACTS / "stage11133_evidence_item_option_probe" / "runtime_model" / "runtime_model_bundle.json"
ORIGINAL_RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
STAGE11134_SUMMARY = ARTIFACTS / "stage11134_evidence_item_option_postrun_audit" / "evidence_item_option_postrun_audit.json"

ROLE_DESCRIPTIONS = {
    "candidate_change_surface": "the candidate edited source surface named by the packet",
    "nearby_definition_or_usage_context": "nearby definition or usage context",
    "external_analogue_reference": "an external analogue reference",
    "algorithmic_background_reference": "algorithmic background reference material",
    "symptom_or_call_path_analogue": "symptom or call-path evidence",
    "verifier_and_test_constraint": "selected-test or verifier constraint evidence",
}
ROLE_NAMES = set(ROLE_DESCRIPTIONS)
ROLE_ENTRY_RE = re.compile(r"(?m)^(" + "|".join(re.escape(r) for r in sorted(ROLE_NAMES, key=len, reverse=True)) + r")\s+\[([^\]]+)\]:")

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {
        "rows": len(rows),
        "scored_rows": len(scored),
        "correct": correct,
        "exact_accuracy": (correct / len(scored)) if scored else None,
    }


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or "unknown")].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def extract_role_entries(prompt: str) -> dict[str, dict[str, str]]:
    matches = list(ROLE_ENTRY_RE.finditer(prompt))
    entries: dict[str, dict[str, str]] = {}
    for index, match in enumerate(matches):
        role = match.group(1)
        source = match.group(2)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt)
        text = " ".join(prompt[start:end].strip().split())
        entries[role] = {"source": source, "text": text}
    return entries


def rewrite_prompt(prompt: str, role_to_eid: dict[str, str], rewritten_options: list[dict[str, Any]]) -> str:
    def replace(match: re.Match[str]) -> str:
        role = match.group(1)
        source = match.group(2)
        eid = role_to_eid.get(role, "EXX")
        return f"{eid} [{source}]:"

    rewritten = ROLE_ENTRY_RE.sub(replace, prompt)
    option_lines = [f"{option['label']}. {option['value']}" for option in rewritten_options]
    option_block = "Options:\n" + "\n".join(option_lines) + "\nAnswer:"
    rewritten = re.sub(r"Options:\n.*?\nAnswer:", option_block, rewritten, flags=re.S)
    return rewritten


def rewrite_evidence_row(row: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    options = list(row.get("opaque_options") or [])
    option_roles = [str(option.get("value") or "") for option in options]
    if not option_roles or any(role not in ROLE_NAMES for role in option_roles):
        return row, "non_role_option"

    prompt = str(row.get("prompt_text") or row.get("input_text") or "")
    entries = extract_role_entries(prompt)
    missing = [role for role in option_roles if role not in entries]
    if missing:
        return row, f"missing_prompt_entries:{','.join(missing)}"

    role_to_eid = {role: f"E{index + 1:02d}" for index, role in enumerate(option_roles)}
    rewritten_options = []
    for option in options:
        label = str(option.get("label") or "")
        role = str(option.get("value") or "")
        entry = entries[role]
        eid = role_to_eid[role]
        description = ROLE_DESCRIPTIONS[role]
        rewritten_options.append(
            {
                **option,
                "value": f"{eid}: {description} from {entry['source']}",
                "evidence_item_id": eid,
            }
        )

    rewritten_prompt = rewrite_prompt(prompt, role_to_eid, rewritten_options)
    target_label = str(row.get("bounded_choice_target_label") or row.get("decoder_text") or "")
    target_role = None
    for option in options:
        if str(option.get("label") or "") == target_label:
            target_role = str(option.get("value") or "")
            break

    rewritten = dict(row)
    rewritten["row_id"] = f"{row.get('row_id')}::reserved_evidence_item_options_v1"
    rewritten["prompt_text"] = rewritten_prompt
    rewritten["input_text"] = rewritten_prompt
    rewritten["query_text"] = rewritten_prompt
    rewritten["opaque_options"] = rewritten_options
    rewritten["anti_cheat"] = {
        **dict(row.get("anti_cheat") or {}),
        "reserved_evidence_item_option_rewrite": True,
        "role_names_removed_from_prompt_entry_headers": True,
        "role_names_removed_from_option_values": True,
        "hidden_target_role": target_role,
    }
    return rewritten, None


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any], str]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = dict(bundle.get("metadata") or {})
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card, str(metadata.get("bounded_choice_aux_source") or "encoder_option_retrieval")


def main() -> None:
    original_rows = load_jsonl(ORIGINAL_RESERVED_ROWS)
    stage11134 = load_json(STAGE11134_SUMMARY) if STAGE11134_SUMMARY.exists() else {}
    rewritten_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    for row in original_rows:
        if str(row.get("task_type") or "") != "evidence_citation":
            rewritten_rows.append(row)
            continue
        rewritten, reason = rewrite_evidence_row(row)
        if reason:
            blocked.append({"row_id": str(row.get("row_id") or ""), "reason": reason})
            rewritten_rows.append(row)
        else:
            rewritten_rows.append(rewritten)

    write_jsonl(REWRITTEN_ROWS_JSONL, rewritten_rows)

    role_leak_rows = []
    for row in rewritten_rows:
        if str(row.get("task_type") or "") != "evidence_citation":
            continue
        prompt = str(row.get("prompt_text") or "")
        options = json.dumps(row.get("opaque_options") or [], sort_keys=True)
        if any(role in prompt or role in options for role in ROLE_NAMES):
            role_leak_rows.append(str(row.get("row_id") or ""))

    model, tokenizer, init_card, scorer_source = load_runtime()
    reserved_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=rewritten_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reserved_evidence_item_option_slice",
        bounded_choice_aux_source=scorer_source,
        eval_batch_size=8,
    )

    source_by_id = {str(row.get("row_id") or ""): row for row in rewritten_rows}
    enriched_cards = []
    for row in list(reserved_card.get("row_cards") or []):
        source = source_by_id.get(str(row.get("row_id") or ""), {})
        merged = dict(row)
        for key in ["language_family", "repo_family", "repo_id", "task_type", "source_root_id", "split_role"]:
            merged[key] = source.get(key)
        enriched_cards.append(merged)

    write_json(RESERVED_AUDIT_JSON, reserved_card)
    write_jsonl(RESERVED_ROWS_SCORED_JSONL, enriched_cards)

    evidence_rows = [row for row in enriched_cards if str(row.get("task_type") or "") == "evidence_citation"]
    overall = metric_block(enriched_cards, "constrained_choice_match")
    evidence = metric_block(evidence_rows, "constrained_choice_match")
    previous_overall = ((stage11134.get("reserved_candidate_result") or {}).get("overall") or {}).get("exact_accuracy")
    previous_evidence = ((stage11134.get("reserved_candidate_result") or {}).get("evidence_citation") or {}).get("exact_accuracy")

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not blocked and not role_leak_rows,
        "decision": (
            "reserved_evidence_item_option_slice_improved"
            if overall.get("exact_accuracy") is not None and float(overall["exact_accuracy"]) > 0.5 and not blocked and not role_leak_rows
            else "reserved_evidence_item_option_slice_diagnostic_only"
        ),
        "claim_scope": [
            "Rewrite the untouched reserved evidence rows into the same evidence-item option interface used by stage11131 train support.",
            "This distinguishes a true stage11133 failure from an old-role-option evaluation-interface mismatch.",
        ],
        "rewrite_metrics": {
            "original_rows": len(original_rows),
            "rewritten_rows": len(rewritten_rows),
            "evidence_rows": sum(1 for row in original_rows if str(row.get("task_type") or "") == "evidence_citation"),
            "blocked_rows": blocked,
            "role_leak_rows_after_rewrite": role_leak_rows,
        },
        "reserved_candidate_result": {
            "overall": overall,
            "evidence_citation": evidence,
            "by_language": group_metrics(enriched_cards, "language_family", "constrained_choice_match"),
            "by_repo_family": group_metrics(enriched_cards, "repo_family", "constrained_choice_match"),
            "by_task_type": group_metrics(enriched_cards, "task_type", "constrained_choice_match"),
            "mismatches": [
                {
                    k: row.get(k)
                    for k in [
                        "row_id",
                        "language_family",
                        "repo_family",
                        "task_type",
                        "target_text",
                        "constrained_choice_top1_label",
                        "target_rank_full_vocab",
                        "full_vocab_top1_text",
                    ]
                }
                for row in enriched_cards
                if row.get("constrained_choice_match") is False
            ],
        },
        "delta_vs_stage11134_original_reserved_interface": {
            "overall_accuracy": None if previous_overall is None or overall.get("exact_accuracy") is None else float(overall["exact_accuracy"]) - float(previous_overall),
            "evidence_accuracy": None if previous_evidence is None or evidence.get("exact_accuracy") is None else float(evidence["exact_accuracy"]) - float(previous_evidence),
        },
        "bounded_choice_aux_source": scorer_source,
        "runtime_initialization": init_card,
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "original_reserved_rows": rel(ORIGINAL_RESERVED_ROWS),
            "stage11134_summary": rel(STAGE11134_SUMMARY),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rewritten_rows_jsonl": rel(REWRITTEN_ROWS_JSONL),
            "reserved_audit_json": rel(RESERVED_AUDIT_JSON),
            "reserved_rows_scored_jsonl": rel(RESERVED_ROWS_SCORED_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
