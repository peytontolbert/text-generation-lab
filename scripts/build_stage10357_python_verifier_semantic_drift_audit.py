#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/local/artifacts/stage10341_unresolved_family_focus_execution_request/unresolved_family_focus_manifest.jsonl"
BASELINE_RESULT = ROOT / "runs/local/artifacts/stage10342_unresolved_family_focus_probe/bounded_decoder_probe/execution_result.json"
PRESERVED_RESULT = ROOT / "runs/local/artifacts/stage10356_preserved_citation_plus_pythonverifier_probe/bounded_decoder_probe/execution_result.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage10357_python_verifier_semantic_drift_audit"
OUT_PATH = OUT_DIR / "python_verifier_semantic_drift_audit.json"
SUMMARY_PATH = ROOT / "runs/summaries/stage10357_python_verifier_semantic_drift_audit.json"

FAMILY_SUBSTRING = "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin"


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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_hash(value: Any) -> str:
    packed = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(packed.encode("utf-8")).hexdigest()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def option_value_by_label(row: dict[str, Any]) -> dict[str, str]:
    options = row.get("standalone_projection_source", {}).get("opaque_options") or []
    return {
        str(option.get("label") or ""): str(option.get("value") or "")
        for option in options
        if isinstance(option, dict) and str(option.get("label") or "")
    }


def family_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        if FAMILY_SUBSTRING in row_id and "python::verifier_outcome" in row_id:
            selected.append(row)
    selected.sort(key=lambda row: str(row.get("row_id") or ""))
    return selected


def cards_by_row_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    strict_eval = (((result.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("row_cards") or [])
    out: dict[str, dict[str, Any]] = {}
    for card in strict_eval:
        if isinstance(card, dict):
            out[str(card.get("row_id") or "")] = card
    return out


def build_probe_summary(*, name: str, rows: list[dict[str, Any]], cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    predicted_value_counts: Counter[str] = Counter()
    predicted_label_counts: Counter[str] = Counter()
    target_value_counts: Counter[str] = Counter()
    label_shift_counts: Counter[str] = Counter()
    row_summaries: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        card = cards[row_id]
        labels_to_values = option_value_by_label(row)
        target_label = str(row.get("target_text") or "")
        predicted_label = str(card.get("constrained_choice_top1_label") or "")
        target_value = labels_to_values.get(target_label, "")
        predicted_value = labels_to_values.get(predicted_label, "")
        target_value_counts[target_value] += 1
        predicted_value_counts[predicted_value] += 1
        predicted_label_counts[predicted_label] += 1
        label_shift_counts[f"{target_label}->{predicted_label}"] += 1
        row_summaries.append(
            {
                "row_id": row_id,
                "perm": row_id.split("::")[-1],
                "target_label": target_label,
                "predicted_label": predicted_label,
                "target_value": target_value,
                "predicted_value": predicted_value,
                "match": bool(card.get("constrained_choice_match")),
                "option_values_by_label": labels_to_values,
            }
        )
    dominant_value, dominant_count = ("", 0)
    if predicted_value_counts:
        dominant_value, dominant_count = predicted_value_counts.most_common(1)[0]
    return {
        "probe_name": name,
        "rows": row_summaries,
        "strict_accuracy": sum(int(row["match"]) for row in row_summaries) / len(row_summaries) if row_summaries else None,
        "predicted_value_counts": dict(predicted_value_counts),
        "predicted_label_counts": dict(predicted_label_counts),
        "target_value_counts": dict(target_value_counts),
        "label_shift_counts": dict(label_shift_counts),
        "semantic_constant_prediction": dominant_count == len(row_summaries) and len(row_summaries) > 0,
        "dominant_predicted_value": dominant_value,
        "dominant_predicted_value_rows": dominant_count,
    }


def build_train_context(rows: list[dict[str, Any]], *, target_values: set[str]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: {"as_gold": 0, "as_option": 0, "task_types": Counter(), "splits": Counter()})
    for row in rows:
        row_json = json.dumps(row, sort_keys=True)
        gold_value = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        for target_value in target_values:
            slot = out[target_value]
            if target_value == gold_value:
                slot["as_gold"] += 1
            if target_value in row_json:
                slot["as_option"] += 1
                slot["task_types"][str(row.get("task_type") or "")] += 1
                slot["splits"][str(row.get("split") or "")] += 1
    materialized: dict[str, Any] = {}
    for target_value, slot in out.items():
        materialized[target_value] = {
            "as_gold": int(slot["as_gold"]),
            "as_option": int(slot["as_option"]),
            "task_types": dict(slot["task_types"]),
            "splits": dict(slot["splits"]),
        }
    return materialized


def main() -> None:
    manifest_rows = load_jsonl(MANIFEST)
    family = family_rows(manifest_rows)
    if not family:
        raise SystemExit("family_not_found")
    baseline_cards = cards_by_row_id(load_json(BASELINE_RESULT))
    preserved_cards = cards_by_row_id(load_json(PRESERVED_RESULT))
    missing = [row["row_id"] for row in family if row["row_id"] not in baseline_cards or row["row_id"] not in preserved_cards]
    if missing:
        raise SystemExit(f"missing_row_cards::{len(missing)}")
    baseline = build_probe_summary(name="stage10342_baseline", rows=family, cards=baseline_cards)
    preserved = build_probe_summary(name="stage10356_preserved_citation_plus_pythonverifier", rows=family, cards=preserved_cards)
    target_values = {
        str(row["target_value"])
        for row in baseline["rows"]
        if str(row.get("target_value") or "")
    }
    target_values.update(
        str(row["predicted_value"])
        for row in preserved["rows"]
        if str(row.get("predicted_value") or "")
    )
    train_context = build_train_context([row for row in manifest_rows if str(row.get("split") or "") == "train"], target_values=target_values)
    family_gold_value = str((family[0].get("standalone_projection_source") or {}).get("gold_value") or "")
    summary = {
        "stage": 10357,
        "stage_name": "stage10357_python_verifier_semantic_drift_audit",
        "created_at_utc": now_utc(),
        "family_manifest": display(MANIFEST),
        "family_row_count": len(family),
        "family_source_row_id": str(family[0].get("source_row_id") or ""),
        "family_gold_value": family_gold_value,
        "baseline_result": display(BASELINE_RESULT),
        "preserved_result": display(PRESERVED_RESULT),
        "baseline": baseline,
        "preserved": preserved,
        "train_context": train_context,
        "drift_interpretation": {
            "baseline_exact": baseline["strict_accuracy"],
            "preserved_exact": preserved["strict_accuracy"],
            "baseline_semantic_constant_prediction": baseline["semantic_constant_prediction"],
            "preserved_semantic_constant_prediction": preserved["semantic_constant_prediction"],
            "preserved_dominant_predicted_value": preserved["dominant_predicted_value"],
            "semantic_drift_detected": False,
        },
    }
    summary["drift_interpretation"]["semantic_drift_detected"] = bool(
        baseline["strict_accuracy"] == 1.0
        and preserved["strict_accuracy"] == 0.0
        and preserved["semantic_constant_prediction"]
        and preserved["dominant_predicted_value"] != family_gold_value
    )
    summary["audit_hash"] = stable_hash(summary)
    write_json(OUT_PATH, summary)
    write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
