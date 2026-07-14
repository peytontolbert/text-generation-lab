#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10543
NAME = "stage10543_masked_projection_successor_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "masked_projection_successor_package.json"
ALL_ROWS_PATH = OUT_DIR / "masked_projection_successor_rows.jsonl"
TRAIN_ROWS_PATH = OUT_DIR / "train_rows.jsonl"
VALIDATION_ROWS_PATH = OUT_DIR / "validation_rows.jsonl"
STRICT_ROWS_PATH = OUT_DIR / "strict_eval_rows.jsonl"

CLEAN_DIR = ROOT / "runs/local/artifacts/stage10528_cleaned_heldout_anticheat_successor"
COMPILED_ROWS_PATH = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

KEEP_BASE_SUBTYPES = {
    "retrieve_answer_abstain",
    "evidence_chain",
    "abstain",
    "next_action",
}

MASKED_VERIFIER_LINE = "Verifier route: [MASKED_FOR_TARGET_LEAKAGE_AUDIT]"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def split_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "train": load_jsonl(CLEAN_DIR / "train_rows.jsonl"),
        "validation": load_jsonl(CLEAN_DIR / "validation_rows.jsonl"),
        "strict_eval": load_jsonl(CLEAN_DIR / "strict_eval_rows.jsonl"),
    }


def mask_verifier_input(text: str) -> str:
    masked = re.sub(r"^Verifier route: .*?$", MASKED_VERIFIER_LINE, text, flags=re.MULTILINE)
    masked = re.sub(r"^Test selection route: .*?$", "Test selection route: [MASKED_FOR_TARGET_LEAKAGE_AUDIT]", masked, flags=re.MULTILINE)
    return masked


def cloned_row(base: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(base))
    out.setdefault("decoder_text", str(out.get("target_text") or ""))
    out.setdefault("loss_mask", {"decoder_ce": True})
    out.setdefault("disable_losses", [])
    out.setdefault("expected_enabled_loss", "decoder_ce")
    out.setdefault("prompt_text", str(out.get("input_text") or ""))
    out.setdefault("objective_family", "masked_projection_successor")
    out.setdefault("target_token_len", None)
    return out


def anti_cheat_card(base: dict[str, Any], *, prompt_target_leak: bool, prompt_target_leak_source: str) -> dict[str, Any]:
    card = dict(base.get("anti_cheat") or {})
    card.update(
        {
            "prompt_target_leak": bool(prompt_target_leak),
            "prompt_target_leak_source": prompt_target_leak_source,
            "same_root_train_eval_forbidden": True,
            "metadata_cleaned_stage": STAGE,
        }
    )
    return card


def derive_top1(row: dict[str, Any]) -> dict[str, Any]:
    target = json.loads(str(row.get("target_text") or "[]"))
    if not isinstance(target, list) or not target:
        raise ValueError(f"missing decisive_evidence list for {row.get('row_id')}")
    top1 = str(target[0])
    out = cloned_row(row)
    out["row_id"] = f"{row['row_id']}::top1"
    out["target_subtype"] = "decisive_evidence_top1"
    out["target_text"] = top1
    out["decoder_text"] = top1
    out["target_family"] = "bounded_decision"
    out["anti_cheat"] = anti_cheat_card(row, prompt_target_leak=(top1 in str(row.get("input_text") or "")), prompt_target_leak_source="stage10543_top1_projection")
    return out


def derive_masked_verifier(compiled_row: dict[str, Any], template_row: dict[str, Any]) -> dict[str, Any]:
    out = cloned_row(template_row)
    target_text = str(compiled_row.get("target_text") or "")
    input_text = mask_verifier_input(str(compiled_row.get("input_text") or ""))
    out["row_id"] = f"{compiled_row['row_id']}::masked"
    out["input_text"] = input_text
    out["prompt_text"] = input_text
    out["target_subtype"] = "verifier_outcome_masked"
    out["target_text"] = target_text
    out["decoder_text"] = target_text
    out["target_family"] = "bounded_decision"
    out["anti_cheat"] = anti_cheat_card(out, prompt_target_leak=(target_text in input_text), prompt_target_leak_source="stage10543_masked_verifier_projection")
    return out


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def length_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(row.get("target_text") or "")) for row in rows]
    return {
        "rows": len(lengths),
        "min": min(lengths) if lengths else None,
        "max": max(lengths) if lengths else None,
        "mean": mean(lengths) if lengths else None,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_splits = split_rows()
    compiled_rows = load_jsonl(COMPILED_ROWS_PATH)

    templates_by_root: dict[str, dict[str, Any]] = {}
    clean_roots_by_split: dict[str, set[str]] = defaultdict(set)
    source_rows_by_split_and_root: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for split_name, rows in clean_splits.items():
        for row in rows:
            root_id = str(row.get("root_id") or "")
            clean_roots_by_split[split_name].add(root_id)
            templates_by_root.setdefault(root_id, row)
            source_rows_by_split_and_root[split_name][root_id].append(row)

    verifier_by_root: dict[str, dict[str, Any]] = {}
    for row in compiled_rows:
        if str(row.get("target_subtype") or "") == "verifier_outcome":
            verifier_by_root[str(row.get("root_id") or "")] = row

    output_splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "strict_eval": []}
    retained_base_subtypes = Counter()
    added_top1 = Counter()
    added_verifier = Counter()

    for split_name, rows in clean_splits.items():
        for row in rows:
            subtype = str(row.get("target_subtype") or "")
            if subtype in KEEP_BASE_SUBTYPES:
                output_splits[split_name].append(cloned_row(row))
                retained_base_subtypes[subtype] += 1
            if subtype == "decisive_evidence":
                top1 = derive_top1(row)
                output_splits[split_name].append(top1)
                added_top1[split_name] += 1

    for split_name, root_ids in clean_roots_by_split.items():
        for root_id in sorted(root_ids):
            compiled_verifier = verifier_by_root.get(root_id)
            if compiled_verifier is None:
                continue
            template = templates_by_root[root_id]
            masked = derive_masked_verifier(compiled_verifier, template)
            output_splits[split_name].append(masked)
            added_verifier[split_name] += 1

    for split_name in output_splits:
        normalized_split = "eval" if split_name == "validation" else split_name
        for row in output_splits[split_name]:
            row["split"] = normalized_split
            row["decoder_text"] = str(row.get("target_text") or "")
            row["loss_mask"] = {"decoder_ce": True}
            row["disable_losses"] = []
            row["expected_enabled_loss"] = "decoder_ce"
            row["prompt_text"] = str(row.get("input_text") or "")
            row["objective_family"] = "masked_projection_successor"
            row["target_token_len"] = None
        output_splits[split_name].sort(key=lambda row: str(row.get("row_id") or ""))

    all_rows = output_splits["train"] + output_splits["validation"] + output_splits["strict_eval"]

    # audits
    split_by_root: dict[str, set[str]] = defaultdict(set)
    leak_counts: dict[str, int] = defaultdict(int)
    for split_name, rows in output_splits.items():
        for row in rows:
            root_id = str(row.get("root_id") or "")
            split_by_root[root_id].add(split_name)
            if bool((row.get("anti_cheat") or {}).get("prompt_target_leak")):
                leak_counts[split_name] += 1
    violating_roots = sorted(root_id for root_id, splits in split_by_root.items() if len(splits) > 1)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(violating_roots) == 0 and sum(leak_counts.values()) == 0,
        "claim_scope": [
            "Short-target successor package for the long-context bootstrap path using the same root-split hygiene as stage10528.",
            "Strict rows remain source-backed and multilingual, but replace long decisive-evidence list generation with top1 evidence-handle generation and a de-leaked verifier outcome projection.",
            "This is a staging curriculum and bootstrap-heldout successor for exact generation, not a broad maintainer headline by itself.",
        ],
        "inputs": {
            "clean_successor": display(CLEAN_DIR / "cleaned_heldout_anticheat_successor.json"),
            "compiled_multitarget_rows": display(COMPILED_ROWS_PATH),
        },
        "rows": {
            "train": len(output_splits["train"]),
            "validation": len(output_splits["validation"]),
            "strict_eval": len(output_splits["strict_eval"]),
            "all": len(all_rows),
        },
        "subtype_counts": {
            split_name: count_by(rows, "target_subtype") for split_name, rows in output_splits.items()
        },
        "language_counts": {
            split_name: count_by(rows, "language_family") for split_name, rows in output_splits.items()
        },
        "target_length": {
            split_name: length_summary(rows) for split_name, rows in output_splits.items()
        },
        "anti_cheat": {
            "root_split_violations": len(violating_roots),
            "violating_roots": violating_roots[:20],
            "prompt_target_leak_rows_by_split": dict(sorted(leak_counts.items())),
            "strict_prompt_target_leak_rows": leak_counts.get("strict_eval", 0),
            "same_root_train_eval_forbidden": True,
        },
        "derivation": {
            "retained_base_subtypes": dict(retained_base_subtypes),
            "added_decisive_evidence_top1_rows_by_split": dict(added_top1),
            "added_verifier_outcome_masked_rows_by_split": dict(added_verifier),
            "masked_verifier_line": MASKED_VERIFIER_LINE,
        },
        "outputs": {
            "all_rows": display(ALL_ROWS_PATH),
            "train_rows": display(TRAIN_ROWS_PATH),
            "validation_rows": display(VALIDATION_ROWS_PATH),
            "strict_rows": display(STRICT_ROWS_PATH),
        },
        "next_best_step": "Use this successor package for the next bootstrap seq2seq probe and same-manifest Gemma comparison. Keep the 24-row repaired overlay as a canary, and treat the old 36-row long-list strict slice as a hard frontier rather than the next promotion target.",
    }

    write_jsonl(ALL_ROWS_PATH, all_rows)
    write_jsonl(TRAIN_ROWS_PATH, output_splits["train"])
    write_jsonl(VALIDATION_ROWS_PATH, output_splits["validation"])
    write_jsonl(STRICT_ROWS_PATH, output_splits["strict_eval"])
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
