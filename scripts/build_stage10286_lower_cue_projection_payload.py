#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10286
NAME = "stage10286_lower_cue_projection_payload"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "lower_cue_projection_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10280_frontier_saved_runtime_harness_payload/frontier_saved_runtime_harness_payload.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10278_frontier_runtime_bundle_probe/runtime_model/runtime_model_bundle.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def evidence_only(prompt: str) -> str:
    marker = "\nOptions:\n"
    return prompt.split(marker, 1)[0] if marker in prompt else prompt
def row_contains_value(prompt: str, value: str) -> bool:
    return normalize_text(value) in normalize_text(prompt)


def tokenize(text: str) -> list[str]:
    import re
    return re.findall(r"[a-z0-9_./-]+", normalize_text(text))


def lexical_overlap_score(prompt: str, value: str) -> float:
    p = set(tokenize(prompt))
    v = set(tokenize(value))
    if not p or not v:
        return 0.0
    return len(p & v) / len(v)


def annotate_row(row: dict[str, Any], language: str) -> dict[str, Any]:
    prompt = str(row.get("prompt") or row.get("prompt_text") or row.get("input_text") or "")
    evidence_prompt = evidence_only(prompt)
    options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
    expected = str(row.get("expected_label") or row.get("target_text") or "")
    label_to_value = {str(opt.get("label") or ""): str(opt.get("value") or "") for opt in options}
    gold_value = label_to_value.get(expected, "")
    containing = [str(opt.get("label") or "") for opt in options if row_contains_value(evidence_prompt, str(opt.get("value") or ""))]
    return {
        **row,
        "language_family": language,
        "_anti_cheat": {
            "gold_value": gold_value,
            "gold_value_mentioned_in_evidence": bool(gold_value and row_contains_value(evidence_prompt, gold_value)),
            "unique_prompt_match": bool(len(containing) == 1 and containing[0] == expected),
            "lexical_overlap": lexical_overlap_score(evidence_prompt, gold_value),
            "mentioning_option_labels": containing,
        },
    }


def choose_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_perspective: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        perspective = str(row.get("perspective") or row.get("task_type") or "")
        by_perspective[perspective].append(row)
    selected: list[dict[str, Any]] = []
    for perspective, candidates in sorted(by_perspective.items()):
        ranked = sorted(
            candidates,
            key=lambda row: (
                1 if row["_anti_cheat"]["gold_value_mentioned_in_evidence"] else 0,
                1 if row["_anti_cheat"]["unique_prompt_match"] else 0,
                float(row["_anti_cheat"]["lexical_overlap"]),
                str(row.get("row_id") or ""),
            ),
        )
        selected.append(ranked[0])
    return selected


def build_payload() -> dict[str, Any]:
    source = load_json(SOURCE)
    runs = []
    selection_cards = []
    row_counts_by_language: dict[str, int] = {}
    for run in source.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        language = str(task_pack.get("language_family") or "")
        rows = [annotate_row(dict(row), language) for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        if not rows:
            continue
        selected = choose_rows(rows)
        row_counts_by_language[language] = len(selected)
        selection_cards.append({
            "language_family": language,
            "source_rows": len(rows),
            "selected_rows": len(selected),
            "selected": [
                {
                    "row_id": row.get("row_id"),
                    "perspective": row.get("perspective") or row.get("task_type"),
                    "gold_value": row["_anti_cheat"].get("gold_value"),
                    "gold_value_mentioned_in_evidence": row["_anti_cheat"].get("gold_value_mentioned_in_evidence"),
                    "unique_prompt_match": row["_anti_cheat"].get("unique_prompt_match"),
                    "lexical_overlap": row["_anti_cheat"].get("lexical_overlap"),
                }
                for row in selected
            ],
        })
        cleaned_rows = []
        for row in selected:
            copy = dict(row)
            copy.pop("_anti_cheat", None)
            cleaned_rows.append(copy)
        runs.append({
            "cell_key": f"compact_projection_lower_cue::{language}",
            "task_pack": {
                "bundle_id": f"stage10286_lower_cue::{language}",
                "task_pack_id": f"stage10286_lower_cue::{language}",
                "source_id": f"stage10286_lower_cue::{language}",
                "lineage_hash": f"stage10286_lower_cue::{language}",
                "language_family": language,
                "skill_area": "edit_localization",
                "split_role": "locked_regression",
                "train_eligible": False,
                "promotion_only": True,
                "hidden_final": False,
                "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                "slice_tags": ["compact_bounded", "lower_cue", language, "saved_runtime"],
                "rows": cleaned_rows,
            },
            "hundred_m_backend": {
                "kind": "preserved_bounded_choice_scoring",
                "runtime_model_bundle": str(RUNTIME_BUNDLE),
                "bounded_choice_aux_source": "encoder_option_retrieval",
                "max_encoder_tokens": 768,
                "device": "cuda",
            },
            "gemma_backend": {
                "kind": "ollama_generate",
                "model": "gemma3:12b",
                "seed": 0,
                "temperature": 0.0,
                "num_predict": 8,
                "timeout_seconds": 120,
            },
        })
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": bool(runs),
        "source_payload": display(SOURCE),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "claim_scope": "lower-cue compact bounded diagnostic packet derived from the stage10280 frontier payload by minimizing direct gold-value mention and prompt-match shortcuts per perspective",
        "metrics": {
            "runs": len(runs),
            "rows": sum(row_counts_by_language.values()),
            "row_counts_by_language": row_counts_by_language,
        },
        "selection_cards": selection_cards,
        "runs": runs,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    PAYLOAD.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
