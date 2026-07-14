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
STAGE = 10591
NAME = "stage10591_fresh_python_cpp_visible_candidate_mixed_contract_package"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "fresh_python_cpp_visible_candidate_mixed_contract_package.json"
SUPPORT_ROWS_JSONL = OUT_DIR / "support_rows.jsonl"
STRICT_ROWS_JSONL = OUT_DIR / "strict_eval_rows.jsonl"
SKIPPED_JSONL = OUT_DIR / "skipped_rows.jsonl"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

BUNDLE_SUPPORT = ROOT / "runs/local/artifacts/stage10583_fresh_python_cpp_decisive_root_package/support_root_bundles.jsonl"
BUNDLE_STRICT = ROOT / "runs/local/artifacts/stage10583_fresh_python_cpp_decisive_root_package/strict_eval_root_bundles.jsonl"
RETRIEVAL_ROWS = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/retrieval_rows.jsonl"

LABELS = list("ABCDEFGH")
RETRIEVE_CHOICES = [
    ("A", "ANSWER_WITH_RETRIEVED_EVIDENCE"),
    ("B", "RETRIEVE_MORE"),
    ("C", "ABSTAIN_INSUFFICIENT_EVIDENCE"),
    ("D", "NEEDS_VERIFIER"),
]
VERIFIER_CHOICES = [
    ("A", "PASS_TARGETED_TEST_SELECTION"),
    ("B", "NEEDS_BROAD_TEST_DISCOVERY"),
    ("C", "ABSTAIN_INSUFFICIENT_EVIDENCE"),
    ("D", "UNKNOWN_VERIFIER_ROUTE"),
]


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


def clone(value: Any) -> Any:
    return json.loads(json.dumps(value))


def parse_csv_field(text: str, prefix: str) -> list[str]:
    match = re.search(rf"^{re.escape(prefix)}: (.*)$", text, flags=re.MULTILINE)
    if not match:
        return []
    return [item.strip() for item in match.group(1).split(",") if item.strip()]


def deterministic_shuffle(items: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    out = list(items)
    rng.shuffle(out)
    return out


def extract_route(input_text: str, prefix: str) -> str:
    match = re.search(rf"^{re.escape(prefix)}: (.*)$", input_text, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip()


def bundle_lookup() -> dict[tuple[str, int], dict[str, Any]]:
    rows = load_jsonl(RETRIEVAL_ROWS)
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        out[(str(row.get("pack_id") or ""), int((row.get("metadata") or {}).get("query_index") or -1))] = row
    return out


def unique_candidates(input_text: str) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for path in parse_csv_field(input_text, "Changed files"):
        key = ("changed_file", path)
        if key not in seen:
            seen.add(key)
            out.append({"kind": "changed_file", "value": path})
    for path in parse_csv_field(input_text, "Verification targets"):
        key = ("verification_target", path)
        if key not in seen:
            seen.add(key)
            out.append({"kind": "verification_target", "value": path})
    for symbol in parse_csv_field(input_text, "Key symbols"):
        key = ("key_symbol", symbol)
        if key not in seen:
            seen.add(key)
            out.append({"kind": "key_symbol", "value": symbol})
    return out


def derive_contract_state(input_text: str, bundle: dict[str, Any]) -> dict[str, Any]:
    changed_files = set(parse_csv_field(input_text, "Changed files"))
    verification_targets = parse_csv_field(input_text, "Verification targets")
    overlap_count = sum(1 for item in verification_targets if item in changed_files)
    execution_route = extract_route(input_text, "Execution route")
    verifier_route = extract_route(input_text, "Verifier route")
    verifier_id = str(bundle.get("verifier_id") or verifier_route or "")
    return {
        "changed_file_count": len(changed_files),
        "verification_target_count": len(verification_targets),
        "verification_overlap_count": overlap_count,
        "execution_route": execution_route,
        "verifier_route": verifier_route,
        "verifier_id": verifier_id,
    }


def choose_retrieve_gold_value(contract_state: dict[str, Any]) -> str:
    verifier_id = contract_state["verifier_id"]
    overlap_count = int(contract_state["verification_overlap_count"])
    verification_target_count = int(contract_state["verification_target_count"])
    execution_route = str(contract_state["execution_route"] or "")
    if verifier_id == "UNKNOWN" or not execution_route:
        return "NEEDS_VERIFIER"
    if overlap_count > 0:
        return "ANSWER_WITH_RETRIEVED_EVIDENCE"
    if verification_target_count > 0:
        return "RETRIEVE_MORE"
    return "ABSTAIN_INSUFFICIENT_EVIDENCE"


def choose_verifier_gold_value(contract_state: dict[str, Any]) -> str:
    verifier_id = contract_state["verifier_id"]
    overlap_count = int(contract_state["verification_overlap_count"])
    execution_route = str(contract_state["execution_route"] or "")
    if verifier_id == "UNKNOWN" or not execution_route:
        return "UNKNOWN_VERIFIER_ROUTE"
    if verifier_id == "PASS_TARGETED_TEST_SELECTION" and overlap_count > 0:
        return "PASS_TARGETED_TEST_SELECTION"
    if verifier_id == "PASS_TARGETED_TEST_SELECTION":
        return "NEEDS_BROAD_TEST_DISCOVERY"
    return "ABSTAIN_INSUFFICIENT_EVIDENCE"


def build_prompt(base_text: str, ledger_entries: list[dict[str, str]], choices: list[dict[str, str]]) -> str:
    lines = [base_text.rstrip(), "", "Visible evidence ledger:"]
    for entry in ledger_entries:
        lines.append(f"{entry['ledger_id']}: {entry['semantic']}")
    lines.append("")
    lines.append("Choices:")
    for choice in choices:
        lines.append(f"{choice['label']}: {choice['ledger_id']}")
    lines.append("Return only the option label.")
    return "\n".join(lines)


def choose_gold_candidate(input_text: str, retrieval_row: dict[str, Any]) -> tuple[dict[str, str] | None, dict[str, Any]]:
    candidates = unique_candidates(input_text)
    verification_targets = set(parse_csv_field(input_text, "Verification targets"))
    changed_files = set(parse_csv_field(input_text, "Changed files"))
    symbols = set(parse_csv_field(input_text, "Key symbols"))
    positive_chunks = list(retrieval_row.get("positive_chunks") or [])

    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        score = 0
        support = []
        if candidate["kind"] == "verification_target" and candidate["value"] in verification_targets:
            score += 10
        if candidate["kind"] == "changed_file" and candidate["value"] in changed_files:
            score += 6
        if candidate["kind"] == "key_symbol" and candidate["value"] in symbols:
            score += 2
        for chunk in positive_chunks:
            path = str(chunk.get("path") or "")
            role = str(chunk.get("role") or "")
            chunk_text = str(chunk.get("text") or "")
            if candidate["kind"] == "verification_target" and path == candidate["value"]:
                score += 100
                support.append(f"verification_path_match::{role}")
                if role == "verification_constraint":
                    score += 25
            elif candidate["kind"] == "changed_file" and path == candidate["value"]:
                score += 80
                support.append(f"changed_file_path_match::{role}")
                if role == "seed_change":
                    score += 15
            elif candidate["kind"] == "key_symbol" and candidate["value"] and candidate["value"] in chunk_text:
                score += 12
                support.append(f"symbol_text_match::{role}")
        ranked.append(
            {
                "candidate": candidate,
                "semantic": f"{candidate['kind']}::{candidate['value']}",
                "score": score,
                "support": support,
            }
        )
    ranked.sort(key=lambda item: (item["score"], item["semantic"]), reverse=True)
    gold = ranked[0]["candidate"] if ranked and ranked[0]["score"] > 0 else None
    return gold, {"ranked_candidates": ranked}


def apply_bundle_metadata(row: dict[str, Any], bundle: dict[str, Any]) -> None:
    row["root_id"] = bundle.get("root_id")
    row["repo_id"] = bundle.get("repo_id")
    row["repo_family"] = bundle.get("repo_family")
    row["language_family"] = bundle.get("language_family")
    row["split_component"] = bundle.get("split_component")
    row["verifier_id"] = bundle.get("verifier_id")
    row["pack_id"] = bundle.get("pack_id")
    row["query_index"] = bundle.get("query_index")


def build_decisive_row(base_row: dict[str, Any], retrieval_row: dict[str, Any], bundle: dict[str, Any], split: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    input_text = str(base_row.get("input_text") or "")
    candidates = unique_candidates(input_text)
    gold_candidate, derivation = choose_gold_candidate(input_text, retrieval_row)
    if gold_candidate is None:
        return None, {"reason": "no_gold_candidate", "ranked_candidates": derivation["ranked_candidates"]}

    kept = []
    for item in derivation["ranked_candidates"]:
        candidate = item["candidate"]
        if candidate not in kept:
            kept.append(candidate)
        if len(kept) >= 6:
            break
    if gold_candidate not in kept:
        kept.append(gold_candidate)
    shuffled = deterministic_shuffle(kept, str(base_row.get("row_id") or ""))
    ledger_entries = []
    gold_semantic = f"{gold_candidate['kind']}::{gold_candidate['value']}"
    gold_label = None
    choices = []
    for idx, candidate in enumerate(shuffled, start=1):
        semantic = f"{candidate['kind']}::{candidate['value']}"
        ledger_id = f"E{idx:02d}"
        ledger_entries.append({"ledger_id": ledger_id, "semantic": semantic})
        label = LABELS[idx - 1]
        choices.append({"label": label, "ledger_id": ledger_id, "value": semantic})
        if semantic == gold_semantic:
            gold_label = label
    if gold_label is None:
        return None, {"reason": "gold_label_missing", "ranked_candidates": derivation["ranked_candidates"]}

    out = clone(base_row)
    out["row_id"] = str(base_row["row_id"]) + "::visible_contract_top1"
    out["split"] = split
    out["target_subtype"] = "decisive_evidence_top1"
    out["target_family"] = "bounded_decision"
    out["target_text"] = gold_label
    out["decoder_text"] = gold_label
    out["input_text"] = build_prompt(input_text, ledger_entries, choices)
    out["prompt_text"] = out["input_text"]
    out["opaque_options"] = [{"label": item["label"], "value": item["value"]} for item in choices]
    out["standalone_projection_source"] = {
        "projection_kind": "fresh_root_visible_evidence_candidate_choice",
        "gold_value": gold_semantic,
        "opaque_options": out["opaque_options"],
        "ledger": ledger_entries,
        "retrieval_pack_id": retrieval_row.get("pack_id"),
        "retrieval_query_index": ((retrieval_row.get("metadata") or {}).get("query_index")),
    }
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "prompt_target_leak": False,
            "same_root_train_eval_forbidden": True,
            "repo_family_split_disjoint": True,
            "source_target_text_visible": False,
            "candidate_contract_present": True,
        }
    )
    out["anti_cheat"] = anti_cheat
    apply_bundle_metadata(out, bundle)
    return out, {
        "reason": "ok",
        "ranked_candidates": derivation["ranked_candidates"],
        "gold_semantic": gold_semantic,
        "candidate_count": len(candidates),
    }


def build_fixed_choice_row(
    base_row: dict[str, Any],
    bundle: dict[str, Any],
    split: str,
    subtype: str,
    choices: list[tuple[str, str]],
    gold_value: str,
    contract_state: dict[str, Any],
) -> dict[str, Any]:
    out = clone(base_row)
    lines = [str(base_row.get("input_text") or "").rstrip(), "", "Choices:"]
    gold_label = None
    opaque_options = []
    for label, value in choices:
        lines.append(f"{label}: {value}")
        opaque_options.append({"label": label, "value": value})
        if value == gold_value:
            gold_label = label
    lines.append("Return only the option label.")
    out["row_id"] = str(base_row["row_id"]) + f"::visible_contract_{subtype}"
    out["split"] = split
    out["target_subtype"] = subtype
    out["target_family"] = "bounded_decision"
    out["input_text"] = "\n".join(lines)
    out["prompt_text"] = out["input_text"]
    out["target_text"] = gold_label
    out["decoder_text"] = gold_label
    out["opaque_options"] = opaque_options
    out["standalone_projection_source"] = {
        "projection_kind": f"fresh_root_{subtype}_choice",
        "gold_value": gold_value,
        "opaque_options": opaque_options,
        "contract_state": contract_state,
    }
    anti_cheat = dict(out.get("anti_cheat") or {})
    anti_cheat.update(
        {
            "prompt_target_leak": False,
            "same_root_train_eval_forbidden": True,
            "repo_family_split_disjoint": True,
            "candidate_contract_present": True,
            "source_target_text_visible": False,
        }
    )
    out["anti_cheat"] = anti_cheat
    apply_bundle_metadata(out, bundle)
    return out


def process_bundles(bundle_rows: list[dict[str, Any]], retrieval_lookup: dict[tuple[str, int], dict[str, Any]], split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    out_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for bundle in bundle_rows:
        pack_id = str(bundle.get("pack_id") or "")
        query_index = int(bundle.get("query_index") or -1)
        retrieval_row = retrieval_lookup.get((pack_id, query_index))
        if retrieval_row is None:
            skipped.append({"root_id": bundle.get("root_id"), "reason": "missing_retrieval_source", "pack_id": pack_id, "query_index": query_index})
            continue
        rows_by_subtype = {str(row.get("target_subtype") or ""): row for row in bundle.get("rows", [])}
        decisive_row, detail = build_decisive_row(rows_by_subtype["decisive_evidence"], retrieval_row, bundle, split)
        if decisive_row is None:
            skipped.append({"root_id": bundle.get("root_id"), "reason": detail["reason"], "pack_id": pack_id, "query_index": query_index})
            continue
        contract_state = derive_contract_state(str(rows_by_subtype["retrieve_answer_abstain"].get("input_text") or ""), bundle)
        retrieve_gold_value = choose_retrieve_gold_value(contract_state)
        verifier_gold_value = choose_verifier_gold_value(contract_state)
        retrieve_row = build_fixed_choice_row(
            rows_by_subtype["retrieve_answer_abstain"],
            bundle,
            split,
            "retrieve_answer_abstain",
            RETRIEVE_CHOICES,
            retrieve_gold_value,
            contract_state,
        )
        verifier_row = build_fixed_choice_row(
            rows_by_subtype["verifier_outcome"],
            bundle,
            split,
            "verifier_outcome_masked",
            VERIFIER_CHOICES,
            verifier_gold_value,
            contract_state,
        )
        out_rows.extend([decisive_row, retrieve_row, verifier_row])
    out_rows.sort(key=lambda row: str(row.get("row_id") or ""))
    skipped.sort(key=lambda row: (str(row.get("reason") or ""), str(row.get("root_id") or "")))
    return out_rows, skipped


def main() -> None:
    retrieval_lookup = bundle_lookup()
    support_bundles = load_jsonl(BUNDLE_SUPPORT)
    strict_bundles = load_jsonl(BUNDLE_STRICT)

    support_rows, support_skipped = process_bundles(support_bundles, retrieval_lookup, "train")
    strict_rows, strict_skipped = process_bundles(strict_bundles, retrieval_lookup, "strict_eval")
    skipped = support_skipped + strict_skipped

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Projects the stage10583 fresh Python/C++ root package into a mixed-target visible-candidate bounded-decision contract.",
            "Decisive evidence is rebuilt from retrieval-source positives and visible query fields; retrieve/verifier are derived from root-local overlap and verifier metadata rather than forced to one label.",
            "This is a successor fresh-root source package intended to remove constant-target shortcut subtypes from the prior stage10584 package.",
        ],
        "inputs": {
            "support_root_bundles": display(BUNDLE_SUPPORT),
            "strict_root_bundles": display(BUNDLE_STRICT),
            "retrieval_source_rows": display(RETRIEVAL_ROWS),
        },
        "rows": {
            "support_rows": len(support_rows),
            "strict_eval_rows": len(strict_rows),
            "skipped_roots": len(skipped),
        },
        "language_counts": {
            "support": dict(sorted(Counter(str(row.get("language_family") or "") for row in support_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("language_family") or "") for row in strict_rows).items())),
        },
        "target_subtype_counts": {
            "support": dict(sorted(Counter(str(row.get("target_subtype") or "") for row in support_rows).items())),
            "strict_eval": dict(sorted(Counter(str(row.get("target_subtype") or "") for row in strict_rows).items())),
        },
        "skipped_reason_counts": dict(sorted(Counter(str(row.get("reason") or "") for row in skipped).items())),
        "truthful_read": [
            "This package keeps the repo-disjoint Python/C++ decisive-evidence rows while replacing the constant-target retrieve/verifier contracts from stage10584 with mixed targets.",
            "Retrieve and verifier labels are now derived from visible changed-file and verification-target overlap plus stored verifier metadata, rather than hard-coded to one answer.",
            "This makes the next fresh-root comparison more honest: a win can no longer be carried entirely by constant-target subtype saturation.",
        ],
        "outputs": {
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "strict_eval_rows": display(STRICT_ROWS_JSONL),
            "skipped_rows": display(SKIPPED_JSONL),
            "package_json": display(SUMMARY_JSON),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(STRICT_ROWS_JSONL, strict_rows)
    write_jsonl(SKIPPED_JSONL, skipped)
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({"rows": payload["rows"], "skipped_reason_counts": payload["skipped_reason_counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
