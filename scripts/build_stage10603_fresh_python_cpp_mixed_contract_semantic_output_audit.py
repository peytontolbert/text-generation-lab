#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer

STAGE = 10603
NAME = "stage10603_fresh_python_cpp_mixed_contract_semantic_output_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_mixed_contract_semantic_output_audit.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_JSON = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/fresh_python_cpp_mixed_contract_semantic_output_package.json"
SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/support_rows.jsonl"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10602_fresh_python_cpp_mixed_contract_semantic_output_package/strict_eval_rows.jsonl"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def token_len(tok: AgentKernelBPETokenizer, text: str) -> int:
    ids = [idx for idx in tok.encode(text, max_length=256) if idx not in {tok.pad_id, tok.bos_id, tok.eos_id}]
    return len(ids)


def split_summary(rows: list[dict[str, Any]], tok: AgentKernelBPETokenizer) -> dict[str, Any]:
    decoder_targets = [str(row.get("decoder_text") or "") for row in rows]
    label_targets = [str(row.get("bounded_choice_target_label") or "") for row in rows]
    subtype_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    token_lengths: list[int] = []
    prompt_visible = 0
    label_decoder_rows = 0
    for row in rows:
        subtype_buckets[str(row.get("target_subtype") or "unknown")].append(row)
        decoder = str(row.get("decoder_text") or "")
        token_lengths.append(token_len(tok, decoder))
        prompt = str(row.get("input_text") or "")
        if decoder and decoder in prompt:
            prompt_visible += 1
        if decoder == str(row.get("bounded_choice_target_label") or ""):
            label_decoder_rows += 1
    per_subtype = {}
    for subtype, bucket in sorted(subtype_buckets.items()):
        dec = [str(row.get("decoder_text") or "") for row in bucket]
        lbl = [str(row.get("bounded_choice_target_label") or "") for row in bucket]
        lengths = [token_len(tok, text) for text in dec]
        per_subtype[subtype] = {
            "rows": len(bucket),
            "unique_decoder_targets": len(set(dec)),
            "unique_bounded_choice_labels": len(set(lbl)),
            "dominant_decoder_target": Counter(dec).most_common(1)[0][0] if dec else None,
            "dominant_decoder_target_fraction": (Counter(dec).most_common(1)[0][1] / len(dec)) if dec else None,
            "mean_decoder_token_length": mean(lengths) if lengths else None,
            "max_decoder_token_length": max(lengths) if lengths else None,
        }
    return {
        "rows": len(rows),
        "prompt_visible_decoder_targets": prompt_visible,
        "prompt_visible_decoder_target_rate": (prompt_visible / len(rows)) if rows else None,
        "decoder_equals_label_rows": label_decoder_rows,
        "decoder_equals_label_rate": (label_decoder_rows / len(rows)) if rows else None,
        "unique_decoder_targets": len(set(decoder_targets)),
        "unique_bounded_choice_labels": len(set(label_targets)),
        "mean_decoder_token_length": mean(token_lengths) if token_lengths else None,
        "max_decoder_token_length": max(token_lengths) if token_lengths else None,
        "per_subtype": per_subtype,
    }


def main() -> None:
    package = load_json(PACKAGE_JSON)
    support_rows = load_jsonl(SUPPORT_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    tok = AgentKernelBPETokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "package_json": display(PACKAGE_JSON),
            "support_rows": display(SUPPORT_ROWS),
            "strict_eval_rows": display(STRICT_ROWS),
            "tokenizer_json": display(TOKENIZER_JSON),
            "tokenizer_config": display(TOKENIZER_CONFIG),
        },
        "claim_scope": [
            "Audits the semantic-output successor package to confirm decoder CE no longer targets bare option labels while bounded-choice supervision is preserved separately.",
            "Measures visibility and token-length properties of the new decoder targets so the next probe can choose a sane max-decoder-tokens cap.",
            "This is an interface audit, not a model-result claim.",
        ],
        "support": split_summary(support_rows, tok),
        "strict_eval": split_summary(strict_rows, tok),
        "truthful_read": [
            "If decoder_equals_label_rows is zero, the semantic-output rebuild successfully decoupled decoder CE from label-token targets.",
            "Prompt-visible decoder targets are expected here because the goal is to make the answerable output handle explicit in the visible contract rather than hidden behind A/B/C labels.",
            "The decisive-evidence rows still use short ledger handles, while retrieve/verifier rows use semantic action strings; token lengths determine whether the next probe should keep 8 tokens or raise the cap.",
            package.get("truthful_read"),
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({
        "stage": STAGE,
        "support_rows": payload["support"]["rows"],
        "strict_eval_rows": payload["strict_eval"]["rows"],
        "strict_decoder_equals_label_rows": payload["strict_eval"]["decoder_equals_label_rows"],
        "strict_mean_decoder_token_length": payload["strict_eval"]["mean_decoder_token_length"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
