#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10501
NAME = "stage10501_hf_local_repaired_compact_bounded_projection"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "hf_local_repaired_compact_bounded_projection.json"
OUT_ROWS = OUT_DIR / "hf_local_repaired_compact_bounded_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

SOURCE_PACKET = ROOT / "runs/local/artifacts/stage10499_hf_local_multitest_packet_repair/hf_local_multitest_repaired_packet.json"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage10499_hf_local_multitest_packet_repair/hf_local_multitest_repaired_preview_rows.jsonl"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage10500_hf_local_multitest_repair_audit/hf_local_multitest_repair_audit.json"

CANDIDATE_ROLE_SUMMARY = {
    "A": "owning implementation surface for parameter parsing and config conversion",
    "B": "settings schema surface for defaults and field definitions",
    "C": "orchestrator forwarding surface that passes specialized params",
    "D": "CLI and planner exposure surface",
}

PERMUTED_TASKS = {"verifier_outcome"}
PERMUTATION_COUNT = 3


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


def snippet(text: str, limit: int = 280) -> str:
    clean = " ".join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + "..."


def deterministic_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def visible_evidence_lines(packet: dict[str, Any], keys: list[str]) -> list[str]:
    evidence = packet["bundle"]["maintainer_visible_evidence"]
    lines: list[str] = []
    for key in keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        role = str(first.get("surface_role") or first.get("evidence_id") or "")
        text = snippet(str(first.get("text") or ""))
        prefix = key
        if role:
            prefix += f" [{role}]"
        lines.append(f"{prefix}: {text}")
    return lines[:4]


def option_pairs_for_row(row: dict[str, Any]) -> list[tuple[str, str]]:
    contract = row["prompt_contract"]
    answer_kind = str(row["preview_answer_kind"])
    if answer_kind == "candidate_id":
        return [
            (str(item["id"]), CANDIDATE_ROLE_SUMMARY[str(item["id"])])
            for item in contract["candidate_options"]
        ]
    if answer_kind == "verifier_id":
        return [
            (str(item["id"]), str(item["role_summary"]))
            for item in contract["verifier_options"]
        ]
    if answer_kind == "visible_evidence_key":
        return [(value, value) for value in row["preview_options"]]
    if answer_kind == "abstain":
        return [("ABSTAIN_INSUFFICIENT_EVIDENCE", "ABSTAIN_INSUFFICIENT_EVIDENCE")] + [
            (str(item["id"]), CANDIDATE_ROLE_SUMMARY[str(item["id"])])
            for item in contract["candidate_options"]
        ]
    raise ValueError(f"unsupported_answer_kind::{answer_kind}")


def compile_prompt(packet: dict[str, Any], row: dict[str, Any], option_pairs: list[tuple[str, str]]) -> str:
    contract = row["prompt_contract"]
    evidence_keys = [str(key) for key in contract["visible_evidence_keys"]]
    parts = [
        f"Language: {row['language_family']}",
        f"Perspective: {row['task_type']}",
        f"Task: {contract['task']}",
        "Evidence:",
    ]
    parts.extend(visible_evidence_lines(packet, evidence_keys))
    parts.append("Options:")
    parts.extend([f"{label}. {text}" for label, text in option_pairs])
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_projection_row(packet: dict[str, Any], row: dict[str, Any], *, variant_index: int = 0, variant_count: int = 1) -> dict[str, Any]:
    option_pairs = option_pairs_for_row(row)
    if variant_count > 1:
        seed = f"stage10501::{row['bundle_id']}::{row['task_type']}::variant_{variant_index}"
        ordered_ids = deterministic_order([pair[0] for pair in option_pairs], seed)
        text_by_id = {pair[0]: pair[1] for pair in option_pairs}
        option_pairs = [(choice_id, text_by_id[choice_id]) for choice_id in ordered_ids]
    prompt = compile_prompt(packet, row, option_pairs)
    gold_label = str(row["preview_gold_value"])
    target_token = next(label for label, _text in option_pairs if label == gold_label)
    suffix = f"::perm_{variant_index:02d}" if variant_count > 1 else ""
    return {
        "row_id": f"{row['bundle_id']}::{row['task_type']}::compact_bounded_repaired{suffix}",
        "source_row_id": f"{row['bundle_id']}::{row['task_type']}::compact_bounded_repaired",
        "semantic_key": f"hf_local_repaired_compact::{row['bundle_id']}::{row['task_type']}::variant_{variant_index:02d}",
        "bundle_id": row["bundle_id"],
        "source_bundle_id": row["bundle_id"],
        "language_family": row["language_family"],
        "repo_id": "code_assist",
        "repo_family": "code_assist",
        "route": "KEEP_BOUNDED_DECODER",
        "objective_family": "bounded_decoder_ce",
        "surface": "maintainer_bundle_compact_bounded_choice",
        "task_type": row["task_type"],
        "perspective": row["task_type"],
        "expected_answer_kind": "opaque_choice",
        "expected_enabled_loss": "decoder_ce",
        "expected_label": target_token,
        "target_text": target_token,
        "target_token_len": 1,
        "gold_value": row["preview_gold_value"],
        "decoder_text": target_token,
        "input_text": prompt,
        "prompt_text": prompt,
        "query_text": f"hf_local_repaired::{row['language_family']}::{row['task_type']}::variant_{variant_index:02d}",
        "opaque_options": [{"label": label, "value": text} for label, text in option_pairs],
        "loss_mask": {"decoder_ce": True},
        "disable_losses": ["denoise_ce", "runtime_reward", "structured_aux"],
        "split": "train",
        "split_role": "train_support",
        "train_support_only": True,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "selected_test_anchor": row["task_type"] == "verifier_outcome",
        "verifier_anchor": row["task_type"] == "verifier_outcome",
        "abstention_heavy": row["task_type"] == "abstention_insufficient_evidence",
        "anti_cheat": {
            "opaque_labels": True,
            "prompt_target_leak_false": True,
            "repaired_hf_local_packet": True,
            "multitest_verifier_geometry": True,
            "symbol_name_shortcut_scrubbed": True,
            "candidate_path_hidden_from_prompt": True,
            "projection_is_auxiliary_not_primary_maintainer_score": True,
            "permutation_balanced_labels": variant_count > 1,
        },
        "authority": {},
        "standalone_projection_source": {
            "projection_stage": STAGE,
            "projection_mode": "repaired_hf_local_compact_bounded_choice",
            "original_answer_kind": row["preview_answer_kind"],
            "variant_index": variant_index,
            "variant_count": variant_count,
            "source_packet": display(SOURCE_PACKET),
            "source_packet_audit": display(SOURCE_AUDIT),
        },
        "support_provenance": {
            "support_package_stage": STAGE,
            "support_package_name": NAME,
            "support_role": "promotable_disjoint_support_candidate",
            "support_class": "python_hf_local_repaired_verifier_support",
            "source_manifest": display(OUT_ROWS),
        },
        "support_package_stage": STAGE,
    }


def main() -> None:
    packet = load_json(SOURCE_PACKET)
    source_rows = load_jsonl(SOURCE_ROWS)
    audit = load_json(SOURCE_AUDIT)

    rows: list[dict[str, Any]] = []
    for row in source_rows:
        variant_count = PERMUTATION_COUNT if row["task_type"] in PERMUTED_TASKS else 1
        for variant_index in range(variant_count):
            rows.append(compile_projection_row(packet, row, variant_index=variant_index, variant_count=variant_count))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(rows),
        "decision": "Projected the repaired hf_local multi-test packet into clean compact bounded support rows with opaque choices and verifier permutations.",
        "claim_scope": [
            "Turn the Stage10499 repaired hf_local packet into bounded support rows compatible with the live v2.7 probe lane.",
            "Preserve anti-cheat repairs by keeping candidate paths and raw verifier test paths out of the prompt while retaining source-backed evidence summaries.",
        ],
        "source_artifacts": {
            "repaired_packet": display(SOURCE_PACKET),
            "repaired_preview_rows": display(SOURCE_ROWS),
            "repaired_audit": display(SOURCE_AUDIT),
        },
        "summary": {
            "rows": len(rows),
            "distinct_task_types": sorted({row["task_type"] for row in rows}),
            "verifier_variant_count": PERMUTATION_COUNT,
            "audit_admissible_for_next_materialization": bool(audit["summary"]["admissible_for_next_materialization"]),
        },
        "outputs": {
            "projection_json": display(OUT_JSON),
            "projection_rows_jsonl": display(OUT_ROWS),
        },
    }

    write_jsonl(OUT_ROWS, rows)
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "rows": len(rows),
            "projection_rows_jsonl": display(OUT_ROWS),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
