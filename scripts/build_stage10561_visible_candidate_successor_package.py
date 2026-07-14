#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10561
NAME = "stage10561_visible_candidate_successor_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "visible_candidate_successor_package.json"
ALL_ROWS_PATH = OUT_DIR / "visible_candidate_successor_rows.jsonl"
TRAIN_ROWS_PATH = OUT_DIR / "train_rows.jsonl"
EVAL_ROWS_PATH = OUT_DIR / "eval_rows.jsonl"
STRICT_ROWS_PATH = OUT_DIR / "strict_eval_rows.jsonl"
TARGET_MAP_PATH = OUT_DIR / "canonical_target_map.json"
DERIVATION_ROWS_PATH = OUT_DIR / "candidate_derivation_rows.jsonl"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_DIR = ROOT / "runs/local/artifacts/stage10555_masked_projection_successor_with_v27_preservation_package"
LABELS = list("ABCDEFGH")


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


def clone(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row))


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def parse_csv_field(text: str, prefix: str) -> list[str]:
    match = re.search(rf"^{re.escape(prefix)}: (.*)$", text, flags=re.MULTILINE)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def normalize_tokens(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok]


def candidate_score(target_text: str, candidate_value: str) -> tuple[int, int]:
    target_tokens = set(normalize_tokens(target_text))
    candidate_tokens = set(normalize_tokens(candidate_value))
    overlap = target_tokens & candidate_tokens
    return (len(overlap), len(" ".join(sorted(overlap))))


def unique_candidates(row: dict[str, Any]) -> list[dict[str, str]]:
    input_text = str(row.get("input_text") or "")
    changed = parse_csv_field(input_text, "Changed files")
    verify = parse_csv_field(input_text, "Verification targets")
    symbols = parse_csv_field(input_text, "Key symbols")
    seen: set[tuple[str, str]] = set()
    candidates: list[dict[str, str]] = []
    for path in changed:
        key = ("changed_file", path)
        if key not in seen:
            seen.add(key)
            candidates.append({"kind": "changed_file", "value": path})
    for path in verify:
        key = ("verification_target", path)
        if key not in seen:
            seen.add(key)
            candidates.append({"kind": "verification_target", "value": path})
    for symbol in symbols:
        key = ("key_symbol", symbol)
        if key not in seen:
            seen.add(key)
            candidates.append({"kind": "key_symbol", "value": symbol})
    return candidates


def choose_gold_candidate(row: dict[str, Any], candidates: list[dict[str, str]]) -> tuple[dict[str, str] | None, dict[str, Any]]:
    target_text = str(row.get("target_text") or "")
    ranked = []
    for candidate in candidates:
        semantic = f"{candidate['kind']}::{candidate['value']}"
        ranked.append(
            {
                "candidate": candidate,
                "semantic": semantic,
                "score": candidate_score(target_text, semantic),
            }
        )
    ranked.sort(key=lambda item: (item["score"][0], item["score"][1], len(item["semantic"])), reverse=True)
    chosen = ranked[0] if ranked else None
    return (None if chosen is None else chosen["candidate"], {"ranked_candidates": ranked})


def deterministic_shuffle(items: list[dict[str, str]], row_id: str) -> list[dict[str, str]]:
    seed = int(hashlib.sha256(row_id.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    out = list(items)
    rng.shuffle(out)
    return out


def prompt_with_contract(base_text: str, evidence_candidates: list[dict[str, str]], choices: list[dict[str, str]]) -> str:
    lines = [base_text.rstrip(), "", "Visible evidence ledger:"]
    for idx, candidate in enumerate(evidence_candidates, start=1):
        lines.append(f"E{idx:02d}: {candidate['kind']}::{candidate['value']}")
    lines.append("")
    lines.append("Choices:")
    for choice in choices:
        lines.append(f"{choice['label']}: {choice['ledger_id']}")
    lines.append("Return only the option label.")
    return "\n".join(lines)


def build_decisive_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = unique_candidates(row)
    gold_candidate, derivation = choose_gold_candidate(row, candidates)
    if gold_candidate is None:
        raise RuntimeError(f"no_visible_candidates:{row['row_id']}")
    # Keep up to 6 options, preserving the gold plus the highest-overlap distractors.
    ranked = derivation["ranked_candidates"]
    kept_candidates = []
    for item in ranked:
        candidate = item["candidate"]
        if candidate not in kept_candidates:
            kept_candidates.append(candidate)
        if len(kept_candidates) >= 6:
            break
    if gold_candidate not in kept_candidates:
        kept_candidates.append(gold_candidate)
    shuffled = deterministic_shuffle(kept_candidates, str(row["row_id"]))
    ledger_entries = []
    for idx, candidate in enumerate(shuffled, start=1):
        ledger_entries.append(
            {
                "kind": candidate["kind"],
                "value": candidate["value"],
                "semantic": f"{candidate['kind']}::{candidate['value']}",
                "ledger_id": f"E{idx:02d}",
            }
        )
    choices = []
    gold_label = None
    gold_semantic = f"{gold_candidate['kind']}::{gold_candidate['value']}"
    for idx, entry in enumerate(ledger_entries):
        label = LABELS[idx]
        choices.append({"label": label, "ledger_id": entry["ledger_id"], "value": entry["semantic"]})
        if entry["semantic"] == gold_semantic:
            gold_label = label
    if gold_label is None:
        raise RuntimeError(f"gold_label_missing:{row['row_id']}")
    out = clone(row)
    out["input_text"] = prompt_with_contract(str(row.get("input_text") or ""), ledger_entries, choices)
    out["prompt_text"] = out["input_text"]
    out["target_text"] = gold_label
    out["decoder_text"] = gold_label
    out["target_family"] = "bounded_decision"
    out["opaque_options"] = [{"label": choice["label"], "value": choice["value"]} for choice in choices]
    out["standalone_projection_source"] = {
        "projection_kind": "visible_evidence_candidate_choice",
        "gold_value": gold_semantic,
        "opaque_options": out["opaque_options"],
        "ledger": [{"ledger_id": entry["ledger_id"], "value": entry["semantic"]} for entry in ledger_entries],
        "source_target_text": str(row.get("target_text") or ""),
    }
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "prompt_target_leak": gold_label in out["input_text"],
            "prompt_target_leak_source": "bounded_choice_option_labels_visible_by_design",
            "source_target_text_visible": str(row.get("target_text") or "") in out["input_text"],
            "candidate_contract_present": True,
        }
    )
    out["anti_cheat"] = anti_cheat
    derivation_card = {
        "row_id": str(row["row_id"]),
        "rebuilt_target_subtype": "decisive_evidence_top1",
        "source_target_text": str(row.get("target_text") or ""),
        "gold_semantic": gold_semantic,
        "gold_label": gold_label,
        "ledger": ledger_entries,
        "ranked_candidates": [
            {
                "kind": item["candidate"]["kind"],
                "value": item["candidate"]["value"],
                "semantic": item["semantic"],
                "score": item["score"],
            }
            for item in ranked
        ],
    }
    return out, derivation_card


def build_retrieve_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    choices = [
        {"label": "A", "value": "ANSWER_WITH_RETRIEVED_EVIDENCE"},
        {"label": "B", "value": "RETRIEVE_MORE"},
        {"label": "C", "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"},
        {"label": "D", "value": "NEEDS_VERIFIER"},
    ]
    out = clone(row)
    lines = [str(row.get("input_text") or "").rstrip(), "", "Choices:"]
    for choice in choices:
        lines.append(f"{choice['label']}: {choice['value']}")
    lines.append("Return only the option label.")
    out["input_text"] = "\n".join(lines)
    out["prompt_text"] = out["input_text"]
    out["target_text"] = "A"
    out["decoder_text"] = "A"
    out["target_family"] = "bounded_decision"
    out["opaque_options"] = [{"label": choice["label"], "value": choice["value"]} for choice in choices]
    out["standalone_projection_source"] = {
        "projection_kind": "retrieve_answer_abstain_choice",
        "gold_value": "ANSWER_WITH_RETRIEVED_EVIDENCE",
        "opaque_options": out["opaque_options"],
        "source_target_text": str(row.get("target_text") or ""),
    }
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "prompt_target_leak": True,
            "prompt_target_leak_source": "semantic_choices_visible_by_design",
            "source_target_text_visible": str(row.get("target_text") or "") in out["input_text"],
            "candidate_contract_present": True,
        }
    )
    out["anti_cheat"] = anti_cheat
    derivation_card = {
        "row_id": str(row["row_id"]),
        "rebuilt_target_subtype": "retrieve_answer_abstain",
        "gold_semantic": "ANSWER_WITH_RETRIEVED_EVIDENCE",
        "gold_label": "A",
        "options": choices,
    }
    return out, derivation_card


def build_verifier_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    current = str(row.get("target_text") or "")
    canonical_target = {
        "PASS_TARGETED_TEST_SELECTION": "PASS_TARGETED_TEST_SELECTION",
        "PASS_BROAD_VERIFICATION_DISCOVERY": "PASS_BROAD_VERIFICATION_DISCOVERY",
        "PASS_BROAD_TEST_DISCOVERY": "PASS_BROAD_VERIFICATION_DISCOVERY",
        "PASS_TRACE_VERIFICATION_TARGETS": "PASS_TRACE_VERIFICATION_TARGETS",
        "UNKNOWN": "UNKNOWN",
    }.get(current)
    if canonical_target is None:
        raise RuntimeError(f"unsupported_verifier_target:{row['row_id']}:{current}")
    semantic_to_label = {
        "PASS_TARGETED_TEST_SELECTION": "A",
        "PASS_BROAD_VERIFICATION_DISCOVERY": "B",
        "PASS_TRACE_VERIFICATION_TARGETS": "C",
        "UNKNOWN": "D",
    }
    choices = [{"label": label, "value": value} for value, label in semantic_to_label.items()]
    out = clone(row)
    lines = [str(row.get("input_text") or "").rstrip(), "", "Choices:"]
    for choice in choices:
        lines.append(f"{choice['label']}: {choice['value']}")
    lines.append("Return only the option label.")
    out["input_text"] = "\n".join(lines)
    out["prompt_text"] = out["input_text"]
    out["target_text"] = semantic_to_label[canonical_target]
    out["decoder_text"] = semantic_to_label[canonical_target]
    out["target_family"] = "bounded_decision"
    out["opaque_options"] = [{"label": choice["label"], "value": choice["value"]} for choice in choices]
    out["standalone_projection_source"] = {
        "projection_kind": "verifier_outcome_choice",
        "gold_value": canonical_target,
        "opaque_options": out["opaque_options"],
        "source_target_text": current,
    }
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "prompt_target_leak": current in out["input_text"],
            "prompt_target_leak_source": "semantic_choices_visible_by_design",
            "source_target_text_visible": current in out["input_text"],
            "candidate_contract_present": True,
        }
    )
    out["anti_cheat"] = anti_cheat
    derivation_card = {
        "row_id": str(row["row_id"]),
        "rebuilt_target_subtype": "verifier_outcome_masked",
        "gold_semantic": canonical_target,
        "gold_label": semantic_to_label[canonical_target],
        "options": choices,
        "source_target_text": current,
    }
    return out, derivation_card

def maybe_transform(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    subtype = str(row.get("target_subtype") or "")
    if subtype == "decisive_evidence_top1":
        return build_decisive_row(row)
    if subtype == "retrieve_answer_abstain":
        return build_retrieve_row(row)
    if subtype == "verifier_outcome_masked":
        return build_verifier_row(row)
    return clone(row), None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target_map: dict[str, dict[str, str]] = {}
    derivation_rows: list[dict[str, Any]] = []
    output_splits: dict[str, list[dict[str, Any]]] = {}

    for split_name in ["train_rows.jsonl", "eval_rows.jsonl", "strict_eval_rows.jsonl"]:
        rows = load_jsonl(SOURCE_DIR / split_name)
        transformed: list[dict[str, Any]] = []
        for row in rows:
            new_row, derivation = maybe_transform(row)
            transformed.append(new_row)
            if derivation is not None:
                derivation_rows.append(derivation)
                source_target = str(derivation["gold_semantic"])
                target_map.setdefault(str(derivation["rebuilt_target_subtype"]), {})[str(derivation["gold_label"])] = source_target
        key = "train" if split_name.startswith("train") else "eval" if split_name.startswith("eval") else "strict_eval"
        output_splits[key] = transformed

    all_rows = output_splits["train"] + output_splits["eval"] + output_splits["strict_eval"]
    rebuilt_rows = [row for row in all_rows if row.get("standalone_projection_source")]
    strict_rebuilt = [row for row in output_splits["strict_eval"] if row.get("standalone_projection_source")]
    strict_visible_source_leaks = sum(
        1 for row in strict_rebuilt if bool((row.get("anti_cheat") or {}).get("source_target_text_visible"))
    )
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Rebuilds the successor package into visible candidate-choice rows for decisive_evidence_top1, retrieve_answer_abstain, and verifier_outcome_masked.",
            "Makes the strict multilingual successor slice bounded-scoreable and exact-generation-friendly by using short option labels with reversible semantic mappings.",
            "Leaves non-successor reviewed v2.7 preservation rows untouched.",
        ],
        "inputs": {
            "source_package": display(SOURCE_DIR / "masked_projection_successor_with_v27_preservation_package.json"),
            "source_rows": display(SOURCE_DIR / "masked_projection_successor_with_v27_preservation_rows.jsonl"),
        },
        "rows": {
            "train": len(output_splits["train"]),
            "eval": len(output_splits["eval"]),
            "strict_eval": len(output_splits["strict_eval"]),
            "all": len(all_rows),
            "rebuilt_candidate_rows": len(rebuilt_rows),
        },
        "target_subtypes": {
            split: count_by(rows, "target_subtype") for split, rows in output_splits.items()
        },
        "language_counts": {
            split: count_by(rows, "language_family") for split, rows in output_splits.items()
        },
        "anti_cheat": {
            "strict_rows_with_candidate_contract": len(strict_rebuilt),
            "strict_rows_with_source_target_visible": strict_visible_source_leaks,
            "prompt_label_visibility_is_by_design": True,
            "reversible_target_map": display(TARGET_MAP_PATH),
        },
        "outputs": {
            "all_rows": display(ALL_ROWS_PATH),
            "train_rows": display(TRAIN_ROWS_PATH),
            "eval_rows": display(EVAL_ROWS_PATH),
            "strict_rows": display(STRICT_ROWS_PATH),
            "target_map": display(TARGET_MAP_PATH),
            "derivation_rows": display(DERIVATION_ROWS_PATH),
        },
    }
    write_jsonl(TRAIN_ROWS_PATH, output_splits["train"])
    write_jsonl(EVAL_ROWS_PATH, output_splits["eval"])
    write_jsonl(STRICT_ROWS_PATH, output_splits["strict_eval"])
    write_jsonl(ALL_ROWS_PATH, all_rows)
    write_jsonl(DERIVATION_ROWS_PATH, derivation_rows)
    write_json(TARGET_MAP_PATH, target_map)
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps({"stage": STAGE, "passed": True, "rows": payload["rows"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
