#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10602
NAME = "stage10602_fresh_python_cpp_mixed_contract_semantic_output_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_mixed_contract_semantic_output_package.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "support_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PACKAGE = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/fresh_python_cpp_visible_candidate_mixed_contract_package.json"
SOURCE_SUPPORT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/support_rows.jsonl"
SOURCE_STRICT_ROWS = ROOT / "runs/local/artifacts/stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package/strict_eval_rows.jsonl"


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


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def replace_return_instruction(prompt: str, replacement: str) -> str:
    lines = prompt.rstrip().splitlines()
    if lines and lines[-1].strip().lower() == "return only the option label.":
        lines[-1] = replacement
        return "\n".join(lines)
    return prompt.rstrip() + "\n" + replacement


def ledger_id_for_gold(row: dict[str, Any]) -> str:
    source = row.get("standalone_projection_source") or {}
    gold_value = str(source.get("gold_value") or "")
    ledger = source.get("ledger") or []
    for item in ledger:
        if str(item.get("semantic") or "") == gold_value:
            return str(item.get("ledger_id") or "")
    return ""


def semantic_output_choices(row: dict[str, Any]) -> list[dict[str, str]]:
    source = row.get("standalone_projection_source") or {}
    opaque_options = source.get("opaque_options") or row.get("opaque_options") or []
    ledger = source.get("ledger") or []
    semantic_to_ledger = {str(item.get("semantic") or ""): str(item.get("ledger_id") or "") for item in ledger}
    out: list[dict[str, str]] = []
    for option in opaque_options:
        label = str(option.get("label") or "")
        value = str(option.get("value") or "")
        output_text = semantic_to_ledger.get(value, value)
        out.append({"label": label, "value": value, "output_text": output_text})
    return out


def transform_row(row: dict[str, Any]) -> dict[str, Any]:
    out = clone(row)
    subtype = str(out.get("target_subtype") or "")
    old_label = str(out.get("target_text") or out.get("decoder_text") or "")
    source = out.get("standalone_projection_source") or {}
    gold_value = str(source.get("gold_value") or "")
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat["decoder_target_is_option_label"] = False
    anti_cheat["semantic_output_contract_present"] = True
    out["anti_cheat"] = anti_cheat

    if subtype == "decisive_evidence_top1":
        gold_output = ledger_id_for_gold(out)
        if not gold_output:
            raise ValueError(f"missing gold ledger id for {out.get('row_id')}")
        out["input_text"] = replace_return_instruction(
            str(out.get("input_text") or ""),
            "Return only the evidence handle (for example E01), not the option label.",
        )
        out["prompt_text"] = out["input_text"]
        out["target_text"] = gold_output
        out["decoder_text"] = gold_output
        out["bounded_choice_target_label"] = old_label
        out["semantic_output_choices"] = semantic_output_choices(out)
        out["semantic_output_target_kind"] = "ledger_id"
        out["standalone_projection_source"] = dict(source)
        out["standalone_projection_source"]["semantic_decoder_target"] = gold_output
        out["standalone_projection_source"]["semantic_output_choices"] = out["semantic_output_choices"]
        out["row_id"] = str(row.get("row_id") or "") + "::semantic_output"
        return out

    if subtype in {"retrieve_answer_abstain", "verifier_outcome_masked"}:
        if not gold_value:
            raise ValueError(f"missing gold value for {out.get('row_id')}")
        out["input_text"] = replace_return_instruction(
            str(out.get("input_text") or ""),
            "Return only the answer value, not the option label.",
        )
        out["prompt_text"] = out["input_text"]
        out["target_text"] = gold_value
        out["decoder_text"] = gold_value
        out["bounded_choice_target_label"] = old_label
        out["semantic_output_choices"] = semantic_output_choices(out)
        out["semantic_output_target_kind"] = "visible_choice_value"
        out["standalone_projection_source"] = dict(source)
        out["standalone_projection_source"]["semantic_decoder_target"] = gold_value
        out["standalone_projection_source"]["semantic_output_choices"] = out["semantic_output_choices"]
        out["row_id"] = str(row.get("row_id") or "") + "::semantic_output"
        return out

    raise ValueError(f"unsupported target_subtype: {subtype}")


def transform_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [transform_row(row) for row in rows]
    out.sort(key=lambda row: str(row.get("row_id") or ""))
    return out


def target_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subtype_counts = Counter(str(row.get("target_subtype") or "") for row in rows)
    decoder_counts = Counter(str(row.get("decoder_text") or "") for row in rows)
    label_counts = Counter(str(row.get("bounded_choice_target_label") or "") for row in rows)
    return {
        "rows": len(rows),
        "target_subtype_counts": dict(sorted(subtype_counts.items())),
        "unique_decoder_targets": len(decoder_counts),
        "unique_bounded_choice_labels": len(label_counts),
        "dominant_decoder_target": decoder_counts.most_common(1)[0][0] if decoder_counts else None,
        "dominant_decoder_target_fraction": (decoder_counts.most_common(1)[0][1] / len(rows)) if rows else None,
    }


def main() -> None:
    source_package = load_json(SOURCE_PACKAGE)
    support_rows = transform_rows(load_jsonl(SOURCE_SUPPORT_ROWS))
    strict_rows = transform_rows(load_jsonl(SOURCE_STRICT_ROWS))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Transforms the audited stage10591 fresh Python/C++ mixed-contract package into a semantic-output successor without changing the underlying fresh-root rows.",
            "Decoder CE now targets visible semantic handles instead of bare option labels, while bounded-choice supervision is preserved separately through bounded_choice_target_label.",
            "This is an interface repair package meant to reduce label-token collapse pressure before the next diagnostic or promotable probe.",
        ],
        "inputs": {
            "source_package": display(SOURCE_PACKAGE),
            "source_support_rows": display(SOURCE_SUPPORT_ROWS),
            "source_strict_rows": display(SOURCE_STRICT_ROWS),
        },
        "rows": {
            "support_rows": len(support_rows),
            "strict_eval_rows": len(strict_rows),
        },
        "language_counts": {
            "support": dict(sorted(Counter(str(row.get("language_family") or "") for row in support_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("language_family") or "") for row in strict_rows).items())),
        },
        "target_views": {
            "support": target_summary(support_rows),
            "strict_eval": target_summary(strict_rows),
            "source_truth_note": source_package.get("truthful_read") if isinstance(source_package, dict) else None,
        },
        "truthful_read": [
            "The underlying fresh-root package is unchanged from stage10591; only the decoder contract is changed.",
            "Decisive evidence rows now decode visible ledger handles like E01/E02 instead of A-F labels.",
            "Retrieve/verifier rows now decode visible action values like ANSWER_WITH_RETRIEVED_EVIDENCE or NEEDS_VERIFIER instead of A-D labels.",
            "Bounded-choice supervision remains available through bounded_choice_target_label, so constrained scoring and decoder CE can now be trained against different targets.",
        ],
        "outputs": {
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "strict_eval_rows": display(STRICT_ROWS_JSONL),
            "package_json": display(SUMMARY_JSON),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({"stage": STAGE, "support_rows": len(support_rows), "strict_eval_rows": len(strict_rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
