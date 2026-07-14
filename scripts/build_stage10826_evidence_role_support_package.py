#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10826
NAME = "stage10826_evidence_role_support_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_role_support_package.json"
CANDIDATE_ROWS_JSONL = OUT_DIR / "evidence_role_candidate_rows.jsonl"
ROOT_ROWS_JSONL = OUT_DIR / "evidence_role_root_rows.jsonl"

BASE_DIR = ARTIFACTS / "stage10814_reviewed_v27_plus_cpp_python_queue_support_package"
INPUT_FILES = {
    "train": BASE_DIR / "agentkernel_lite_encdec_train.jsonl",
    "validation": BASE_DIR / "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl",
}


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def role_for_option(option_value: str, gold_value: str) -> str:
    if option_value == gold_value:
        return "DECISIVE_EVIDENCE"
    if option_value == "candidate_change_surface":
        return "SURFACE_DISTRACTOR"
    if option_value == "verifier_and_test_constraint":
        return "VERIFIER_CONSTRAINT_DISTRACTOR"
    if option_value == "symptom_or_call_path_analogue":
        return "CALL_PATH_DISTRACTOR"
    if option_value == "nearby_definition_or_usage_context":
        return "NEARBY_CONTEXT_DISTRACTOR"
    return "BACKGROUND_DISTRACTOR"


def build_candidate_prompt(row: dict[str, Any], option: dict[str, Any], role: str) -> str:
    return (
        f"{row['prompt_text']}\n"
        f"Candidate under review: {option['label']}. {option['value']}\n"
        "Classify the role of this candidate evidence relative to the maintenance decision.\n\n"
        "Choices:\n"
        "A. DECISIVE_EVIDENCE\n"
        "B. SURFACE_DISTRACTOR\n"
        "C. VERIFIER_CONSTRAINT_DISTRACTOR\n"
        "D. CALL_PATH_DISTRACTOR\n"
        "E. NEARBY_CONTEXT_DISTRACTOR\n"
        "F. BACKGROUND_DISTRACTOR\n"
        "Answer:\n"
    )


ROLE_TO_LABEL = {
    "DECISIVE_EVIDENCE": "A",
    "SURFACE_DISTRACTOR": "B",
    "VERIFIER_CONSTRAINT_DISTRACTOR": "C",
    "CALL_PATH_DISTRACTOR": "D",
    "NEARBY_CONTEXT_DISTRACTOR": "E",
    "BACKGROUND_DISTRACTOR": "F",
}


def main() -> None:
    candidate_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    counts_by_split = Counter()
    counts_by_role = Counter()
    counts_by_language = Counter()

    for split_name, path in INPUT_FILES.items():
        for row in load_jsonl(path):
            if row.get("task_type") != "evidence_citation":
                continue
            options = row.get("opaque_options") or []
            gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value")) or "")
            root_rows.append(
                {
                    "row_id": row["row_id"],
                    "language_family": row["language_family"],
                    "repo_family": row.get("repo_family"),
                    "source_bundle_id": row.get("source_bundle_id"),
                    "split": split_name,
                    "gold_value": gold_value,
                    "option_values": [opt.get("value") for opt in options],
                    "anti_cheat": row.get("anti_cheat"),
                }
            )
            for option in options:
                option_value = str(option["value"])
                role = role_for_option(option_value, gold_value)
                candidate_rows.append(
                    {
                        "row_id": f"{row['row_id']}::candidate::{option['label']}",
                        "parent_row_id": row["row_id"],
                        "language_family": row["language_family"],
                        "repo_family": row.get("repo_family"),
                        "source_bundle_id": row.get("source_bundle_id"),
                        "split": split_name,
                        "task_type": "evidence_role_classification",
                        "target_text": ROLE_TO_LABEL[role],
                        "decoder_text": ROLE_TO_LABEL[role],
                        "semantic_role": role,
                        "candidate_label": option["label"],
                        "candidate_value": option_value,
                        "gold_value": gold_value,
                        "prompt_text": build_candidate_prompt(row, option, role),
                        "opaque_options": [{"label": k, "value": v} for v, k in {v: k for k, v in ROLE_TO_LABEL.items()}.items()],
                        "anti_cheat": {
                            **(row.get("anti_cheat") or {}),
                            "semantic_role_projection": True,
                            "same_surface_eval_admissible": False,
                        },
                        "train_support_only": split_name == "train",
                        "strict_eval_eligible": split_name != "train",
                        "selected_test_anchor": row.get("selected_test_anchor"),
                        "verifier_anchor": row.get("verifier_anchor"),
                        "evidence_role_projection_source": {
                            "base_task_type": row.get("task_type"),
                            "base_gold_value": gold_value,
                            "candidate_value": option_value,
                            "derived_semantic_role": role,
                            "projection_mode": "stage10826_evidence_role_projection_v1",
                        },
                    }
                )
                counts_by_split[split_name] += 1
                counts_by_role[role] += 1
                counts_by_language[str(row["language_family"])] += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_role_support_package_ready",
        "claim_scope": [
            "Reframe reviewed v2.7 evidence_citation rows as semantic evidence-role classification candidates.",
            "Provide a train/eval-support package that targets decisive-vs-distractor evidence reasoning instead of opaque answer-letter recovery alone.",
        ],
        "source_package": rel(BASE_DIR / "reviewed_v27_plus_cpp_python_queue_support_package.json"),
        "metrics": {
            "base_evidence_rows": len(root_rows),
            "candidate_rows": len(candidate_rows),
            "rows_by_split": dict(counts_by_split),
            "rows_by_role": dict(counts_by_role),
            "rows_by_language": dict(counts_by_language),
        },
        "anti_cheat_contract": [
            "Derived rows inherit the original reviewed bundle anti-cheat flags and mark same-surface eval inadmissible for promotion.",
            "Semantic roles are computed from visible evidence key values, not from hidden future labels.",
            "This package is support/eval-auxiliary material; it does not replace maintainer-grade root scoring.",
        ],
        "next_best_steps": [
            "Use these rows as an auxiliary evidence-role head or support curriculum alongside the unchanged reviewed v2.7 canary.",
            "Compare future evidence_citation probes by task-family delta, not just overall strict accuracy.",
            "Keep Python verifier fresh-root work parallel because this package targets the shared evidence family, not the MirrorMind verifier miss directly.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "candidate_rows_jsonl": rel(CANDIDATE_ROWS_JSONL),
            "root_rows_jsonl": rel(ROOT_ROWS_JSONL),
        },
    }

    write_json(SUMMARY_JSON, payload)
    write_jsonl(CANDIDATE_ROWS_JSONL, candidate_rows)
    write_jsonl(ROOT_ROWS_JSONL, root_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
