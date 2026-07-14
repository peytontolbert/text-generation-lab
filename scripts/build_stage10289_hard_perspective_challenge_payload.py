#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10289
NAME = "stage10289_hard_perspective_challenge_payload"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "hard_perspective_challenge_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10280_frontier_saved_runtime_harness_payload/frontier_saved_runtime_harness_payload.json"
SHORTCUT = ROOT / "runs/local/artifacts/stage10285_frontier_saved_runtime_shortcut_audit/frontier_saved_runtime_shortcut_audit.json"
RUNTIME_BUNDLE = ROOT / "runs/local/artifacts/stage10278_frontier_runtime_bundle_probe/runtime_model/runtime_model_bundle.json"
PRIORITY = [
    "abstention_insufficient_evidence",
    "verifier_outcome",
    "evidence_citation",
    "symptom_localization",
    "patch_impact",
    "minimal_fix_selection",
]


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


def build_payload() -> dict[str, Any]:
    source = load_json(SOURCE)
    shortcut = load_json(SHORTCUT)
    weak_100m = {str(row.get("row_id") or ""): row for row in shortcut.get("weak_rows_100m") or [] if isinstance(row, dict)}
    weak_gemma = {str(row.get("row_id") or ""): row for row in shortcut.get("weak_rows_gemma") or [] if isinstance(row, dict)}

    runs = []
    selection_cards = []
    row_counts_by_language: dict[str, int] = {}

    for run in source.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_pack = run.get("task_pack") if isinstance(run.get("task_pack"), dict) else {}
        language = str(task_pack.get("language_family") or "")
        rows = [dict(row) for row in task_pack.get("rows") or [] if isinstance(row, dict)]
        annotated = []
        for row in rows:
            row_id = str(row.get("row_id") or "")
            prompt = str(row.get("prompt") or row.get("prompt_text") or row.get("input_text") or "")
            evidence_prompt = evidence_only(prompt)
            perspective = str(row.get("perspective") or row.get("task_type") or "")
            options = [opt for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]
            expected = str(row.get("expected_label") or row.get("target_text") or "")
            label_to_value = {str(opt.get("label") or ""): str(opt.get("value") or "") for opt in options}
            gold_value = label_to_value.get(expected, "")
            annotated.append({
                **row,
                "_challenge": {
                    "perspective": perspective,
                    "gold_value": gold_value,
                    "gold_value_mentioned_in_evidence": bool(gold_value and row_contains_value(evidence_prompt, gold_value)),
                    "weak_100m": row_id in weak_100m,
                    "weak_gemma": row_id in weak_gemma,
                },
            })
        by_perspective: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in annotated:
            by_perspective[row["_challenge"]["perspective"]].append(row)
        selected = []
        for perspective in PRIORITY:
            candidates = by_perspective.get(perspective) or []
            if not candidates:
                continue
            ranked = sorted(
                candidates,
                key=lambda row: (
                    0 if row["_challenge"]["weak_100m"] else 1,
                    0 if row["_challenge"]["weak_gemma"] else 1,
                    0 if not row["_challenge"]["gold_value_mentioned_in_evidence"] else 1,
                    str(row.get("row_id") or ""),
                ),
            )
            selected.append(ranked[0])
            if len(selected) >= 3:
                break
        row_counts_by_language[language] = len(selected)
        selection_cards.append({
            "language_family": language,
            "selected_rows": len(selected),
            "selected": [
                {
                    "row_id": row.get("row_id"),
                    "perspective": row["_challenge"]["perspective"],
                    "weak_100m": row["_challenge"]["weak_100m"],
                    "weak_gemma": row["_challenge"]["weak_gemma"],
                    "gold_value": row["_challenge"]["gold_value"],
                    "gold_value_mentioned_in_evidence": row["_challenge"]["gold_value_mentioned_in_evidence"],
                }
                for row in selected
            ],
        })
        cleaned = []
        for row in selected:
            copy = dict(row)
            copy.pop("_challenge", None)
            cleaned.append(copy)
        runs.append({
            "cell_key": f"compact_projection_hard_perspectives::{language}",
            "task_pack": {
                "bundle_id": f"stage10289_hard_perspectives::{language}",
                "task_pack_id": f"stage10289_hard_perspectives::{language}",
                "source_id": f"stage10289_hard_perspectives::{language}",
                "lineage_hash": f"stage10289_hard_perspectives::{language}",
                "language_family": language,
                "skill_area": "edit_localization",
                "split_role": "locked_regression",
                "train_eligible": False,
                "promotion_only": True,
                "hidden_final": False,
                "thresholds": {"must_compare_100m_and_gemma": True, "projection_only": True},
                "slice_tags": ["compact_bounded", "hard_perspective_challenge", language, "saved_runtime"],
                "rows": cleaned,
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
        "source_shortcut_audit": display(SHORTCUT),
        "runtime_bundle": display(RUNTIME_BUNDLE),
        "claim_scope": "hard-perspective compact bounded challenge built from the current frontier by prioritizing weak abstention, verifier_outcome, and evidence_citation rows with low direct-cue leakage",
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
    SUMMARY.write_text(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": display(PAYLOAD), "metrics": payload["metrics"]}, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
