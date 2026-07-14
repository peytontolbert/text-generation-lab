#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STAGE = 10638
NAME = "stage10638_corrected_strict_exact_label_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "corrected_strict_exact_label_comparison.json"
ROWS_JSONL = OUT_DIR / "corrected_strict_exact_label_comparison_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

MANIFEST = ROOT / "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_request_permuted/repaired_long_context_successor_probe_manifest_permuted.jsonl"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10636_repaired_long_context_successor_probe_permuted/runtime_model/runtime_model_bundle.json"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
GEMMA_MODEL = "gemma3:12b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def exact_text_match(text: str, target: str) -> bool:
    return text.strip() == target.strip()


def parse_label(text: str, allowed_labels: list[str]) -> str | None:
    stripped = text.strip()
    if stripped in allowed_labels:
        return stripped
    for label in sorted(allowed_labels, key=len, reverse=True):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(label)}(?![A-Za-z0-9_])"
        if re.search(pattern, stripped):
            return label
    return None


def ollama_generate(prompt: str, *, model: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "top_k": 1,
            "top_p": 1,
            "num_predict": 8,
        },
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ollama generate failed: {exc}") from exc
    return str(body.get("response") or "")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    from legacy_src.agentkernel_lite.training_data import load_tokenizer
    from legacy_src.agentkernel_lite.training_loop import (
        _build_probe_model,
        _generate_greedy_text,
        _load_runtime_model_bundle,
    )
    import torch

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows = load_jsonl(MANIFEST)
    strict_rows = [
        row for row in manifest_rows
        if row.get("split") == "strict_eval" and row.get("target_subtype") == "decisive_evidence_option"
    ]

    tokenizer = load_tokenizer(TOKENIZER_JSON, TOKENIZER_CONFIG)
    model, implementation_card = _build_probe_model(
        "transformer",
        vocab_size=tokenizer.vocab_size,
        probe_scale="target_100m",
        model_config=MODEL_CONFIG,
    )
    implementation_card = dict(implementation_card)
    implementation_card["runtime_initialization"] = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.eval()

    rows_out: list[dict[str, Any]] = []
    by_model_language: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for row in strict_rows:
        allowed_labels = [str(option.get("label") or "") for option in (row.get("candidate_options") or [])]
        target = str(row.get("target_text") or "").strip()
        language = str(row.get("language_family") or "unknown")

        model_sample = _generate_greedy_text(
            model,
            row,
            tokenizer=tokenizer,
            max_encoder_tokens=1024,
            max_new_tokens=8,
            generation_prefix_field=None,
            generation_repetition_guard=False,
            generation_repetition_guard_top_k=16,
        )
        model_generated = str(model_sample.get("generated_text") or "")
        model_parsed = parse_label(model_generated, allowed_labels)

        gemma_generated = ollama_generate(str(row.get("input_text") or ""), model=GEMMA_MODEL)
        gemma_parsed = parse_label(gemma_generated, allowed_labels)

        row_card = {
            "row_id": row["row_id"],
            "language_family": language,
            "target_text": target,
            "allowed_labels": allowed_labels,
            "target_value": next(
                (str(option.get("value") or "") for option in (row.get("candidate_options") or []) if str(option.get("label") or "") == target),
                "",
            ),
            "model_100m": {
                "generated_text": model_generated,
                "raw_exact_match": exact_text_match(model_generated, target),
                "parsed_label": model_parsed,
                "parsed_label_match": model_parsed == target,
            },
            "gemma3_12b": {
                "generated_text": gemma_generated,
                "raw_exact_match": exact_text_match(gemma_generated, target),
                "parsed_label": gemma_parsed,
                "parsed_label_match": gemma_parsed == target,
            },
        }
        rows_out.append(row_card)

        for model_name, model_info in (("model_100m", row_card["model_100m"]), ("gemma3_12b", row_card["gemma3_12b"])):
            by_model_language[(model_name, language)]["rows"] += 1
            by_model_language[(model_name, language)]["raw_exact_match_rows"] += int(bool(model_info["raw_exact_match"]))
            by_model_language[(model_name, language)]["parsed_label_match_rows"] += int(bool(model_info["parsed_label_match"]))

    summary_by_model: dict[str, Any] = {}
    for model_name in ("model_100m", "gemma3_12b"):
        model_rows = [row for row in rows_out]
        raw_hits = sum(1 for row in model_rows if row[model_name]["raw_exact_match"])
        parsed_hits = sum(1 for row in model_rows if row[model_name]["parsed_label_match"])
        summary_by_model[model_name] = {
            "rows": len(model_rows),
            "raw_exact_match_rows": raw_hits,
            "raw_exact_match_rate": (raw_hits / len(model_rows)) if model_rows else None,
            "parsed_label_match_rows": parsed_hits,
            "parsed_label_match_rate": (parsed_hits / len(model_rows)) if model_rows else None,
            "by_language": {
                language: {
                    "rows": counts["rows"],
                    "raw_exact_match_rows": counts["raw_exact_match_rows"],
                    "raw_exact_match_rate": counts["raw_exact_match_rows"] / counts["rows"] if counts["rows"] else None,
                    "parsed_label_match_rows": counts["parsed_label_match_rows"],
                    "parsed_label_match_rate": counts["parsed_label_match_rows"] / counts["rows"] if counts["rows"] else None,
                }
                for (name, language), counts in sorted(by_model_language.items())
                if name == model_name
            },
            "generated_text_counts": dict(sorted(Counter(str(row[model_name]["generated_text"]) for row in rows_out).items())),
            "parsed_label_counts": dict(sorted(Counter(str(row[model_name]["parsed_label"]) for row in rows_out).items())),
        }

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_boundary": [
            "This comparison uses the corrected permuted strict slice only.",
            "It reports both raw exact label text and parsed-label exactness from the same prompts.",
            "It does not use the inflated first-token bounded-choice metric.",
        ],
        "inputs": {
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
            "gemma_model": GEMMA_MODEL,
        },
        "implementation_card": implementation_card,
        "metrics": summary_by_model,
        "winner_by_metric": {
            "raw_exact_match_rate": (
                "model_100m"
                if summary_by_model["model_100m"]["raw_exact_match_rate"] > summary_by_model["gemma3_12b"]["raw_exact_match_rate"]
                else "gemma3_12b"
                if summary_by_model["model_100m"]["raw_exact_match_rate"] < summary_by_model["gemma3_12b"]["raw_exact_match_rate"]
                else "tie"
            ),
            "parsed_label_match_rate": (
                "model_100m"
                if summary_by_model["model_100m"]["parsed_label_match_rate"] > summary_by_model["gemma3_12b"]["parsed_label_match_rate"]
                else "gemma3_12b"
                if summary_by_model["model_100m"]["parsed_label_match_rate"] < summary_by_model["gemma3_12b"]["parsed_label_match_rate"]
                else "tie"
            ),
        },
        "next_best_step": (
            "Use parsed-label exactness on the corrected strict slice as the minimum honest comparison contract, "
            "then decide whether to train toward exact multi-character label emission or to move to constrained semantic candidate scoring."
        ),
    }

    write_jsonl(ROWS_JSONL, rows_out)
    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY_JSON,
        {
            "stage": STAGE,
            "passed": True,
            "audit": str(AUDIT_JSON.relative_to(ROOT)),
            "rows": len(rows_out),
        },
    )
    print(json.dumps(audit["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
