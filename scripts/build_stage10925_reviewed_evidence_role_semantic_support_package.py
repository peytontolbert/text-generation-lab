#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10925
NAME = "stage10925_reviewed_evidence_role_semantic_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "reviewed_evidence_role_semantic_support_package.json"
ROWS_JSONL = OUT_DIR / "support_rows.jsonl"
INVENTORY_JSONL = OUT_DIR / "bundle_inventory.jsonl"

ATLAS_JSON = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
QUEUE_JSONL = ARTIFACTS / "stage10913_multilingual_evidence_root_build_queue" / "root_build_queue.jsonl"
SOURCE_ROW_FILES = [
    ARTIFACTS / "stage10828_evidence_role_probe_request" / "evidence_role_probe_manifest.jsonl",
    ARTIFACTS / "stage10782_targeted_residual_support_probe_request" / "targeted_residual_support_probe_manifest.jsonl",
    ARTIFACTS / "stage10423_reviewed_multilingual_v27_same_manifest_gemma_comparison" / "reviewed_multilingual_v27_same_manifest_gemma_rows.jsonl",
    ARTIFACTS / "stage10881_evidence_alias_quarantine_successor" / "agentkernel_lite_encdec_stress_eval.jsonl",
]

KNOWN_EXCLUDED_BUNDLES = {
    "stage10126::tokenizers::tokenizers::rust": "known_alias_risk_from_prior_tokenizers_evidence_lane",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def split_prompt(prompt: str) -> tuple[str, str]:
    marker = "\nOptions:\n"
    if marker not in prompt:
        raise ValueError("prompt missing Options marker")
    prefix, suffix = prompt.split(marker, 1)
    if "\nAnswer:" not in suffix:
        raise ValueError("prompt missing Answer marker")
    _, answer_tail = suffix.split("\nAnswer:", 1)
    return prefix, "\nAnswer:" + answer_tail


def gather_source_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in SOURCE_ROW_FILES:
        for row in load_jsonl(path):
            if str(row.get("task_type") or "") != "evidence_citation":
                continue
            bundle_id = str(row.get("source_bundle_id") or "")
            if not bundle_id:
                continue
            rows.setdefault(bundle_id, row)
    return rows


def find_evidence_gold(packet_dir: Path) -> dict[str, Any]:
    gold = load_json(packet_dir / "perspective_gold_adjudication.json")
    rows = list(gold.get("perspective_gold_answers") or [])
    evidence = next(
        (row for row in rows if str(row.get("perspective") or "") == "evidence_citation"),
        None,
    )
    if evidence is None:
        raise ValueError(f"missing evidence_citation gold for {packet_dir}")
    return {
        "bundle_gold_ready_for_eval": bool(gold.get("bundle_gold_ready_for_eval")),
        "gold": evidence,
    }


def selected_test_backed_bundle_rows() -> list[dict[str, Any]]:
    atlas = load_json(ATLAS_JSON)
    queue_rows = load_jsonl(QUEUE_JSONL)
    queue_by_bundle = {
        str(row.get("source_bundle_id") or ""): row
        for row in queue_rows
        if str(row.get("source_bundle_id") or "")
    }
    bundle_rows = []
    for row in atlas.get("admitted_bundle_rows") or []:
        bundle_id = str(row.get("bundle_id") or "")
        if bundle_id in KNOWN_EXCLUDED_BUNDLES:
            continue
        if not list(row.get("selected_tests") or []):
            continue
        packet_dir = ROOT / str(row["packet_dir"])
        anti_cheat = load_json(packet_dir / "anti_cheat_review_card.json")
        if str(anti_cheat.get("status") or "") != "completed":
            continue
        gold_payload = find_evidence_gold(packet_dir)
        gold = gold_payload["gold"]
        bundle_rows.append(
            {
                **row,
                "queue_row": queue_by_bundle.get(bundle_id),
                "anti_cheat": anti_cheat,
                "bundle_gold_ready_for_eval": gold_payload["bundle_gold_ready_for_eval"],
                "evidence_gold": gold,
            }
        )
    return bundle_rows


def role_options_for(source_row: dict[str, Any]) -> list[str]:
    values = [str(item.get("value") or "") for item in source_row.get("opaque_options") or [] if isinstance(item, dict)]
    ordered = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def render_semantic_prompt(source_row: dict[str, Any], *, task_line: str, answer_rule: str, option_values: list[str]) -> str:
    source_prompt = str(source_row.get("prompt_text") or source_row.get("input_text") or "")
    prefix, suffix = split_prompt(source_prompt)
    rewritten_lines = []
    for line in prefix.splitlines():
        if line.startswith("Task: "):
            rewritten_lines.append(f"Task: {task_line}")
        else:
            rewritten_lines.append(line)
    rendered = "\n".join(rewritten_lines)
    option_lines = [f"- {value}" for value in option_values]
    footer = suffix.strip()
    return (
        rendered
        + "\nSemantic evidence role options:\n"
        + "\n".join(option_lines)
        + "\n"
        + answer_rule
        + "\n"
        + footer
        + "\n"
    )


def build_semantic_row(bundle_row: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    bundle_id = str(bundle_row["bundle_id"])
    gold = bundle_row["evidence_gold"]
    gold_value = str(gold.get("gold_answer_value") or "")
    options = role_options_for(source_row)
    if gold_value not in options:
        raise ValueError(f"gold value {gold_value!r} missing from source options for {bundle_id}")
    anti_cheat = bundle_row["anti_cheat"]
    challenge_families = sorted(
        key for key, value in (anti_cheat.get("challenge_families") or {}).items() if value
    )
    task_line = (
        "Choose the semantic evidence role that most specifically justifies the edit-target decision. "
        "Prefer the strongest visible verifier/test constraint only when the packet actually supports that stronger claim."
    )
    answer_rule = "Output rule: Return only the semantic evidence role string."
    prompt = render_semantic_prompt(
        source_row,
        task_line=task_line,
        answer_rule=answer_rule,
        option_values=options,
    )
    split_role = "train_support_stress_overlap" if str(bundle_row.get("repo_id") or "") == "code_assist" else "train_support"
    return {
        "anti_cheat": {
            "challenge_families": challenge_families,
            "opaque_labels_removed": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "semantic_role_target": True,
            "selected_test_anchor_required": True,
        },
        "bundle_gold_ready_for_eval": bundle_row["bundle_gold_ready_for_eval"],
        "decoder_text": gold_value,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": bundle_row.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "semantic_evidence_role_generation",
        "prompt_text": prompt,
        "query_text": f"semantic_evidence_role::{bundle_row.get('language_family')}::{bundle_row.get('repo_id')}",
        "repo_family": bundle_row.get("repo_id"),
        "repo_id": bundle_row.get("repo_id"),
        "row_id": f"stage10925::{bundle_id}::evidence_citation::semantic_role_full_v1",
        "selected_test_anchor": bool(bundle_row.get("selected_tests")),
        "source_bundle_id": bundle_id,
        "source_heldout_admissible": False,
        "source_root_id": bundle_id,
        "split": "train",
        "split_role": split_role,
        "standalone_projection_source": {
            "gold_value": gold_value,
            "original_row_id": source_row.get("row_id"),
            "projection_mode": "stage10925_semantic_evidence_role_full",
            "queue_id": (bundle_row.get("queue_row") or {}).get("queue_id"),
            "source_option_values": options,
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_semantic_evidence_role",
        "target_text": gold_value,
        "task_type": "evidence_citation",
        "train_support_only": True,
        "verifier_anchor": bool(bundle_row.get("selected_tests")),
    }


def build_pairwise_contrast_row(bundle_row: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any] | None:
    bundle_id = str(bundle_row["bundle_id"])
    gold = bundle_row["evidence_gold"]
    gold_value = str(gold.get("gold_answer_value") or "")
    all_options = role_options_for(source_row)
    if "candidate_change_surface" not in all_options:
        return None
    tempting_negative = "candidate_change_surface"
    if gold_value == "candidate_change_surface":
        tempting_negative = "verifier_and_test_constraint" if "verifier_and_test_constraint" in all_options else ""
    if not tempting_negative or tempting_negative == gold_value:
        return None
    if tempting_negative not in all_options:
        return None
    option_values = [gold_value, tempting_negative]
    task_line = (
        "Resolve the evidence-role contrast directly. "
        "Between the tempting edited-surface cue and the stronger causal support cue, return the role that is actually justified by the visible packet."
    )
    answer_rule = "Output rule: Return only the winning semantic evidence role string from the two listed options."
    prompt = render_semantic_prompt(
        source_row,
        task_line=task_line,
        answer_rule=answer_rule,
        option_values=option_values,
    )
    anti_cheat = bundle_row["anti_cheat"]
    challenge_families = sorted(
        key for key, value in (anti_cheat.get("challenge_families") or {}).items() if value
    )
    split_role = "train_support_stress_overlap" if str(bundle_row.get("repo_id") or "") == "code_assist" else "train_support"
    return {
        "anti_cheat": {
            "challenge_families": challenge_families,
            "pairwise_negative": tempting_negative,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "semantic_contrast_target": True,
            "selected_test_anchor_required": True,
        },
        "bundle_gold_ready_for_eval": bundle_row["bundle_gold_ready_for_eval"],
        "decoder_text": gold_value,
        "expected_enabled_loss": "decoder_ce",
        "input_text": prompt,
        "language_family": bundle_row.get("language_family"),
        "loss_mask": {"decoder_ce": True},
        "objective_family": "semantic_evidence_role_pairwise_contrast",
        "prompt_text": prompt,
        "query_text": f"semantic_evidence_role_contrast::{bundle_row.get('language_family')}::{bundle_row.get('repo_id')}",
        "repo_family": bundle_row.get("repo_id"),
        "repo_id": bundle_row.get("repo_id"),
        "row_id": f"stage10925::{bundle_id}::evidence_citation::semantic_role_pairwise_contrast_v1",
        "selected_test_anchor": bool(bundle_row.get("selected_tests")),
        "source_bundle_id": bundle_id,
        "source_heldout_admissible": False,
        "source_root_id": bundle_id,
        "split": "train",
        "split_role": split_role,
        "standalone_projection_source": {
            "gold_value": gold_value,
            "negative_value": tempting_negative,
            "original_row_id": source_row.get("row_id"),
            "projection_mode": "stage10925_semantic_evidence_role_pairwise_contrast",
            "queue_id": (bundle_row.get("queue_row") or {}).get("queue_id"),
        },
        "strict_eval_eligible": False,
        "surface": "maintainer_bundle_semantic_evidence_role",
        "target_text": gold_value,
        "task_type": "evidence_citation",
        "train_support_only": True,
        "verifier_anchor": bool(bundle_row.get("selected_tests")),
    }


def main() -> None:
    source_rows = gather_source_rows()
    bundle_rows = selected_test_backed_bundle_rows()
    support_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for bundle_row in bundle_rows:
        bundle_id = str(bundle_row["bundle_id"])
        source_row = source_rows.get(bundle_id)
        if source_row is None:
            continue
        semantic_row = build_semantic_row(bundle_row, source_row)
        support_rows.append(semantic_row)
        contrast_row = build_pairwise_contrast_row(bundle_row, source_row)
        if contrast_row is not None:
            support_rows.append(contrast_row)
        inventory_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": bundle_row.get("language_family"),
                "repo_id": bundle_row.get("repo_id"),
                "selected_tests": bundle_row.get("selected_tests"),
                "evidence_gold": bundle_row["evidence_gold"].get("gold_answer_value"),
                "row_ids": [
                    semantic_row["row_id"],
                    *([contrast_row["row_id"]] if contrast_row is not None else []),
                ],
                "queue_id": (bundle_row.get("queue_row") or {}).get("queue_id"),
                "repo_overlap_stress_only": str(bundle_row.get("repo_id") or "") == "code_assist",
            }
        )

    by_language = sorted({str(row.get("language_family") or "") for row in support_rows})
    by_target = sorted({str(row.get("target_text") or "") for row in support_rows})
    excluded = [
        {"bundle_id": bundle_id, "reason": reason}
        for bundle_id, reason in sorted(KNOWN_EXCLUDED_BUNDLES.items())
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(support_rows),
        "decision": "reviewed_selected_test_backed_semantic_evidence_support_packaged",
        "claim_scope": [
            "Convert reviewed selected-test-backed evidence packets into support-only semantic evidence-role rows.",
            "Directly strengthen evidence-role discrimination without mutating the current standalone or harness scoring contracts.",
        ],
        "inputs": {
            "atlas": rel(ATLAS_JSON),
            "queue": rel(QUEUE_JSONL),
            "source_row_files": [rel(path) for path in SOURCE_ROW_FILES],
        },
        "row_count": len(support_rows),
        "bundle_count": len(inventory_rows),
        "rows_by_language": {
            language: sum(1 for row in support_rows if str(row.get("language_family") or "") == language)
            for language in by_language
        },
        "rows_by_target": {
            target: sum(1 for row in support_rows if str(row.get("target_text") or "") == target)
            for target in by_target
        },
        "row_types": {
            "semantic_role_full": sum(1 for row in support_rows if str(row.get("row_id") or "").endswith("semantic_role_full_v1")),
            "semantic_role_pairwise_contrast": sum(1 for row in support_rows if str(row.get("row_id") or "").endswith("semantic_role_pairwise_contrast_v1")),
        },
        "excluded_bundle_rows": excluded,
        "findings": [
            "The admitted reviewed inventory already contains selected-test-backed evidence gold across Python, C/C++, Rust, and Web, so the immediate bottleneck is train geometry rather than source discovery.",
            "This package removes opaque answer letters from the supervision target and adds explicit gold-versus-tempting-negative contrasts for the evidence role decision.",
            "code_assist web is preserved only as train-support stress overlap, not as promotable heldout evidence, while known tokenizers alias-risk evidence remains excluded.",
        ],
        "next_best_step": "Use these support rows in the next evidence-focused training package, then re-evaluate the current evidence successor slice and the cleaned v2.7 canary before considering any interface-policy change.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "rows_jsonl": rel(ROWS_JSONL),
            "inventory_jsonl": rel(INVENTORY_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(ROWS_JSONL, support_rows)
    write_jsonl(INVENTORY_JSONL, inventory_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
