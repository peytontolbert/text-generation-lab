#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _generate_greedy_text, _load_runtime_model_bundle

STAGE = 10607
NAME = "stage10607_semantic_output_exact_generation_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "semantic_output_exact_generation_audit.json"
ROW_JSONL = OUT_DIR / "semantic_output_exact_generation_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
OUT_DIR.mkdir(parents=True, exist_ok=True)

STRICT_ROWS = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/strict_eval_rows.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe/runtime_model/runtime_model_bundle.json"
EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe/bounded_decoder_probe/execution_result.json"
MAX_ENCODER_TOKENS = 1024
MAX_NEW_TOKENS = 32


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer, init_card


def subtype(row: dict[str, Any]) -> str:
    return str(row.get("target_subtype") or "unknown")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0}
    exact = sum(1 for row in rows if row["exact_match"])
    contentful = sum(1 for row in rows if row["contentful"])
    prefix = sum(1 for row in rows if row["target_prefix_match"])
    junk = sum(1 for row in rows if row["short_or_junk"])
    reps = sum(1 for row in rows if row["degenerate_repetition"])
    gen_counter = Counter(str(row["generated_text"]) for row in rows)
    return {
        "rows": len(rows),
        "exact_match_rows": exact,
        "exact_match_rate": exact / len(rows),
        "contentful_rows": contentful,
        "contentful_rate": contentful / len(rows),
        "target_prefix_match_rows": prefix,
        "target_prefix_match_rate": prefix / len(rows),
        "short_or_junk_rows": junk,
        "short_or_junk_rate": junk / len(rows),
        "degenerate_repetition_rows": reps,
        "degenerate_repetition_rate": reps / len(rows),
        "dominant_generated_text": gen_counter.most_common(1)[0][0] if gen_counter else None,
        "dominant_generated_text_fraction": (gen_counter.most_common(1)[0][1] / len(rows)) if gen_counter else None,
        "mean_generated_token_count": mean(int(row["generated_token_count"]) for row in rows),
    }


def main() -> None:
    if not RUNTIME_BUNDLE.exists():
        raise SystemExit(f"missing runtime bundle: {RUNTIME_BUNDLE}")
    if not EXECUTION_RESULT.exists():
        raise SystemExit(f"missing execution_result: {EXECUTION_RESULT}")
    rows = load_jsonl(STRICT_ROWS)
    rows.sort(key=lambda row: str(row["row_id"]))
    model, tokenizer, init_card = load_runtime()
    execution = load_json(EXECUTION_RESULT)

    scored_rows = []
    for row in rows:
        generation = _generate_greedy_text(
            model,
            row,
            tokenizer=tokenizer,
            max_encoder_tokens=MAX_ENCODER_TOKENS,
            max_new_tokens=MAX_NEW_TOKENS,
            generation_prefix_field=None,
            generation_repetition_guard=False,
        )
        generated_text = str(generation.get("generated_text") or "")
        stripped = generated_text.strip()
        target_text = str(row.get("decoder_text") or "")
        scored_rows.append(
            {
                "row_id": str(row["row_id"]),
                "language_family": str(row.get("language_family") or ""),
                "target_subtype": subtype(row),
                "target_text": target_text,
                "bounded_choice_target_label": str(row.get("bounded_choice_target_label") or ""),
                "generated_text": generated_text,
                "generated_token_count": int(generation.get("generated_token_count") or 0),
                "exact_match": bool(generation.get("exact_match")),
                "target_prefix_match": bool(generation.get("target_prefix_match")),
                "short_or_junk": bool(generation.get("short_or_junk")),
                "degenerate_repetition": bool(generation.get("degenerate_repetition")),
                "internal_token_leak": bool(generation.get("internal_token_leak")),
                "contentful": bool(stripped) and not bool(generation.get("short_or_junk")) and not bool(generation.get("degenerate_repetition")),
            }
        )

    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_subtype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored_rows:
        by_lang[row["language_family"]].append(row)
        by_subtype[row["target_subtype"]].append(row)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Scores exact greedy semantic-output generation on all 189 strict rows for the stage10605 runtime.",
            "Provides the anti-cheat counterpart to first-token full-vocab accuracy by measuring whether the model actually emits the full target semantic handle or action string.",
            "This is an evaluation-integrity artifact, not a benchmark promotion result.",
        ],
        "source_artifacts": {
            "strict_rows": display(STRICT_ROWS),
            "runtime_bundle": display(RUNTIME_BUNDLE),
            "execution_result": display(EXECUTION_RESULT),
        },
        "runtime_initialization": init_card,
        "runtime_weights_sha256": ((execution.get("runtime_model_bundle") or {}).get("weights_sha256")),
        "summary": summarize(scored_rows),
        "per_language": {language: summarize(items) for language, items in sorted(by_lang.items())},
        "per_subtype": {name: summarize(items) for name, items in sorted(by_subtype.items())},
        "lowest_signal_rows": [row for row in scored_rows if not row["exact_match"]][:12],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_cards": display(ROW_JSONL),
        },
    }
    write_json(AUDIT_JSON, payload)
    write_jsonl(ROW_JSONL, scored_rows)
    write_json(SUMMARY, payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
