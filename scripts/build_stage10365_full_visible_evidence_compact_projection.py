#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10365
NAME = "stage10365_full_visible_evidence_compact_projection"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "full_visible_evidence_compact_projection.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
SOURCE = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"

BOUND_KINDS = {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}
CHOICE_LABELS = list("ABCDEFGHJKLMNOPQRSTUVWXYZ")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get("perspective_rows") or []:
        if isinstance(row, dict) and str(row.get("perspective") or "") == perspective:
            contract = row.get("prompt_contract")
            if isinstance(contract, dict):
                return contract
    return {}


def evidence_lines(bundle: dict[str, Any], visible_keys: list[str]) -> list[str]:
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    lines: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        if not isinstance(first, dict):
            continue
        path = str(first.get("path") or "")
        source_type = str(first.get("source_type") or "")
        text = snippet(str(first.get("text") or ""))
        prefix = key
        if path:
            prefix += f" [{path}]"
        elif source_type:
            prefix += f" [{source_type}]"
        lines.append(f"{prefix}: {text}")
    return lines


def deterministic_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest())


def build_option_values(*, answer_kind: str, gold_value: str, contract: dict[str, Any], gold: dict[str, Any]) -> list[str]:
    if answer_kind == "candidate_path":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
    elif answer_kind == "selected_test":
        values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
    elif answer_kind == "visible_evidence_key":
        values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
    elif answer_kind == "abstain":
        values = [str(v) for v in (gold.get("candidate_paths") or contract.get("candidate_paths") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("selected_tests") or contract.get("selected_tests") or []) if v]
        if not values:
            values = [str(v) for v in (gold.get("visible_evidence_keys") or contract.get("visible_evidence_keys") or []) if v]
        values.append("ABSTAIN_INSUFFICIENT_EVIDENCE")
    else:
        values = [gold_value]
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    if gold_value not in seen:
        deduped.append(gold_value)
    return deduped


def compile_prompt(bundle: dict[str, Any], gold: dict[str, Any], *, options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get("perspective") or "")
    contract = contract_for(bundle, perspective)
    task = " ".join(str(contract.get("task") or "").split())
    visible_keys = [str(v) for v in contract.get("visible_evidence_keys") or [] if v]
    ev_lines = evidence_lines(bundle, visible_keys)
    opt_lines = [f"{label}. {value}" for label, value in options]
    parts = [
        f"Language: {bundle.get('language_family')}",
        f"Perspective: {perspective}",
        f"Task: {task}",
    ]
    if ev_lines:
        parts.append("Evidence:")
        parts.extend(ev_lines)
    parts.append("Options:")
    parts.extend(opt_lines)
    parts.append("Answer:")
    return "\n".join(parts) + "\n"


def compile_bounded_row(bundle: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get("perspective") or "")
    answer_kind = str(gold.get("gold_answer_kind") or "")
    gold_value = str(gold.get("gold_answer_value") or "")
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    seed = f"full_visible::{bundle['bundle_id']}::{perspective}::{answer_kind}"
    ordered_values = deterministic_order(values, seed)
    if len(ordered_values) > len(CHOICE_LABELS):
        raise ValueError(f"too_many_options::{bundle['bundle_id']}::{perspective}")
    options = list(zip(CHOICE_LABELS[: len(ordered_values)], ordered_values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_prompt(bundle, gold, options=options)
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}::full_visible_compact_bounded",
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "route": "DIRECT_ANSWER_MAINTAINER_BUNDLE_COMPACT_BOUNDED",
        "objective_family": "maintainer_bundle_compact_bounded_choice",
        "surface": "edit_localization",
        "task_type": perspective,
        "perspective": perspective,
        "original_answer_kind": answer_kind,
        "expected_answer_kind": "opaque_choice",
        "expected_label": label_by_value[gold_value],
        "prompt": prompt,
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"full_visible_compact::{bundle['language_family']}::{perspective}::{answer_kind}",
        "target_text": label_by_value[gold_value],
        "split": "strict_eval",
        "opaque_options": [{"label": label, "value": value} for label, value in options],
        "gold_value": gold_value,
        "anti_cheat": {
            "opaque_labels": True,
            "deterministic_option_shuffle": True,
            "full_visible_evidence_projection": True,
            "projection_is_auxiliary_not_primary_maintainer_score": True,
        },
    }


def build_payload(source: Path = SOURCE) -> dict[str, Any]:
    data = load_json(source)
    bundles = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    runs = []
    excluded_rows = 0
    kept_rows = 0
    for bundle in bundles:
        gold_path = ROOT / str(bundle.get("perspective_gold_adjudication") or "")
        gold = load_json(gold_path)
        answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
        compiled_rows = []
        for answer in answers:
            compiled = compile_bounded_row(bundle, answer)
            if compiled is None:
                excluded_rows += 1
                continue
            compiled_rows.append(compiled)
        if not compiled_rows:
            continue
        kept_rows += len(compiled_rows)
        runs.append(
            {
                "bundle_id": bundle["bundle_id"],
                "language_family": bundle["language_family"],
                "gold_answers_path": display(gold_path),
                "rows": compiled_rows,
            }
        )
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "source": display(source),
        "passed": bool(runs),
        "metrics": {
            "bundles": len(runs),
            "rows": kept_rows,
            "excluded_freeform_rows": excluded_rows,
        },
        "decision": {
            "headline": "full visible evidence successor projection prepared",
            "next_best_step": "replace truncated compact bounded evidence_citation rows with this successor before comparing 100M to Gemma again",
        },
        "runs": runs,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    write_json(OUT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": payload["passed"],
            "payload": display(OUT_JSON),
            "metrics": payload["metrics"],
        },
    )
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "payload": display(OUT_JSON), "metrics": payload["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
