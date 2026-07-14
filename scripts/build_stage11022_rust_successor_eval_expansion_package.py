#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/data/agentkernel-seq2seq-text-lab")
IN_ROWS = ROOT / "runs/local/artifacts/stage11015_ai_adjudicated_fresh_root_package/ai_adjudicated_fresh_root_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts/stage11022_rust_successor_eval_expansion_package"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows) + "\n")


def make_candidate_labels(values: list[str]) -> tuple[list[dict], dict[str, str]]:
    labels = [chr(ord("A") + i) for i in range(len(values))]
    opaque = [{"label": label, "value": value} for label, value in zip(labels, values)]
    return opaque, {value: label for label, value in zip(labels, values)}


def build_row(row: dict) -> dict | None:
    perspective = row.get("perspective")
    bundle_id = row.get("bundle_id", "")
    values: list[str]
    task_type: str
    task: str
    query: str

    if perspective in {"symptom_localization", "patch_impact", "minimal_fix_selection"} and row.get("gold_answer_kind") == "candidate_path":
        values = row.get("candidate_paths") or []
        task_type = perspective
        if perspective == "symptom_localization":
            task = "Choose the most justified edit target from the visible evidence."
            query = "Pick the candidate path that best matches the visible maintenance evidence."
        elif perspective == "patch_impact":
            task = "Choose the candidate path whose patch would most directly change the exposed behavior."
            query = "Pick the candidate path with the highest expected causal impact on the visible symptom."
        else:
            task = "Choose the narrowest candidate path that still fits the visible maintenance evidence."
            query = "Pick the minimal justified repair surface."
        opaque_options, label_map = make_candidate_labels(values)
        target_label = label_map.get(row.get("gold_answer_value"))
        if not target_label:
            return None
    elif perspective == "evidence_citation" and row.get("gold_answer_kind") == "visible_evidence_key":
        values = row.get("visible_evidence_keys") or []
        task_type = "evidence_citation"
        task = "Choose the visible evidence key that best supports the answer."
        query = "Pick the decisive evidence key from the visible evidence ledger."
        opaque_options, label_map = make_candidate_labels(values)
        target_label = label_map.get(row.get("gold_answer_value"))
        if not target_label:
            return None
    elif perspective in {"symptom_localization", "evidence_citation", "patch_impact", "minimal_fix_selection", "abstention_insufficient_evidence"} and row.get("gold_answer_kind") == "abstain":
        task_type = perspective
        if perspective == "evidence_citation":
            values = row.get("visible_evidence_keys") or []
            task = "Decide whether any visible evidence key is strong enough, or whether abstention is more honest."
            query = "Choose the decisive evidence key or abstain."
        else:
            values = row.get("candidate_paths") or []
            task = "Decide whether the visible evidence supports a unique candidate path or whether abstention is more honest."
            query = "Choose a candidate path or abstain due to insufficient evidence."
        opaque_options, _ = make_candidate_labels(values)
        abstain_label = "Z" if all(opt["label"] != "Z" for opt in opaque_options) else "Y"
        opaque_options.append({"label": abstain_label, "value": "ABSTAIN_INSUFFICIENT_EVIDENCE"})
        target_label = abstain_label
    else:
        return None

    evidence_lines = [f"{key}" for key in (row.get("visible_evidence_keys") or [])]
    prompt_lines = [
        "Language: rust",
        f"Perspective: {perspective}",
        f"Task: {task}",
        "Evidence:",
        *evidence_lines,
        "Options:",
        *[f"{opt['label']}. {opt['value']}" for opt in opaque_options],
        "Answer:",
    ]
    input_text = "\n".join(prompt_lines) + "\n"
    return {
        "row_id": row["materialized_id"],
        "repo_id": row.get("repo_id"),
        "repo_family": row.get("repo_id"),
        "language_family": "rust",
        "surface": "fresh_rust_successor_eval_expanded",
        "task_type": task_type,
        "input_text": input_text,
        "prompt_text": input_text,
        "query_text": query,
        "target_text": target_label,
        "decoder_text": target_label,
        "target_token_len": 1,
        "opaque_options": opaque_options,
        "objective_family": "bounded_decoder_ce",
        "disable_losses": [],
        "expected_enabled_loss": "decoder_ce",
        "loss_mask": {"decoder_ce": True},
        "package_source_kind": "fresh_rust_successor_eval_expanded",
        "package_split": None,
        "split": "fresh_rust_successor_eval_expanded",
        "split_role": "fresh_root_successor_eval",
        "train_support_only": False,
        "strict_eval_eligible": True,
        "source_heldout_admissible": True,
        "selected_test_anchor": bool(row.get("selected_tests")),
        "verifier_anchor": False,
        "abstention_heavy": target_label in {"Y", "Z"},
        "standalone_projection_source": {
            "opaque_options": opaque_options,
            "gold_value": row.get("gold_answer_value"),
            "original_answer_kind": row.get("gold_answer_kind"),
            "perspective_gold_adjudication": row.get("packet_dir"),
        },
        "anti_cheat": {
            "compact_prompt_contract": True,
            "opaque_labels": True,
            "fresh_root_extension": True,
            "reviewed_bundle_source": True,
            "same_surface_eval_admissible": False,
            "non_tokenizers_rust_successor": True,
            "prompt_target_leak": False,
        },
        "bundle_id": bundle_id,
        "perspective": perspective,
    }


def main() -> None:
    rows = [row for row in read_jsonl(IN_ROWS) if row.get("language_family") == "rust"]
    selected: list[dict] = []
    for row in rows:
        built = build_row(row)
        if built is not None:
            selected.append(built)

    summary = {
        "stage": 11022,
        "stage_name": "stage11022_rust_successor_eval_expansion_package",
        "row_count": len(selected),
        "bundle_counts": {},
        "task_type_counts": {},
        "notes": [
            "Expanded beyond the initial 2-row candle-core slice.",
            "Includes candidate-path singleton rows where reviewed packets justify a concrete path, plus explicit abstention rows where reviewed packets say the evidence is insufficient.",
            "Still excludes freeform-only perspectives like alternative_hypothesis_elimination and regression_risk.",
        ],
    }
    bundle_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    for row in selected:
        bundle_counts[row["bundle_id"]] = bundle_counts.get(row["bundle_id"], 0) + 1
        task_counts[row["task_type"]] = task_counts.get(row["task_type"], 0) + 1
    summary["bundle_counts"] = bundle_counts
    summary["task_type_counts"] = task_counts

    write_jsonl(OUT_DIR / "fresh_rust_successor_eval_expanded.jsonl", selected)
    write_json(OUT_DIR / "rust_successor_eval_expansion_package.json", summary)


if __name__ == "__main__":
    main()
